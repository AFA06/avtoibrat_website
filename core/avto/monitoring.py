"""Teacher monitoring: how often, how long and how well each student practises.

Derived from TestSessions, their UserAnswers (with answer timestamps) and LoginEvents.
*Time spent* is active time: a pause longer than IDLE_CAP_SECONDS between two answers only
counts as IDLE_CAP_SECONDS (the student walked away), so an open tab never inflates it.
"""
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from django.db.models import Max
from django.utils import timezone

from .leaderboard import REAL_EXAM_MAX_MISTAKES
from .models import LoginEvent, Question, TestSession, UserAnswer

PERIOD_CHOICES = {7: "Oxirgi 7 kun", 30: "Oxirgi 30 kun", 90: "Oxirgi 90 kun"}
DEFAULT_DAYS = 30
GROUP_DAYS = 7  # the group overview always looks at the last week
IDLE_CAP_SECONDS = 300
LEGACY_CAP_SECONDS = 7200  # answers saved before answer timestamps existed
LOW_ACTIVITY_RATIO = 0.25  # fewer than this share of days with a test = «kam faol»
BEFORE_LESSON_HOURS = 3
HOURS = range(24)

LEVELS = {"none": "Yechmayapti", "low": "Kam faol", "good": "Faol"}


def active_seconds(started, finished, answer_times):
    """Active seconds of one session (see module docstring)."""
    times = sorted(t for t in answer_times if t)
    if times and started:
        previous, total = started, 0
        for moment in times:
            total += min(max((moment - previous).total_seconds(), 0), IDLE_CAP_SECONDS)
            previous = moment
        return int(total)
    if started and finished:
        return int(min(max((finished - started).total_seconds(), 0), LEGACY_CAP_SECONDS))
    return 0


@dataclass
class SessionStat:
    id: int
    kind: str
    source: str
    kind_label: str
    category: str
    started: datetime
    finished: datetime | None
    total: int
    answered: int
    correct: int
    wrong: int
    seconds: int

    @property
    def skipped(self):
        return max(self.total - self.answered, 0)

    @property
    def accuracy(self):
        return round(self.correct * 100 / self.answered) if self.answered else None

    @property
    def seconds_per_answer(self):
        return round(self.seconds / self.answered) if self.answered and self.seconds else None

    @property
    def result(self):
        """«passed»/«failed» for a finished real exam, «done»/«open» for practice tests."""
        if self.kind == "real" and self.finished:
            complete = self.answered >= self.total > 0
            return "passed" if complete and self.wrong < REAL_EXAM_MAX_MISTAKES else "failed"
        return "done" if self.finished else "open"


@dataclass
class DayStat:
    logins: int = 0
    tests: int = 0
    answers: int = 0
    seconds: int = 0


