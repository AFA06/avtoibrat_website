from django.contrib.staticfiles import finders
from django.test import TestCase
from django.urls import reverse
from django.utils import translation

from . import legal
from .models import Question, TestCategory, TestType, User
from .views import _create_test_session


class TermsAtLoginTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(username="ali", password="Ali2006", unlimited=True, phone="901234567")

    def login(self, **extra):
        return self.client.post(reverse("login"), {
            "role": "student", "username": "90-123-45-67", "password": "Ali2006", **extra,
        })

    def test_login_page_has_a_required_terms_box_linking_the_terms(self):
        html = self.client.get(reverse("login")).content.decode()
        self.assertRegex(html, r'<input type="checkbox" name="accept_terms" value="1" required>')
        self.assertIn(f'href="{reverse("terms")}"', html)
        self.assertIn(f'href="{reverse("guide")}"', html)

    def test_without_the_tick_nobody_is_signed_in(self):
        response = self.login()
        self.assertRedirects(response, f'{reverse("login")}?error=terms&role=student', fetch_redirect_response=False)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.student.refresh_from_db()
        self.assertIsNone(self.student.terms_accepted_at)

    def test_unticked_box_is_explained_on_the_page(self):
        response = self.client.get(f'{reverse("login")}?error=terms&role=student')
        self.assertContains(response, "foydalanish shartlarini qabul qiling")

    def test_with_the_tick_the_acceptance_is_recorded(self):
        response = self.login(accept_terms="1")
        self.assertRedirects(response, reverse("dashboard"), fetch_redirect_response=False)
        self.student.refresh_from_db()
        self.assertIsNotNone(self.student.terms_accepted_at)
        self.assertEqual(self.student.terms_version, legal.TERMS_VERSION)

    def test_a_wrong_password_records_nothing(self):
        self.login(accept_terms="1", password="nope")
        self.student.refresh_from_db()
        self.assertIsNone(self.student.terms_accepted_at)


class LegalPagesTests(TestCase):
    def test_pages_are_public_in_every_language(self):
        cases = {
            "uz": ("Taqiqlangan harakatlar", "Real imtihon"),
            "uz-kr": ("Тақиқланган ҳаракатлар", "Реал имтиҳон"),
            "ru": ("Запрещённые действия", "Реальный экзамен"),
        }
        for lang, (terms_text, guide_text) in cases.items():
            with self.subTest(lang=lang), translation.override(lang):
                self.assertContains(self.client.get(reverse("terms")), terms_text)
                self.assertContains(self.client.get(reverse("guide")), guide_text)

    def test_terms_forbid_copying_and_sharing(self):
        html = self.client.get(reverse("terms")).content.decode()
        for rule in ("skrinshot", "yuklab olish", "Telegram", "Hisobni yoki parolni boshqa shaxsga berish"):
            self.assertIn(rule, html)

    def test_guide_states_the_real_exam_mistake_limits(self):
        html = self.client.get(reverse("guide")).content.decode()
        self.assertIn("3-xatoda", html)
        self.assertIn("5-xatoda", html)

    def test_signed_in_users_get_a_way_back_to_the_panel(self):
        user = User.objects.create_user(username="ali", password="x", unlimited=True)
        self.client.force_login(user)
        self.assertContains(self.client.get(reverse("guide")), f'href="{reverse("dashboard")}"')


class CopyProtectionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ali", password="x", unlimited=True)
        self.client.force_login(self.user)

    def test_panel_pages_load_the_protection(self):
        self.assertContains(self.client.get(reverse("dashboard")), "dashboard/protect.js")

    def test_test_window_is_strictly_protected(self):
        test_type = TestType.objects.create(nomi="Umumiy", vaqt_daqiqa=25, savollar_soni=1)
        category = TestCategory.objects.create(nomi="Bilet 1", question_count=1)
        Question.objects.create(test_turi=test_type, kategoriya=category, matn_uzb="Savol", matn_uz_kr="С", matn_rus="В")
        session = _create_test_session(self.user, category, "shablon")
        html = self.client.get(reverse("test_page", args=[session.id])).content.decode()
        self.assertIn('data-protect="strict"', html)
        self.assertIn("dashboard/protect.js", html)
        with open(finders.find("dashboard/protect.js"), encoding="utf-8") as handle:
            script = handle.read()
        for guard in ('"contextmenu"', '"dragstart"', '"copy"'):
            self.assertIn(guard, script)
