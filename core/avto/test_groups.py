from datetime import time, timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .leaderboard import EXAM_BONUS, build
from .models import (
    Answer, Branch, Question, StudyGroup, TestCategory, TestSession, TestType, User, UserAnswer,
)


class LeaderboardFixture(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.branch = Branch.objects.create(school_name="Avto", name="Chilonzor")
        cls.group = StudyGroup.objects.create(name="52", category="B", branch=cls.branch)
        cls.other = StudyGroup.objects.create(name="53", category="B", branch=cls.branch)
        cls.teacher = User.objects.create_user(username="t", password="x", is_staff=True, unlimited=True)
        cls.ali = cls.student("ali", "Ali", cls.group)
        cls.vali = cls.student("vali", "Vali", cls.group)
        cls.zero = cls.student("zero", "Zero", cls.group)
        cls.far = cls.student("far", "Far", cls.other)
        cls.category = TestCategory.objects.create(nomi="Mavzu", question_count=3)
        kind = TestType.objects.create(nomi="t", vaqt_daqiqa=10, savollar_soni=3)
        cls.questions = [
            Question.objects.create(
                test_turi=kind, kategoriya=cls.category, matn_uzb=f"q{i}", matn_uz_kr="q", matn_rus="q",
            )
            for i in range(3)
        ]
        for q in cls.questions:
            Answer.objects.create(question=q, matn_uzb="y", matn_uz_kr="y", matn_rus="y", togri=True)
            Answer.objects.create(question=q, matn_uzb="n", matn_uz_kr="n", matn_rus="n", togri=False)

    @classmethod
    def student(cls, username, first, group):
        return User.objects.create_user(
            username=username, password="x", first_name=first, last_name="Test", group=group, unlimited=True,
        )

    def finish(self, user, correct_flags, kind="shablon", finished=True):
        session = TestSession.objects.create(
            user=user, category=self.category, test_kind=kind, started_at=timezone.now(),
            finished_at=timezone.now() if finished else None,
            question_order=[q.pk for q in self.questions[: len(correct_flags)]],
        )
        for question, ok in zip(self.questions, correct_flags):
            UserAnswer.objects.create(
                session=session, question=question, is_correct=ok,
                selected_answer=question.javoblar.get(togri=ok),
            )
        return session


class LeaderboardLogicTests(LeaderboardFixture):
    def test_unique_correct_questions_and_ties(self):
        self.finish(self.ali, [True, True, False])
        self.finish(self.ali, [True, True, False])  # repeat must not add points
        self.finish(self.vali, [True, False, False])
        rows = {r.student.username: r for r in build([self.ali, self.vali, self.zero])}
        self.assertEqual((rows["ali"].points, rows["vali"].points, rows["zero"].points), (2, 1, 0))
        self.assertEqual((rows["ali"].rank, rows["vali"].rank, rows["zero"].rank), (1, 2, 3))
        self.assertEqual(rows["ali"].accuracy, 67)

    def test_unfinished_tests_do_not_count(self):
        self.finish(self.ali, [True, True, True], finished=False)
        self.assertEqual(build([self.ali])[0].points, 0)

    def test_passed_real_exam_gives_bonus_failed_does_not(self):
        self.finish(self.ali, [True, True, True], kind="real")
        self.finish(self.vali, [False, False, False], kind="real")
        rows = {r.student.username: r for r in build([self.ali, self.vali])}
        self.assertEqual(rows["ali"].points, 3 + EXAM_BONUS)
        self.assertEqual((rows["vali"].exams_passed, rows["vali"].points), (0, 0))


class GroupPagesTests(LeaderboardFixture):
    def setUp(self):
        self.client.force_login(self.teacher)

    def test_group_pages_render_with_leaderboard(self):
        self.finish(self.ali, [True, True, True])
        self.assertContains(self.client.get(reverse("groups:list")), "Ali Test")
        detail = self.client.get(reverse("groups:detail", args=[self.group.pk]), {"sort": "accuracy", "period": "week"})
        self.assertEqual([r.student.username for r in detail.context["rows"]][0], "ali")
        self.assertEqual(len(detail.context["rows"]), 3)

    def test_admin_leaderboard_filters_by_group(self):
        response = self.client.get(reverse("admin_leaderboard"), {"group": self.other.pk})
        self.assertEqual([r.student.username for r in response.context["rows"]], ["far"])

    def test_create_and_delete_group_keeps_students(self):
        response = self.client.post(reverse("groups:create"), {
            "name": "60", "category": "A", "branch": self.branch.pk, "teacher": self.teacher.pk,
        })
        group = StudyGroup.objects.get(name="60")
        self.assertRedirects(response, reverse("groups:detail", args=[group.pk]))
        self.client.post(reverse("groups:delete", args=[self.group.pk]))
        self.ali.refresh_from_db()
        self.assertIsNone(self.ali.group)

    def test_staff_only(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("groups:list")).status_code, 302)