@dataclass
class Activity:
    student: object
    days: int
    sessions: list = field(default_factory=list)  # only sessions with at least one answer
    day_stats: dict = field(default_factory=dict)  # date -> DayStat for every day of the window
    last_login: datetime | None = None
    last_test: datetime | None = None
    wrong_questions: Counter = field(default_factory=Counter)

    # -- totals -------------------------------------------------------------------------------
    @property
    def tests(self):
        return len(self.sessions)

    @property
    def finished_tests(self):
        return sum(1 for s in self.sessions if s.finished)

    @property
    def answered(self):
        return sum(s.answered for s in self.sessions)

    @property
    def correct(self):
        return sum(s.correct for s in self.sessions)

    @property
    def wrong(self):
        return self.answered - self.correct

    @property
    def accuracy(self):
        return round(self.correct * 100 / self.answered) if self.answered else None

    @property
    def seconds(self):
        return sum(s.seconds for s in self.sessions)

    @property
    def seconds_per_answer(self):
        return round(self.seconds / self.answered) if self.answered and self.seconds else None

    @property
    def logins(self):
        return sum(d.logins for d in self.day_stats.values())

    @property
    def real_exams(self):
        finished = [s for s in self.sessions if s.kind == "real" and s.finished]
        return {"total": len(finished), "passed": sum(1 for s in finished if s.result == "passed")}

    # -- regularity ---------------------------------------------------------------------------
    @property
    def solve_days(self):
        return sum(1 for d in self.day_stats.values() if d.tests)

    @property
    def active_days(self):
        return sum(1 for d in self.day_stats.values() if d.tests or d.logins)

    @property
    def level(self):
        if not self.solve_days:
            return "none"
        return "low" if self.solve_days / self.days < LOW_ACTIVITY_RATIO else "good"

    @property
    def level_label(self):
        return LEVELS[self.level]

    @property
    def streak(self):
        """Consecutive days with a test, counted back from today (or yesterday)."""
        day = timezone.localdate()
        if not self.day_stats.get(day, DayStat()).tests:
            day -= timedelta(days=1)
        streak = 0
        while self.day_stats.get(day, DayStat()).tests:
            streak, day = streak + 1, day - timedelta(days=1)
        return streak

    @property
    def last_active(self):
        moments = [m for m in (self.last_login, self.last_test) if m]
        return max(moments) if moments else None

    @property
    def days_since_active(self):
        return (timezone.localdate() - timezone.localtime(self.last_active).date()).days if self.last_active else None

    @property
    def week_strip(self):
        """Last seven days, oldest first: (date, DayStat) — the at-a-glance regularity bar."""
        today = timezone.localdate()
        return [(today - timedelta(days=i), self.day_stats.get(today - timedelta(days=i), DayStat()))
                for i in range(GROUP_DAYS - 1, -1, -1)]

    @property
    def chart(self):
        """Every day of the window with bar height in percent of the busiest day."""
        ordered = sorted(self.day_stats.items())
        peak = max([d.seconds for _, d in ordered] + [1])
        return [{"day": day, "stat": stat, "height": round(stat.seconds * 100 / peak)} for day, stat in ordered]

    @property
    def active_day_list(self):
        return [(day, stat) for day, stat in sorted(self.day_stats.items(), reverse=True) if stat.tests or stat.logins]

    @property
    def hours(self):
        """Tests started per hour of day, with bar heights."""
        counts = Counter(timezone.localtime(s.started).hour for s in self.sessions)
        peak = max(counts.values(), default=1)
        return [{"hour": h, "count": counts.get(h, 0), "height": round(counts.get(h, 0) * 100 / peak)} for h in HOURS]

    @property
    def by_category(self):
        """Accuracy per topic, weakest first."""
        totals = defaultdict(lambda: [0, 0])
        for s in self.sessions:
            totals[s.category][0] += s.answered
            totals[s.category][1] += s.correct
        rows = [{"name": name, "answered": a, "accuracy": round(c * 100 / a)} for name, (a, c) in totals.items() if a]
        return sorted(rows, key=lambda r: (r["accuracy"], -r["answered"]))


def _window_start(days):
    first_day = timezone.localdate() - timedelta(days=days - 1)
    return timezone.make_aware(datetime.combine(first_day, time.min))


