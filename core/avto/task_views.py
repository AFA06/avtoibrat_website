"""Students see and solve the exact content assigned to their audience."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .assignments import progress, student_items
from .models import Assignment, User
from . import topic_tests


def addressed_tasks(user):
    if user.is_staff or user.is_superuser or user.archived_at:
        return Assignment.objects.none()
    audience = Q(audience="group", group_id=user.group_id) if user.group_id else Q(pk__in=[])
    if user.is_express:
        express = Q(audience="express", recipient_scope="all")
        express |= Q(audience="express", recipient_scope="selected", recipients=user) & (
            Q(created_by__is_superuser=True) | Q(created_by__isnull=True) | Q(created_by_id=user.group.teacher_id if user.group_id else None)
        )
        audience |= express
    if not user.group_id and not user.is_express:
        audience |= Q(audience="individual", recipients=user)
    return Assignment.objects.filter(is_active=True).filter(audience).select_related("group", "created_by").distinct()


def tasks_for(user, today):
    return [a for a in addressed_tasks(user).filter(start_date__lte=today) if a.runs_on(today)]


def _my_task(user, pk):
    assignment = get_object_or_404(addressed_tasks(user), pk=pk)
    # Share the same authoritative audience boundary as staff progress and the roster.
    if not assignment.students().filter(pk=user.pk).exists():
        raise Http404
    return assignment


@login_required
def student_tasks(request):
    today = timezone.localdate()
    cards = []
    # Completed/overdue selections stay readable. Existing daily plans keep their original schedule.
    for assignment in addressed_tasks(request.user).filter(start_date__lte=today).prefetch_related("bilets", "topics"):
        if not assignment.is_selection and not assignment.runs_on(today):
            continue
        (mine,) = progress(assignment, students=[request.user], today=today)
        done = mine.completed if assignment.is_selection else mine.today
        cards.append({"assignment": assignment, "progress": mine, "left": max(mine.target - done, 0),
                      "overdue": bool(assignment.end_date and assignment.end_date < today),
                      "items": student_items(assignment, request.user) if assignment.is_selection else []})
    cards.sort(key=lambda card: (card["progress"].done_today, card["overdue"]))
    return render(request, "dashboard/tasks.html", {
        "cards": cards, "pending": sum(1 for card in cards if not card["progress"].done_today and not card["overdue"]),
    })


@login_required
def student_task_detail(request, pk):
    assignment = _my_task(request.user, pk)
    if not assignment.is_selection:
        return redirect("tasks")
    (mine,) = progress(assignment, students=[request.user])
    return render(request, "dashboard/task_detail.html", {
        "assignment": assignment, "progress": mine, "items": student_items(assignment, request.user),
        "running": assignment.runs_on(timezone.localdate()),
    })


@login_required
@require_POST
@transaction.atomic
def start_task_item(request, pk, item_id):
    # Concurrent clicks resume one attempt instead of creating two on PostgreSQL.
    User.objects.select_for_update().get(pk=request.user.pk)
    assignment = _my_task(request.user, pk)
    if not assignment.is_selection:
        raise Http404
    if not assignment.runs_on(timezone.localdate()):
        messages.error(request, "Vazifani boshlash muddati tugagan yoki hali boshlanmagan.")
        return redirect("task_detail", pk=assignment.pk)
    item = next((item for item in student_items(assignment, request.user) if item["id"] == item_id), None)
    if item is None:
        raise Http404
    if not item["available"]:
        messages.error(request, "Bu test savollari hozir mavjud emas. O‘qituvchingizga murojaat qiling.")
        return redirect("task_detail", pk=assignment.pk)
    session = item["ongoing"]
    if session is None:
        if assignment.content_type == "topic":
            session = topic_tests.start(request.user, assignment.topics.get(pk=item_id), "all", assignment=assignment)
        else:
            from .views import _create_test_session
            session = _create_test_session(request.user, assignment.bilets.get(pk=item_id), "shablon", assignment=assignment)
        if session is None:
            messages.error(request, "Bu testda hozir savollar yo‘q. O‘qituvchingizga murojaat qiling.")
            return redirect("task_detail", pk=assignment.pk)
    return redirect("test_page", session_id=session.pk)
