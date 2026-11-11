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
        if session.elapsed_seconds(now) < session.time_limit_seconds:
            return session
    return None


def finish_active(user):
    TestSession.objects.filter(user=user, source=SOURCE, finished_at__isnull=True).update(finished_at=timezone.now())


GLOBAL = "all"  # scope of the main page jar: every size combined


def _scope(size, section, retry):
    """Which jar a run belongs to: the main jar's run fixes every size, any other run only its own size."""
    if retry and section is None and size == ALL:
        return GLOBAL
    return size


def answer_states(user):
    """{size: {question id: was its latest answer in that size right?}} — unanswered questions are absent.

    A mistake belongs to the size it was made in and is fixed by a right answer in that size.
    A right answer in the main jar's run (every mistake combined) fixes the question in every size.
    """
    states = {}
    answers = (UserAnswer.objects
               .filter(session__user=user, session__source=SOURCE, selected_answer__isnull=False,
                       session__marathon_size__isnull=False)
               .order_by("id")
               .values_list("question_id", "is_correct",
                            "session__marathon_size", "session__marathon_section", "session__marathon_retry"))
    for question_id, correct, size, section, retry in answers:
        scope = _scope(size, section, retry)
        if scope == GLOBAL:
            if correct:
                for state in states.values():
                    if question_id in state:
                        state[question_id] = True
            continue  # a wrong answer there leaves the question a mistake wherever it already is
        states.setdefault(scope, {})[question_id] = correct  # later answers overwrite earlier ones
    return states


def mistake_ids(user, size=GLOBAL, number=None, states=None, ids=None):
    """Questions still answered wrong, in marathon order.

    size=GLOBAL: every size combined (the main jar). Otherwise one size's mistakes:
    a single section of it, or the whole size when number is None.
    """
    states = answer_states(user) if states is None else states
    ids = ordered_ids() if ids is None else ids
    if size == GLOBAL:
        wrong = {qid for state in states.values() for qid, ok in state.items() if ok is False}
        return [qid for qid in ids if qid in wrong]
    state = states.get(size, {})
    scope = ids if number is None else section_ids(size, number, ids)
    return [qid for qid in scope if state.get(qid) is False]


def sections(user, size):
    """Sections of one size: progress from the latest full attempt, plus mistakes still to fix."""
    ids = ordered_ids()
    step = section_size(size, len(ids))
    state = answer_states(user).get(size, {})
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


def jar(user, size=GLOBAL):
    """A mistakes jar: one crumpled paper ball per mistake, piled from the bottom.

    The main jar (size=GLOBAL) holds every size's mistakes, coloured by bilet;
    a size's jar holds only that size's, coloured by section.
    """
    states = answer_states(user)
    ids = ordered_ids()
    mistakes = mistake_ids(user, size, states=states, ids=ids)
    shown = mistakes[:JAR_CAPACITY]
    if size == GLOBAL:
        colour = dict(Question.objects.filter(id__in=shown).values_list("id", "kategoriya_id"))
        answered = len(set().union(*states.values())) if states else 0
    else:
        step = section_size(size, len(ids))
        position = {qid: index for index, qid in enumerate(ids)}
        colour = {qid: position[qid] // step + 1 for qid in shown}
        answered = len(states.get(size, {}))
    balls = []
    for index, qid in enumerate(shown):
        row, col = divmod(index, JAR_COLUMNS)
        wobble = (qid * 7919) % 7 - 3  # small, stable offset so the pile looks tossed, not gridded
        # SVG numbers as plain strings: the template would localise a float to «44,8».
        balls.append({
            "x": f"{53 + col * 21 + (10 if row % 2 else 0) + wobble * .7:.1f}",
            "y": f"{225 - row * 18.5 + (wobble % 3):.1f}",
            "r": f"{10 + (qid % 3) * .6:.1f}",
            "hue": (colour.get(qid, 0) * 47) % 360,
            "turn": (qid * 37) % 360,
            "delay": index * 25,
        })
    active = active_session(user)
    stored_size = ALL if size == GLOBAL else size
    if not (active and active.marathon_retry and active.marathon_section is None and active.marathon_size == stored_size):
        active = None
    return {
        "active": active,  # this jar's mistakes run, still going
        "size": size,
        "is_global": size == GLOBAL,
        "count": len(mistakes),
        "answered": answered,
        "balls": balls,
        "overflow": max(len(mistakes) - JAR_CAPACITY, 0),
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


def start_mistakes(user, size=GLOBAL, number=None):
    """A run over questions still answered wrong: the main jar (every size), a size's jar, or one section."""
    if size == GLOBAL:
        question_ids = mistake_ids(user)
        size, number = ALL, None  # stored as size 0 without a section: see _scope()
    elif is_valid_size(size) and size != ALL:
        question_ids = mistake_ids(user, size, number)
    else:
        raise ValueError("unknown size")
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