def collect(students, days=DEFAULT_DAYS):
    """Activity for every student over the last `days` days, using a handful of bulk queries."""
    students = list(students)
    ids = [s.pk for s in students]
    since = _window_start(days)
    today = timezone.localdate()

    sessions = list(
        TestSession.objects.filter(user_id__in=ids, started_at__gte=since).select_related("category")
    )
    answers = defaultdict(list)
    rows = UserAnswer.objects.filter(session__in=sessions).values_list(
        "session_id", "question_id", "is_correct", "selected_answer_id", "answered_at",
    )
    for session_id, question_id, is_correct, selected_id, answered_at in rows:
        answers[session_id].append((question_id, is_correct, selected_id, answered_at))

    last_login = dict(LoginEvent.objects.filter(user_id__in=ids).values_list("user_id").annotate(m=Max("at")))
    last_test = dict(TestSession.objects.filter(user_id__in=ids).values_list("user_id").annotate(m=Max("started_at")))

    result = {}
    for student in students:
        activity = Activity(
            student=student, days=days,
            day_stats={today - timedelta(days=i): DayStat() for i in range(days)},
            last_login=max([m for m in (last_login.get(student.pk), student.last_login) if m], default=None),
            last_test=last_test.get(student.pk),
        )
        result[student.pk] = activity

    for session in sessions:
        given = answers.get(session.pk, [])
        picked = [a for a in given if a[2]]
        if not picked:
            continue
        correct = sum(1 for a in picked if a[1])
        stat = SessionStat(
            id=session.pk, kind=session.test_kind, source=session.source,
            kind_label=session.get_test_kind_display() if session.test_kind == "real" else session.get_source_display(),
            category=session.category.nomi, started=session.started_at, finished=session.finished_at,
            total=len(session.question_order) or session.category.question_count,
            answered=len(picked), correct=correct, wrong=len(picked) - correct,
            seconds=active_seconds(session.started_at, session.finished_at, [a[3] for a in picked]),
        )
        activity = result[session.user_id]
        activity.sessions.append(stat)
        activity.wrong_questions.update(a[0] for a in picked if not a[1])
        day = activity.day_stats.get(timezone.localtime(session.started_at).date())
        if day:
            day.tests, day.answers, day.seconds = day.tests + 1, day.answers + stat.answered, day.seconds + stat.seconds

    for user_id, at in LoginEvent.objects.filter(user_id__in=ids, at__gte=since).values_list("user_id", "at"):
        day = result[user_id].day_stats.get(timezone.localtime(at).date())
        if day:
            day.logins += 1

    for activity in result.values():
        activity.sessions.sort(key=lambda s: s.started, reverse=True)
    return result


def lesson_insight(activity, group):
    """Share of practice on lesson days and in the hours just before the lesson (None if unknown)."""
    if not group or not group.lesson_days or not activity.tests:
        return None
    lesson_days = set(group.lesson_day_numbers)
    on_lesson_day = before_lesson = 0
    for session in activity.sessions:
        started = timezone.localtime(session.started)
        if started.isoweekday() not in lesson_days:
            continue
        on_lesson_day += 1
        if group.lesson_start:
            gap = datetime.combine(started.date(), group.lesson_start) - started.replace(tzinfo=None)
            if timedelta(0) <= gap <= timedelta(hours=BEFORE_LESSON_HOURS):
                before_lesson += 1
    tests = activity.tests
    before_pct = round(before_lesson * 100 / tests)
    return {
        "on_lesson_day_pct": round(on_lesson_day * 100 / tests),
        "before_lesson_pct": before_pct,
        "hours": BEFORE_LESSON_HOURS,
        "cramming": before_pct >= 50,
    }


def session_review(session, language):
    """Question-by-question review of one session: what was chosen, what was right, how long it took."""
    answers = {
        a.question_id: a
        for a in UserAnswer.objects.filter(session=session).select_related("question", "selected_answer")
    }
    questions = {
        q.pk: q for q in Question.objects.filter(pk__in=session.question_order).prefetch_related("javoblar")
    }
    previous, rows = session.started_at, []
    for number, question_id in enumerate(session.question_order, start=1):
        question = questions.get(question_id)
        answer = answers.get(question_id)
        if not question:
            continue
        seconds = None
        if answer and answer.answered_at and previous:
            seconds = int(min(max((answer.answered_at - previous).total_seconds(), 0), IDLE_CAP_SECONDS))
            previous = answer.answered_at
        correct = next((a for a in question.javoblar.all() if a.togri), None)
        status = "skipped" if not answer or not answer.selected_answer_id else ("correct" if answer.is_correct else "wrong")
        rows.append({
            "number": number, "question": question.get_text(language), "status": status, "seconds": seconds,
            "chosen": answer.selected_answer.get_text(language) if status != "skipped" else "",
            "right": correct.get_text(language) if correct else "",
        })
    return rows
