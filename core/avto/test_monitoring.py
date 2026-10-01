from datetime import time, timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import LoginEvent, StatisticsReset, TestSession, UserAnswer
from .monitoring import IDLE_CAP_SECONDS, active_seconds, collect, lesson_insight
from .test_groups import LeaderboardFixture


class ActiveSecondsTests(TestCase):
    def test_long_pauses_are_capped(self):
        start = timezone.now()
        times = [start + timedelta(seconds=20), start + timedelta(hours=5)]
        self.assertEqual(active_seconds(start, None, times), 20 + IDLE_CAP_SECONDS)

    def test_legacy_answers_without_timestamps_fall_back_to_session_length(self):
        start = timezone.now()
        self.assertEqual(active_seconds(start, start + timedelta(minutes=10), [None, None]), 600)
        self.assertEqual(active_seconds(start, start + timedelta(days=2), []), 7200)

    def test_nothing_without_start(self):
        self.assertEqual(active_seconds(None, None, []), 0)


class MonitoringFixture(LeaderboardFixture):
    def solve(self, user, flags, when=None, kind="shablon", finish=True, gap=30):
        """A session whose answers arrive `gap` seconds apart, starting at `when`."""
        when = when or timezone.now()
        session = TestSession.objects.create(
            user=user, category=self.category, test_kind=kind, started_at=when,
            finished_at=when + timedelta(seconds=gap * len(flags)) if finish else None,
            question_order=[q.pk for q in self.questions[: len(flags)]],
        )
        for i, (question, ok) in enumerate(zip(self.questions, flags), start=1):
            UserAnswer.objects.create(
                session=session, question=question, is_correct=ok,
                selected_answer=question.javoblar.get(togri=ok), answered_at=when + timedelta(seconds=gap * i),
            )
        return session

    def activity(self, user, days=30):
        return collect([user], days)[user.pk]


class CollectTests(MonitoringFixture):
    def test_totals_time_and_accuracy(self):
        self.solve(self.ali, [True, True, False])
        a = self.activity(self.ali)
        self.assertEqual((a.tests, a.answered, a.correct, a.wrong, a.accuracy), (1, 3, 2, 1, 67))
        self.assertEqual((a.seconds, a.seconds_per_answer), (90, 30))
        self.assertEqual(a.sessions[0].seconds_per_answer, 30)

    def test_regularity_levels(self):
        self.assertEqual(self.activity(self.zero, 7).level, "none")
        self.solve(self.ali, [True], when=timezone.now() - timedelta(days=1))
        self.assertEqual(self.activity(self.ali, 30).level, "low")      # 1 of 30 days
        self.assertEqual(self.activity(self.ali, 7).level, "low")       # 1 of 7 days is under 25%
        self.solve(self.ali, [True], when=timezone.now() - timedelta(days=2))
        self.assertEqual(self.activity(self.ali, 7).level, "good")

    def test_streak_counts_back_from_today_or_yesterday(self):
        for days_ago in (1, 2, 3, 5):
            self.solve(self.vali, [True], when=timezone.now() - timedelta(days=days_ago))
        self.assertEqual(self.activity(self.vali).streak, 3)

    def test_sessions_without_answers_and_old_sessions_are_ignored(self):
        TestSession.objects.create(user=self.ali, category=self.category, test_kind="shablon", started_at=timezone.now())
        self.solve(self.ali, [True], when=timezone.now() - timedelta(days=40))
        self.assertEqual(self.activity(self.ali, 30).tests, 0)
        self.assertEqual(self.activity(self.ali, 90).tests, 1)

    def test_logins_and_last_activity(self):
        LoginEvent.objects.create(user=self.far, at=timezone.now() - timedelta(days=2))
        a = self.activity(self.far)
        self.assertEqual((a.logins, a.active_days, a.solve_days, a.days_since_active), (1, 1, 0, 2))

    def test_unfinished_session_counts_and_is_open(self):
        self.solve(self.ali, [True, False], finish=False)
        a = self.activity(self.ali)
        self.assertEqual((a.tests, a.finished_tests, a.sessions[0].result), (1, 0, "open"))

    def test_real_exam_result(self):
        self.solve(self.ali, [True, True, True], kind="real")
        self.solve(self.vali, [False, False, False], kind="real")
        self.assertEqual(self.activity(self.ali).real_exams, {"total": 1, "passed": 1})
        self.assertEqual(self.activity(self.vali).sessions[0].result, "failed")

    def test_wrong_questions_and_categories(self):
        self.solve(self.ali, [True, False, False])
        a = self.activity(self.ali)
        self.assertEqual(sum(a.wrong_questions.values()), 2)
        self.assertEqual(a.by_category, [{"name": "Mavzu", "answered": 3, "accuracy": 33}])


