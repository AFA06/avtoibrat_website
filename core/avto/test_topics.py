import json
import tempfile
from io import StringIO

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone, translation

from . import topic_tests
from .management.commands.import_bilets import DATA_FILE, TOPICS_FILE
from .models import Answer, Question, TestCategory, TestSession, TestType, Topic, TopicGroup, User, UserAnswer


class TopicDataTests(TestCase):
    """The shipped files: every bilet question names a topic that exists."""

    def test_every_question_has_a_known_topic(self):
        slugs = {t["slug"] for g in json.loads(TOPICS_FILE.read_text(encoding="utf-8")) for t in g["topics"]}
        for bilet in json.loads(DATA_FILE.read_text(encoding="utf-8")):
            for number, item in enumerate(bilet["questions"], start=1):
                self.assertIn(item.get("topic"), slugs, f"Bilet {bilet['bilet']}, question {number}")

    def test_topics_have_names_in_three_languages(self):
        for group in json.loads(TOPICS_FILE.read_text(encoding="utf-8")):
            for item in [group, *group["topics"]]:
                self.assertTrue(all(item[lang].strip() for lang in ("uz", "kr", "ru")))


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class ImportTopicsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("import_bilets", stdout=StringIO())

    def test_every_question_is_sorted_into_a_topic(self):
        self.assertFalse(Question.objects.filter(mavzu__isnull=True).exists())
        self.assertEqual(TopicGroup.objects.count(), 8)

    def test_a_teacher_change_survives_a_rerun_and_force_resets_it(self):
        question = Question.objects.order_by("id").first()
        original = question.mavzu
        other = Topic.objects.exclude(pk=original.pk).first()
        Question.objects.filter(pk=question.pk).update(mavzu=other)

        call_command("import_bilets", stdout=StringIO())
        question.refresh_from_db()
        self.assertEqual(question.mavzu, other)

        call_command("import_bilets", "--force", stdout=StringIO())
        question.refresh_from_db()
        self.assertEqual(question.mavzu, original)


class TopicTestsTests(TestCase):
    def setUp(self):
        translation.activate("uz")
        self.addCleanup(translation.deactivate)
        self.user = User.objects.create_user(username="talaba", password="x", unlimited=True, phone="9999999")
        self.client.force_login(self.user)
        self.test_type = TestType.objects.create(nomi="Umumiy", vaqt_daqiqa=25, savollar_soni=20)
        self.bilet = TestCategory.objects.create(nomi="Bilet 1", show_in_shablon=True)
        group = TopicGroup.objects.create(slug="manyovrlar", nomi_uzb="Asosiy manyovrlar", nomi_rus="Основные манёвры")
        self.topic = Topic.objects.create(group=group, slug="quvib-otish", nomi_uzb="Quvib o‘tish", nomi_rus="Обгон")
        self.empty_topic = Topic.objects.create(group=group, slug="tezlik", nomi_uzb="Harakatlanish tezligi")
        self.questions = [self.make_question(i) for i in range(25)]

    def make_question(self, i, bilet=None):
        question = Question.objects.create(
            test_turi=self.test_type, kategoriya=bilet or self.bilet, mavzu=self.topic,
            matn_uzb=f"Savol {i}", matn_uz_kr=f"Савол {i}", matn_rus=f"Вопрос {i}",
        )
        Answer.objects.create(question=question, matn_uzb="Ha", matn_uz_kr="Ҳа", matn_rus="Да", togri=True)
        Answer.objects.create(question=question, matn_uzb="Yo‘q", matn_uz_kr="Йўқ", matn_rus="Нет", togri=False)
        return question

    def answer(self, question, correct):
        session = TestSession.objects.create(
            user=self.user, category=self.bilet, test_kind="shablon", started_at=timezone.now()
        )
        UserAnswer.objects.create(
            session=session, question=question, is_correct=correct,
            selected_answer=question.javoblar.get(togri=correct),
        )

    def start(self, mode):
        response = self.client.get(reverse("start_mavzu_test", args=[self.topic.id]) + f"?mode={mode}")
        return response, TestSession.objects.filter(source="mavzu").order_by("-id").first()

    def test_page_lists_topics_with_questions_only(self):
        response = self.client.get(reverse("mavzulashtirilgan"))
        self.assertContains(response, "Quvib o‘tish")
        self.assertContains(response, "Asosiy manyovrlar")
        self.assertNotContains(response, "Harakatlanish tezligi")
        self.assertContains(response, reverse("start_mavzu_test", args=[self.topic.id]))

    def test_page_shows_topic_names_in_the_site_language(self):
        response = self.client.get("/ru/mavzulashtirilgan/")
        self.assertContains(response, "Обгон")

    def test_progress_counts_the_latest_answer_of_each_question(self):
        self.answer(self.questions[0], correct=False)
        self.answer(self.questions[0], correct=True)
        self.answer(self.questions[1], correct=True)
        self.answer(self.questions[2], correct=False)
        [group] = topic_tests.page_groups(self.user)
        [topic] = group["topics"]
        self.assertEqual((topic["total"], topic["learned"], topic["mistakes"], topic["percent"]), (25, 2, 1, 8))

    def test_quick_test_takes_twenty_random_questions_of_the_topic(self):
        response, session = self.start("quick")
        self.assertRedirects(response, reverse("test_page", args=[session.id]), fetch_redirect_response=False)
        self.assertEqual(len(session.question_order), 20)
        self.assertEqual(set(session.question_order) <= {q.id for q in self.questions}, True)
        self.assertEqual((session.topic, session.test_kind, session.duration_minutes), (self.topic, "shablon", 20))

    def test_all_mode_takes_every_question(self):
        _, session = self.start("all")
        self.assertEqual(sorted(session.question_order), sorted(q.id for q in self.questions))
        self.assertEqual(session.duration_minutes, 25)

    def test_mistakes_mode_takes_only_questions_last_answered_wrong(self):
        self.answer(self.questions[0], correct=False)
        self.answer(self.questions[1], correct=False)
        self.answer(self.questions[1], correct=True)
        _, session = self.start("mistakes")
        self.assertEqual(session.question_order, [self.questions[0].id])

    def test_mistakes_mode_without_mistakes_goes_back_to_the_list(self):
        response, session = self.start("mistakes")
        self.assertRedirects(response, reverse("mavzulashtirilgan"), fetch_redirect_response=False)
        self.assertIsNone(session)

    def test_questions_of_a_hidden_bilet_are_left_out(self):
        hidden = TestCategory.objects.create(nomi="Bilet 2", aktiv=False)
        extra = self.make_question(99, bilet=hidden)
        _, session = self.start("all")
        self.assertNotIn(extra.id, session.question_order)

    def test_result_page_names_the_topic_and_restarts_it(self):
        _, session = self.start("quick")
        self.client.post(reverse("finish_test", args=[session.id]))
        response = self.client.get(reverse("test_result", args=[session.id]))
        self.assertContains(response, "Quvib o‘tish")
        self.assertContains(response, reverse("start_mavzu_test", args=[self.topic.id]) + "?mode=quick")
        self.assertContains(response, f'href="{reverse("mavzulashtirilgan")}"')
