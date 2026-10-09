from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from . import marathon
from .models import Answer, Question, TestCategory, TestSession, TestType, User, UserAnswer


class MarathonFixture(TestCase):
    POOL = 120

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="s", password="x", unlimited=True)
        kind = TestType.objects.create(nomi="t", vaqt_daqiqa=20, savollar_soni=20)
        cls.category = TestCategory.objects.create(nomi="Bilet", aktiv=True, question_count=20, duration_minutes=20)
        hidden = TestCategory.objects.create(nomi="Yashirin", aktiv=False)
        cls.questions = [
            Question.objects.create(test_turi=kind, kategoriya=cls.category, matn_uzb=f"q{i}", matn_uz_kr="q", matn_rus="q")
            for i in range(cls.POOL)
        ]
        Question.objects.create(test_turi=kind, kategoriya=hidden, matn_uzb="hidden", matn_uz_kr="q", matn_rus="q")
        for q in cls.questions:
            Answer.objects.create(question=q, matn_uzb="y", matn_uz_kr="y", matn_rus="y", togri=True)
            Answer.objects.create(question=q, matn_uzb="n", matn_uz_kr="n", matn_rus="n", togri=False)

    def setUp(self):
        self.client.force_login(self.user)


class MarathonLogicTests(MarathonFixture):
    def test_each_question_gets_a_minute_like_the_real_exam(self):
        self.assertEqual([marathon.time_limit_minutes(s) for s in marathon.SIZES], [100, 300, 500, 700, 1000])

    def test_duration_label(self):
        self.assertEqual(marathon.duration_label(100), "1 soat 40 daqiqa")
        self.assertEqual(marathon.duration_label(300), "5 soat")
        self.assertEqual(marathon.duration_label(45), "45 daqiqa")

    def test_ranges_above_the_question_bank_are_disabled(self):
        enabled = {o["size"]: o["enabled"] for o in marathon.size_options(self.POOL)}
        self.assertEqual(enabled, {100: True, 300: False, 500: False, 700: False, 1000: False})

    def test_pool_ignores_inactive_categories(self):
        self.assertEqual(marathon.question_pool().count(), self.POOL)

    def test_start_builds_unique_questions_with_matching_time_limit(self):
        session = marathon.start(self.user, 100)
        self.assertEqual(len(set(session.question_order)), 100)
        self.assertEqual(session.questions.count(), 100)
        self.assertEqual((session.source, session.test_kind), ("marafon", "shablon"))
        self.assertEqual(session.time_limit_seconds, 100 * 60)

    def test_start_rejects_unknown_or_too_big_sizes(self):
        for size in (50, 300):
            with self.assertRaises(ValueError):
                marathon.start(self.user, size)
        self.assertFalse(TestSession.objects.exists())

    def test_starting_again_finishes_the_previous_marathon(self):
        first = marathon.start(self.user, 100)
        second = marathon.start(self.user, 100)
        first.refresh_from_db()
        self.assertIsNotNone(first.finished_at)
        self.assertEqual(marathon.active_session(self.user), second)

    def test_expired_marathon_is_not_resumable(self):
        session = marathon.start(self.user, 100)
        TestSession.objects.filter(pk=session.pk).update(started_at=timezone.now() - timedelta(minutes=101))
        self.assertIsNone(marathon.active_session(self.user))


