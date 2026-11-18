"""Teacher-facing student management, living inside the admin panel at /admin/students/."""
from datetime import timedelta

from django.contrib import admin, messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.cache import add_never_cache_headers
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_POST

from . import lockout
from .admin_access import groups_for, school_admin_required, students_for
from .models import normalize_phone
from .student_forms import StudentForm, generate_password

PAGE_SIZE = 20
EXTEND_CHOICES = {"14": "2 hafta", "30": "1 oy", "60": "2 oy", "0": "muddatsiz"}


def status_filters(now):
    """A student is blocked (teacher's switch), expired (access date passed) or active."""
    live = Q(unlimited=True) | Q(account_expires_at__gt=now)
    current = Q(archived_at__isnull=True)
    return {
        "active": current & Q(is_blocked=False) & live,
        "expired": current & Q(is_blocked=False) & ~live,
        "blocked": current & Q(is_blocked=True),
        "archived": Q(archived_at__isnull=False),
    }


SORTS = {
    "name": ("Ism bo‘yicha (A–Z)", ("first_name", "last_name")),
    "new": ("Eng yangilari", ("-date_joined",)),
    "group": ("Guruh bo‘yicha", ("group__name", "first_name")),
}


def _page(request, title, **context):
    return {**admin.site.each_context(request), "title": title, **context}


def _temporary_credentials(request, identifier, password, back_url):
    response = render(request, "admin/temporary_credentials.html", _page(
        request, "Vaqtinchalik parol", identifier=identifier, temporary_password=password, back_url=back_url,
    ))
    add_never_cache_headers(response)
    return response


def _return_to_students(request):
    target = request.POST.get("next", "")
    if target.startswith("/admin/students/") and url_has_allowed_host_and_scheme(target, allowed_hosts=set()):
        return redirect(target)
    return redirect("students:list")


def _editable_student(request, pk):
    return get_object_or_404(students_for(request.user), pk=pk, archived_at__isnull=True)


@staff_member_required
def student_list(request):
    query = request.GET.get("q", "").strip()
    group_id = request.GET.get("group", "")
    status = request.GET.get("status", "")

    students = students_for(request.user).select_related("group__branch")
    if query:
        digits = normalize_phone(query)
        match = Q(first_name__icontains=query) | Q(last_name__icontains=query)
        if digits:
            match |= Q(phone__contains=digits)
        students = students.filter(match)
    if group_id.isdigit():
        students = students.filter(group_id=group_id)
    now = timezone.now()
    filters = status_filters(now)
    students = students.filter(filters.get(status, Q(archived_at__isnull=True)))

    sort = request.GET.get("sort", "name")
    page = Paginator(students.order_by(*SORTS.get(sort, SORTS["name"])[1]), PAGE_SIZE).get_page(request.GET.get("page"))
    everyone = students_for(request.user).select_related("group__branch")
    total = everyone.count()
    counts = {name: everyone.filter(q).count() for name, q in filters.items()}
    return render(request, "admin/students/list.html", _page(
        request, "Talabalar",
        page=page,
        query=query,
        group_id=group_id,
        status=status,
        sort=sort,
        sorts=SORTS,
        groups=groups_for(request.user).select_related("branch"),
        total=total,
        counts=counts,
        extend_choices=EXTEND_CHOICES,
        today=now,
    ))


@staff_member_required
def student_create(request):
    form = StudentForm(request.POST or None, groups=groups_for(request.user), require_group=not request.user.is_superuser, initial={"group": request.GET.get("group")})
    if request.method == "POST" and form.is_valid():
        student = form.save()
        return _temporary_credentials(request, student.phone_display, form.temporary_password, "students:list")
    return render(request, "admin/students/form.html", _page(request, "Yangi talaba", form=form, student=None))


@staff_member_required
def student_edit(request, pk):
    student = _editable_student(request, pk)
    form = StudentForm(request.POST or None, groups=groups_for(request.user), require_group=not request.user.is_superuser, instance=student)
    if request.method == "POST" and form.is_valid():
        student = form.save()
        if form.temporary_password:
            lockout.clear(student.username)
            return _temporary_credentials(request, student.phone_display, form.temporary_password, "students:list")
        messages.success(request, f"{student.get_full_name()} ma’lumotlari saqlandi.")
        return redirect("students:list")
    return render(request, "admin/students/form.html", _page(
        request, student.get_full_name(), form=form, student=student,
        devices=student.devices.order_by("-last_used"),
    ))


@staff_member_required
@require_POST
def student_toggle(request, pk):
    student = _editable_student(request, pk)
    student.is_blocked = not student.is_blocked
    student.save(update_fields=["is_blocked"])
    student.sync_active_status()
    state = "bloklandi" if student.is_blocked else "faollashtirildi"
    messages.success(request, f"{student.get_full_name()} {state}.")
    return _return_to_students(request)


@staff_member_required
@require_POST
def student_extend(request, pk):
    """Open-ended by default; the teacher pushes the end date out until the student is done."""
    student = _editable_student(request, pk)
    days = request.POST.get("days", "")
    if days not in EXTEND_CHOICES:
        return redirect("students:list")
    now = timezone.now()
    if days == "0":
        student.unlimited, student.account_expires_at = True, None
    else:
        current = student.account_expires_at if not student.unlimited else None
        student.unlimited = False
        student.account_expires_at = max(now, current or now) + timedelta(days=int(days))
        student.account_started_at = student.account_started_at or now
    student.save(update_fields=["unlimited", "account_expires_at", "account_started_at"])
    student.sync_active_status()
    messages.success(request, f"{student.get_full_name()} uchun kirish {EXTEND_CHOICES[days]} qilib belgilandi.")
    return _return_to_students(request)


@staff_member_required
@require_POST
def student_reset_password(request, pk):
    student = _editable_student(request, pk)
    password = generate_password()
    student.set_password(password)
    student.must_change_password = True
    student.save(update_fields=["password", "must_change_password"])
    lockout.clear(student.username)
    return _temporary_credentials(request, student.phone_display, password, "students:list")


@staff_member_required
@require_POST
def student_remove_device(request, pk, device_id):
    """Forget one of the student's devices, freeing a place so they can sign in on a new one."""
    student = _editable_student(request, pk)
    student.devices.filter(pk=device_id).delete()
    messages.success(request, f"{student.get_full_name()}: qurilma o‘chirildi.")
    return redirect("students:edit", pk=student.pk)


@school_admin_required
@require_POST
def student_archive(request, pk):
    student = get_object_or_404(students_for(request.user).select_related("group__branch"), pk=pk)
    students_for(request.user).filter(pk=student.pk, archived_at__isnull=True).update(
        archived_at=timezone.now(), is_active=False,
    )
    messages.success(request, f"{student.get_full_name()} arxivlandi.")
    return redirect("students:list")


@school_admin_required
@require_POST
def student_restore(request, pk):
    student = get_object_or_404(students_for(request.user), pk=pk, archived_at__isnull=False)
    student.archived_at = None
    student.save(update_fields=["archived_at"])
    student.sync_active_status()
    messages.success(request, f"{student.get_full_name()} arxivdan qaytarildi.")
    return redirect("students:list")


@staff_member_required
@require_GET
def suggest_password(request):
    response = JsonResponse({"password": generate_password()})
    add_never_cache_headers(response)
    return response
