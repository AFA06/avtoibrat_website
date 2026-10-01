"""Admin → Monitoring: pick a group, see every student's practice, drill into one student."""
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, render

from . import monitoring
from .models import Question, StudyGroup, TestSession
from .monitoring import (
    GROUP_DAYS, LEVELS, PERIOD_CHOICES, active_seconds, collect, lesson_insight, session_review,
)
from .student_views import _page, _students

GROUP_SORTS = {
    "attention": "Diqqat talab qiladi (eng kam faol birinchi)",
    "name": "Ism bo‘yicha",
    "accuracy": "Aniqlik bo‘yicha",
    "tests": "Testlar soni",
    "time": "Sarflangan vaqt",
}
HISTORY_LIMIT = 50
MISSED_LIMIT = 5


def _days(request, default):
    try:
        days = int(request.GET.get("days", default))
    except ValueError:
        return default
    return days if days in PERIOD_CHOICES else default


def _summary(activities):
    """Headline numbers for a set of students."""
    accuracies = [a.accuracy for a in activities if a.accuracy is not None]
    return {
        "count": len(activities),
        "idle": sum(1 for a in activities if a.level == "none"),
        "tests": sum(a.tests for a in activities),
        "accuracy": round(sum(accuracies) / len(accuracies)) if accuracies else None,
    }


def _sort(activities, key):
    never = float("-inf")
    keys = {
        "attention": lambda a: (a.solve_days, a.last_active.timestamp() if a.last_active else never),
        "name": lambda a: a.student.first_name.lower(),
        "accuracy": lambda a: -(a.accuracy if a.accuracy is not None else -1),
        "tests": lambda a: -a.tests,
        "time": lambda a: -a.seconds,
    }
    return sorted(activities, key=keys.get(key, keys["attention"]))


@staff_member_required
def overview(request):
    """Step 1: choose a group."""
    activity = collect(_students().select_related("group"), GROUP_DAYS)
    by_group = {}
    for item in activity.values():
        by_group.setdefault(item.student.group_id, []).append(item)

    groups = StudyGroup.objects.select_related("teacher", "branch").order_by("name")
    cards = [{"group": g, **_summary(by_group.get(g.pk, []))} for g in groups]
    ungrouped = by_group.get(None, [])
    return render(request, "admin/monitoring/overview.html", _page(
        request, "Monitoring", cards=cards,
        ungrouped=_summary(ungrouped) if ungrouped else None,
    ))


@staff_member_required
def group_monitor(request, pk=None):
    """Step 2: every student of the group with their regularity at a glance."""
    group = get_object_or_404(StudyGroup.objects.select_related("teacher", "branch"), pk=pk) if pk else None
    days = _days(request, GROUP_DAYS)
    level = request.GET.get("level", "")
    sort = request.GET.get("sort", "attention")
    query = request.GET.get("q", "").strip().lower()

    students = _students().filter(group=group) if group else _students().filter(group__isnull=True)
    everyone = list(collect(students.select_related("group"), days).values())
    rows = [a for a in everyone if a.level == level] if level in LEVELS else everyone
    if query:
        rows = [a for a in rows if query in a.student.get_full_name().lower()]
    return render(request, "admin/monitoring/group.html", _page(
        request, group.name if group else "Guruhsiz talabalar",
        group=group, rows=_sort(rows, sort), summary=_summary(everyone),
        days=days, level=level, sort=sort, query=query,
        periods=PERIOD_CHOICES, levels=LEVELS, sorts=GROUP_SORTS,
        level_counts={key: sum(1 for a in everyone if a.level == key) for key in LEVELS},
    ))


@staff_member_required
def student_monitor(request, pk):
    """Step 3: everything about one student."""
    student = get_object_or_404(_students().select_related("group__teacher"), pk=pk)
    days = _days(request, monitoring.DEFAULT_DAYS)
    activity = collect([student], days)[student.pk]
    questions = Question.objects.in_bulk([q for q, _ in activity.wrong_questions.most_common(MISSED_LIMIT)])
    missed = [
        {"text": questions[q].get_text(student.group_language), "count": n}
        for q, n in activity.wrong_questions.most_common(MISSED_LIMIT) if q in questions
    ]
    return render(request, "admin/monitoring/student.html", _page(
        request, student.get_full_name() or student.username,
        student=student, a=activity, days=days, periods=PERIOD_CHOICES,
        insight=lesson_insight(activity, student.group), missed=missed,
        history=activity.sessions[:HISTORY_LIMIT], history_limit=HISTORY_LIMIT,
        reset=student.statistics_resets.first(),
    ))


@staff_member_required
def session_detail(request, pk):
    """One test, question by question."""
    session = get_object_or_404(TestSession.objects.select_related("user", "category"), pk=pk, user__is_staff=False)
    rows = session_review(session, session.user.group_language)
    counts = {status: sum(1 for r in rows if r["status"] == status) for status in ("correct", "wrong", "skipped")}
    return render(request, "admin/monitoring/session.html", _page(
        request, "Test tafsilotlari", session=session, student=session.user, rows=rows, counts=counts,
        seconds=active_seconds(
            session.started_at, session.finished_at,
            session.useranswer_set.values_list("answered_at", flat=True),
        ),
        kind=session.get_test_kind_display() if session.test_kind == "real" else session.get_source_display(),
    ))
