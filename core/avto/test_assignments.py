from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .assignments import progress, summary
from .models import Answer, Assignment, AssignmentCompletion, Branch, Question, StudyGroup, TestCategory, TestSession, TestType, Topic, TopicGroup, User, UserAnswer


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
        cls.category = TestCategory.objects.create(nomi="Shablon", question_count=3, show_in_shablon=True)
        cls.kind = TestType.objects.create(nomi="Bilet", vaqt_daqiqa=20, savollar_soni=3)
        cls.questions = []
        for number in range(3):
            question = Question.objects.create(test_turi=cls.kind, kategoriya=cls.category, matn_uzb=f"Savol {number}", matn_uz_kr="Савол", matn_rus="Вопрос")
            Answer.objects.create(question=question, matn_uzb="To‘g‘ri", matn_uz_kr="Ҳа", matn_rus="Да", togri=True)
            Answer.objects.create(question=question, matn_uzb="Xato", matn_uz_kr="Йўқ", matn_rus="Нет", togri=False)
            cls.questions.append(question)
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
        self.owner = User.objects.create_superuser(username="owner", password="x")
        self.client.force_login(self.owner)

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
            "content_type": "bilet", "bilets": [self.category.pk],
        })
        task = Assignment.objects.get()
        self.assertRedirects(response, reverse("assignments:detail", args=[task.pk]))
        self.assertIsNone(task.group)
        self.assertEqual(task.created_by, self.owner)

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

    def test_edit_updates_the_target_and_audience_used_for_progress(self):
        task = self.express_task()
        self.finish_tests(self.group_mate, 2)
        self.assertRedirects(self.client.post(reverse("assignments:edit", args=[task.pk]), {
            "title": "Updated task", "audience": "group", "group": self.group.pk,
            "tests_per_day": 2, "start_date": self.today.isoformat(), "is_active": "on",
        }), reverse("assignments:detail", args=[task.pk]))
        task.refresh_from_db()
        self.assertEqual((task.title, task.audience, task.tests_per_day), ("Updated task", "group", 2))
        rows = progress(task)
        self.assertEqual([row.student for row in rows], [self.group_mate])
        self.assertTrue(rows[0].done_today)

    def test_teacher_can_assign_only_their_groups(self):
        self.group.teacher = self.teacher
        self.group.save(update_fields=["teacher"])
        other_group = StudyGroup.objects.create(name="Other", category="B", branch=self.branch)
        other_task = Assignment.objects.create(title="Other", audience="group", group=other_group)
        self.client.force_login(self.teacher)
        self.assertEqual(self.client.post(reverse("assignments:delete", args=[other_task.pk])).status_code, 404)
        data = {"title": "My group", "audience": "group", "group": self.group.pk, "content_type": "bilet", "bilets": [self.category.pk]}
        data["start_date"] = self.today.isoformat()
        response = self.client.post(reverse("assignments:create"), {**data, "audience": "express"})
        self.assertIn("audience", response.context["form"].errors)
        response = self.client.post(reverse("assignments:create"), {**data, "group": other_group.pk})
        self.assertIn("group", response.context["form"].errors)
        self.assertEqual(self.client.post(reverse("assignments:create"), data).status_code, 302)


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


