"""Progress on daily test tasks: how many tests each student finished per day versus the target."""
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
