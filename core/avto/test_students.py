from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from django.urls import reverse

from .models import Branch, StudyGroup, TestCategory, TestSession, User
from .student_forms import generate_password

FORM = {
    "first_name": "Abdurashid", "last_name": "Fattokhov", "phone": "99-999-99-99",
    "group_language": "uz", "birth_date": "2006-05-01", "password": "Abdu2006",
}


class PasswordGeneratorTests(TestCase):
    def test_generated_passwords_use_random_tokens(self):
        passwords = {generate_password() for _ in range(5)}
        self.assertEqual(len(passwords), 5)
        self.assertTrue(all(len(password) >= 20 for password in passwords))


class StudentSectionTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(username="teacher", password="x", is_staff=True, unlimited=True)
        self.client.force_login(self.teacher)
        branch = Branch.objects.create(school_name="Avto", name="Main")
        self.group = StudyGroup.objects.create(name="52", category="B", branch=branch, teacher=self.teacher)

    def create(self, **extra):
        return self.client.post(reverse("students:create"), {**FORM, "group": self.group.pk, **extra})

    def test_requires_staff(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("students:list")).status_code, 302)

    def test_temporary_password_must_be_replaced_before_access(self):
        issued = self.create()
        self.assertContains(issued, "Abdu2006")
        self.assertIn("no-store", issued.headers["Cache-Control"])
        student = User.objects.get(phone="999999999")
        self.assertEqual(student.username, "999999999")
        self.assertTrue(student.unlimited and not student.is_staff and student.must_change_password)
        self.assertTrue(student.check_password("Abdu2006"))
        self.assertNotContains(self.client.get(reverse("students:list")), "Abdu2006")
        credentials = {"role": "student", "username": "99-999-99-99", "password": "Abdu2006", "accept_terms": "1"}
        change = reverse("change_temporary_password")
        self.assertRedirects(self.client.post(reverse("login"), credentials), change, fetch_redirect_response=False)
        self.assertRedirects(self.client.get(reverse("dashboard")), change, fetch_redirect_response=False)
        permanent = "my-new-permanent-password"
        response = self.client.post(change, {"new_password1": permanent, "new_password2": permanent})
        self.assertRedirects(response, reverse("dashboard"), fetch_redirect_response=False)
        student.refresh_from_db()
        self.assertFalse(student.must_change_password or student.check_password("Abdu2006"))
        self.assertTrue(student.check_password(permanent))
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)

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

    def test_reset_password_replaces_the_hash_and_displays_once(self):
        self.create()
        student = User.objects.get(phone="999999999")
        response = self.client.post(reverse("students:reset_password", args=[student.pk]))
        password = response.context["temporary_password"]
        student.refresh_from_db()
        self.assertFalse(student.check_password("Abdu2006"))
        self.assertTrue(student.must_change_password and student.check_password(password))
        self.assertNotContains(self.client.get(reverse("students:list")), password)

    def test_search_by_name_and_phone(self):
        self.create()
        self.create(first_name="Ali", phone="90-123-45-67", password="Ali2000")
        by_name = self.client.get(reverse("students:list"), {"q": "abdu"})
        self.assertEqual(len(by_name.context["page"]), 1)
        by_phone = self.client.get(reverse("students:list"), {"q": "90-123"})
        self.assertEqual(by_phone.context["page"][0].first_name, "Ali")

    def test_archive_preserves_student_history_and_can_be_restored(self):
        self.create()
        student = User.objects.get(phone="999999999")
        category = TestCategory.objects.create(nomi="Bilet")
        attempt = TestSession.objects.create(user=student, category=category, test_kind="shablon")
        archive = reverse("students:archive", args=[student.pk])
        self.assertEqual(self.client.post(archive).status_code, 403)
        self.client.force_login(User.objects.create_superuser(username="owner", password="x"))
        self.client.post(archive)
        student.refresh_from_db()
        self.assertEqual(student.access_state, "archived")
        self.assertFalse(student.is_active)
        self.assertTrue(TestSession.objects.filter(pk=attempt.pk).exists())
        self.assertNotIn(student, self.client.get(reverse("students:list")).context["page"])
        archive_page = self.client.get(reverse("students:list"), {"status": "archived"})
        self.assertIn(student, archive_page.context["page"])
        self.client.post(reverse("students:restore", args=[student.pk]))
        student.refresh_from_db()
        self.assertTrue(student.is_active)

    def test_staff_cannot_be_edited_here(self):
        self.assertEqual(self.client.get(reverse("students:edit", args=[self.teacher.pk])).status_code, 404)


class AccessWindowTests(TestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_superuser(username="owner", password="x"))
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
