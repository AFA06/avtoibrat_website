"""Express roster with each student's actual assigned-task progress."""
from django.contrib import messages
from django.db.models import F, Max
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .assignments import finished_per_day, progress
from .models import Assignment, TestSession
from .admin_access import school_admin_required, students_for
from .student_views import _page


def daily_target(today):
    """Tests per day expected from express students right now: the strictest running express task, if any."""
    targets = [
        a.tests_per_day
        for a in Assignment.objects.filter(audience="express", content_type="daily", is_active=True, start_date__lte=today)
        if a.runs_on(today)
    ]
    return max(targets, default=None)


def _roster(staff, today, tasks):
    """Express students with today's finished-test count and their last finished test."""
    students = list(students_for(staff).filter(is_express=True, archived_at__isnull=True).order_by("first_name", "last_name"))
    counts = finished_per_day([s.pk for s in students], today, today)
    last_finished = dict(
        TestSession.objects.filter(user__in=students, finished_at__isnull=False)
        .values_list("user_id").annotate(last=Max("finished_at"))
    )
    totals = {student.pk: [0, 0] for student in students}
    for task in tasks:
        for row in progress(task, today=today):
            if row.student.pk in totals:
                done = row.completed if task.is_selection else min(row.today, row.target)
                totals[row.student.pk][0] += done
                totals[row.student.pk][1] += row.target
    for s in students:
        s.today = counts.get((s.pk, today), 0)
        s.last_test = last_finished.get(s.pk)
        s.assignment_done, s.assignment_total = totals[s.pk]
        s.done = bool(s.assignment_total) and s.assignment_done >= s.assignment_total
        s.percent = min(100, round(s.assignment_done * 100 / s.assignment_total)) if s.assignment_total else 0
    return students


@school_admin_required
def express_list(request):
    today = timezone.localdate()
    target = daily_target(today)
    tasks = [task for task in Assignment.objects.filter(audience="express", is_active=True, start_date__lte=today).select_related("created_by") if task.runs_on(today)]
    roster = _roster(request.user, today, tasks)
    return render(request, "admin/express/list.html", _page(
        request, "Express",
        roster=roster,
        target=target,
        task_count=len(tasks),
        done_count=sum(1 for s in roster if s.done),
        candidates=students_for(request.user).filter(is_express=False, archived_at__isnull=True).order_by(F("group").asc(nulls_first=True), "first_name"),
    ))


@school_admin_required
@require_POST
def express_add(request):
    added = students_for(request.user).filter(
        pk__in=request.POST.getlist("students"), is_express=False, archived_at__isnull=True,
    ).update(is_express=True)
    if added:
        messages.success(request, f"{added} ta talaba Express kursiga qo‘shildi.")
    else:
        messages.error(request, "Hech kim tanlanmadi.")
    return redirect("express:list")


@school_admin_required
@require_POST
def express_remove(request, pk):
    removed = students_for(request.user).filter(pk=pk, is_express=True).update(is_express=False)
    if removed:
        messages.success(request, "Talaba Express kursidan chiqarildi.")
    return redirect("express:list")
