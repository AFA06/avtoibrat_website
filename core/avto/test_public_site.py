from django.test import TestCase
from django.urls import reverse

from .models import ConsultRequest, Course, SchoolProfile
from .public_site import MAX_PER_HOUR, normalize_phone


class HomePageTests(TestCase):
    def test_home_shows_school_courses_and_form(self):
        html = self.client.get("/uz/").content.decode()
        self.assertIn(SchoolProfile.current().headline, html)
        self.assertIn("4 500 000", html)  # demo B course price, formatted
        self.assertIn('id="apply"', html)
        self.assertIn("namuna", html)  # demo content is flagged on the page

    def test_no_links_to_the_template_seller(self):
        html = self.client.get("/uz/").content.decode()
        self.assertNotIn("tonatheme", html)

    def test_page_follows_the_site_language(self):
        html = self.client.get("/ru/").content.decode()
        self.assertIn("Записаться на курс", html)
        self.assertIn(SchoolProfile.current().headline_ru, html)

    def test_hidden_course_is_not_shown(self):
        Course.objects.filter(category="C").update(is_active=False)
        html = self.client.get("/uz/").content.decode()
        self.assertNotIn("Yuk avtomobili<", html)

    def test_real_content_drops_the_demo_badge(self):
        SchoolProfile.objects.update(is_demo=False)
        self.assertNotIn("st-demo", self.client.get("/uz/").content.decode())


class ConsultFormTests(TestCase):
    def post(self, **data):
        return self.client.post(reverse("home"), {"name": "Ali", "phone": "90 123 45 67", **data})

    def test_valid_request_is_saved_and_thanked(self):
        response = self.post(category="B", message="Kechki guruh")
        self.assertRedirects(response, reverse("home") + "#apply", fetch_redirect_response=False)
        request = ConsultRequest.objects.get()
        self.assertEqual((request.first_name, request.phone, request.category), ("Ali", "+998901234567", "B"))
        self.assertContains(self.client.get(reverse("home")), "Rahmat!")

    def test_bad_phone_is_refused_with_the_values_kept(self):
        response = self.post(phone="12345")
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "Telefon raqamni to‘liq yozing", status_code=400)
        self.assertContains(response, 'value="Ali"', status_code=400)
        self.assertFalse(ConsultRequest.objects.exists())

    def test_honeypot_pretends_success_and_saves_nothing(self):
        response = self.post(website="http://spam.example")
        self.assertEqual(response.status_code, 302)
        self.assertFalse(ConsultRequest.objects.exists())

    def test_same_phone_is_saved_once_a_day(self):
        self.post()
        self.post(phone="+998 (90) 123-45-67")
        self.assertEqual(ConsultRequest.objects.count(), 1)

    def test_flood_is_capped_per_hour(self):
        for i in range(MAX_PER_HOUR):
            ConsultRequest.objects.create(first_name="x", phone=f"+9989000{i:05d}")
        response = self.post()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(ConsultRequest.objects.count(), MAX_PER_HOUR)

    def test_unknown_category_is_dropped(self):
        self.post(category="Z")
        self.assertEqual(ConsultRequest.objects.get().category, "")

    def test_phone_normalisation(self):
        self.assertEqual(normalize_phone("+998 90 123 45 67"), "+998901234567")
        self.assertEqual(normalize_phone("901234567"), "+998901234567")
        self.assertIsNone(normalize_phone("+7 900 123 45 67"))
        self.assertIsNone(normalize_phone(""))


class InnerPagesTests(TestCase):
    def test_every_public_page_uses_the_new_design(self):
        for url in ("/uz/", "/uz/contact/", "/uz/team/", "/uz/faq/", "/ru/contact/", "/uz-kr/faq/"):
            html = self.client.get(url).content.decode()
            self.assertIn("site/site.css", html, url)
            self.assertNotIn("tonatheme", html, url)
            self.assertNotIn("assets/css/style.css", html, url)

    def test_current_page_is_marked_in_the_menu(self):
        self.assertContains(self.client.get("/uz/faq/"), 'aria-current="page"')

    def test_faq_page_lists_active_questions(self):
        from .models import FAQ
        FAQ.objects.create(question="Yashirin savol?", answer="-", is_active=False)
        html = self.client.get("/uz/faq/").content.decode()
        self.assertIn(FAQ.objects.filter(is_active=True).first().question, html)
        self.assertNotIn("Yashirin savol?", html)

    def test_unknown_page_is_a_dead_end_404(self):
        with self.settings(DEBUG=False):
            response = self.client.get("/uz/bunday-sahifa-yoq/")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Bu yo‘l berk", status_code=404)


class ContactFormTests(TestCase):
    def post(self, **data):
        return self.client.post(reverse("contact"), {"name": "Vali", "phone": "+998 93 111 22 33", **data})

    def test_message_is_saved_with_an_uzbek_subject(self):
        from .models import ContactMessage
        response = self.client.post("/ru/contact/", {"name": "Vali", "phone": "+998 93 111 22 33",
                                                     "topic": "platform", "message": "Parolni unutdim"})
        self.assertEqual(response.status_code, 302)
        message = ContactMessage.objects.get()
        self.assertEqual((message.phone, message.subject), ("+998931112233", "Onlayn platforma"))

    def test_unknown_topic_falls_back_to_other(self):
        from .models import ContactMessage
        self.post(topic="hack")
        self.assertEqual(ContactMessage.objects.get().subject, "Boshqa savol")

    def test_errors_are_shown_and_nothing_saved(self):
        from .models import ContactMessage
        response = self.post(name="", phone="1")
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "Ismingizni yozing", status_code=400)
        self.assertFalse(ContactMessage.objects.exists())

    def test_honeypot(self):
        from .models import ContactMessage
        self.post(website="x")
        self.assertFalse(ContactMessage.objects.exists())