class LessonInsightTests(MonitoringFixture):
    def test_detects_practice_right_before_the_lesson(self):
        now = timezone.localtime()
        self.group.lesson_days = str(now.isoweekday())
        self.group.lesson_start, self.group.lesson_end = time(19), time(21)
        self.group.save()
        lesson_eve = now.replace(hour=17, minute=30, second=0, microsecond=0)
        self.solve(self.ali, [True], when=lesson_eve)
        insight = lesson_insight(self.activity(self.ali), self.group)
        self.assertEqual((insight["on_lesson_day_pct"], insight["before_lesson_pct"], insight["cramming"]), (100, 100, True))

    def test_none_without_schedule_or_tests(self):
        self.assertIsNone(lesson_insight(self.activity(self.ali), self.group))


class MonitoringPagesTests(MonitoringFixture):
    def setUp(self):
        self.client.force_login(self.teacher)
        self.session = self.solve(self.ali, [True, False, True])

    def test_flow_overview_group_student_session(self):
        overview = self.client.get(reverse("monitoring:overview"))
        self.assertContains(overview, "52")
        group = self.client.get(reverse("monitoring:group", args=[self.group.pk]))
        self.assertEqual([r.student.username for r in group.context["rows"]][-1], "ali")  # busiest last under «attention»
        student = self.client.get(reverse("monitoring:student", args=[self.ali.pk]), {"days": 90})
        self.assertEqual(student.context["a"].tests, 1)
        self.assertContains(student, reverse("monitoring:session", args=[self.session.pk]))
        detail = self.client.get(reverse("monitoring:session", args=[self.session.pk]))
        self.assertEqual(detail.context["counts"], {"correct": 2, "wrong": 1, "skipped": 0})
        self.assertEqual(detail.context["seconds"], 90)

    def test_level_filter_and_search(self):
        idle = self.client.get(reverse("monitoring:group", args=[self.group.pk]), {"level": "none"})
        self.assertEqual({r.student.username for r in idle.context["rows"]}, {"vali", "zero"})
        found = self.client.get(reverse("monitoring:group", args=[self.group.pk]), {"q": "ali"})
        self.assertIn("ali", [r.student.username for r in found.context["rows"]])

    def test_ungrouped_page_and_bad_period_fall_back(self):
        self.ali.group = None
        self.ali.save()
        page = self.client.get(reverse("monitoring:ungrouped"), {"days": "abc"})
        self.assertEqual(page.status_code, 200)
        self.assertEqual(page.context["days"], 7)

    def test_staff_only_and_staff_accounts_are_not_monitored(self):
        self.assertEqual(self.client.get(reverse("monitoring:student", args=[self.teacher.pk])).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.get(reverse("monitoring:overview")).status_code, 302)


class TrackingTests(MonitoringFixture):
    def test_student_login_is_recorded_but_staff_login_is_not(self):
        self.ali.phone = "901112233"
        self.ali.save()
        self.client.post(reverse("login"), {"role": "student", "username": "90-111-22-33", "password": "x"})
        self.assertEqual(LoginEvent.objects.filter(user=self.ali).count(), 1)
        self.client.logout()
        self.client.post(reverse("login"), {"role": "staff", "username": "t", "password": "x"})
        self.assertFalse(LoginEvent.objects.filter(user=self.teacher).exists())

    def test_clearing_statistics_leaves_a_trace_for_the_teacher(self):
        self.solve(self.ali, [True, True])
        self.client.force_login(self.ali)
        self.client.post(reverse("clear_statistics"))
        reset = StatisticsReset.objects.get(user=self.ali)
        self.assertEqual((reset.tests, reset.answers), (1, 2))
        self.client.force_login(self.teacher)
        page = self.client.get(reverse("monitoring:student", args=[self.ali.pk]))
        self.assertContains(page, "statistikasini tozalagan")

    def test_new_answers_get_a_timestamp(self):
        self.client.force_login(self.ali)
        session = TestSession.objects.create(
            user=self.ali, category=self.category, test_kind="shablon", started_at=timezone.now(),
            question_order=[q.pk for q in self.questions],
        )
        question = self.questions[0]
        self.client.post(reverse("submit_answer"), {
            "session_id": session.pk, "question_id": question.pk, "answer_id": question.javoblar.first().pk,
        })
        self.assertIsNotNone(UserAnswer.objects.get(session=session).answered_at)
