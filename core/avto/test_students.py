from datetime import date, timedelta

from django.test import TestCase
from django.utils import timezone
from django.urls import reverse

from .models import User
from .student_forms import generate_password

FORM = {
    "first_name": "Abdurashid", "last_name": "Fattokhov", "phone": "99-999-99-99",
    "group_language": "uz", "birth_date": "2006-05-01", "password": "Abdu2006",
}


class PasswordGeneratorTests(TestCase):
    def test_name_and_birth_year(self):
        self.assertEqual(generate_password("Abdurashid", date(2006, 5, 1)), "Abdu2006")

    def test_cyrillic_name_is_transliterated(self):
        self.assertEqual(generate_password("Абдурашид", date(2006, 5, 1)), "Abdu2006")

    def test_random_variant_has_four_digits(self):
        password = generate_password("Abdurashid", date(2006, 5, 1), randomize=True)
        self.assertRegex(password, r"^Abdu\d{4}$")


class StudentSectionTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(username="teacher", password="x", is_staff=True, unlimited=True)
        self.client.force_login(self.teacher)

    def create(self, **extra):
        return self.client.post(reverse("students:create"), {**FORM, **extra})

    def test_requires_staff(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("students:list")).status_code, 302)

    def test_create_student_logs_in_with_phone_and_password(self):
        self.assertRedirects(self.create(), reverse("students:list"))
        student = User.objects.get(phone="999999999")
        self.assertEqual((student.username, student.initial_password), ("999999999", "Abdu2006"))
        self.assertTrue(student.unlimited and not student.is_staff)
        self.assertTrue(student.check_password("Abdu2006"))
        response = self.client.post(reverse("login"), {"role": "student", "username": "99-999-99-99", "password": "Abdu2006"})
        self.assertRedirects(response, reverse("dashboard"), fetch_redirect_response=False)

    def test_phone_must_be_nine_digits_and_unique(self):
        self.assertEqual(self.create(phone="99-999-99").status_code, 200)
        self.assertFalse(User.objects.filter(first_name="Abdurashid").exists())
        self.create()
        self.assertEqual(self.create().status_code, 200)
        self.assertEqual(User.objects.filter(is_staff=False).count(), 1)

    def test_block_stops_login_and_unblock_restores_it(self):
        self.create()
        student = User.objects.get(phone="999999999")
        self.client.post(reverse("students:toggle", args=[student.pk]))
        student.refresh_from_db()
        self.assertTrue(student.is_blocked)
        student.sync_active_status()
        self.assertFalse(student.is_active)
        self.client.post(reverse("students:toggle", args=[student.pk]))
        student.refresh_from_db()
        self.assertTrue(student.is_active and not student.is_blocked)

    def test_reset_password_changes_visible_and_real_password(self):
        self.create()
        student = User.objects.get(phone="999999999")
        self.client.post(reverse("students:reset_password", args=[student.pk]))
        student.refresh_from_db()
        self.assertNotEqual(student.initial_password, "Abdu2006")
        self.assertTrue(student.check_password(student.initial_password))

    def test_search_by_name_and_phone(self):
        self.create()
        self.create(first_name="Ali", phone="90-123-45-67", password="Ali2000")
        by_name = self.client.get(reverse("students:list"), {"q": "abdu"})
        self.assertEqual(len(by_name.context["page"]), 1)
        by_phone = self.client.get(reverse("students:list"), {"q": "90-123"})
        self.assertEqual(by_phone.context["page"][0].first_name, "Ali")

    def test_delete_student(self):
        self.create()
        student = User.objects.get(phone="999999999")
        self.client.post(reverse("students:delete", args=[student.pk]))
        self.assertFalse(User.objects.filter(pk=student.pk).exists())

    def test_staff_cannot_be_edited_here(self):
        self.assertEqual(self.client.get(reverse("students:edit", args=[self.teacher.pk])).status_code, 404)


class AccessWindowTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(username="teacher", password="x", is_staff=True, unlimited=True)
        self.client.force_login(self.teacher)
        now = timezone.now()
        self.open = self.student("open", unlimited=True)
        self.running = self.student("running", account_started_at=now - timedelta(days=5), account_expires_at=now + timedelta(days=5))
        self.expired = self.student("expired", account_started_at=now - timedelta(days=60), account_expires_at=now - timedelta(days=1))
        self.blocked = self.student("blocked", unlimited=True, is_blocked=True)

    def student(self, username, **extra):
        return User.objects.create_user(username=username, password="x", first_name=username, phone=username[:2] * 4 + "1", **extra)

    def names(self, status):
        page = self.client.get(reverse("students:list"), {"status": status}).context["page"]
        return {s.username for s in page}

    def test_status_filters_separate_active_expired_and_blocked(self):
        self.assertEqual(self.names("active"), {"open", "running"})
        self.assertEqual(self.names("expired"), {"expired"})
        self.assertEqual(self.names("blocked"), {"blocked"})

    def test_extend_reopens_an_expired_student_and_can_go_open_ended(self):
        self.client.post(reverse("students:extend", args=[self.expired.pk]), {"days": "30"})
        self.expired.refresh_from_db()
        self.assertTrue(self.expired.is_active and self.expired.has_active_account())
        self.assertGreater(self.expired.account_expires_at, timezone.now() + timedelta(days=29))
        self.client.post(reverse("students:extend", args=[self.expired.pk]), {"days": "0"})
        self.expired.refresh_from_db()
        self.assertTrue(self.expired.unlimited and self.expired.account_expires_at is None)

    def test_extend_adds_to_a_running_window(self):
        before = self.running.account_expires_at
        self.client.post(reverse("students:extend", args=[self.running.pk]), {"days": "14"})
        self.running.refresh_from_db()
        self.assertEqual(self.running.account_expires_at - before, timedelta(days=14))

    def test_status_label_and_filter_agree_for_student_without_dates(self):
        ghost = User.objects.create_user(username="ghost", password="x", first_name="ghost", phone="7777777")
        self.assertEqual(ghost.access_state, "expired")
        self.assertIn("ghost", self.names("expired"))
        self.assertNotIn("ghost", self.names("active"))
