"""Exact assigned tests and durable completion, plus existing daily-plan progress."""
from dataclasses import dataclass
from datetime import timedelta

from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone

from .models import TestSession


@dataclass
class StudentProgress:
    student: object
    today: int          # tests finished today
    target: int         # tests required per day
    days_done: int      # days (up to today) on which the target was reached
    days_total: int     # days (up to today) the task has been running

    @property
    def done_today(self):
        return self.today >= self.target

    @property
    def percent(self):
        return min(100, round(self.today * 100 / self.target))

    @property
    def days_percent(self):
        return round(self.days_done * 100 / self.days_total) if self.days_total else 0


def finished_per_day(user_ids, since, until):
    """{(user_id, date): finished tests} between two local dates, inclusive."""
    rows = (
        TestSession.objects
        .filter(user_id__in=user_ids, finished_at__isnull=False,
                finished_at__date__gte=since, finished_at__date__lte=until)
        .annotate(day=TruncDate("finished_at"))
        .values("user_id", "day")
        .annotate(total=Count("id"))
    )
    return {(row["user_id"], row["day"]): row["total"] for row in rows}


def running_days(assignment, today):
    """Dates from the task's start up to today (or its end date), so a long task never counts future days."""
    last = min(today, assignment.end_date) if assignment.end_date else today
    count = (last - assignment.start_date).days + 1
    return [assignment.start_date + timedelta(days=i) for i in range(max(count, 0))]


def progress(assignment, students=None, today=None):
    """One StudentProgress per student, least finished today first."""
    if assignment.is_selection:
        return selected_progress(assignment, students)
    today = today or timezone.localdate()
    students = list(students if students is not None else assignment.students().order_by("first_name", "last_name"))
    days = running_days(assignment, today)
    counts = finished_per_day([s.pk for s in students], days[0], days[-1]) if days else {}
    target = assignment.tests_per_day
    rows = [
        StudentProgress(
            student=s,
            today=counts.get((s.pk, today), 0),
            target=target,
            days_done=sum(1 for d in days if counts.get((s.pk, d), 0) >= target),
            days_total=len(days),
        )
        for s in students
    ]
    return sorted(rows, key=lambda r: (r.done_today, r.today))


def summary(rows):
    done = sum(1 for r in rows if r.done_today)
    return {"students": len(rows), "done": done, "pending": len(rows) - done}


@dataclass
class SelectedProgress:
    student: object
    completed: int
    target: int
    completions: list

    @property
    def done_today(self):
        return self.target > 0 and self.completed >= self.target

    @property
    def percent(self):
        return round(self.completed * 100 / self.target) if self.target else 0


def selection_items(assignment):
    """The exact assigned content, including unavailable items so nothing silently disappears."""
    from .models import Question
    if assignment.content_type == "bilet":
        targets = list(assignment.bilets.all())
        counts = dict(Question.objects.filter(kategoriya_id__in=[t.pk for t in targets], is_archived=False)
                      .values_list("kategoriya_id").annotate(n=Count("id")))
        return [{"id": t.pk, "key": f"bilet:{t.pk}", "label": t.nomi, "count": min(t.question_count, counts.get(t.pk, 0)),
                 "available": t.aktiv and t.show_in_shablon and bool(counts.get(t.pk)) and t.question_count > 0} for t in targets]
    if assignment.content_type != "topic":
        return []
    targets = list(assignment.topics.select_related("group"))
    ids = [t.pk for t in targets]
    live = Question.objects.filter(is_archived=False, kategoriya__aktiv=True)
    pairs = list(live.filter(mavzu_id__in=ids).values_list("mavzu_id", "id"))
    pairs += list(live.filter(extra_topics__in=ids).values_list("extra_topics", "id"))
    pools = {}
    for topic_id, question_id in pairs:
        pools.setdefault(topic_id, set()).add(question_id)
    return [{"id": t.pk, "key": f"topic:{t.pk}", "label": t.name(), "count": len(pools.get(t.pk, ())),
             "available": t.aktiv and bool(pools.get(t.pk))} for t in targets]


def selected_progress(assignment, students=None):
    from .models import AssignmentCompletion
    students = list(students if students is not None else assignment.students().select_related("group").order_by("first_name", "last_name"))
    keys = {item["key"] for item in selection_items(assignment)}
    by_student = {}
    for completion in AssignmentCompletion.objects.filter(
        assignment=assignment, user__in=students, item_key__in=keys,
    ).select_related("session").order_by("completed_at"):
        by_student.setdefault(completion.user_id, []).append(completion)
    rows = [SelectedProgress(s, len(by_student.get(s.pk, [])), len(keys), by_student.get(s.pk, [])) for s in students]
    return sorted(rows, key=lambda row: (row.done_today, row.completed))


def session_item_key(session):
    if session.source == "mavzu" and session.topic_id:
        return f"topic:{session.topic_id}"
    if session.source == "shablon" and not session.topic_id:
        return f"bilet:{session.category_id}"
    return None


def record_completion(session):
    """Only a finished assignment attempt with every question answered counts, once per item."""
    from .models import AssignmentCompletion, UserAnswer
    if not session.assignment_id or not session.finished_at:
        return
    assignment = session.assignment
    key = session_item_key(session)
    if key not in {item["key"] for item in selection_items(assignment)}:
        return
    total = len(session.question_order)
    if not total:
        return
    answers = UserAnswer.objects.filter(session=session, question_id__in=session.question_order, selected_answer__isnull=False)
    if answers.count() != total:
        return
    AssignmentCompletion.objects.get_or_create(
        assignment=assignment, user=session.user, item_key=key,
        defaults={"label": session.title, "session": session, "correct": answers.filter(is_correct=True).count(), "total": total},
    )


def student_items(assignment, user):
    """Content rows with durable completion and resumable attempts for the student's task page."""
    from .models import AssignmentCompletion
    items = selection_items(assignment)
    completed = {c.item_key: c for c in AssignmentCompletion.objects.filter(assignment=assignment, user=user)}
    ongoing = {}
    for session in assignment.sessions.filter(user=user, finished_at__isnull=True).select_related("category").order_by("-started_at", "-pk"):
        key = session_item_key(session)
        if key not in ongoing and session.remaining_seconds > 0:
            ongoing[key] = session
    for item in items:
        item["completion"] = completed.get(item["key"])
        item["ongoing"] = ongoing.get(item["key"])
    return items