class SelectedAssignmentTests(AssignmentFixture):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.owner = User.objects.create_superuser(username="owner", password="x")
        section = TopicGroup.objects.create(nomi_uzb="Qoidalar", slug="qoidalar")
        cls.topic = Topic.objects.create(group=section, nomi_uzb="Chorrahalar", slug="chorrahalar")
        Question.objects.filter(pk__in=[q.pk for q in cls.questions]).update(mavzu=cls.topic)
        cls.other = TestCategory.objects.create(nomi="Bilet 2", question_count=1, show_in_shablon=True)
        cls.other_question = Question.objects.create(test_turi=cls.kind, kategoriya=cls.other, matn_uzb="Boshqa bilet", matn_uz_kr="Бошқа", matn_rus="Другой")
        Answer.objects.create(question=cls.other_question, matn_uzb="Ha", matn_uz_kr="Ҳа", matn_rus="Да", togri=True)
        cls.group.teacher = cls.teacher
        cls.group.save(update_fields=["teacher"])

    def setUp(self):
        self.client.force_login(self.owner)

    def payload(self, **extra):
        return {"title": "Aniq vazifa", "audience": "express", "recipient_scope": "all", "content_type": "bilet",
                "bilets": [self.category.pk], "start_date": self.today.isoformat(), "is_active": "on", **extra}

    def create_task(self, **extra):
        response = self.client.post(reverse("assignments:create"), self.payload(**extra))
        self.assertEqual(response.status_code, 302, response.context and response.context["form"].errors)
        return Assignment.objects.latest("pk")

    def start(self, task, item=None, user=None):
        self.client.force_login(user or self.ali)
        response = self.client.post(reverse("start_task_item", args=[task.pk, item or self.category.pk]))
        self.assertEqual(response.status_code, 302)
        return TestSession.objects.get(pk=int(response.url.strip("/").split("/")[-1]))

    def finish(self, session, answered=None):
        self.client.force_login(session.user)
        for qid in session.question_order[:answered]:
            answer = Answer.objects.filter(question_id=qid, togri=True).first()
            response = self.client.post(reverse("submit_answer"), {"session_id": session.pk, "question_id": qid, "answer_id": answer.pk})
            self.assertEqual(response.status_code, 200)
        return self.client.post(reverse("finish_test", args=[session.pk]))

    def test_editor_shows_three_audiences_and_exact_content_pickers(self):
        response = self.client.get(reverse("assignments:create"))
        for name in ("express", "group", "individual"):
            self.assertContains(response, f'value="{name}"')
        for name in ("bilets", "topics", "express_students", "individual_students"):
            self.assertContains(response, f'name="{name}"')
        self.assertNotContains(response, 'name="tests_per_day"')

    def test_all_express_and_selected_express_are_distinct_audiences(self):
        all_task = self.create_task()
        self.assertEqual(set(all_task.students()), {self.ali, self.vali})
        self.assertFalse(all_task.recipients.exists())
        selected = self.create_task(recipient_scope="selected", express_students=[self.ali.pk])
        self.assertEqual(list(selected.students()), [self.ali])
        self.client.force_login(self.vali)
        self.assertNotContains(self.client.get(reverse("tasks")), reverse("task_detail", args=[selected.pk]))
        self.assertEqual(self.client.get(reverse("task_detail", args=[selected.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("start_task_item", args=[selected.pk, self.category.pk])).status_code, 404)

    def test_individual_tasks_only_reach_selected_students_outside_group_and_express(self):
        task = self.create_task(audience="individual", individual_students=[self.outsider.pk])
        self.assertEqual(list(task.students()), [self.outsider])
        self.assertEqual(task.recipient_scope, "selected")
        self.client.force_login(self.outsider)
        self.assertContains(self.client.get(reverse("tasks")), task.title)
        self.assertEqual(self.client.get(reverse("task_detail", args=[task.pk])).status_code, 200)
        for invalid in (self.ali, self.group_mate, self.teacher, self.owner):
            self.client.force_login(self.owner)
            response = self.client.post(reverse("assignments:create"), self.payload(audience="individual", individual_students=[invalid.pk]))
            self.assertIn("individual_students", response.context["form"].errors)
        self.outsider.group = self.group
        self.outsider.save(update_fields=["group"])
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(reverse("task_detail", args=[task.pk])).status_code, 404)

    def test_whole_group_includes_express_members_of_that_group(self):
        self.ali.group = self.group
        self.ali.save(update_fields=["group"])
        task = self.create_task(audience="group", group=self.group.pk)
        self.assertEqual(set(task.students()), {self.ali, self.group_mate})
        self.assertFalse(task.recipients.exists())

    def test_invalid_or_empty_audience_selection_cannot_be_saved(self):
        for changes, field in (
            ({"audience": "group", "group": ""}, "group"),
            ({"recipient_scope": "selected", "express_students": []}, "express_students"),
            ({"recipient_scope": "selected", "express_students": [self.outsider.pk]}, "express_students"),
            ({"audience": "individual", "individual_students": []}, "individual_students"),
        ):
            with self.subTest(changes=changes):
                response = self.client.post(reverse("assignments:create"), self.payload(**changes))
                self.assertIn(field, response.context["form"].errors)
        self.assertFalse(Assignment.objects.exists())

    def test_content_selection_is_required_and_legacy_daily_cannot_be_created(self):
        empty = TestCategory.objects.create(nomi="Empty")
        hidden = TestCategory.objects.create(nomi="Hidden", aktiv=False)
        for changes, field in (({"bilets": []}, "bilets"), ({"bilets": [empty.pk]}, "bilets"),
                               ({"bilets": [hidden.pk]}, "bilets"), ({"content_type": "topic", "topics": []}, "topics"),
                               ({"content_type": "daily"}, "content_type")):
            with self.subTest(changes=changes):
                response = self.client.post(reverse("assignments:create"), self.payload(**changes))
                self.assertIn(field, response.context["form"].errors)
        self.assertFalse(Assignment.objects.exists())

    def test_teacher_all_express_is_bounded_to_their_students(self):
        self.ali.group = self.group
        self.ali.save(update_fields=["group"])
        self.client.force_login(self.teacher)
        task = self.create_task()
        self.assertEqual(task.recipient_scope, "selected")
        self.assertEqual(list(task.students()), [self.ali])
        self.assertEqual(self.client.get(reverse("assignments:edit", args=[task.pk])).status_code, 200)
        response = self.client.post(reverse("assignments:create"), self.payload(recipient_scope="selected", express_students=[self.vali.pk]))
        self.assertIn("express_students", response.context["form"].errors)
        response = self.client.post(reverse("assignments:create"), self.payload(audience="individual", individual_students=[self.outsider.pk]))
        self.assertIn("audience", response.context["form"].errors)
        self.client.force_login(self.owner)
        global_task = self.create_task()
        self.client.force_login(self.teacher)
        self.assertEqual(self.client.get(reverse("assignments:detail", args=[global_task.pk])).status_code, 404)
        self.ali.group = None
        self.ali.save(update_fields=["group"])
        self.assertFalse(task.students().exists())
        self.client.force_login(self.ali)
        self.assertEqual(self.client.get(reverse("task_detail", args=[task.pk])).status_code, 404)

    def test_start_is_post_only_and_rejects_unassigned_items_and_students(self):
        task = self.create_task()
        self.client.force_login(self.ali)
        self.assertEqual(self.client.get(reverse("start_task_item", args=[task.pk, self.category.pk])).status_code, 405)
        self.assertEqual(self.client.post(reverse("start_task_item", args=[task.pk, self.other.pk])).status_code, 404)
        for user in (self.outsider, self.owner, self.teacher):
            self.client.force_login(user)
            self.assertEqual(self.client.post(reverse("start_task_item", args=[task.pk, self.category.pk])).status_code, 404)
        self.assertFalse(TestSession.objects.exists())

    def test_start_opens_exact_bilet_and_double_click_resumes_one_attempt(self):
        task = self.create_task()
        session = self.start(task)
        self.assertEqual(session.assignment, task)
        self.assertEqual(set(session.question_order), {q.pk for q in self.questions})
        self.assertEqual(self.start(task).pk, session.pk)
        self.assertEqual(TestSession.objects.count(), 1)
        self.assertEqual(self.client.get(reverse("test_page", args=[session.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("task_detail", args=[task.pk])).context["items"][0]["ongoing"].pk, session.pk)

    def test_topic_task_contains_all_topic_questions_including_extra_topics(self):
        for i in range(22):
            question = Question.objects.create(test_turi=self.kind, kategoriya=self.category, mavzu=self.topic,
                                               matn_uzb=str(i), matn_uz_kr="x", matn_rus="y")
            Answer.objects.create(question=question, matn_uzb="Yes", togri=True)
        self.other_question.extra_topics.add(self.topic)
        task = self.create_task(content_type="topic", topics=[self.topic.pk])
        self.assertFalse(task.bilets.exists())
        session = self.start(task, self.topic.pk)
        self.assertEqual((session.source, session.topic_id), ("mavzu", self.topic.pk))
        self.assertEqual(set(session.question_order), set(Question.objects.filter(mavzu=self.topic).values_list("pk", flat=True)) | {self.other_question.pk})
        self.assertEqual(len(session.question_order), 26)

    def test_only_completed_assigned_tests_count_once(self):
        task = self.create_task(bilets=[self.category.pk, self.other.pk])
        self.finish_tests(self.ali, 4)
        self.assertEqual(progress(task, [self.ali])[0].completed, 0)
        session = self.start(task)
        self.finish(session)
        row = progress(task, [self.ali])[0]
        self.assertEqual((row.completed, row.target, row.percent, row.done_today), (1, 2, 50, False))
        self.client.post(reverse("finish_test", args=[session.pk]))
        self.finish(self.start(task))
        self.assertEqual(progress(task, [self.ali])[0].completed, 1)
        self.finish(self.start(task, self.other.pk))
        self.assertTrue(progress(task, [self.ali])[0].done_today)
        self.assertEqual(AssignmentCompletion.objects.filter(assignment=task, user=self.ali).count(), 2)

    def test_partial_or_empty_finished_test_does_not_complete_task(self):
        task = self.create_task()
        self.finish(self.start(task), answered=0)
        self.finish(self.start(task), answered=2)
        self.assertEqual(progress(task, [self.ali])[0].completed, 0)
        self.assertFalse(AssignmentCompletion.objects.exists())

    def test_task_progress_survives_statistics_reset(self):
        for kind in ("bilet", "topic"):
            self.client.force_login(self.owner)
            task = self.create_task(content_type=kind, topics=[self.topic.pk] if kind == "topic" else [])
            session = self.start(task, self.topic.pk if kind == "topic" else self.category.pk)
            self.finish(session)
            self.assertTrue(progress(task, [self.ali])[0].done_today)
            reset = "clear_topic_statistics" if kind == "topic" else "clear_statistics"
            self.client.post(reverse(reset))
            completion = AssignmentCompletion.objects.get(assignment=task)
            self.assertIsNone(completion.session_id)
            self.assertTrue(progress(task, [self.ali])[0].done_today)
            self.assertEqual(self.client.get(reverse("task_detail", args=[task.pk])).status_code, 200)

    def test_two_tasks_on_same_bilet_keep_their_own_attempts(self):
        first = self.create_task()
        second = self.create_task()
        first_session = self.start(first)
        self.finish(first_session)
        self.assertEqual(progress(second, [self.ali])[0].completed, 0)
        second_session = self.start(second)
        self.assertNotEqual(first_session.pk, second_session.pk)
        self.assertEqual(second_session.assignment, second)

    def test_edit_replaces_exact_content_and_keeps_matching_completion(self):
        task = self.create_task()
        self.finish(self.start(task))
        self.client.force_login(self.owner)
        response = self.client.post(reverse("assignments:edit", args=[task.pk]), self.payload(bilets=[self.category.pk, self.other.pk]))
        self.assertEqual(response.status_code, 302)
        task.refresh_from_db()
        row = progress(task, [self.ali])[0]
        self.assertEqual((row.completed, row.target), (1, 2))
        self.client.force_login(self.ali)
        detail = self.client.get(reverse("task_detail", args=[task.pk]))
        self.assertEqual({item["id"] for item in detail.context["items"]}, {self.category.pk, self.other.pk})

    def test_expired_inactive_and_future_tasks_cannot_start(self):
        for changes in ({"end_date": self.today - timedelta(days=1), "start_date": self.today - timedelta(days=2)},
                        {"start_date": self.today + timedelta(days=1)}, {"is_active": False}):
            task = Assignment.objects.create(title="Unavailable", audience="express", content_type="bilet", **changes)
            task.bilets.add(self.category)
            self.client.force_login(self.ali)
            self.client.post(reverse("start_task_item", args=[task.pk, self.category.pk]))
        self.assertFalse(TestSession.objects.exists())

    def test_unavailable_selected_content_is_shown_but_cannot_start(self):
        task = self.create_task()
        self.category.aktiv = False
        self.category.save(update_fields=["aktiv"])
        self.client.force_login(self.ali)
        detail = self.client.get(reverse("task_detail", args=[task.pk]))
        self.assertContains(detail, "Shablon")
        self.assertFalse(detail.context["items"][0]["available"])
        self.client.post(reverse("start_task_item", args=[task.pk, self.category.pk]))
        self.assertFalse(TestSession.objects.exists())

    def test_express_roster_uses_each_students_actual_assignment(self):
        task = self.create_task(recipient_scope="selected", express_students=[self.ali.pk])
        self.finish(self.start(task))
        self.client.force_login(self.owner)
        response = self.client.get(reverse("express:list"))
        roster = {student.pk: student for student in response.context["roster"]}
        self.assertTrue(roster[self.ali.pk].done)
        self.assertEqual(roster[self.ali.pk].assignment_total, 1)
        self.assertEqual(roster[self.vali.pk].assignment_total, 0)
        self.assertFalse(roster[self.vali.pk].done)

    def test_result_returns_to_assignment_and_deleting_task_keeps_exam_history(self):
        task = self.create_task()
        session = self.start(task)
        self.finish(session)
        response = self.client.get(reverse("test_result", args=[session.pk]))
        self.assertEqual(response.context["list_url"], reverse("task_detail", args=[task.pk]))
        self.assertContains(response, "Vazifaga qaytish")
        self.client.force_login(self.owner)
        self.client.post(reverse("assignments:delete", args=[task.pk]))
        session.refresh_from_db()
        self.assertIsNone(session.assignment_id)
        self.assertEqual(session.useranswer_set.count(), 3)
        self.assertFalse(AssignmentCompletion.objects.filter(assignment_id=task.pk).exists())

    def test_omitted_title_is_generated_and_archived_recipients_are_excluded(self):
        task = self.create_task(title="")
        self.assertEqual(task.title, "Biletlar · 1 ta test")
        self.ali.archived_at = timezone.now()
        self.ali.save(update_fields=["archived_at"])
        self.assertNotIn(self.ali, task.students())
        self.client.force_login(self.ali)
        self.assertEqual(self.client.get(reverse("tasks")).status_code, 302)

    def test_timeout_records_a_fully_answered_assignment_attempt(self):
        task = self.create_task()
        session = self.start(task)
        for qid in session.question_order:
            answer = Answer.objects.get(question_id=qid, togri=True)
            UserAnswer.objects.create(session=session, question_id=qid, selected_answer=answer, is_correct=True)
        TestSession.objects.filter(pk=session.pk).update(started_at=timezone.now() - timedelta(hours=1))
        self.client.get(reverse("test_page", args=[session.pk]))
        self.assertTrue(progress(task, [self.ali])[0].done_today)

    def test_switching_audience_and_content_clears_old_selections(self):
        task = self.create_task(recipient_scope="selected", express_students=[self.ali.pk])
        response = self.client.post(reverse("assignments:edit", args=[task.pk]), self.payload(
            audience="individual", individual_students=[self.outsider.pk], content_type="topic", topics=[self.topic.pk], bilets=[],
        ))
        self.assertEqual(response.status_code, 302)
        task.refresh_from_db()
        self.assertFalse(task.bilets.exists())
        self.assertEqual(list(task.topics.all()), [self.topic])
        self.assertEqual(list(task.recipients.all()), [self.outsider])
        self.assertEqual(list(task.students()), [self.outsider])

    def test_legacy_plan_can_be_converted_without_inventing_completed_content(self):
        task = self.express_task()
        self.finish_tests(self.ali, 5)
        url = reverse("assignments:edit", args=[task.pk]) + "?select=1"
        self.assertContains(self.client.get(url), 'name="content_type"')
        self.assertEqual(self.client.post(url, self.payload()).status_code, 302)
        task.refresh_from_db()
        self.assertEqual(task.content_type, "bilet")
        self.assertEqual(progress(task, [self.ali])[0].completed, 0)
