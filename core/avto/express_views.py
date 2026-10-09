"""Admin panel: the Express course roster (/admin/express/) and how its students do on the daily task."""
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import F, Max
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .assignments import finished_per_day
from .models import Assignment, TestSession
from .student_views import _page, _students


def daily_target(today):
    """Tests per day expected from express students right now: the strictest running express task, if any."""
    targets = [
        a.tests_per_day
        for a in Assignment.objects.filter(audience="express", is_active=True, start_date__lte=today)
        if a.runs_on(today)
    ]
    return max(targets, default=None)


def _roster(today, target):
    """Express students with today's finished-test count and their last finished test."""
    students = list(_students().filter(is_express=True).order_by("first_name", "last_name"))
    counts = finished_per_day([s.pk for s in students], today, today)
    last_finished = dict(
        TestSession.objects.filter(user__in=students, finished_at__isnull=False)
        .values_list("user_id").annotate(last=Max("finished_at"))
    )
    for s in students:
        s.today = counts.get((s.pk, today), 0)
        s.last_test = last_finished.get(s.pk)
        s.done = target is not None and s.today >= target
        s.percent = min(100, round(s.today * 100 / target)) if target else 0
    return students


@staff_member_required
def express_list(request):
    today = timezone.localdate()
    target = daily_target(today)
    roster = _roster(today, target)
    return render(request, "admin/express/list.html", _page(
        request, "Express",
        roster=roster,
        target=target,
        done_count=sum(1 for s in roster if s.done),
        candidates=_students().filter(is_express=False).order_by(F("group").asc(nulls_first=True), "first_name"),
    ))


@staff_member_required
@require_POST
def express_add(request):
    added = _students().filter(pk__in=request.POST.getlist("students"), is_express=False).update(is_express=True)
    if added:
        messages.success(request, f"{added} ta talaba Express kursiga qo‘shildi.")
    else:
        messages.error(request, "Hech kim tanlanmadi.")
    return redirect("express:list")


@staff_member_required
@require_POST
def express_remove(request, pk):
    removed = _students().filter(pk=pk, is_express=True).update(is_express=False)
    if removed:
        messages.success(request, "Talaba Express kursidan chiqarildi.")
    return redirect("express:list")