class MarathonViewTests(MarathonFixture):
    def test_page_lists_ranges_and_shows_resume_card(self):
        response = self.client.get(reverse("marathon"))
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["active"])
        session = marathon.start(self.user, 100)
        UserAnswer.objects.create(session=session, question_id=session.question_order[0], is_correct=True)
        response = self.client.get(reverse("marathon"))
        self.assertEqual((response.context["active"], response.context["active_answered"]), (session, 1))

    def test_start_redirects_into_the_exam(self):
        response = self.client.post(reverse("start_marathon"), {"size": "100"})
        session = TestSession.objects.get()
        self.assertRedirects(response, reverse("test_page", args=[session.id]))

    def test_start_with_too_many_questions_shows_an_error(self):
        response = self.client.post(reverse("start_marathon"), {"size": "1000"}, follow=True)
        self.assertRedirects(response, reverse("marathon"))
        self.assertFalse(TestSession.objects.exists())

    def test_start_requires_post_and_login(self):
        self.assertEqual(self.client.get(reverse("start_marathon")).status_code, 405)
        self.client.logout()
        self.assertEqual(self.client.post(reverse("start_marathon"), {"size": "100"}).status_code, 302)

    def test_exam_page_uses_the_marathon_time_budget(self):
        session = marathon.start(self.user, 100)
        response = self.client.get(reverse("test_page", args=[session.id]))
        self.assertEqual(response.status_code, 200)
        self.assertGreater(response.context["remaining_seconds"], 99 * 60)
        self.assertEqual(len(response.context["questions_data"]), 100)

    def test_answers_are_accepted_beyond_the_category_time(self):
        session = marathon.start(self.user, 100)
        TestSession.objects.filter(pk=session.pk).update(started_at=timezone.now() - timedelta(minutes=30))
        question = Question.objects.get(pk=session.question_order[0])
        answer = question.javoblar.first()
        response = self.client.post(reverse("submit_answer"), {
            "session_id": session.id, "question_id": question.id, "answer_id": answer.id,
        })
        self.assertEqual(response.status_code, 200)

    def test_result_page_restart_leads_back_to_the_picker(self):
        session = marathon.start(self.user, 100)
        response = self.client.post(reverse("finish_test", args=[session.id]), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["restart_url"], reverse("marathon"))
        self.assertEqual(len(response.context["cells"]), 100)


class MarathonMixTests(TestCase):
    TESTS, PER_TEST = 10, 20

    @classmethod
    def setUpTestData(cls):
        kind = TestType.objects.create(nomi="t", vaqt_daqiqa=20, savollar_soni=20)
        cls.tests = [TestCategory.objects.create(nomi=f"Bilet {i}", aktiv=True) for i in range(cls.TESTS)]
        for test in cls.tests:
            for i in range(cls.PER_TEST):
                Question.objects.create(test_turi=kind, kategoriya=test, matn_uzb=f"{test.nomi}-{i}", matn_uz_kr="q", matn_rus="q")

    def share(self, ids):
        counts = {}
        for test_id in Question.objects.filter(id__in=ids).values_list("kategoriya_id", flat=True):
            counts[test_id] = counts.get(test_id, 0) + 1
        return counts

    def test_every_test_contributes_evenly(self):
        for _ in range(5):
            counts = self.share(marathon.pick_question_ids(100))
            self.assertEqual(set(counts), {t.pk for t in self.tests})
            self.assertEqual(set(counts.values()), {10})

    def test_remainder_spreads_over_tests(self):
        counts = self.share(marathon.pick_question_ids(105))
        self.assertEqual(sorted(set(counts.values())), [10, 11])
        self.assertEqual(sum(counts.values()), 105)

    def test_a_small_test_hands_its_share_to_the_others(self):
        Question.objects.filter(kategoriya=self.tests[0]).exclude(
            id__in=Question.objects.filter(kategoriya=self.tests[0]).values_list("id", flat=True)[:2]
        ).delete()
        ids = marathon.pick_question_ids(100)
        counts = self.share(ids)
        self.assertEqual(len(ids), 100)
        self.assertEqual(counts[self.tests[0].pk], 2)

    def test_questions_are_not_grouped_by_test(self):
        ids = marathon.pick_question_ids(100)
        owner = dict(Question.objects.filter(id__in=ids).values_list("id", "kategoriya_id"))
        runs = sum(1 for a, b in zip(ids, ids[1:]) if owner[a] != owner[b])
        self.assertGreater(runs, 60)  # grouped by test would give only 9 changes
        self.assertEqual(len(set(ids)), 100)

    def test_asking_for_more_than_exists_returns_everything(self):
        self.assertEqual(len(marathon.pick_question_ids(1000)), self.TESTS * self.PER_TEST)
