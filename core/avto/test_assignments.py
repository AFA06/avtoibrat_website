from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .assignments import progress, summary
from .models import Assignment, Branch, StudyGroup, TestCategory, TestSession, User


class AssignmentFixture(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.branch = Branch.objects.create(school_name="Avto", name="Chilonzor")
        cls.group = StudyGroup.objects.create(name="52", category="B", branch=cls.branch)
        cls.teacher = User.objects.create_user(username="teacher", password="x", is_staff=True, unlimited=True)
        cls.ali = cls.student("ali", is_express=True)
        cls.vali = cls.student("vali", is_express=True)
        cls.group_mate = cls.student("mate", group=cls.group)
        cls.outsider = cls.student("outsider")
        cls.category = TestCategory.objects.create(nomi="Shablon", question_count=3)
        cls.today = timezone.localdate()

    @classmethod
    def student(cls, username, **extra):
        return User.objects.create_user(username=username, password="x", first_name=username.title(), unlimited=True, **extra)

    def finish_tests(self, user, count, days_ago=0):
        when = timezone.now() - timedelta(days=days_ago)
        for _ in range(count):
            TestSession.objects.create(user=user, category=self.category, test_kind="shablon", started_at=when, finished_at=when)

    def express_task(self, **extra):
        defaults = {"title": "Kunlik 25", "audience": "express", "tests_per_day": 3, "start_date": self.today}
        return Assignment.objects.create(**{**defaults, **extra})


class ProgressTests(AssignmentFixture):
    def test_counts_only_finished_tests_of_today(self):
        task = self.express_task()
        self.finish_tests(self.ali, 2)
        TestSession.objects.create(user=self.ali, category=self.category, test_kind="shablon", started_at=timezone.now())
        self.finish_tests(self.ali, 5, days_ago=1)
        rows = {r.student: r for r in progress(task)}
        self.assertEqual(rows[self.ali].today, 2)
        self.assertFalse(rows[self.ali].done_today)
        self.assertEqual(rows[self.vali].today, 0)

    def test_task_is_only_for_its_audience(self):
        self.assertEqual(set(self.express_task().students()), {self.ali, self.vali})
        group_task = self.express_task(audience="group", group=self.group)
        self.assertEqual(list(group_task.students()), [self.group_mate])

    def test_days_done_counts_days_reaching_the_target(self):
        task = self.express_task(start_date=self.today - timedelta(days=2))
        self.finish_tests(self.ali, 3, days_ago=2)
        self.finish_tests(self.ali, 2, days_ago=1)
        self.finish_tests(self.ali, 4)
        row = next(r for r in progress(task) if r.student == self.ali)
        self.assertEqual((row.days_done, row.days_total), (2, 3))
        self.assertTrue(row.done_today)

    def test_future_days_are_not_counted(self):
        task = self.express_task(start_date=self.today - timedelta(days=5), end_date=self.today - timedelta(days=3))
        self.assertEqual(progress(task)[0].days_total, 3)

    def test_unfinished_students_come_first(self):
        task = self.express_task()
        self.finish_tests(self.ali, 3)
        self.assertEqual(progress(task)[0].student, self.vali)
        self.assertEqual(summary(progress(task)), {"students": 2, "done": 1, "pending": 1})

    def test_runs_on_respects_dates_and_active_flag(self):
        task = self.express_task(end_date=self.today)
        self.assertTrue(task.runs_on(self.today))
        self.assertFalse(task.runs_on(self.today + timedelta(days=1)))
        task.is_active = False
        self.assertFalse(task.runs_on(self.today))


class AdminPagesTests(AssignmentFixture):
    def setUp(self):
        self.client.force_login(self.teacher)

    def test_pages_render(self):
        task = self.express_task()
        for url in (
            reverse("express:list"), reverse("assignments:list"), reverse("assignments:create"),
            reverse("assignments:detail", args=[task.pk]), reverse("assignments:edit", args=[task.pk]),
        ):
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_pages_require_staff(self):
        self.client.force_login(self.ali)
        for name in ("express:list", "assignments:list", "assignments:create"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 302, name)

    def test_add_and_remove_express_students(self):
        self.client.post(reverse("express:add"), {"students": [self.outsider.pk, self.teacher.pk]})
        self.outsider.refresh_from_db()
        self.teacher.refresh_from_db()
        self.assertTrue(self.outsider.is_express)
        self.assertFalse(self.teacher.is_express)
        self.client.post(reverse("express:remove", args=[self.outsider.pk]))
        self.outsider.refresh_from_db()
        self.assertFalse(self.outsider.is_express)

    def test_express_page_shows_today_against_the_daily_target(self):
        self.express_task(tests_per_day=5)
        self.finish_tests(self.ali, 5)
        response = self.client.get(reverse("express:list"))
        self.assertEqual(response.context["target"], 5)
        self.assertEqual(response.context["done_count"], 1)

    def test_create_express_task_drops_group(self):
        response = self.client.post(reverse("assignments:create"), {
            "title": "Kunlik 25", "audience": "express", "group": self.group.pk, "tests_per_day": 25,
            "start_date": self.today.isoformat(), "is_active": "on",
        })
        task = Assignment.objects.get()
        self.assertRedirects(response, reverse("assignments:detail", args=[task.pk]))
        self.assertIsNone(task.group)
        self.assertEqual(task.created_by, self.teacher)

    def test_group_task_needs_a_group(self):
        response = self.client.post(reverse("assignments:create"), {
            "title": "Uyga vazifa", "audience": "group", "tests_per_day": 10, "start_date": self.today.isoformat(),
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn("group", response.context["form"].errors)

    def test_end_date_cannot_precede_start(self):
        response = self.client.post(reverse("assignments:create"), {
            "title": "X", "audience": "express", "tests_per_day": 10,
            "start_date": self.today.isoformat(), "end_date": (self.today - timedelta(days=1)).isoformat(),
        })
        self.assertIn("end_date", response.context["form"].errors)

    def test_delete(self):
        task = self.express_task()
        self.client.post(reverse("assignments:delete", args=[task.pk]))
        self.assertFalse(Assignment.objects.exists())


class StudentTasksTests(AssignmentFixture):
    def test_express_student_sees_express_task_with_progress(self):
        self.express_task(tests_per_day=4)
        self.finish_tests(self.ali, 1)
        self.client.force_login(self.ali)
        response = self.client.get(reverse("tasks"))
        (card,) = response.context["cards"]
        self.assertEqual((card["progress"].today, card["left"]), (1, 3))

    def test_students_only_see_tasks_meant_for_them(self):
        self.express_task()
        self.express_task(audience="group", group=self.group, title="Guruh")
        self.express_task(title="Tugagan", start_date=self.today - timedelta(days=5), end_date=self.today - timedelta(days=1))
        self.express_task(title="O‘chirilgan", is_active=False)
        titles = {}
        for user in (self.ali, self.group_mate, self.outsider):
            self.client.force_login(user)
            titles[user.username] = [c["assignment"].title for c in self.client.get(reverse("tasks")).context["cards"]]
        self.assertEqual(titles, {"ali": ["Kunlik 25"], "mate": ["Guruh"], "outsider": []})

    def test_requires_login(self):
        self.assertEqual(self.client.get(reverse("tasks")).status_code, 302)
