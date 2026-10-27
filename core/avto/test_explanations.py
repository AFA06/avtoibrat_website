import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Answer, Question, TestCategory, TestSession, TestType, User, UserAnswer

PRIVATE = tempfile.mkdtemp()


@override_settings(PRIVATE_MEDIA_ROOT=PRIVATE)
class VoiceExplanationTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(PRIVATE, ignore_errors=True)

    def setUp(self):
        self.student = User.objects.create_user(username="s", password="x", unlimited=True)
        self.russian = User.objects.create_user(username="r", password="x", unlimited=True, group_language="ru")
        kind = TestType.objects.create(nomi="B", vaqt_daqiqa=25, savollar_soni=20)
        self.category = TestCategory.objects.create(nomi="Bilet 1")
        self.question = Question.objects.create(
            test_turi=kind, kategoriya=self.category, matn_uzb="q", matn_uz_kr="q", matn_rus="q",
            audio_uzb=SimpleUploadedFile("uz.mp3", b"0123456789"),
        )
        self.right = Answer.objects.create(question=self.question, matn_uzb="a", togri=True)
        self.wrong = Answer.objects.create(question=self.question, matn_uzb="b")
        self.url = reverse("question_explanation", args=[self.question.pk])

    def answer(self, user, correct, kind="shablon", finished=False):
        session = TestSession.objects.create(
            user=user, category=self.category, test_kind=kind, started_at=timezone.now(),
            finished_at=timezone.now() if finished else None, question_order=[self.question.pk],
        )
        UserAnswer.objects.create(
            session=session, question=self.question, selected_answer=self.right if correct else self.wrong, is_correct=correct,
        )

    def test_locked_until_the_student_makes_a_mistake(self):
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.answer(self.student, correct=True)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.answer(self.student, correct=False)
        response = self.client.get(self.url)
        self.assertEqual((response.status_code, response.content), (200, b"0123456789"))

    def test_someone_elses_mistake_does_not_unlock_it(self):
        self.answer(self.student, correct=False)
        self.client.force_login(self.russian)
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_a_running_real_exam_stays_silent_until_it_is_finished(self):
        self.answer(self.student, correct=False, kind="real")
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        TestSession.objects.filter(test_kind="real").update(finished_at=timezone.now())
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_the_students_language_decides_which_recording_plays(self):
        self.answer(self.russian, correct=False)
        self.client.force_login(self.russian)
        self.assertEqual(self.client.get(self.url).status_code, 404)  # only an Uzbek recording exists
        self.question.audio_rus = SimpleUploadedFile("ru.mp3", b"ruso")
        self.question.save()
        self.assertEqual(self.client.get(self.url).content, b"ruso")

    def test_byte_ranges_work_for_safari(self):
        self.answer(self.student, correct=False)
        self.client.force_login(self.student)
        response = self.client.get(self.url, HTTP_RANGE="bytes=2-5")
        self.assertEqual((response.status_code, response.content), (206, b"2345"))
        self.assertEqual(response["Content-Range"], "bytes 2-5/10")

    def test_the_file_has_no_public_url_and_the_exam_page_only_says_it_exists(self):
        self.client.force_login(self.student)
        self.assertTrue(self.question.audio_uzb.path.startswith(PRIVATE))  # outside MEDIA_ROOT: no public URL
        session = TestSession.objects.create(
            user=self.student, category=self.category, test_kind="shablon", started_at=timezone.now(),
            question_order=[self.question.pk],
        )
        session.questions.add(self.question)
        html = self.client.get(reverse("test_page", args=[session.pk])).content.decode()
        self.assertIn('"has_explanation": true', html.replace('":true', '": true'))
        self.assertNotIn("questions/audio", html)

    def test_teacher_can_listen_upload_and_remove_it(self):
        teacher = User.objects.create_user(username="t", password="x", is_staff=True, is_superuser=True)
        self.client.force_login(teacher)
        self.assertEqual(self.client.get(reverse("questions:audio", args=[self.question.pk, "uz"])).content, b"0123456789")
        self.assertEqual(self.client.get(reverse("questions:audio", args=[self.question.pk, "ru"])).status_code, 404)

        from .models import Topic, TopicGroup
        topic = Topic.objects.create(group=TopicGroup.objects.create(slug="g", nomi_uzb="G"), slug="t", nomi_uzb="T")
        edit = reverse("questions:edit", args=[self.question.pk])
        data = {
            "kategoriya": self.category.pk, "mavzu": topic.pk, "matn_uzb": "q", "matn_uz_kr": "q", "matn_rus": "q",
            "uz_id": [self.right.pk, self.wrong.pk], "uz_uz": ["a", "b"], "uz_kr": ["a", "b"], "uz_correct": "0",
            "ru_id": ["", ""], "ru_ru": ["x", "y"], "ru_correct": "0",
        }
        bad = self.client.post(edit, {**data, "audio_uzb": SimpleUploadedFile("voice.exe", b"x")})
        self.assertContains(bad, "MP3, M4A, OGG, WEBM yoki WAV")
        ok = self.client.post(edit, {**data, "audio_uzb": SimpleUploadedFile("uz.webm", b"voice")})
        self.assertEqual(ok.status_code, 302)
        self.question.refresh_from_db()
        self.assertTrue(self.question.audio_uzb)
        self.assertContains(self.client.get(edit), "data-voice-delete")
        stored = self.question.audio_uzb.name
        delete = reverse("questions:audio_delete", args=[self.question.pk, "uz"])
        self.assertEqual(self.client.get(delete).status_code, 405)
        self.assertEqual(self.client.post(delete).json(), {"ok": True})
        self.question.refresh_from_db()
        self.assertFalse(self.question.audio_uzb)
        self.assertFalse(self.question.audio_uzb.storage.exists(stored))
        # Saving the form afterwards keeps it deleted, and a new recording can be saved.
        self.assertEqual(self.client.post(edit, data).status_code, 302)
        self.question.refresh_from_db()
        self.assertFalse(self.question.audio_uzb)
        self.client.post(edit, {**data, "audio_uzb": SimpleUploadedFile("again.webm", b"voice2")})
        self.question.refresh_from_db()
        self.assertTrue(self.question.audio_uzb)

    def test_students_cannot_delete_explanations(self):
        student = User.objects.create_user(username="s2", password="x", unlimited=True)
        self.client.force_login(student)
        self.client.post(reverse("questions:audio_delete", args=[self.question.pk, "uz"]))
        self.question.refresh_from_db()
        self.assertTrue(self.question.audio_uzb)


