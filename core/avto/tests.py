from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Answer, Question, TestCategory, TestSession, TestType, UserAnswer

User = get_user_model()


class ExamEngineTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="student", password="pass12345", unlimited=True)
        self.test_type = TestType.objects.create(nomi="Umumiy", vaqt_daqiqa=25, savollar_soni=3)
        self.category = TestCategory.objects.create(
            nomi="Test kategoriya",
            aktiv=True,
            show_in_real=True,
            question_count=3,
            duration_minutes=25,
        )

        self.questions = []
        for i in range(3):
            question = Question.objects.create(
                test_turi=self.test_type,
                kategoriya=self.category,
                matn_uzb=f"Savol {i}",
                matn_uz_kr=f"Савол {i}",
                matn_rus=f"Вопрос {i}",
            )
            Answer.objects.create(question=question, matn_uzb="To'g'ri", matn_uz_kr="Тўғри", matn_rus="Верно", togri=True)
            Answer.objects.create(question=question, matn_uzb="Xato", matn_uz_kr="Хато", matn_rus="Неверно", togri=False)
            self.questions.append(question)

        self.client.force_login(self.user)

    def _start_session(self):
        response = self.client.get(reverse("start_test", args=[self.category.id]))
        self.assertEqual(response.status_code, 302)
        session_id = int(response.url.rstrip("/").split("/")[-1])
        return TestSession.objects.get(id=session_id)

    def test_start_creates_session_with_fixed_question_order(self):
        session = self._start_session()
        self.assertEqual(len(session.question_order), self.category.question_count)
        self.assertEqual(
            set(session.question_order),
            set(session.questions.values_list("id", flat=True)),
        )
        self.assertIsNotNone(session.started_at)

    def test_exam_page_hides_correctness_before_submit(self):
        session = self._start_session()
        response = self.client.get(reverse("test_page", args=[session.id]))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode().lower()
        self.assertNotIn("togri", content)
        self.assertNotIn('"is_correct"', content)

    def test_submit_correct_and_wrong_answer(self):
        session = self._start_session()
        question = self.questions[0]
        correct = question.javoblar.get(togri=True)

        response = self.client.post(reverse("submit_answer"), {
            "session_id": session.id,
            "question_id": question.id,
            "answer_id": correct.id,
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["is_correct"])
        self.assertEqual(data["correct_answer_id"], correct.id)

        question2 = self.questions[1]
        wrong = question2.javoblar.get(togri=False)
        response = self.client.post(reverse("submit_answer"), {
            "session_id": session.id,
            "question_id": question2.id,
            "answer_id": wrong.id,
        })
        data = response.json()
        self.assertFalse(data["is_correct"])

    def test_submit_answer_rejects_duplicate(self):
        session = self._start_session()
        question = self.questions[0]
        answer = question.javoblar.first()

        self.client.post(reverse("submit_answer"), {
            "session_id": session.id, "question_id": question.id, "answer_id": answer.id,
        })
        response = self.client.post(reverse("submit_answer"), {
            "session_id": session.id, "question_id": question.id, "answer_id": answer.id,
        })
        self.assertEqual(response.status_code, 409)

    def test_submit_answer_rejects_question_not_in_session(self):
        session = self._start_session()
        other_type = TestType.objects.create(nomi="Boshqa", vaqt_daqiqa=10, savollar_soni=1)
        other_category = TestCategory.objects.create(nomi="Boshqa kategoriya", question_count=1)
        outside_question = Question.objects.create(
            test_turi=other_type,
            kategoriya=other_category,
            matn_uzb="Tashqi savol",
            matn_uz_kr="Ташқи",
            matn_rus="Внешний",
        )
        outside_answer = Answer.objects.create(question=outside_question, matn_uzb="X", matn_uz_kr="X", matn_rus="X", togri=True)

        response = self.client.post(reverse("submit_answer"), {
            "session_id": session.id,
            "question_id": outside_question.id,
            "answer_id": outside_answer.id,
        })
        self.assertEqual(response.status_code, 400)

    def test_submit_answer_rejects_after_finish(self):
        session = self._start_session()
        self.client.post(reverse("finish_test", args=[session.id]))

        question = self.questions[0]
        answer = question.javoblar.first()
        response = self.client.post(reverse("submit_answer"), {
            "session_id": session.id, "question_id": question.id, "answer_id": answer.id,
        })
        self.assertEqual(response.status_code, 409)

    def test_finish_test_requires_post(self):
        session = self._start_session()
        response = self.client.get(reverse("finish_test", args=[session.id]))
        self.assertEqual(response.status_code, 405)

    def test_finish_test_sets_finished_at_only_once(self):
        session = self._start_session()
        self.client.post(reverse("finish_test", args=[session.id]))
        session.refresh_from_db()
        first_finished_at = session.finished_at
        self.assertIsNotNone(first_finished_at)

        self.client.post(reverse("finish_test", args=[session.id]))
        session.refresh_from_db()
        self.assertEqual(session.finished_at, first_finished_at)

    def test_result_page_counts(self):
        session = self._start_session()
        correct = self.questions[0].javoblar.get(togri=True)
        wrong = self.questions[1].javoblar.get(togri=False)

        self.client.post(reverse("submit_answer"), {
            "session_id": session.id, "question_id": self.questions[0].id, "answer_id": correct.id,
        })
        self.client.post(reverse("submit_answer"), {
            "session_id": session.id, "question_id": self.questions[1].id, "answer_id": wrong.id,
        })
        self.client.post(reverse("finish_test", args=[session.id]))

        response = self.client.get(reverse("test_result", args=[session.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["correct"], 1)
        self.assertEqual(response.context["wrong"], 1)
        self.assertEqual(response.context["empty"], 1)

    def test_exam_page_redirects_to_result_when_finished(self):
        session = self._start_session()
        session.finished_at = timezone.now()
        session.save(update_fields=["finished_at"])

        response = self.client.get(reverse("test_page", args=[session.id]))
        self.assertRedirects(response, reverse("test_result", args=[session.id]))
