from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import translation

from .cheatsheet import SECTIONS

User = get_user_model()


class CheatsheetTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="s", password="x", unlimited=True)

    def test_requires_login(self):
        response = self.client.get(reverse("cheatsheet"))
        self.assertEqual(response.status_code, 302)

    def test_every_section_and_card_is_rendered(self):
        self.client.force_login(self.user)
        html = self.client.get(reverse("cheatsheet")).content.decode()
        for section in SECTIONS:
            self.assertIn(f'id="cs-{section["id"]}"', html)
        cards = sum(len(items) for s in SECTIONS if s["kind"] == "numbers" for _, items in s["groups"])
        rules = sum(len(s["rules"]) for s in SECTIONS if s["kind"] == "rules")
        self.assertEqual(html.count("data-item"), cards + rules)

    def test_card_ids_are_unique(self):
        self.client.force_login(self.user)
        html = self.client.get(reverse("cheatsheet")).content.decode()
        import re
        ids = re.findall(r'data-item data-id="([^"]+)"', html)
        self.assertEqual(len(ids), len(set(ids)))

    def test_sidebar_links_to_the_cheatsheet(self):
        self.client.force_login(self.user)
        html = self.client.get(reverse("dashboard")).content.decode()
        self.assertIn(reverse("cheatsheet"), html)

    def test_russian_text(self):
        self.client.force_login(self.user)
        with translation.override("ru"):
            url = reverse("cheatsheet")
        html = self.client.get(url).content.decode()
        self.assertTrue("Шпаргалка" in html and "Скорость" in html)
