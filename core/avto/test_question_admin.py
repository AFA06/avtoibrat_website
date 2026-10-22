from django.test import TestCase
from django.urls import reverse

from . import topic_tests
from .models import Answer, Question, TestCategory, TestType, Topic, TopicGroup, User


class QuestionAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.teacher = User.objects.create_user(username="t", password="x", is_staff=True, is_superuser=True)
        cls.student = User.objects.create_user(username="s", password="x", unlimited=True)
        cls.bilet = TestCategory.objects.create(nomi="Bilet 3", tartib=3)
        cls.other_bilet = TestCategory.objects.create(nomi="Bilet 4", tartib=4)
        group = TopicGroup.objects.create(slug="g", nomi_uzb="Guruh")
        cls.topic = Topic.objects.create(group=group, slug="a", nomi_uzb="Mavzu A")
        cls.second = Topic.objects.create(group=group, slug="b", nomi_uzb="Mavzu B", tartib=2)
        cls.kind = TestType.objects.create(nomi="Bilet", vaqt_daqiqa=25, savollar_soni=20)
        cls.question = Question.objects.create(
            test_turi=cls.kind, kategoriya=cls.bilet, mavzu=cls.topic,
            matn_uzb="Birinchi savol", matn_uz_kr="Биринчи савол", matn_rus="Первый вопрос",
        )
        cls.answers = [
            Answer.objects.create(question=cls.question, matn_uzb=f"A{i}", matn_uz_kr=f"К{i}", togri=i == 1) for i in (1, 2)
        ] + [Answer.objects.create(question=cls.question, matn_rus=f"Р{i}", togri=i == 2) for i in (1, 2)]

    def setUp(self):
        self.client.force_login(self.teacher)

    def posted(self, **over):
        data = {
            "kategoriya": self.bilet.pk, "mavzu": self.topic.pk,
            "matn_uzb": "Yangi savol", "matn_uz_kr": "Янги савол", "matn_rus": "Новый вопрос",
            "uz_id": ["", "", "", ""], "uz_uz": ["Bir", "Ikki", "", ""], "uz_kr": ["Бир", "Икки", "", ""], "uz_correct": "1",
            "ru_id": ["", "", "", ""], "ru_ru": ["Раз", "Два", "", ""], "ru_correct": "0",
        }
        data.update(over)
        return data

    def test_students_cannot_open_it(self):
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(reverse("questions:list")).status_code, 302)

    def test_search_by_text_bilet_topic_and_number(self):
        second = Question.objects.create(
            test_turi=self.kind, kategoriya=self.bilet, mavzu=self.second, matn_uzb="Ikkinchi", matn_uz_kr="x", matn_rus="y",
        )
        second.extra_topics.add(self.topic)
        url = reverse("questions:list")
        ids = lambda **q: {x.pk for x in self.client.get(url, q).context["page"]}
        self.assertEqual(ids(q="Ikkinchi"), {second.pk})
        self.assertEqual(ids(q="3-2"), {second.pk})
        self.assertEqual(ids(q="3-1"), {self.question.pk})
        self.assertEqual(ids(topic=self.topic.pk), {self.question.pk, second.pk})  # extra topic counts
        self.assertEqual(ids(topic=self.second.pk), {second.pk})
        self.assertEqual(ids(bilet=self.other_bilet.pk), set())

    def test_adding_a_question_with_two_topics(self):
        response = self.client.post(reverse("questions:create"), self.posted(extra_topics=[self.second.pk]))
        self.assertRedirects(response, reverse("questions:list"))
        question = Question.objects.get(matn_uzb="Yangi savol")
        self.assertEqual(question.mavzu, self.topic)
        self.assertEqual(list(question.extra_topics.all()), [self.second])
        rows = list(question.javoblar.values_list("matn_uzb", "matn_uz_kr", "matn_rus", "togri"))
        self.assertEqual(rows, [
            ("Bir", "Бир", "", False), ("Ikki", "Икки", "", True), ("", "", "Раз", True), ("", "", "Два", False),
        ])
        self.assertEqual([a.pk for a in question.answers_for("ru")], [a.pk for a in question.javoblar.all()[2:]])

    def test_the_topic_test_includes_questions_of_an_extra_topic(self):
        self.question.extra_topics.add(self.second)
        self.assertIn(self.question, topic_tests.question_pool(self.second))
        self.assertEqual(topic_tests.question_pool(self.second).count(), 1)

    def test_a_question_needs_a_topic_and_one_correct_answer(self):
        response = self.client.post(reverse("questions:create"), self.posted(mavzu="", uz_correct=""))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Question.objects.filter(matn_uzb="Yangi savol").exists())
        self.assertContains(response, "to‘g‘ri javobni bitta qilib belgilang")

    def test_editing_keeps_the_answer_rows_and_their_order(self):
        uz_ids = [str(self.answers[0].pk), str(self.answers[1].pk), "", ""]
        ru_ids = [str(self.answers[2].pk), str(self.answers[3].pk), "", ""]
        data = self.posted(
            matn_uzb="O‘zgargan", uz_id=uz_ids, uz_uz=["A1", "A2 yangi", "", ""], uz_kr=["К1", "К2", "", ""],
            ru_id=ru_ids, ru_ru=["Р1", "Р2", "", ""], ru_correct="1",
        )
        self.client.post(reverse("questions:edit", args=[self.question.pk]), data)
        self.question.refresh_from_db()
        self.assertEqual(self.question.matn_uzb, "O‘zgargan")
        self.assertEqual([a.pk for a in self.question.javoblar.all()], [a.pk for a in self.answers])
        self.answers[1].refresh_from_db()
        self.assertEqual(self.answers[1].matn_uzb, "A2 yangi")

    def test_the_form_lists_answers_in_stored_order(self):
        response = self.client.get(reverse("questions:edit", args=[self.question.pk]))
        self.assertEqual([r["uz"] for r in response.context["uz_rows"][:2]], ["A1", "A2"])
        self.assertEqual([r["ru"] for r in response.context["ru_rows"][:2]], ["Р1", "Р2"])

    def test_delete(self):
        self.client.post(reverse("questions:delete", args=[self.question.pk]))
        self.assertFalse(Question.objects.filter(pk=self.question.pk).exists())


class GuideInPanelTests(TestCase):
    def test_a_student_reads_the_guide_inside_the_panel(self):
        student = User.objects.create_user(username="s", password="x", unlimited=True)
        self.client.force_login(student)
        html = self.client.get(reverse("guide")).content.decode()
        self.assertIn('id="lg-back"', html)
        self.assertIn(reverse("real_imtihon"), html)  # the panel sidebar is there

    def test_visitors_get_the_public_page(self):
        html = self.client.get(reverse("guide")).content.decode()
        self.assertNotIn('id="lg-back"', html)
