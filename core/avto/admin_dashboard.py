"""Data for the admin home page (templates/admin/index.html)."""
from django.contrib import admin
from django.db.models import Q
from django.utils import timezone

from .models import (
    ConsultRequest, ContactMessage, Question, StudyGroup, TestSession, User, UserAnswer,
)

EXPIRING_DAYS = 7
CHART_DAYS = 7
RECENT_LIMIT = 5


def _student_stats(now):
    students = User.objects.filter(is_staff=False)
    live = Q(unlimited=True) | Q(account_started_at__lte=now, account_expires_at__gt=now)
    expiring = students.filter(
        unlimited=False,
        account_expires_at__gt=now,
        account_expires_at__lte=now + timezone.timedelta(days=EXPIRING_DAYS),
    )
    return {
        "total": students.count(),
        "active": students.filter(is_active=True).filter(live).count(),
        "expired": students.filter(unlimited=False, account_expires_at__lte=now).count(),
        "expiring_count": expiring.count(),
        "expiring": expiring.order_by("account_expires_at")[:RECENT_LIMIT],
    }


def _activity_chart(today):
    """Finished tests per day for the last CHART_DAYS days, with bar heights in percent."""
    since = today - timezone.timedelta(days=CHART_DAYS - 1)
    counts = {}
    for finished in TestSession.objects.filter(finished_at__date__gte=since).values_list("finished_at", flat=True):
        day = timezone.localtime(finished).date()
        counts[day] = counts.get(day, 0) + 1
    days = [since + timezone.timedelta(days=i) for i in range(CHART_DAYS)]
    peak = max([counts.get(d, 0) for d in days] + [1])
    return [
        {"day": d, "count": counts.get(d, 0), "height": round(counts.get(d, 0) * 100 / peak)}
        for d in days
    ]


def dashboard_context():
    now = timezone.now()
    finished = TestSession.objects.filter(finished_at__isnull=False)
    answers = UserAnswer.objects.all()
    total_answers = answers.count()
    correct = answers.filter(is_correct=True).count()
    return {
        "students": _student_stats(now),
        "staff_count": User.objects.filter(is_staff=True).count(),
        "group_count": StudyGroup.objects.count(),
        "question_count": Question.objects.count(),
        "tests_total": finished.count(),
        "tests_today": finished.filter(finished_at__date=timezone.localdate()).count(),
        "real_exams": finished.filter(test_kind="real").count(),
        "accuracy": round(correct * 100 / total_answers) if total_answers else None,
        "chart": _activity_chart(timezone.localdate()),
        "messages": ContactMessage.objects.all()[:RECENT_LIMIT],
        "consults": ConsultRequest.objects.order_by("-created_at")[:RECENT_LIMIT],
        "recent_tests": finished.select_related("user", "category").order_by("-finished_at")[:RECENT_LIMIT],
    }


def install():
    """Feed the stats to the admin index without replacing the default AdminSite."""
    original_index = admin.site.index

    def index(request, extra_context=None):
        return original_index(request, {**dashboard_context(), **(extra_context or {})})

    admin.site.index = index
