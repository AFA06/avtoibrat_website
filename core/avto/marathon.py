"""Marathon: the whole question bank in a fixed order, cut into numbered sections.

The student picks a section size (50, 300, …, or all questions at once) and then a section.
Questions keep the order they were added in: section 1 starts with bilet 1, question 1, and
questions added later land in the last section. Every question gets a minute, like the real exam.
"""
import random
from collections import defaultdict

from django.utils import timezone

from .models import Question, TestSession, UserAnswer

ALL = 0  # «all questions at once»: a single section holding the whole bank
SIZES = (50, 300, 500, 700, ALL)
# Real exam: 20 minutes for 20 questions, so a marathon gets the same minute per question.
MINUTES_PER_QUESTION = 1
SOURCE = "marafon"


def question_pool():
    return Question.objects.filter(kategoriya__aktiv=True)


def ordered_ids():
    """Every active question id in the fixed marathon order (the order they were added in)."""
    return list(question_pool().order_by("id").values_list("id", flat=True))


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


def section_size(size, available):
    return available if size == ALL else size


def section_count(size, available):
    step = section_size(size, available)
    return -(-available // step) if step else 0  # ceiling division


def section_ids(size, number, ids=None):
    """Question ids of section `number` (1-based) for this size, or [] when it doesn't exist."""
    ids = ordered_ids() if ids is None else ids
    step = section_size(size, len(ids))
    if number < 1 or not step:
        return []
    return ids[(number - 1) * step:number * step]


def size_options(available):
    """Every size with how many sections it makes; a size larger than the bank is not offered."""
    return [
        {
            "size": size,
            "sections": section_count(size, available),
            "enabled": available > 0 and (size == ALL or size <= available),
        }
        for size in SIZES
    ]


def is_valid_size(size):
    return size in SIZES


def active_session(user):
    """The student's unfinished marathon that still has time left, if any."""
    now = timezone.now()
    for session in TestSession.objects.filter(user=user, source=SOURCE, finished_at__isnull=True).select_related("category"):
        if (now - session.started_at).total_seconds() < session.time_limit_seconds:
            return session
    return None


def finish_active(user):
    TestSession.objects.filter(user=user, source=SOURCE, finished_at__isnull=True).update(finished_at=timezone.now())


def sections(user, size):
    """Sections of one size with the student's progress in each (from its latest attempt)."""
    ids = ordered_ids()
    step = section_size(size, len(ids))
    active = active_session(user)
    latest = {}
    for session in (TestSession.objects
                    .filter(user=user, source=SOURCE, marathon_size=size)
                    .order_by("started_at")):
        latest[session.marathon_section] = session  # later attempts overwrite earlier ones

    rows = []
    for number in range(1, section_count(size, len(ids)) + 1):
        chunk = ids[(number - 1) * step:number * step]
        session = latest.get(number)
        row = {
            "number": number,
            "first": (number - 1) * step + 1,
            "last": (number - 1) * step + len(chunk),
            "total": len(chunk),
            "minutes": time_limit_minutes(len(chunk)),
            "state": "new",
            "answered": 0,
            "correct": 0,
            "percent": 0,
        }
        if session:
            answers = UserAnswer.objects.filter(session=session)
            total = len(session.question_order) or len(chunk)
            row.update(
                session=session,
                answered=answers.count(),
                correct=answers.filter(is_correct=True).count(),
            )
            row["percent"] = round(row["correct"] * 100 / total) if total else 0
            row["progress"] = round(row["answered"] * 100 / total) if total else 0
            if active and active.pk == session.pk:
                row["state"] = "active"
            elif session.finished_at:
                row["state"] = "done"
        rows.append(row)
    return rows


def start(user, size, number):
    """Finish any running marathon and open section `number` of the given size, in fixed order."""
    if not is_valid_size(size):
        raise ValueError("unknown size")
    ids = ordered_ids()
    if size != ALL and size > len(ids):
        raise ValueError("size larger than the question bank")
    question_ids = section_ids(size, number, ids)
    if not question_ids:
        raise ValueError("no such section")
    finish_active(user)
    first = Question.objects.select_related("kategoriya").get(id=question_ids[0])
    session = TestSession.objects.create(
        user=user, category=first.kategoriya, test_kind="shablon", source=SOURCE,
        started_at=timezone.now(), duration_minutes=time_limit_minutes(len(question_ids)),
        marathon_size=size, marathon_section=number,
    )
    session.questions.set(question_ids)
    session.question_order = question_ids
    session.save(update_fields=["question_order"])
    return session


def pick_question_ids(size, spread_over="kategoriya_id"):
    """`size` question ids drawn evenly from every bilet (or topic: spread_over="mavzu_id"), then shuffled.

    Used by the real exam, which wants a random mix; the marathon itself keeps a fixed order.
    """
    by_test = defaultdict(list)
    for question_id, test_id in question_pool().values_list("id", spread_over):
        by_test[test_id].append(question_id)
    for ids in by_test.values():
        random.shuffle(ids)

    picked = []
    remaining = size
    pending = list(by_test.values())
    while remaining > 0 and pending:
        # One question per test per round; the round's order is random so the remainder
        # (size not divisible by the number of tests) doesn't always favour the same tests.
        random.shuffle(pending)
        for ids in pending:
            if remaining == 0:
                break
            picked.append(ids.pop())
            remaining -= 1
        pending = [ids for ids in pending if ids]
    random.shuffle(picked)
    return picked