class RevealDataTests(TestCase):
    def test_a_finished_real_exam_carries_the_reveal_data(self):
        student = User.objects.create_user(username="s", password="x", first_name="Ali", unlimited=True)
        kind = TestType.objects.create(nomi="B", vaqt_daqiqa=25, savollar_soni=20)
        category = TestCategory.objects.create(nomi="Bilet 1")
        questions = [
            Question.objects.create(test_turi=kind, kategoriya=category, matn_uzb="q", matn_uz_kr="q", matn_rus="q")
            for _ in range(20)
        ]
        session = TestSession.objects.create(
            user=student, category=category, test_kind="real", started_at=timezone.now(), finished_at=timezone.now(),
            question_order=[q.pk for q in questions],
        )
        for q in questions:
            right = Answer.objects.create(question=q, matn_uzb="a", togri=True)
            UserAnswer.objects.create(session=session, question=q, selected_answer=right, is_correct=True)
        self.client.force_login(student)
        response = self.client.get(reverse("test_result", args=[session.pk]))
        reveal = response.context["reveal"]
        self.assertTrue(reveal["passed"])
        self.assertEqual((reveal["name"], reveal["correct"], reveal["allowed"]), ("Ali", 20, 2))
        self.assertContains(response, 'id="reveal-data"')
        session.test_kind = "shablon"
        session.save()
        self.assertNotContains(self.client.get(reverse("test_result", args=[session.pk])), 'id="reveal-data"')


class StudyMaterialsTests(TestCase):
    def test_materials_are_imported_once_and_shown_and_viewable(self):
        import tempfile
        from django.core.management import call_command
        from io import StringIO
        from .models import PdfMaterial
        with self.settings(MEDIA_ROOT=tempfile.mkdtemp()):
            call_command("import_materials", stdout=StringIO())
            call_command("import_materials", stdout=StringIO())
            self.assertEqual(PdfMaterial.objects.count(), 2)
            self.client.force_login(User.objects.create_user(username="s", password="x", unlimited=True))
            page = self.client.get(reverse("manular"))
            self.assertContains(page, "Yo‘l belgilari")
            pdf = PdfMaterial.objects.first()
            response = self.client.get(reverse("manular_view", args=[pdf.pk]))
            self.assertEqual(response["Content-Type"], "application/pdf")
            self.assertEqual(response["X-Frame-Options"], "SAMEORIGIN")
