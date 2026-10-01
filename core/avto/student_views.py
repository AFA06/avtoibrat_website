"""Teacher-facing student management, living inside the admin panel at /admin/students/."""
from datetime import date, timedelta

from django.contrib import admin, messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .models import StudyGroup, User, normalize_phone
from .student_forms import StudentForm, generate_password

PAGE_SIZE = 20
EXTEND_CHOICES = {"14": "2 hafta", "30": "1 oy", "60": "2 oy", "0": "muddatsiz"}


def status_filters(now):
    """A student is blocked (teacher's switch), expired (access date passed) or active."""
    live = Q(unlimited=True) | Q(account_expires_at__gt=now)
    return {
        "active": Q(is_blocked=False) & live,
        "expired": Q(is_blocked=False) & ~live,
        "blocked": Q(is_blocked=True),
    }


SORTS = {
    "name": ("Ism bo‘yicha (A–Z)", ("first_name", "last_name")),
    "new": ("Eng yangilari", ("-date_joined",)),
    "group": ("Guruh bo‘yicha", ("group__name", "first_name")),
}


def _students():
    return User.objects.filter(is_staff=False, is_superuser=False).select_related("group__branch")


def _page(request, title, **context):
    return {**admin.site.each_context(request), "title": title, **context}


@staff_member_required
def student_list(request):
    query = request.GET.get("q", "").strip()
    group_id = request.GET.get("group", "")
    status = request.GET.get("status", "")

    students = _students()
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
    if status in filters:
        students = students.filter(filters[status])

    sort = request.GET.get("sort", "name")
    page = Paginator(students.order_by(*SORTS.get(sort, SORTS["name"])[1]), PAGE_SIZE).get_page(request.GET.get("page"))
    everyone = _students()
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
        groups=StudyGroup.objects.select_related("branch"),
        total=total,
        counts=counts,
        extend_choices=EXTEND_CHOICES,
        today=now,
    ))


@staff_member_required
def student_create(request):
    form = StudentForm(request.POST or None, initial={"group": request.GET.get("group")})
    if request.method == "POST" and form.is_valid():
        student = form.save()
        messages.success(
            request,
            f"{student.get_full_name()} qo‘shildi. Login: {student.phone_display}, parol: {student.initial_password}",
        )
        return redirect("students:list")
    return render(request, "admin/students/form.html", _page(request, "Yangi talaba", form=form, student=None))


@staff_member_required
def student_edit(request, pk):
    student = get_object_or_404(_students(), pk=pk)
    form = StudentForm(request.POST or None, instance=student)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"{student.get_full_name()} ma’lumotlari saqlandi.")
        return redirect("students:list")
    return render(request, "admin/students/form.html", _page(
        request, student.get_full_name(), form=form, student=student,
    ))


@staff_member_required
@require_POST
def student_toggle(request, pk):
    student = get_object_or_404(_students(), pk=pk)
    student.is_blocked = not student.is_blocked
    student.save(update_fields=["is_blocked"])
    student.sync_active_status()
    state = "bloklandi" if student.is_blocked else "faollashtirildi"
    messages.success(request, f"{student.get_full_name()} {state}.")
    return redirect(request.POST.get("next") or "students:list")


@staff_member_required
@require_POST
def student_extend(request, pk):
    """Open-ended by default; the teacher pushes the end date out until the student is done."""
    student = get_object_or_404(_students(), pk=pk)
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
    return redirect(request.POST.get("next") or "students:list")


@staff_member_required
@require_POST
def student_reset_password(request, pk):
    student = get_object_or_404(_students(), pk=pk)
    password = generate_password(student.first_name, student.birth_date, randomize=True)
    student.initial_password = password
    student.set_password(password)
    student.save(update_fields=["password", "initial_password"])
    messages.success(request, f"{student.get_full_name()} uchun yangi parol: {password}")
    return redirect(request.POST.get("next") or "students:list")


@staff_member_required
@require_POST
def student_delete(request, pk):
    student = get_object_or_404(_students(), pk=pk)
    name = student.get_full_name()
    student.delete()
    messages.success(request, f"{name} o‘chirildi.")
    return redirect("students:list")


@staff_member_required
@require_GET
def suggest_password(request):
    """Password suggestion for the create/edit form's «Generatsiya» button."""
    try:
        birth_date = date.fromisoformat(request.GET.get("birth_date", ""))
    except ValueError:
        birth_date = None
    password = generate_password(
        request.GET.get("first_name", ""), birth_date, randomize=request.GET.get("again") == "1",
    )
    return JsonResponse({"password": password})
