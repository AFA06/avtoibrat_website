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
    """POOL = 120 questions: size 50 makes sections of 50, 50 and 20."""

    def test_sizes_start_at_50_and_include_all_questions(self):
        self.assertEqual(marathon.SIZES, (50, 300, 500, 700, marathon.ALL))

    def test_duration_label(self):
        self.assertEqual(marathon.duration_label(100), "1 soat 40 daqiqa")
        self.assertEqual(marathon.duration_label(300), "5 soat")
        self.assertEqual(marathon.duration_label(45), "45 daqiqa")

    def test_sizes_above_the_question_bank_are_disabled(self):
        options = {o["size"]: (o["enabled"], o["sections"]) for o in marathon.size_options(self.POOL)}
        self.assertEqual(options[50], (True, 3))
        self.assertEqual(options[300], (False, 1))
        self.assertEqual(options[marathon.ALL], (True, 1))

    def test_pool_ignores_inactive_categories(self):
        self.assertEqual(marathon.question_pool().count(), self.POOL)

    def test_sections_keep_the_order_questions_were_added_in(self):
        ids = [q.id for q in self.questions]
        self.assertEqual(marathon.section_ids(50, 1), ids[:50])
        self.assertEqual(marathon.section_ids(50, 2), ids[50:100])
        self.assertEqual(marathon.section_ids(50, 3), ids[100:])
        self.assertEqual(marathon.section_ids(50, 4), [])
        self.assertEqual(marathon.section_ids(marathon.ALL, 1), ids)

    def test_start_is_not_random(self):
        first = marathon.start(self.user, 50, 2)
        second = marathon.start(self.user, 50, 2)
        self.assertEqual(first.question_order, second.question_order)
        self.assertEqual(first.question_order, [q.id for q in self.questions[50:100]])

    def test_new_questions_land_in_the_last_section(self):
        new = Question.objects.create(test_turi=self.questions[0].test_turi, kategoriya=self.category,
                                      matn_uzb="new", matn_uz_kr="q", matn_rus="q")
        self.assertEqual(marathon.section_ids(50, 3)[-1], new.id)

    def test_start_records_the_section_and_its_time_budget(self):
        session = marathon.start(self.user, 50, 3)
        self.assertEqual((session.marathon_size, session.marathon_section), (50, 3))
        self.assertEqual(len(session.question_order), 20)
        self.assertEqual(session.time_limit_seconds, 20 * 60)
        self.assertEqual((session.source, session.test_kind), ("marafon", "shablon"))

    def test_start_rejects_unknown_sizes_and_sections(self):
        for size, number in ((100, 1), (50, 0), (50, 4), (300, 1)):
            with self.assertRaises(ValueError):
                marathon.start(self.user, size, number)
        self.assertFalse(TestSession.objects.exists())

    def test_starting_again_finishes_the_previous_marathon(self):
        first = marathon.start(self.user, 50, 1)
        second = marathon.start(self.user, 50, 2)
        first.refresh_from_db()
        self.assertIsNotNone(first.finished_at)
        self.assertEqual(marathon.active_session(self.user), second)

    def test_expired_marathon_is_not_resumable(self):
        session = marathon.start(self.user, 50, 1)
        TestSession.objects.filter(pk=session.pk).update(started_at=timezone.now() - timedelta(minutes=51))
        self.assertIsNone(marathon.active_session(self.user))

    def test_section_progress_comes_from_the_latest_attempt(self):
        old = marathon.start(self.user, 50, 1)
        UserAnswer.objects.create(session=old, question_id=old.question_order[0], is_correct=False)
        latest = marathon.start(self.user, 50, 1)
        for qid in latest.question_order[:10]:
            UserAnswer.objects.create(session=latest, question_id=qid, is_correct=True)
        rows = marathon.sections(self.user, 50)
        self.assertEqual([r["total"] for r in rows], [50, 50, 20])
        self.assertEqual((rows[0]["state"], rows[0]["answered"], rows[0]["correct"], rows[0]["percent"]), ("active", 10, 10, 20))
        self.assertEqual(rows[1]["state"], "new")
        TestSession.objects.filter(pk=latest.pk).update(finished_at=timezone.now())
        self.assertEqual(marathon.sections(self.user, 50)[0]["state"], "done")


