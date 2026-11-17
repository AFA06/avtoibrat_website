from django.test import TestCase
from django.urls import reverse

from . import legal
from .models import DEVICE_COOKIE, User, UserDevice

PHONE = "901112233"


class DeviceLimitTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(username="ali", password="pass-123", phone=PHONE, unlimited=True)

    def login(self, client=None, ua="Mozilla/5.0 (Linux; Android 14) Chrome/120"):
        client = client or self.client_class()
        response = client.post(reverse("login"), {
            "role": "student", "username": PHONE, "password": "pass-123", legal.TERMS_FIELD: "1",
        }, HTTP_USER_AGENT=ua)
        return client, response

    def test_new_students_get_three_devices(self):
        self.assertEqual(User.objects.create_user(username="x", password="x").device_limit, 3)

    def test_fourth_device_is_refused_and_retrying_does_not_sneak_in(self):
        for _ in range(3):
            self.assertEqual(self.login()[1].url, reverse("dashboard"))
        fourth = self.client_class()
        for _ in range(2):
            _, response = self.login(fourth)
            self.assertIn("device_limit=1", response.url)
        self.assertEqual(self.student.devices.count(), 3)

    def test_same_browser_is_one_device_even_when_the_network_changes(self):
        client, _ = self.login()
        for ip in ("10.0.0.1", "192.168.1.5", "85.1.2.3"):
            client.post(reverse("logout"))
            client.post(reverse("login"), {"role": "student", "username": PHONE, "password": "pass-123",
                                           legal.TERMS_FIELD: "1"}, REMOTE_ADDR=ip)
        self.assertEqual(self.student.devices.count(), 1)

    def test_device_cookie_is_long_lived_and_http_only(self):
        _, response = self.login()
        cookie = response.cookies[DEVICE_COOKIE]
        self.assertTrue(cookie["httponly"])
        self.assertGreater(int(cookie["max-age"]), 365 * 24 * 3600)

    def test_forged_cookie_value_is_replaced(self):
        client = self.client_class()
        client.cookies[DEVICE_COOKIE] = "x" * 500
        _, response = self.login(client)
        self.assertNotEqual(response.cookies[DEVICE_COOKIE].value, "x" * 500)

    def test_staff_are_not_limited(self):
        User.objects.create_user(username="ustoz", password="pass-123", is_staff=True, device_limit=1)
        for _ in range(3):
            response = self.client_class().post(reverse("login"), {
                "role": "staff", "username": "ustoz", "password": "pass-123", legal.TERMS_FIELD: "1"})
            self.assertNotIn("device_limit", response.url)

    def test_admin_sees_devices_and_removing_one_frees_a_place(self):
        for _ in range(3):
            self.login()
        admin = User.objects.create_user(username="boss", password="x", is_staff=True, is_superuser=True)
        self.client.force_login(admin)
        page = self.client.get(reverse("students:edit", args=[self.student.pk]))
        self.assertContains(page, "Android · Chrome")
        self.assertContains(page, "3 / 3")
        device = self.student.devices.first()
        self.client.post(reverse("students:remove_device", args=[self.student.pk, device.pk]))
        self.assertEqual(self.student.devices.count(), 2)
        self.assertEqual(self.login()[1].url, reverse("dashboard"))
