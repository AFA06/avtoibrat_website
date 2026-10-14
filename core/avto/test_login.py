import os
from datetime import timedelta
from io import StringIO
from unittest import mock

from django.core.management import call_command

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .student_forms import StudentForm


class StudentLoginTests(TestCase):
    def create_student(self, **extra):
        form = StudentForm({
            "first_name": "Ali", "last_name": "Valiyev", "phone": "90-123-45-67",
            "password": "Ali2006", "group_language": "uz", **extra,
        })
        self.assertTrue(form.is_valid(), form.errors)
        return form.save()

    def login(self, language, phone="90-123-45-67", password="Ali2006"):
        return self.client.post(
            f"/{language}/login/", {"role": "student", "username": phone, "password": password, "accept_terms": "1"}, follow=True,
        )

    def test_student_created_in_admin_can_log_in_under_every_language(self):
        self.create_student()
        for language in ("uz", "ru", "uz-kr"):
            self.client.logout()
            response = self.login(language)
            self.assertEqual(response.redirect_chain[-1][0].split("?")[0].rstrip("/").split("/")[-1], "dashboard", language)
            self.assertEqual(response.status_code, 200, language)

    def test_wrong_password_is_rejected(self):
        self.create_student()
        response = self.login("ru", password="nope")
        self.assertIn("error=invalid", response.redirect_chain[-1][0])


class ExpiryValidationTests(TestCase):
    def form(self, expires, instance=None):
        return StudentForm({
            "first_name": "Ali", "last_name": "Valiyev", "phone": "90-123-45-67", "password": "Ali2006",
            "group_language": "uz", "account_expires_at": expires.isoformat(),
        }, instance=instance)

    def test_new_student_cannot_get_an_already_past_expiry(self):
        past = timezone.localdate() - timedelta(days=1)
        self.assertIn("account_expires_at", self.form(past).errors)

    def test_today_and_future_are_fine(self):
        self.assertTrue(self.form(timezone.localdate()).is_valid())

    def test_editing_an_expired_student_keeps_working(self):
        student = StudentForm({
            "first_name": "Ali", "last_name": "Valiyev", "phone": "90-123-45-67", "password": "Ali2006", "group_language": "uz",
        }).save()
        student.unlimited = False
        student.account_expires_at = timezone.now() - timedelta(days=3)
        student.save()
        same_date = timezone.localtime(student.account_expires_at).date()
        self.assertTrue(self.form(same_date, instance=student).is_valid())


class SeedDemoTests(TestCase):
    def test_demo_student_can_log_in_with_the_number_the_form_accepts(self):
        with mock.patch.dict(os.environ, {"DEMO_PASSWORD": "demo-pass-1"}):
            call_command("seed_demo", stdout=StringIO())
        response = self.client.post(reverse("login"), {
            "role": "student", "username": "99-999-99-99", "password": "demo-pass-1", "accept_terms": "1",
        })
        self.assertRedirects(response, reverse("dashboard"), fetch_redirect_response=False)
