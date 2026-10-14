"""Real exam (Real imtihon): 20 or 50 questions drawn at random from every topic, new ones each time.

A 20-question exam allows 2 mistakes (the 3rd ends it as failed), a 50-question exam allows 4
(the 5th ends it). Each question gets a minute.
"""
from django.utils import timezone

from . import marathon
from .models import Question, TestSession, UserAnswer

SIZES = (20, 50)
MINUTES_PER_QUESTION = 1
HISTORY_LIMIT = 6


# The wrong answer that ends the exam: the 3rd in a 20-question exam, the 5th in a 50-question one.
FAILING_MISTAKE = {20: 3, 50: 5}


def max_mistakes(size):
    """The number of wrong answers that fails an exam of `size` questions."""
    return FAILING_MISTAKE.get(size, size // 10 + 1)


def passed(size, wrong, answered):
    return size > 0 and answered >= size and wrong < max_mistakes(size)


def options():
    available = marathon.question_pool().count()
    return [
        {
            "size": size,
            "minutes": size * MINUTES_PER_QUESTION,
            "allowed": max_mistakes(size) - 1,
            "enabled": size <= available,
        }
        for size in SIZES
    ]


def start(user, size):
    """Open a real exam of `size` questions spread over all topics. Raises ValueError if it cannot."""
    if size not in SIZES:
        raise ValueError("unknown size")
    question_ids = marathon.pick_question_ids(size, spread_over="mavzu_id")
    if len(question_ids) < size:
        raise ValueError("not enough questions")
    first = Question.objects.select_related("kategoriya").get(id=question_ids[0])
    session = TestSession.objects.create(
        user=user, category=first.kategoriya, test_kind="real", source="shablon",
        started_at=timezone.now(), duration_minutes=size * MINUTES_PER_QUESTION,
    )
    session.questions.set(question_ids)
    session.question_order = question_ids
    session.save(update_fields=["question_order"])
    return session


def history(user):
    sessions = TestSession.objects.filter(
        user=user, test_kind="real", finished_at__isnull=False
    ).order_by("-finished_at")[:HISTORY_LIMIT]
    rows = []
    for session in sessions:
        size = len(session.question_order)
        answers = UserAnswer.objects.filter(session=session, selected_answer__isnull=False)
        correct = answers.filter(is_correct=True).count()
        wrong = answers.filter(is_correct=False).count()
        rows.append({
            "session": session, "size": size, "correct": correct, "wrong": wrong,
            "passed": passed(size, wrong, correct + wrong),
        })
    return rows
