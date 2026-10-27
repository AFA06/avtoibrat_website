import json
import tempfile
from io import StringIO

from django.contrib.staticfiles import finders
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .management.commands.import_bilets import DATA_FILE, IMAGE_DIR
from .models import Answer, Question, TestCategory, TestSession, TestType, User

MEDIA = tempfile.mkdtemp()


class BiletDataTests(TestCase):
    """The shipped data file itself: 60 bilets, 20 questions, one correct answer per language."""

    def test_every_bilet_is_complete(self):
        bilets = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        self.assertEqual([b["bilet"] for b in bilets], list(range(1, 61)))
        for bilet in bilets:
            self.assertEqual(len(bilet["questions"]), 20)
            for item in bilet["questions"]:
                self.assertTrue(all(item[lang].strip() for lang in ("uz", "kr", "ru")))
                self.assertEqual(sum(a["correct"] for a in item["answers"]), 1)
                self.assertEqual(sum(a["correct"] for a in item["answers_ru"]), 1)

    def test_each_language_part_is_written_in_its_own_script(self):
        bilets = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        for bilet in bilets:
            for item in bilet["questions"]:
                self.assertNotRegex(item["uz"], "[а-яё]")
                self.assertNotRegex(item["kr"], "[a-z]{4,}")
                self.assertNotRegex(item["ru"], "[ўқғҳ]|[a-z]{4,}")
                for answer in item["answers_ru"]:
                    self.assertNotRegex(answer["ru"], "[ўқғҳ]|[a-z]{4,}")


@override_settings(MEDIA_ROOT=MEDIA)
class ImportBiletsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("import_bilets", stdout=StringIO())

    def test_creates_sixty_bilets_of_twenty_questions(self):
        self.assertEqual(TestCategory.objects.count(), 60)
        self.assertEqual(Question.objects.count(), 1200)
        first = TestCategory.objects.get(nomi="Bilet 1")
        self.assertEqual((first.tartib, first.question_count, first.question_set.count()), (1, 20, 20))
        self.assertTrue(first.show_in_shablon and first.show_in_real)

    def test_every_language_sees_its_own_answers_with_one_correct(self):
        for question in Question.objects.prefetch_related("javoblar"):
            for lang in ("uz", "uz-kr", "ru"):
                answers = question.answers_for(lang)
                self.assertGreaterEqual(len(answers), 2)
                self.assertEqual(sum(a.togri for a in answers), 1)
                self.assertTrue(all(a.get_text(lang).strip() for a in answers))

    def test_russian_never_shows_uzbek_answers(self):
        question = Question.objects.filter(kategoriya__nomi="Bilet 1").order_by("id").first()
        russian = question.answers_for("ru")
        self.assertTrue(all(a.matn_uzb == "" and a.matn_uz_kr == "" for a in russian))
        self.assertTrue(all(a.matn_rus == "" for a in question.answers_for("uz")))
        self.assertEqual(question.answers_for("uz"), question.answers_for("uz-kr"))

    def test_rerun_keeps_existing_bilets_and_teacher_edits(self):
        question = Question.objects.first()
        Question.objects.filter(pk=question.pk).update(matn_uzb="Tahrirlangan savol")
        call_command("import_bilets", stdout=StringIO())
        self.assertEqual(Question.objects.count(), 1200)
        question.refresh_from_db()
        self.assertEqual(question.matn_uzb, "Tahrirlangan savol")

    def test_force_rewrites_texts_without_recreating_questions(self):
        question = Question.objects.first()
        ids = set(Question.objects.values_list("id", flat=True))
        answer_ids = set(Answer.objects.values_list("id", flat=True))
        Question.objects.filter(pk=question.pk).update(matn_uzb="Tahrirlangan savol")
        call_command("import_bilets", force=True, stdout=StringIO())
        question.refresh_from_db()
        self.assertNotEqual(question.matn_uzb, "Tahrirlangan savol")
        self.assertEqual(set(Question.objects.values_list("id", flat=True)), ids)
        self.assertEqual(set(Answer.objects.values_list("id", flat=True)), answer_ids)


@override_settings(MEDIA_ROOT=MEDIA)
class DemoContentReplacementTests(TestCase):
    def test_placeholder_questions_are_replaced_and_demo_category_purged(self):
        kind = TestType.objects.create(nomi="t", vaqt_daqiqa=20, savollar_soni=20)
        demo_bilet = TestCategory.objects.create(nomi="Bilet 2", tartib=2)
        junk = TestCategory.objects.create(nomi="dsds", tartib=1)
        real = TestCategory.objects.create(nomi="Mavzu: belgilar", tartib=99)
        Question.objects.create(test_turi=kind, kategoriya=demo_bilet, matn_uzb="Bilet 2 - savol 1", matn_uz_kr="q", matn_rus="q")
        Question.objects.create(test_turi=kind, kategoriya=junk, matn_uzb="Demo savol 2 (uz)", matn_uz_kr="q", matn_rus="q")
        Question.objects.create(test_turi=kind, kategoriya=real, matn_uzb="Haqiqiy savol", matn_uz_kr="q", matn_rus="q")

        call_command("import_bilets", purge_demo=True, stdout=StringIO())

        self.assertEqual(demo_bilet.question_set.count(), 20)
        self.assertFalse(demo_bilet.question_set.filter(matn_uzb__startswith="Bilet 2 - ").exists())
        self.assertFalse(TestCategory.objects.filter(nomi="dsds").exists())
        self.assertTrue(TestCategory.objects.filter(nomi="Mavzu: belgilar").exists())


