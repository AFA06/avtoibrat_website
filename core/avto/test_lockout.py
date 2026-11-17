from datetime import timedelta
from unittest import mock

from django.contrib.auth import authenticate
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from . import legal, lockout
from .models import LoginLock, User

PHONE = "901234567"


class LockoutTestCase(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(
            username="ali", password="right-pass", phone=PHONE, unlimited=True)
        self.now = timezone.now()

    def at(self, **delta):
        """Run the code as if the clock had moved forward."""
        return mock.patch("avto.lockout.timezone.now", return_value=self.now + timedelta(**delta))

    def wrong(self, times=1, username="ali"):
        for _ in range(times):
            self.assertIsNone(authenticate(username=username, password="wrong"))

    def ok(self, username="ali"):
        return authenticate(username=username, password="right-pass")


class LockRulesTests(LockoutTestCase):
    def test_three_wrong_passwords_do_not_lock(self):
        with self.at():
            self.wrong(3)
            self.assertEqual(lockout.locked_for("ali"), 0)
            self.assertIsNotNone(self.ok())

    def test_fourth_wrong_password_locks_for_five_minutes_even_with_the_right_password(self):
        with self.at():
            self.wrong(4)
            self.assertIsNone(self.ok())
            self.assertEqual(lockout.minutes_left("ali"), 5)
        with self.at(minutes=4, seconds=59):
            self.assertIsNone(self.ok())
        with self.at(minutes=5, seconds=1):
            self.assertIsNotNone(self.ok())

    def test_each_next_lock_is_longer_up_to_one_hour(self):
        expected = [5, 15, 60, 60]
        clock = 0
        for minutes in expected:
            with self.at(minutes=clock):
                self.wrong(4)
                self.assertEqual(lockout.minutes_left("ali"), minutes)
            clock += minutes + 1

    def test_tries_during_a_lock_do_not_stretch_it(self):
        with self.at():
            self.wrong(4)
        with self.at(minutes=3):
            self.wrong(10)
            self.assertEqual(lockout.minutes_left("ali"), 2)

    def test_correct_password_clears_the_count(self):
        with self.at():
            self.wrong(3)
            self.assertIsNotNone(self.ok())
            self.wrong(3)
            self.assertEqual(lockout.locked_for("ali"), 0)

    def test_old_failures_stop_counting_after_an_hour(self):
        with self.at():
            self.wrong(3)
        with self.at(minutes=61):
            self.wrong(1)
            self.assertEqual(lockout.locked_for("ali"), 0)

    def test_a_quiet_day_resets_the_lock_length(self):
        with self.at():
            self.wrong(4)
        with self.at(minutes=6):
            self.wrong(4)
            self.assertEqual(lockout.minutes_left("ali"), 15)
        with self.at(days=2):
            self.wrong(4)
            self.assertEqual(lockout.minutes_left("ali"), 5)

    def test_other_accounts_are_not_affected(self):
        User.objects.create_user(username="vali", password="right-pass")
        with self.at():
            self.wrong(4)
            self.assertIsNotNone(self.ok("vali"))

    def test_unknown_usernames_leave_no_rows(self):
        with self.at():
            self.wrong(10, username="nobody")
        self.assertFalse(LoginLock.objects.exists())


class LoginPageTests(LockoutTestCase):
    def post(self, password, role="student", username=PHONE):
        return self.client.post(reverse("login"), {
            "role": role, "username": username, "password": password,
            legal.TERMS_FIELD: "1",
        })

    def test_student_form_shows_the_lock_and_minutes(self):
        for _ in range(3):
            self.assertIn("error=invalid", self.post("wrong").url)
        locked = self.post("wrong")
        self.assertIn("error=locked", locked.url)
        self.assertIn("minutes=5", locked.url)
        self.assertIn("error=locked", self.post("right-pass").url)
        page = self.client.get(locked.url)
        self.assertContains(page, "5 daqiqadan keyin")

    def test_django_admin_login_is_locked_too(self):
        User.objects.create_user(username="boss", password="right-pass", is_staff=True, is_superuser=True)
        url = reverse("admin:login")
        for _ in range(4):
            self.client.post(url, {"username": "boss", "password": "wrong"})
        self.client.post(url, {"username": "boss", "password": "right-pass"})
        self.assertFalse(self.client.session.get("_auth_user_id"))

    def test_admin_can_unlock_from_the_list(self):
        boss = User.objects.create_user(username="boss", password="x", is_staff=True, is_superuser=True)
        self.wrong(4)
        self.client.force_login(boss)
        self.client.post(reverse("admin:avto_loginlock_changelist"), {
            "action": "unlock", "_selected_action": [LoginLock.objects.get().pk],
        })
        self.assertFalse(LoginLock.objects.exists())
        self.assertIsNotNone(self.ok())