class StudentLeaderboardTests(LeaderboardFixture):
    def test_student_sees_group_and_overall_rank_without_private_data(self):
        self.finish(self.ali, [True, True, True])
        self.finish(self.far, [True, True, False])
        self.client.force_login(self.vali)
        response = self.client.get(reverse("leaderboard"))
        self.assertEqual(response.context["scope"], "group")
        self.assertEqual(response.context["my_group_rank"].rank, 2)
        self.assertEqual(response.context["my_overall_rank"].rank, 3)
        self.assertContains(response, "Ali T.")
        self.assertNotContains(response, "ali</")

    def test_all_scope_and_top_limit_keep_own_row(self):
        self.client.force_login(self.zero)
        self.finish(self.ali, [True])
        response = self.client.get(reverse("leaderboard"), {"scope": "all", "top": "10"})
        self.assertEqual(len(response.context["podium"]) + len(response.context["rest"]), 4)

    def test_metric_changes_ranking_and_search_filters_names(self):
        self.finish(self.ali, [True, True, True, ][:3])           # 3 solved, 100%
        self.finish(self.vali, [True, False, False])              # 1 solved, 33%
        self.client.force_login(self.ali)
        by_acc = self.client.get(reverse("leaderboard"), {"scope": "all", "metric": "accuracy"})
        self.assertEqual(by_acc.context["my_overall_rank"].rank, 1)
        found = self.client.get(reverse("leaderboard"), {"scope": "all", "q": "vali"})
        self.assertEqual([r.student.username for r in found.context["rest"]], ["vali"])
        self.assertEqual(found.context["podium"], [])

    def test_activity_metric_ranks_by_days_not_by_points(self):
        yesterday = timezone.now() - timedelta(days=1)
        for when in (timezone.now(), yesterday):          # ali: 2 days, 1 correct answer in total
            session = self.finish(self.ali, [True][:1])
            TestSession.objects.filter(pk=session.pk).update(finished_at=when)
        self.finish(self.vali, [True, True, True])        # vali: 1 day, 3 points
        self.client.force_login(self.ali)
        response = self.client.get(reverse("leaderboard"), {"scope": "all", "metric": "active"})
        ranked = response.context["podium"] + response.context["rest"]
        by_user = {r.student.username: r for r in ranked}
        self.assertEqual((by_user["ali"].active_days, by_user["vali"].active_days), (2, 1))
        self.assertEqual((by_user["ali"].rank, by_user["vali"].rank), (1, 2))   # fewer points, more regular
        self.assertGreater(by_user["vali"].points, by_user["ali"].points)

    def test_podium_is_top_three_by_rank_for_any_sort(self):
        self.finish(self.ali, [True, True, True])
        self.finish(self.vali, [True, True, False])
        self.finish(self.far, [True, False, False])
        self.client.force_login(self.ali)
        response = self.client.get(reverse("leaderboard"), {"scope": "all"})
        self.assertEqual([r.student.username for r in response.context["podium"]], ["ali", "vali", "far"])
        self.assertContains(response, "lb-crown")
        by_name = self.client.get(reverse("leaderboard"), {"scope": "all", "metric": "points", "period": "week"})
        self.assertEqual(len(by_name.context["podium"]), 3)

    def test_admin_podium_ignores_name_sort_and_shows_without_points(self):
        self.finish(self.ali, [True])
        self.client.force_login(self.teacher)
        response = self.client.get(reverse("admin_leaderboard"), {"sort": "name"})
        podium = response.context["podium"]
        self.assertEqual(podium[0].student.username, "ali")  # best rank leads even when listed by name
        self.assertEqual(len(podium), 3)
        self.assertEqual(len(podium) + len(response.context["rest"]), 4)