@override_settings(MEDIA_ROOT=MEDIA)
class ExamLanguageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("import_bilets", stdout=StringIO())
        cls.category = TestCategory.objects.get(nomi="Bilet 16")

    def _exam(self, language):
        user = User.objects.create_user(username=f"s-{language}", password="x", unlimited=True, group_language=language)
        self.client.force_login(user)
        response = self.client.post(reverse("start_shablon_test", args=[self.category.id]))
        session = TestSession.objects.get(user=user)
        return session, self.client.get(response.url)

    def test_test_page_carries_every_language_and_starts_in_the_students_own(self):
        session, response = self._exam("ru")
        questions = response.context["questions_data"]
        for question in questions:
            self.assertEqual(set(question["languages"]), {"uz", "uz-kr", "ru"})
        self.assertEqual(response.context["default_language"], "ru")
        stored = session.questions.first()
        data = next(q for q in questions if q["id"] == stored.id)
        self.assertEqual(
            [a["id"] for a in data["languages"]["ru"]["answers"]],
            [a.id for a in stored.answers_for("ru")],
        )

    def test_answering_reports_the_correct_answer_in_every_language(self):
        session, _ = self._exam("ru")
        question = session.questions.first()
        wrong = next(a for a in question.answers_for("ru") if not a.togri)
        response = self.client.post(
            reverse("submit_answer"),
            {"session_id": session.id, "question_id": question.id, "answer_id": wrong.id},
        )
        ids = response.json()["correct_answer_ids"]
        self.assertEqual(ids["ru"], question.correct_answer_for("ru").id)
        self.assertEqual(ids["uz"], question.correct_answer_for("uz").id)


@override_settings(MEDIA_ROOT=MEDIA)
class LinkedOptionTests(TestCase):
    """«F1 va F2 javoblar to‘g‘ri» names options by key; the exam script re-points the keys after a shuffle."""

    @classmethod
    def setUpTestData(cls):
        call_command("import_bilets", stdout=StringIO())

    def test_exam_sends_options_in_original_order_so_keys_can_be_followed(self):
        question = Question.objects.filter(kategoriya__nomi="Bilet 52").order_by("id")[4]
        for lang in ("uz", "uz-kr", "ru"):
            texts = [a.get_text(lang) for a in question.answers_for(lang)]
            self.assertRegex(texts[3], r"^F1 \S+ F2 ")
            self.assertTrue(question.answers_for(lang)[3].togri)

    def test_exam_script_links_keys_to_options(self):
        with open(finders.find("exam/exam.js"), encoding="utf-8") as handle:
            script = handle.read()
        self.assertIn("text.textContent = linkedText(question, answer);", script)
        # The confirm dialog copies the rendered option rows, so its texts are linked the same way.
        self.assertIn("const row = option.cloneNode(true);", script)


@override_settings(MEDIA_ROOT=MEDIA)
class BiletPictureTests(TestCase):
    """Picture "<bilet>-<N>.webp" belongs to question N of that bilet, counted as in the Word document."""

    @classmethod
    def setUpTestData(cls):
        call_command("import_bilets", stdout=StringIO())

    def _question(self, bilet, number):
        return Question.objects.filter(kategoriya__nomi=f"Bilet {bilet}").order_by("id")[number - 1]

    def test_picture_files_are_named_and_sized_correctly(self):
        files = sorted(IMAGE_DIR.glob("*.webp"))
        self.assertTrue(files)
        for path in files:
            bilet, number = map(int, path.stem.split("-"))
            self.assertTrue(1 <= bilet <= 60 and 1 <= number <= 20, path.name)
            with Image.open(path) as image:
                self.assertEqual(image.size, (945, 530), path.name)

    def test_every_picture_lands_on_its_own_question(self):
        files = list(IMAGE_DIR.glob("*.webp"))
        self.assertEqual(Question.objects.exclude(rasm="").exclude(rasm=None).count(), len(files))
        for path in files:
            bilet, number = map(int, path.stem.split("-"))
            question = self._question(bilet, number)
            self.assertEqual(question.rasm.name, f"questions/images/bilet-{bilet}-{number}.webp")
            with question.rasm.open() as stored:
                self.assertEqual(stored.read(), path.read_bytes())

    def test_known_pairs(self):
        self.assertIn("Umurtqa pog", self._question(1, 9).matn_uzb)
        self.assertTrue(self._question(1, 9).rasm)
        self.assertIn("Tibbiyot qutichasi", self._question(1, 3).matn_uzb)
        self.assertFalse(self._question(1, 3).rasm)

    def test_rerun_keeps_a_teachers_picture_and_force_restores_the_original(self):
        question = self._question(1, 1)
        Question.objects.filter(pk=question.pk).update(rasm="questions/images/teacher.png")
        call_command("import_bilets", stdout=StringIO())
        question.refresh_from_db()
        self.assertEqual(question.rasm.name, "questions/images/teacher.png")
        call_command("import_bilets", force=True, stdout=StringIO())
        question.refresh_from_db()
        self.assertEqual(question.rasm.name, "questions/images/bilet-1-1.webp")

    def test_exam_page_sends_the_picture(self):
        user = User.objects.create_user(username="pic", password="x", unlimited=True)
        self.client.force_login(user)
        start = self.client.post(reverse("start_shablon_test", args=[TestCategory.objects.get(nomi="Bilet 1").id]))
        self.assertContains(self.client.get(start.url), "questions/images/bilet-1-9.webp")
