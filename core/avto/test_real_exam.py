from django.test import TestCase
from django.urls import reverse
from django.utils import translation

from . import real_exam
from .models import Answer, Question, TestCategory, TestSession, TestType, Topic, TopicGroup, User


class RealExamTests(TestCase):
    def setUp(self):
        translation.activate("uz")
        self.addCleanup(translation.deactivate)
        self.user = User.objects.create_user(username="talaba", password="x", unlimited=True, phone="9999999")
        self.client.force_login(self.user)
        test_type = TestType.objects.create(nomi="Umumiy", vaqt_daqiqa=25, savollar_soni=20)
        group = TopicGroup.objects.create(slug="g", nomi_uzb="Bo‘lim")
        self.topics = [Topic.objects.create(group=group, slug=f"t{i}", nomi_uzb=f"Mavzu {i}") for i in range(5)]
        bilet = TestCategory.objects.create(nomi="Bilet 1")
        for i in range(60):
            question = Question.objects.create(
                test_turi=test_type, kategoriya=bilet, mavzu=self.topics[i % 5],
                matn_uzb=f"Savol {i}", matn_uz_kr=f"Савол {i}", matn_rus=f"Вопрос {i}",
            )
            Answer.objects.create(question=question, matn_uzb="Ha", matn_uz_kr="Ҳа", matn_rus="Да", togri=True)
            Answer.objects.create(question=question, matn_uzb="Yo‘q", matn_uz_kr="Йўқ", matn_rus="Нет", togri=False)

    def start(self, size):
        response = self.client.get(reverse("start_real_exam", args=[size]))
        return response, TestSession.objects.filter(test_kind="real").order_by("-id").first()

    def test_page_offers_twenty_and_fifty_questions(self):
        response = self.client.get(reverse("real_imtihon"))
        self.assertContains(response, reverse("start_real_exam", args=[20]))
        self.assertContains(response, reverse("start_real_exam", args=[50]))
        self.assertNotContains(response, "Bilet 1")

    def test_exam_draws_random_questions_evenly_from_every_topic(self):
        _, session = self.start(20)
        self.assertEqual(len(set(session.question_order)), 20)
        topics = list(Question.objects.filter(id__in=session.question_order).values_list("mavzu_id", flat=True))
        self.assertEqual(sorted(topics.count(t.id) for t in self.topics), [4] * 5)
        self.assertEqual((session.duration_minutes, session.source), (20, "shablon"))

    def test_each_exam_gets_new_questions(self):
        orders = {tuple(self.start(50)[1].question_order) for _ in range(3)}
        self.assertGreater(len(orders), 1)

    def test_unknown_size_or_too_few_questions_go_back_to_the_page(self):
        for size in (30, 100):
            response, session = self.start(size)
            self.assertRedirects(response, reverse("real_imtihon"), fetch_redirect_response=False)
            self.assertIsNone(session)
        Question.objects.filter(id__in=list(Question.objects.values_list("id", flat=True)[:20])).delete()
        response, session = self.start(50)
        self.assertIsNone(session)

    def test_allowed_mistakes_grow_with_the_exam(self):
        self.assertEqual((real_exam.max_mistakes(20), real_exam.max_mistakes(50)), (3, 5))
        self.assertTrue(real_exam.passed(20, 2, 20))
        self.assertFalse(real_exam.passed(20, 3, 20))
        self.assertTrue(real_exam.passed(50, 4, 50))
        self.assertFalse(real_exam.passed(50, 5, 50))
        self.assertFalse(real_exam.passed(50, 4, 49))

    def answer_wrong(self, session, question_id):
        wrong = Answer.objects.get(question_id=question_id, togri=False)
        return self.client.post(reverse("submit_answer"), {
            "session_id": session.id, "question_id": question_id, "answer_id": wrong.id,
        }).json()

    def test_twenty_question_exam_ends_at_the_third_mistake(self):
        _, session = self.start(20)
        results = [self.answer_wrong(session, qid)["exam_failed"] for qid in session.question_order[:3]]
        self.assertEqual(results, [False, False, True])

    def test_fifty_question_exam_ends_at_the_fifth_mistake(self):
        _, session = self.start(50)
        results = [self.answer_wrong(session, qid)["exam_failed"] for qid in session.question_order[:5]]
        self.assertEqual(results, [False] * 4 + [True])

    def test_page_states_the_allowed_mistakes(self):
        response = self.client.get(reverse("real_imtihon"))
        self.assertContains(response, "2 tagacha xatoga ruxsat")
        self.assertContains(response, "4 tagacha xatoga ruxsat")

    def test_result_page_names_the_exam_and_restarts_the_same_size(self):
        _, session = self.start(50)
        self.client.post(reverse("finish_test", args=[session.id]))
        response = self.client.get(reverse("test_result", args=[session.id]))
        self.assertContains(response, "Real imtihon · 50 ta savol")
        self.assertContains(response, reverse("start_real_exam", args=[50]))
        self.assertContains(response, f'href="{reverse("real_imtihon")}"')

    def test_finished_exams_are_listed_as_passed_or_failed(self):
        _, session = self.start(20)
        for qid in session.question_order[:3]:
            self.answer_wrong(session, qid)
        response = self.client.get(reverse("real_imtihon"))
        self.assertContains(response, "Topshirilmadi")
