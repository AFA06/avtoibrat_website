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
    "name": ("Ism bo‘yicha", lambda r: r.student.first_name.lower()),
}


@dataclass
class Row:
    student: object
    solved: int = 0
    attempts: int = 0
    correct: int = 0
    tests: int = 0
    exams_passed: int = 0
    rank: int = 0

    @property
    def points(self):
        return self.solved + self.exams_passed * EXAM_BONUS

    @property
    def accuracy(self):
        return round(self.correct * 100 / self.attempts) if self.attempts else None

    @property
    def public_name(self):
        """Name shown to other students: «Abdurashid F.»"""
        last = (self.student.last_name or "")[:1]
        first = self.student.first_name or self.student.username
        return f"{first} {last}." if last else first


def since_for(period):
    days = PERIODS.get(period, PERIODS["all"])[1]
    return timezone.now() - timedelta(days=days) if days else None


def build(students, period="all"):
    """Ranked rows (best first) for the given students; `rank` is by points, ties share a rank."""
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

    for item in sessions.values("user_id").annotate(n=Count("id")):
        rows[item["user_id"]].tests = item["n"]

    real = sessions.filter(test_kind="real").annotate(
        right=Count("useranswer", filter=Q(useranswer__is_correct=True)),
        wrong=Count("useranswer", filter=Q(useranswer__is_correct=False, useranswer__selected_answer__isnull=False)),
    )
    for session in real:
        complete = session.right + session.wrong >= len(session.question_order) > 0
        if complete and session.wrong < REAL_EXAM_MAX_MISTAKES:
            rows[session.user_id].exams_passed += 1

    ranked = sorted(rows.values(), key=SORTS["points"][1])
    previous, rank = None, 0
    for position, row in enumerate(ranked, start=1):
        key = (row.points, row.accuracy)
        if key != previous:
            rank, previous = position, key
        row.rank = rank
    return ranked


def sort_rows(rows, sort):
    return sorted(rows, key=SORTS.get(sort, SORTS["points"])[1])
