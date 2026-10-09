"""Student-facing daily tasks: what the teacher asked for and how much is done today."""
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render
from django.utils import timezone

from .assignments import progress
from .models import Assignment


def tasks_for(user, today):
    """Running tasks addressed to this student: their express course and/or their group."""
    audience = Q(audience="group", group_id=user.group_id) if user.group_id else Q(pk__in=[])
    if user.is_express:
        audience |= Q(audience="express")
    candidates = Assignment.objects.filter(is_active=True, start_date__lte=today).filter(audience)
    return [a for a in candidates.select_related("group") if a.runs_on(today)]


@login_required
def student_tasks(request):
    today = timezone.localdate()
    cards = []
    for assignment in tasks_for(request.user, today):
        (mine,) = progress(assignment, students=[request.user], today=today)
        cards.append({"assignment": assignment, "progress": mine, "left": max(mine.target - mine.today, 0)})
    cards.sort(key=lambda c: c["progress"].done_today)
    return render(request, "dashboard/tasks.html", {
        "cards": cards, "pending": sum(1 for c in cards if not c["progress"].done_today),
    })
