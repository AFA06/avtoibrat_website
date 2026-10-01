"""Student ranking shared by the admin panel and the student dashboard.

Points = unique questions answered correctly (so repeating the same test cannot be farmed)
       + EXAM_BONUS for every passed real exam.
Ties are broken by accuracy, then by the number of finished tests.
Only finished tests count.
"""
from dataclasses import dataclass
from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone

from .models import TestSession, UserAnswer

# The real exam is failed as soon as the student reaches this many wrong answers.
REAL_EXAM_MAX_MISTAKES = 3
EXAM_BONUS = 20

PERIODS = {
    "all": ("Barcha vaqt", None),
    "month": ("Oxirgi 30 kun", 30),
    "week": ("Oxirgi 7 kun", 7),
}
SORTS = {
    "points": ("Ball bo‘yicha", lambda r: (-r.points, -(r.accuracy or 0), -r.tests)),
    "accuracy": ("Aniqlik bo‘yicha", lambda r: (-(r.accuracy or 0), -r.points)),
    "solved": ("Yechilgan savollar", lambda r: (-r.solved, -r.points)),
    "tests": ("Testlar soni", lambda r: (-r.tests, -r.points)),
    "active": ("Faollik (kunlar)", lambda r: (-r.active_days, -r.points)),
    "name": ("Ism bo‘yicha", lambda r: r.student.first_name.lower()),
}


PODIUM_SIZE = 3


@dataclass
class Row:
    student: object
    solved: int = 0
    attempts: int = 0
    correct: int = 0
    tests: int = 0
    exams_passed: int = 0
    active_days: int = 0  # distinct days with a finished test
    rank: int = 0

    @property
    def points(self):
        return self.solved + self.exams_passed * EXAM_BONUS

    @property
    def accuracy(self):
        return round(self.correct * 100 / self.attempts) if self.attempts else None

    @property
    def hue(self):
        """Stable avatar colour per student."""
        return self.student.pk * 47 % 360

    @property
    def public_name(self):
        """Name shown to other students: «Abdurashid F.»"""
        last = (self.student.last_name or "")[:1]
        first = self.student.first_name or self.student.username
        return f"{first} {last}." if last else first


def since_for(period):
    days = PERIODS.get(period, PERIODS["all"])[1]
    return timezone.now() - timedelta(days=days) if days else None


def build(students, period="all", sort="points"):
    """Rows for the given students, best first by `sort`; equal rows share a rank."""
    rows = {s.pk: Row(student=s) for s in students}
    since = since_for(period)

    sessions = TestSession.objects.filter(user_id__in=rows, finished_at__isnull=False)
    if since:
        sessions = sessions.filter(finished_at__gte=since)

    answers = UserAnswer.objects.filter(
        session__in=sessions, selected_answer__isnull=False,
    ).values("session__user_id").annotate(
        attempts=Count("id"),
        correct=Count("id", filter=Q(is_correct=True)),
        solved=Count("question", filter=Q(is_correct=True), distinct=True),
    )
    for item in answers:
        row = rows[item["session__user_id"]]
        row.attempts, row.correct, row.solved = item["attempts"], item["correct"], item["solved"]

    days = {}
    for user_id, finished in sessions.values_list("user_id", "finished_at"):
        rows[user_id].tests += 1
        days.setdefault(user_id, set()).add(timezone.localtime(finished).date())
    for user_id, user_days in days.items():
        rows[user_id].active_days = len(user_days)

    real = sessions.filter(test_kind="real").annotate(
        right=Count("useranswer", filter=Q(useranswer__is_correct=True)),
        wrong=Count("useranswer", filter=Q(useranswer__is_correct=False, useranswer__selected_answer__isnull=False)),
    )
    for session in real:
        complete = session.right + session.wrong >= len(session.question_order) > 0
        if complete and session.wrong < REAL_EXAM_MAX_MISTAKES:
            rows[session.user_id].exams_passed += 1

    # Rank by the chosen metric; «name» only reorders the display, rank stays by points.
    rank_key = SORTS[sort][1] if sort in SORTS and sort != "name" else SORTS["points"][1]
    ranked = sorted(rows.values(), key=rank_key)
    previous, rank = None, 0
    for position, row in enumerate(ranked, start=1):
        key = rank_key(row)
        if key != previous:
            rank, previous = position, key
        row.rank = rank
    return sorted(ranked, key=SORTS["name"][1]) if sort == "name" else ranked


def split_podium(rows):
    """(top three by rank, the rest in display order). Shown whatever the sort or filter."""
    if len(rows) < PODIUM_SIZE:
        return [], rows
    podium = sorted(rows, key=lambda r: r.rank)[:PODIUM_SIZE]
    on_podium = {r.student.pk for r in podium}
    return podium, [r for r in rows if r.student.pk not in on_podium]