class GroupMembershipTests(LeaderboardFixture):
    def setUp(self):
        self.client.force_login(self.teacher)

    def test_add_existing_students_moves_them_between_groups(self):
        self.client.post(reverse("groups:add_students", args=[self.other.pk]), {"students": [self.ali.pk, self.zero.pk]})
        self.ali.refresh_from_db()
        self.assertEqual(self.ali.group, self.other)
        detail = self.client.get(reverse("groups:detail", args=[self.group.pk]))
        self.assertIn(self.far, detail.context["candidates"])
        self.assertNotIn(self.vali, detail.context["candidates"])

    def test_remove_student_from_group(self):
        self.client.post(reverse("groups:remove_student", args=[self.group.pk, self.ali.pk]))
        self.ali.refresh_from_db()
        self.assertIsNone(self.ali.group)

    def test_changing_group_on_student_form_updates_profile(self):
        self.client.force_login(self.teacher)
        self.group.teacher, self.group.lesson_days = self.teacher, "135"
        self.group.lesson_start, self.group.lesson_end = time(19), time(21)
        self.group.save()
        response = self.client.post(reverse("students:edit", args=[self.far.pk]), {
            "first_name": "Far", "last_name": "Test", "phone": "90-111-22-33", "group": self.group.pk,
            "group_language": "uz", "password": "Far12345",
        })
        self.assertEqual(response.status_code, 302, getattr(response, "context", None) and response.context["form"].errors)
        self.far.refresh_from_db()  # the password was reset by the form
        self.client.force_login(self.far)
        profile = self.client.get(reverse("profile"))
        self.assertContains(profile, "Du-Chor-Ju · 19:00–21:00")


class TeacherPagesTests(LeaderboardFixture):
    def test_admin_creates_teacher_who_can_be_assigned_and_log_in(self):
        admin = User.objects.create_superuser(username="boss", password="x")
        self.client.force_login(admin)
        self.client.post(reverse("teachers:create"), {
            "first_name": "Ibrat", "last_name": "Karimov", "username": "ibrat", "phone": "", "password": "Ibra1980",
        })
        teacher = User.objects.get(username="ibrat")
        self.assertTrue(teacher.is_staff and teacher.unlimited and teacher.check_password("Ibra1980"))
        self.client.post(reverse("groups:edit", args=[self.group.pk]), {
            "name": "52", "category": "B", "branch": self.branch.pk, "teacher": teacher.pk,
            "lesson_days": ["2", "4", "6"], "lesson_start": "10:00", "lesson_end": "12:00",
        })
        self.group.refresh_from_db()
        self.assertEqual((self.group.teacher, self.group.lesson_time), (teacher, "Se-Pay-Shan · 10:00–12:00"))

    def test_teachers_cannot_manage_teachers(self):
        self.client.force_login(self.teacher)
        self.assertRedirects(self.client.get(reverse("teachers:list")), reverse("admin:index"), fetch_redirect_response=False)


class LessonScheduleTests(LeaderboardFixture):
    def post(self, **extra):
        self.client.force_login(self.teacher)
        data = {"name": "70", "category": "B", "branch": self.branch.pk, "teacher": "", **extra}
        return self.client.post(reverse("groups:create"), data)

    def test_days_are_stored_sorted_and_shown_as_text(self):
        self.post(lesson_days=["5", "1", "3"], lesson_start="09:30", lesson_end="11:30")
        group = StudyGroup.objects.get(name="70")
        self.assertEqual(group.lesson_days, "135")
        self.assertEqual(group.lesson_time, "Du-Chor-Ju · 09:30–11:30")

    def test_schedule_is_optional(self):
        self.post()
        self.assertEqual(StudyGroup.objects.get(name="70").lesson_time, "")

    def test_end_must_follow_start_and_both_are_required_together(self):
        self.assertEqual(self.post(lesson_start="19:00", lesson_end="18:00").status_code, 200)
        self.assertEqual(self.post(lesson_start="19:00").status_code, 200)
        self.assertFalse(StudyGroup.objects.filter(name="70").exists())
