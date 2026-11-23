"""School task editor and audience-scoped assignment results."""
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, redirect, render
from django.db import transaction
from django.utils import timezone
from django.views.decorators.http import require_POST

from .assignments import progress, summary, selection_items
from .assignment_forms import AssignmentForm, LegacyAssignmentForm
from .admin_access import assignments_for
from .models import Assignment
from .student_views import _page


def _with_summary(assignment, today):
    rows = progress(assignment, today=today)
    assignment.summary = summary(rows)
    assignment.running = assignment.runs_on(today)
    return assignment


@staff_member_required
def assignment_list(request):
    today = timezone.localdate()
    assignments = [_with_summary(a, today) for a in assignments_for(request.user).select_related("group", "created_by").prefetch_related("bilets", "topics")]
    return render(request, "admin/assignments/list.html", _page(
        request, "Vazifalar", assignments=assignments,
        running_count=sum(1 for a in assignments if a.running),
    ))


@staff_member_required
def assignment_form(request, pk=None):
    assignment = get_object_or_404(assignments_for(request.user), pk=pk) if pk else None
    converting = bool(assignment and not assignment.is_selection and request.GET.get("select") == "1")
    legacy = bool(assignment and not assignment.is_selection and not converting)
    form_class = LegacyAssignmentForm if legacy else AssignmentForm
    form = form_class(request.POST if request.method == "POST" else None, instance=assignment, staff=request.user)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            saved = form.save(commit=False)
            saved.created_by = saved.created_by or request.user
            if not request.user.is_superuser and saved.audience == "express":
                saved.created_by = request.user
            saved.save()
            form.save_m2m()
        messages.success(request, f"«{saved.title}» vazifasi saqlandi.")
        return redirect("assignments:detail", pk=saved.pk)
    template = "admin/assignments/legacy_form.html" if legacy else "admin/assignments/form.html"
    return render(request, template, _page(
        request, assignment.title if assignment else "Yangi vazifa", form=form, assignment=assignment, legacy=legacy, converting=converting,
    ))


@staff_member_required
def assignment_detail(request, pk):
    assignment = get_object_or_404(assignments_for(request.user).select_related("group", "created_by").prefetch_related("bilets", "topics"), pk=pk)
    today = timezone.localdate()
    rows = progress(assignment, today=today)
    return render(request, "admin/assignments/detail.html", _page(
        request, assignment.title,
        assignment=assignment, rows=rows, items=selection_items(assignment), stats=summary(rows), running=assignment.runs_on(today), today=today,
    ))


@staff_member_required
@require_POST
def assignment_delete(request, pk):
    assignment = get_object_or_404(assignments_for(request.user), pk=pk)
    title = assignment.title
    assignment.delete()
    messages.success(request, f"«{title}» vazifasi o‘chirildi.")
    return redirect("assignments:list")