class MarathonViewTests(MarathonFixture):
    def test_page_lists_sizes_and_shows_resume_card(self):
        response = self.client.get(reverse("marathon"))
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["active"])
        self.assertContains(response, reverse("marathon_sections", args=[50]))
        session = marathon.start(self.user, 50, 1)
        UserAnswer.objects.create(session=session, question_id=session.question_order[0], is_correct=True)
        response = self.client.get(reverse("marathon"))
        self.assertEqual((response.context["active"], response.context["active_answered"]), (session, 1))

    def test_sections_page_lists_every_section(self):
        response = self.client.get(reverse("marathon_sections", args=[50]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual([s["number"] for s in response.context["sections"]], [1, 2, 3])
        self.assertContains(response, "101–120")
        self.assertEqual(self.client.get(reverse("marathon_sections", args=[100])).status_code, 404)

    def test_all_questions_start_straight_away_without_sections(self):
        self.assertRedirects(self.client.get(reverse("marathon_sections", args=[marathon.ALL])), reverse("marathon"))
        response = self.client.post(reverse("start_marathon"), {"size": "0", "section": "1"})
        session = TestSession.objects.get()
        self.assertRedirects(response, reverse("test_page", args=[session.id]))
        self.assertEqual(len(session.question_order), self.POOL)
        # While it runs, the card continues it instead of starting over.
        self.assertEqual(self.client.get(reverse("marathon")).context["all_active"], session)
        finished = self.client.post(reverse("finish_test", args=[session.id]), follow=True)
        self.assertEqual(finished.context["restart_url"], reverse("marathon"))

    def test_start_redirects_into_the_exam(self):
        response = self.client.post(reverse("start_marathon"), {"size": "50", "section": "2"})
        session = TestSession.objects.get()
        self.assertRedirects(response, reverse("test_page", args=[session.id]))
        self.assertEqual(session.marathon_section, 2)

    def test_start_with_a_missing_section_shows_an_error(self):
        response = self.client.post(reverse("start_marathon"), {"size": "50", "section": "9"}, follow=True)
        self.assertRedirects(response, reverse("marathon"))
        self.assertFalse(TestSession.objects.exists())

    def test_start_requires_post_and_login(self):
        self.assertEqual(self.client.get(reverse("start_marathon")).status_code, 405)
        self.client.logout()
        self.assertEqual(self.client.post(reverse("start_marathon"), {"size": "50", "section": "1"}).status_code, 302)

    def test_exam_page_uses_the_marathon_time_budget(self):
        session = marathon.start(self.user, 50, 1)
        response = self.client.get(reverse("test_page", args=[session.id]))
        self.assertEqual(response.status_code, 200)
        self.assertGreater(response.context["remaining_seconds"], 49 * 60)
        self.assertEqual(len(response.context["questions_data"]), 50)

    def test_answers_are_accepted_beyond_the_category_time(self):
        session = marathon.start(self.user, 50, 1)
        TestSession.objects.filter(pk=session.pk).update(started_at=timezone.now() - timedelta(minutes=30))
        question = Question.objects.get(pk=session.question_order[0])
        answer = question.javoblar.first()
        response = self.client.post(reverse("submit_answer"), {
            "session_id": session.id, "question_id": question.id, "answer_id": answer.id,
        })
        self.assertEqual(response.status_code, 200)

    def test_result_page_restart_leads_back_to_the_sections(self):
        session = marathon.start(self.user, 50, 1)
        response = self.client.post(reverse("finish_test", args=[session.id]), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["restart_url"], reverse("marathon_sections", args=[50]))
        self.assertEqual(len(response.context["cells"]), 50)


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
