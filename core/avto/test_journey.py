from django.test import TestCase
from django.urls import reverse
from django.utils import timezone, translation

from . import journey
from .models import Answer, Question, TestCategory, TestSession, TestType, User, UserAnswer


class JourneyTests(TestCase):
    """8 bilets of 4 questions: two bilets per season."""

    def setUp(self):
        translation.activate("uz")
        self.addCleanup(translation.deactivate)
        self.user = User.objects.create_user(username="talaba", password="x", unlimited=True, phone="9999999")
        self.client.force_login(self.user)
        test_type = TestType.objects.create(nomi="Umumiy", vaqt_daqiqa=25, savollar_soni=4)
        self.bilets = []
        for b in range(8):
            bilet = TestCategory.objects.create(nomi=f"Bilet {b + 1}", tartib=b + 1, show_in_shablon=True, question_count=4)
            for i in range(4):
                question = Question.objects.create(
                    test_turi=test_type, kategoriya=bilet, matn_uzb=f"S{b}-{i}", matn_uz_kr="С", matn_rus="В",
                )
                Answer.objects.create(question=question, matn_uzb="Ha", togri=True)
                Answer.objects.create(question=question, matn_uzb="Yo‘q", togri=False)
            self.bilets.append(bilet)

    def run_bilet(self, bilet, correct, source="shablon"):
        questions = list(Question.objects.filter(kategoriya=bilet).order_by("id"))
        return self._session(bilet, questions, correct, "shablon", source)

    def run_real(self, mistakes):
        questions = list(Question.objects.order_by("id")[:20])
        return self._session(questions[0].kategoriya, questions, 20 - mistakes, "real", "shablon")

    def _session(self, category, questions, correct, kind, source):
        now = timezone.now()
        session = TestSession.objects.create(
            user=self.user, category=category, test_kind=kind, source=source,
            started_at=now, finished_at=now, question_order=[q.id for q in questions],
        )
        for i, question in enumerate(questions):
            answer = question.javoblar.get(togri=i < correct)
            UserAnswer.objects.create(session=session, question=question, selected_answer=answer, is_correct=answer.togri)
        return session

    def clear_all(self):
        for bilet in self.bilets:
            self.run_bilet(bilet, 4)

    def test_stars_follow_the_real_exam_mistake_rule(self):
        self.assertEqual([journey.stars_for(c, 20) for c in (20, 19, 18, 17)], [3, 2, 1, 0])

    def test_best_run_counts_and_too_many_mistakes_do_not_clear(self):
        self.run_bilet(self.bilets[0], 1)
        stage = journey.build(self.user)["seasons"][0]["stages"][0]
        self.assertEqual((stage["cleared"], stage["stars"], stage["best"], stage["attempts"]), (False, 0, 25, 1))
        self.run_bilet(self.bilets[0], 3)
        self.run_bilet(self.bilets[0], 2)
        stage = journey.build(self.user)["seasons"][0]["stages"][0]
        self.assertEqual((stage["cleared"], stage["stars"], stage["best"], stage["attempts"]), (True, 2, 75, 3))

    def test_unfinished_short_and_topic_runs_do_not_count(self):
        session = self.run_bilet(self.bilets[0], 4)
        session.finished_at = None
        session.save()
        short = self.run_bilet(self.bilets[1], 4)
        short.question_order = short.question_order[:2]
        short.save()
        self.run_bilet(self.bilets[2], 4, source="mavzu")
        data = journey.build(self.user)
        self.assertEqual(data["stages_cleared"], 0)

    def test_seasons_open_one_after_another_and_earlier_clears_still_count(self):
        self.run_bilet(self.bilets[2], 4)  # summer, solved before spring is done
        data = journey.build(self.user)
        spring, summer = data["seasons"][:2]
        self.assertEqual((spring["unlocked"], summer["unlocked"], summer["cleared"]), (True, False, 1))
        self.assertEqual(spring["current_id"], self.bilets[0].id)
        self.assertEqual(data["next_stage"]["id"], self.bilets[0].id)

        self.run_bilet(self.bilets[0], 4)
        self.run_bilet(self.bilets[1], 3, source="ohshash")
        data = journey.build(self.user)
        spring, summer = data["seasons"][:2]
        self.assertTrue(spring["done"] and summer["unlocked"])
        self.assertEqual((data["active_key"], summer["current_id"]), ("summer", self.bilets[3].id))

    def test_readiness_mixes_mastery_and_real_exam_form(self):
        self.assertEqual(journey.build(self.user)["readiness"], 0)
        self.clear_all()
        data = journey.build(self.user)
        self.assertEqual((data["mastery"], data["readiness"], data["active_key"]), (100, 75, "final"))
        self.run_real(mistakes=3)  # failed
        self.run_real(mistakes=2)  # passed
        data = journey.build(self.user)
        self.assertEqual((data["form_passes"], data["readiness"], data["final"]["streak"]), (1, 83, 1))
        self.assertFalse(data["final"]["certified"])

    def test_certificate_needs_every_season_and_two_passed_exams_in_a_row(self):
        self.run_real(0)
        self.run_real(1)
        self.assertFalse(journey.build(self.user)["final"]["certified"])
        self.clear_all()
        data = journey.build(self.user)
        self.assertTrue(data["final"]["certified"])
        self.assertEqual((data["readiness"], data["tier"]), (100, "ready"))
        self.run_real(5)  # a later failure does not take the certificate away
        self.assertTrue(journey.build(self.user)["final"]["certified"])

    def test_page_dashboard_and_result_link(self):
        session = self.run_bilet(self.bilets[0], 3)
        response = self.client.get(reverse("journey"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="jr-data"')
        self.assertContains(response, reverse("start_shablon_test", args=[self.bilets[1].id]))
        self.assertContains(self.client.get(reverse("dashboard")), reverse("journey"))
        result = self.client.get(reverse("test_result", args=[session.id]))
        self.assertContains(result, "★★")
        self.assertContains(result, reverse("journey"))

    def test_certificate_is_shown_once_earned(self):
        self.clear_all()
        self.run_real(0)
        self.run_real(0)
        response = self.client.get(reverse("journey"))
        self.assertContains(response, 'id="jr-cert"')
        self.assertContains(response, f"AI-{self.user.pk:05d}-08")
