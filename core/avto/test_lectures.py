from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, SimpleTestCase
from django.urls import reverse
from django.utils import translation

from .lectures import COPY, SLUGS, load_decks, topics_for


class LectureAssetTests(SimpleTestCase):
    def test_all_source_pages_have_real_web_assets(self):
        for lang, counts in (("uz", [93, 29, 110, 55, 145, 12, 80]), ("ru", [93, 29, 110, 55, 145, 13, 80])):
            decks = load_decks(lang)
            self.assertEqual([d["slug"] for d in decks], list(SLUGS))
            self.assertEqual([len(d["slides"]) for d in decks], counts)
            for deck in decks:
                self.assertEqual([s["number"] for s in deck["slides"]], list(range(1, len(deck["slides"]) + 1)))
                for slide in deck["slides"]:
                    for field in ("image", "thumbnail"):
                        asset = Path(settings.BASE_DIR) / "static" / slide[field]
                        self.assertTrue(asset.is_file(), str(asset))
                        self.assertGreater(asset.stat().st_size, 100)
                    self.assertIn(slide["kind"], ("rule", "example"))
                    if slide.get("video"):
                        self.assertTrue((Path(settings.BASE_DIR) / "static" / slide["video"]).is_file())

    def test_cyrillic_uzbek_uses_the_uzbek_deck(self):
        latin, cyrillic, russian = [topics_for(lang) for lang in ("uz", "uz-kr", "ru")]
        self.assertEqual(latin[0]["slides"], cyrillic[0]["slides"])
        self.assertNotEqual(latin[0]["slides"], russian[0]["slides"])
        self.assertEqual(set(COPY["uz"]), set(COPY["ru"]))
        self.assertEqual(set(COPY["uz"]), set(COPY["uz-kr"]))


class LecturePageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="lecture-student", unlimited=True)

    def setUp(self):
        self.addCleanup(translation.activate, translation.get_language())

    def test_login_is_required_for_library_and_reader(self):
        for url in ("/uz/konspekt/", "/ru/konspekt/priority/"):
            self.assertEqual(self.client.get(url).status_code, 302)

    def test_library_in_all_site_languages(self):
        self.client.force_login(self.user)
        for lang in ("uz", "uz-kr", "ru"):
            response = self.client.get(f"/{lang}/konspekt/")
            self.assertContains(response, COPY[lang]["title"])
            self.assertEqual(len(response.context["topics"]), 7)
            self.assertEqual(response.context["total_slides"], 525 if lang == "ru" else 524)
            self.assertEqual(response.context["storage_scope"], f"{self.user.pk}:{'ru' if lang == 'ru' else 'uz'}")

    def test_each_topic_renders_the_correct_language_and_page(self):
        self.client.force_login(self.user)
        for lang in ("uz", "ru"):
            for topic in topics_for(lang):
                response = self.client.get(f"/{lang}/konspekt/{topic['slug']}/?slide=3")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context["current"], topic["slides"][2])
                self.assertContains(response, 'id="reader-paragraphs"')
                self.assertContains(response, '--slide-ratio:1.77778')
                self.assertContains(response, topic["slides"][2]["image"])
                self.assertEqual(response.context["deck"]["source"], topic["source"])

    def test_first_visit_skips_presentation_covers(self):
        self.client.force_login(self.user)
        for lang, slug, expected in (("ru", "service", 3), ("uz", "service", 2), ("ru", "priority", 2)):
            response = self.client.get(f"/{lang}/konspekt/{slug}/")
            self.assertEqual(response.context["page"], expected)

    def test_invalid_topic_and_slide_parameters(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get("/uz/konspekt/unknown/").status_code, 404)
        for query, expected in (("garbage", 1), ("0", 1), ("-1", 1), ("999999", 29)):
            response = self.client.get(f"/uz/konspekt/priority/?slide={query}")
            self.assertEqual(response.context["page"], expected)

    def test_student_navigation_exposes_the_library_in_russian(self):
        self.client.force_login(self.user)
        response = self.client.get("/ru/shpargalka/")
        self.assertContains(response, '/ru/konspekt/')
        self.assertContains(response, 'Конспекты уроков')

    def test_language_switch_keeps_reader_page(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("set_language"), {"language": "ru", "next": "/uz/konspekt/priority/?slide=14"})
        self.assertEqual(response.status_code, 302)
        self.assertIn("/ru/konspekt/priority/?slide=14", response.url)
