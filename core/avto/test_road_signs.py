import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import RoadSign, RoadSignCategory, User
from .road_signs import sign_sort_key, sorted_signs

PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe\xa7\x9a\xa0\xa0\x00\x00\x00\x00IEND\xaeB`\x82"
)
SVG = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><circle cx="5" cy="5" r="4"/></svg>'

MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=MEDIA)
class RoadSignTestCase(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    @classmethod
    def setUpTestData(cls):
        cls.teacher = User.objects.create_user(username="teacher", password="x", is_staff=True, unlimited=True)
        cls.student = User.objects.create_user(username="student", password="x", unlimited=True)

    def make_sign(self, category, number, title="Belgi", order=0):
        return RoadSign.objects.create(
            category=category, number=number, title=title, slug=f"s-{category.pk}-{number or title}-{order}",
            order=order, image=SimpleUploadedFile("s.png", PNG),
        )


class OrderingTests(RoadSignTestCase):
    def test_categories_follow_the_teachers_order_on_the_student_page(self):
        names = ["Uchinchi", "Birinchi", "Ikkinchi"]
        for title, order in zip(names, (3, 1, 2)):
            self.make_sign(RoadSignCategory.objects.create(title=title, slug=title.lower(), order=order), "1.1")
        self.client.force_login(self.student)
        response = self.client.get(reverse("road_signs"))
        shown = [c.title for c in response.context["main_categories"]]
        self.assertEqual(shown, ["Birinchi", "Ikkinchi", "Uchinchi"])

    def test_signs_sort_by_number_part_by_part(self):
        category = RoadSignCategory.objects.create(title="Ogohlantiruvchi", slug="og")
        for number in ("1.10", "1.2", "", "1.1", "2.1", "1.4.2", "1.4.1"):
            self.make_sign(category, number, title=f"t{number}", order=len(number))
        self.assertEqual(
            [s.number for s in sorted_signs(category)], ["1.1", "1.2", "1.4.1", "1.4.2", "1.10", "2.1", ""],
        )

    def test_student_category_page_uses_the_same_order(self):
        category = RoadSignCategory.objects.create(title="Taqiq", slug="taqiq")
        self.make_sign(category, "3.10", order=0)
        self.make_sign(category, "3.2", order=1)
        self.client.force_login(self.student)
        response = self.client.get(reverse("road_signs_two", args=[category.slug]))
        self.assertEqual([s.number for s in response.context["signs"]], ["3.2", "3.10"])

    def test_sort_key_puts_unnumbered_last(self):
        category = RoadSignCategory.objects.create(title="X", slug="x")
        assert sign_sort_key(self.make_sign(category, "9.9")) < sign_sort_key(self.make_sign(category, ""))


class AdminTests(RoadSignTestCase):
    def setUp(self):
        self.client.force_login(self.teacher)

    def test_pages_render(self):
        category = RoadSignCategory.objects.create(title="Taqiq", slug="taqiq")
        sign = self.make_sign(category, "3.1")
        for url in (
            reverse("signs:list"), reverse("signs:category", args=[category.pk]),
            reverse("signs:category_create"), reverse("signs:category_edit", args=[category.pk]),
            reverse("signs:sign_create") + f"?category={category.pk}", reverse("signs:sign_edit", args=[sign.pk]),
        ):
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_students_cannot_open_the_section(self):
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(reverse("signs:list")).status_code, 302)

    def test_create_category_gets_slug_and_goes_last(self):
        RoadSignCategory.objects.create(title="Eski", slug="eski", order=5)
        self.client.post(reverse("signs:category_create"), {"title": "Yangi bo‘lim"})
        created = RoadSignCategory.objects.get(title="Yangi bo‘lim")
        self.assertEqual(created.order, 6)
        self.assertTrue(created.slug)

    def test_duplicate_category_titles_get_distinct_slugs(self):
        for _ in range(2):
            self.client.post(reverse("signs:category_create"), {"title": "Taqiq"})
        self.assertEqual(RoadSignCategory.objects.values("slug").distinct().count(), 2)

    def test_add_sign_with_png_and_svg(self):
        category = RoadSignCategory.objects.create(title="Taqiq", slug="taqiq")
        for number, upload in (("3.1", SimpleUploadedFile("a.png", PNG)), ("3.2", SimpleUploadedFile("b.svg", SVG))):
            response = self.client.post(reverse("signs:sign_create"), {
                "category": category.pk, "number": number, "title": "Kirish taqiqlangan",
                "description": "Tavsif matni", "image": upload,
            })
            self.assertRedirects(response, reverse("signs:category", args=[category.pk]))
        self.assertEqual(category.signs.count(), 2)
        first = category.signs.get(number="3.1")
        self.assertEqual((first.description, first.order), ("Tavsif matni", 1))

    def test_save_and_add_another_stays_on_the_form_for_that_category(self):
        category = RoadSignCategory.objects.create(title="Taqiq", slug="taqiq")
        response = self.client.post(reverse("signs:sign_create"), {
            "category": category.pk, "number": "3.1", "title": "A", "image": SimpleUploadedFile("a.png", PNG),
            "add_another": "1",
        })
        self.assertRedirects(response, reverse("signs:sign_create") + f"?category={category.pk}")

    def test_rejects_non_images_and_requires_image_for_new_sign(self):
        category = RoadSignCategory.objects.create(title="Taqiq", slug="taqiq")
        bad = self.client.post(reverse("signs:sign_create"), {
            "category": category.pk, "title": "A", "image": SimpleUploadedFile("a.exe", b"MZ"),
        })
        missing = self.client.post(reverse("signs:sign_create"), {"category": category.pk, "title": "A"})
        self.assertIn("image", bad.context["form"].errors)
        self.assertIn("image", missing.context["form"].errors)
        self.assertFalse(RoadSign.objects.exists())

    def test_editing_without_new_image_keeps_the_old_one(self):
        category = RoadSignCategory.objects.create(title="Taqiq", slug="taqiq")
        sign = self.make_sign(category, "3.1")
        old_image = sign.image.name
        self.client.post(reverse("signs:sign_edit", args=[sign.pk]), {
            "category": category.pk, "number": "3.1", "title": "Yangi nom", "description": "Yangi",
        })
        sign.refresh_from_db()
        self.assertEqual((sign.title, sign.image.name), ("Yangi nom", old_image))

    def test_move_category_swaps_neighbours(self):
        a = RoadSignCategory.objects.create(title="A", slug="a", order=1)
        b = RoadSignCategory.objects.create(title="B", slug="b", order=2)
        c = RoadSignCategory.objects.create(title="C", slug="c", order=3)
        self.client.post(reverse("signs:category_move", args=[c.pk, "up"]))
        self.assertEqual([x.title for x in RoadSignCategory.objects.all()], ["A", "C", "B"])
        self.client.post(reverse("signs:category_move", args=[a.pk, "up"]))
        self.assertEqual([x.title for x in RoadSignCategory.objects.all()], ["A", "C", "B"])
        self.assertEqual(self.client.post(reverse("signs:category_move", args=[b.pk, "sideways"])).status_code, 404)

    def test_delete_sign_and_category(self):
        category = RoadSignCategory.objects.create(title="Taqiq", slug="taqiq")
        sign = self.make_sign(category, "3.1")
        self.client.post(reverse("signs:sign_delete", args=[sign.pk]))
        self.assertFalse(RoadSign.objects.exists())
        self.client.post(reverse("signs:category_delete", args=[category.pk]))
        self.assertFalse(RoadSignCategory.objects.exists())
