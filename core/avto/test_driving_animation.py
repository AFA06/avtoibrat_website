from django.contrib.auth import get_user_model
from django.contrib.staticfiles import finders
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .animation_scenarios import QUESTION_TEXT, SCENARIO_KEY, scenario_for
from .models import Answer, Question, TestCategory, TestSession, TestType


User = get_user_model()


class DrivingAnimationScenarioTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="animation-student", password="pass", unlimited=True)
        self.client.force_login(self.user)
        test_type = TestType.objects.create(nomi="Bilet", vaqt_daqiqa=25, savollar_soni=1)
        self.category = TestCategory.objects.create(
            nomi="Bilet 16",
            tartib=16,
            aktiv=True,
            show_in_shablon=True,
            show_in_real=True,
            question_count=1,
            duration_minutes=25,
        )
        self.question = Question.objects.create(
            test_turi=test_type,
            kategoriya=self.category,
            matn_uzb=QUESTION_TEXT,
            matn_uz_kr="Автомобиллар чорраҳани қуйидаги тартибда кесиб ўтадилар:",
            matn_rus="Автомобили проедут перекресток в следующем порядке:",
        )
        self.correct = Answer.objects.create(
            question=self.question,
            matn_uzb="To‘g‘ri tartib",
            matn_uz_kr="Тўғри тартиб",
            matn_rus="Верный порядок",
            togri=True,
        )
        self.wrong = Answer.objects.create(
            question=self.question,
            matn_uzb="Noto‘g‘ri tartib",
            matn_uz_kr="Нотўғри тартиб",
            matn_rus="Неверный порядок",
            togri=False,
        )

    def session(self, kind="shablon"):
        session = TestSession.objects.create(
            user=self.user,
            category=self.category,
            test_kind=kind,
            started_at=timezone.now(),
            question_order=[self.question.id],
        )
        session.questions.set([self.question])
        return session

    def submit(self, session, answer):
        return self.client.post(reverse("submit_answer"), {
            "session_id": session.id,
            "question_id": self.question.id,
            "answer_id": answer.id,
        })

    def test_only_the_verified_question_matches(self):
        self.assertEqual(scenario_for(self.question)["id"], SCENARIO_KEY)
        self.question.matn_uzb = "Boshqa savol"
        self.assertIsNone(scenario_for(self.question))
        self.question.matn_uzb = QUESTION_TEXT
        self.category.tartib = 15
        self.assertIsNone(scenario_for(self.question))

    def test_sequence_is_not_sent_before_answer_submission(self):
        response = self.client.get(reverse("test_page", args=[self.session().id]))
        html = response.content.decode()
        self.assertNotIn(SCENARIO_KEY, html)
        self.assertNotIn("burilishni tugatadi", html)

    def test_correct_and_incorrect_practice_answers_receive_the_same_scenario(self):
        correct_data = self.submit(self.session(), self.correct).json()
        wrong_data = self.submit(self.session(), self.wrong).json()
        self.assertTrue(correct_data["is_correct"])
        self.assertFalse(wrong_data["is_correct"])
        self.assertEqual(correct_data["animation_scenario"], wrong_data["animation_scenario"])
        self.assertEqual(correct_data["animation_scenario"]["id"], SCENARIO_KEY)

    def test_real_exam_keeps_the_animation_hidden(self):
        data = self.submit(self.session("real"), self.correct).json()
        self.assertNotIn("animation_scenario", data)

    def test_timed_marathon_keeps_the_animation_hidden(self):
        session = self.session()
        session.source = "marafon"
        session.save(update_fields=["source"])
        data = self.submit(session, self.correct).json()
        self.assertNotIn("animation_scenario", data)

    def test_answered_practice_question_restores_the_scenario(self):
        session = self.session()
        self.submit(session, self.correct)
        response = self.client.get(reverse("test_page", args=[session.id]))
        self.assertEqual(response.context["answered_data"][self.question.id]["animation_scenario"]["id"], SCENARIO_KEY)

    def test_animation_assets_are_collectable(self):
        self.assertIsNotNone(finders.find("exam/driving-animation.js"))
        self.assertIsNotNone(finders.find("exam/driving-animation.css"))
        self.assertIsNotNone(finders.find("exam/animation/bilet-16-question-14-scene.svg"))
