"""Teacher-facing student management, living inside the admin panel at /admin/students/."""
from datetime import date

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
STATUS_FILTERS = {
    "active": Q(is_blocked=False),
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
    if status in STATUS_FILTERS:
        students = students.filter(STATUS_FILTERS[status])

    sort = request.GET.get("sort", "name")
    page = Paginator(students.order_by(*SORTS.get(sort, SORTS["name"])[1]), PAGE_SIZE).get_page(request.GET.get("page"))
    everyone = _students()
    total = everyone.count()
    blocked = everyone.filter(is_blocked=True).count()
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
        blocked=blocked,
        active=total - blocked,
        today=timezone.now(),
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
