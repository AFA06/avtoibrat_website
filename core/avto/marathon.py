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


def answer_state(user):
    """{question id: was its latest marathon answer right?} — questions never answered are absent.

    Every marathon run counts (any size, sections and mistake runs alike), so a question
    answered wrong once stays a mistake until the student answers it right later.
    """
    state = {}
    for question_id, correct in (UserAnswer.objects
                                 .filter(session__user=user, session__source=SOURCE, selected_answer__isnull=False)
                                 .order_by("id")
                                 .values_list("question_id", "is_correct")):
        state[question_id] = correct  # later answers overwrite earlier ones
    return state


def mistake_ids(user, size=ALL, number=None, state=None, ids=None):
    """Questions last answered wrong, in marathon order: one section's, or the whole bank's (number=None)."""
    state = answer_state(user) if state is None else state
    ids = ordered_ids() if ids is None else ids
    scope = ids if number is None else section_ids(size, number, ids)
    return [qid for qid in scope if state.get(qid) is False]


def sections(user, size):
    """Sections of one size: progress from the latest full attempt, plus mistakes still to fix."""
    ids = ordered_ids()
    step = section_size(size, len(ids))
    state = answer_state(user)
    active = active_session(user)
    latest = {}
    for session in (TestSession.objects
                    .filter(user=user, source=SOURCE, marathon_size=size, marathon_retry=False)
                    .order_by("started_at")):
        latest[session.marathon_section] = session  # later attempts overwrite earlier ones
    retry_active = active if active and active.marathon_retry and active.marathon_size == size else None

    rows = []
    for number in range(1, section_count(size, len(ids)) + 1):
        chunk = ids[(number - 1) * step:number * step]
        session = latest.get(number)
        mistakes = sum(state.get(qid) is False for qid in chunk)
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
            "mistakes": mistakes,
            # 100%: every question of the section has been answered right (latest answer).
            "mastered": all(state.get(qid) is True for qid in chunk),
            "retry_session": retry_active if retry_active and retry_active.marathon_section == number else None,
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


JAR_COLUMNS, JAR_ROWS = 6, 8
JAR_CAPACITY = JAR_COLUMNS * JAR_ROWS


def jar(user):
    """The mistakes jar: one crumpled paper ball per mistake, piled from the bottom, coloured by bilet."""
    state = answer_state(user)
    mistakes = [qid for qid in ordered_ids() if state.get(qid) is False]
    bilet = dict(Question.objects.filter(id__in=mistakes[:JAR_CAPACITY]).values_list("id", "kategoriya_id"))
    balls = []
    for index, qid in enumerate(mistakes[:JAR_CAPACITY]):
        row, col = divmod(index, JAR_COLUMNS)
        wobble = (qid * 7919) % 7 - 3  # small, stable offset so the pile looks tossed, not gridded
        # SVG numbers as plain strings: the template would localise a float to «44,8».
        balls.append({
            "x": f"{53 + col * 21 + (10 if row % 2 else 0) + wobble * .7:.1f}",
            "y": f"{225 - row * 18.5 + (wobble % 3):.1f}",
            "r": f"{10 + (qid % 3) * .6:.1f}",
            "hue": (bilet.get(qid, 0) * 47) % 360,
            "turn": (qid * 37) % 360,
            "delay": index * 25,
        })
    return {
        "count": len(mistakes),
        "answered": len(state),
        "balls": balls,
        "overflow": max(len(mistakes) - JAR_CAPACITY, 0),
        "level": min(len(mistakes) / JAR_CAPACITY, 1),
    }


def _open_session(user, question_ids, size, number, retry=False):
    finish_active(user)
    first = Question.objects.select_related("kategoriya").get(id=question_ids[0])
    session = TestSession.objects.create(
        user=user, category=first.kategoriya, test_kind="shablon", source=SOURCE,
        started_at=timezone.now(), duration_minutes=time_limit_minutes(len(question_ids)),
        marathon_size=size, marathon_section=number, marathon_retry=retry,
    )
    session.questions.set(question_ids)
    session.question_order = question_ids
    session.save(update_fields=["question_order"])
    return session


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
    return _open_session(user, question_ids, size, number)


def start_mistakes(user, size, number=None):
    """A run over the questions last answered wrong: one section's, or every mistake (number=None)."""
    if not is_valid_size(size):
        raise ValueError("unknown size")
    question_ids = mistake_ids(user, size, number)
    if not question_ids:
        raise ValueError("no mistakes to work on")
    return _open_session(user, question_ids, size, number, retry=True)


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
