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
        self.assertEqual(len(response.context["rows"]), 4)
