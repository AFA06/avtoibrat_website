"""Marathon: one long practice session of 100–1000 questions with a time budget like the real exam."""
import random
from collections import defaultdict

from django.utils import timezone

from .models import Question, TestSession

SIZES = (100, 300, 500, 700, 1000)
# Real exam: 20 minutes for 20 questions, so a marathon gets the same minute per question.
MINUTES_PER_QUESTION = 1
SOURCE = "marafon"


def question_pool():
    return Question.objects.filter(kategoriya__aktiv=True)


def time_limit_minutes(size):
    return size * MINUTES_PER_QUESTION


def duration_label(minutes, hours_word="soat", minutes_word="daqiqa"):
    hours, rest = divmod(minutes, 60)
    parts = []
    if hours:
        parts.append(f"{hours} {hours_word}")
    if rest or not hours:
        parts.append(f"{rest} {minutes_word}")
    return " ".join(parts)


def size_options(available):
    """Every range with its time budget; ranges bigger than the question bank are marked unavailable."""
    return [
        {"size": size, "minutes": time_limit_minutes(size), "enabled": size <= available}
        for size in SIZES
    ]


def active_session(user):
    """The student's unfinished marathon that still has time left, if any."""
    now = timezone.now()
    for session in TestSession.objects.filter(user=user, source=SOURCE, finished_at__isnull=True).select_related("category"):
        if (now - session.started_at).total_seconds() < session.time_limit_seconds:
            return session
    return None


def finish_active(user):
    TestSession.objects.filter(user=user, source=SOURCE, finished_at__isnull=True).update(finished_at=timezone.now())


def pick_question_ids(size):
    """`size` question ids drawn evenly from every test (bilet/topic), then shuffled together.

    Each test contributes about the same number of questions, so a marathon is never
    one topic after another; tests with fewer questions hand their share to the others.
    """
    by_test = defaultdict(list)
    for question_id, test_id in question_pool().values_list("id", "kategoriya_id"):
        by_test[test_id].append(question_id)
    for ids in by_test.values():
        random.shuffle(ids)

    picked = []
    remaining = size
    pending = list(by_test.values())
    while remaining > 0 and pending:
        # Hand out one question per test per round; the round's order is random so the
        # remainder (size not divisible by the number of tests) doesn't always favour the same tests.
        random.shuffle(pending)
        for ids in pending:
            if remaining == 0:
                break
            picked.append(ids.pop())
            remaining -= 1
        pending = [ids for ids in pending if ids]
    random.shuffle(picked)
    return picked


def start(user, size):
    """Finish any running marathon and open a new one with `size` mixed questions."""
    question_ids = pick_question_ids(size)
    if size not in SIZES or len(question_ids) < size:
        raise ValueError("not enough questions")
    finish_active(user)
    first = Question.objects.select_related("kategoriya").get(id=question_ids[0])
    session = TestSession.objects.create(
        user=user, category=first.kategoriya, test_kind="shablon", source=SOURCE,
        started_at=timezone.now(), duration_minutes=time_limit_minutes(size),
    )
    session.questions.set(question_ids)
    session.question_order = question_ids
    session.save(update_fields=["question_order"])
    return session
