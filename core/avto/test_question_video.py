from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase

from .models import Question, validate_video_file


class QuestionVideoUploadTests(SimpleTestCase):
    def test_question_takes_an_uploaded_file_not_a_link(self):
        field = Question._meta.get_field("video")
        self.assertEqual(field.get_internal_type(), "FileField")
        self.assertFalse(any(f.name == "video_url" for f in Question._meta.get_fields()))

    def test_accepts_common_video_formats(self):
        for name in ("a.mp4", "b.WEBM", "c.mov"):
            validate_video_file(SimpleUploadedFile(name, b"x"))

    def test_rejects_other_files_and_oversized_videos(self):
        with self.assertRaises(ValidationError):
            validate_video_file(SimpleUploadedFile("a.exe", b"x"))
        big = SimpleUploadedFile("a.mp4", b"x")
        big.size = 51 * 1024 * 1024
        with self.assertRaises(ValidationError):
            validate_video_file(big)
