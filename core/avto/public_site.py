"""Forms on the public site: «sign me up» on the home page and «write to us» on the contact page.

Spam guards, all database-based so they hold across Gunicorn workers:
- a hidden «website» field people never see; a bot that fills it is told «sent» and nothing is saved;
- the same phone number is saved at most once a day per form (a repeat still shows «sent»);
- at most MAX_PER_HOUR messages are saved per hour per form, so a flood cannot fill the database.
"""
import re
from datetime import timedelta

from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .models import ConsultRequest, ContactMessage

HONEYPOT = "website"
MAX_PER_HOUR = 40
CATEGORIES = ("A", "B", "BC", "C", "D")
CONTACT_TOPICS = (
    ("course", _("Kursga yozilish")),
    ("platform", _("Onlayn platforma")),
    ("other", _("Boshqa savol")),
)
# Saved in Uzbek whatever the visitor's language, so the admin list reads the same for everyone.
CONTACT_SUBJECTS = {"course": "Kursga yozilish", "platform": "Onlayn platforma", "other": "Boshqa savol"}


def normalize_phone(raw):
    """«+998 (90) 123-45-67» → «+998901234567»; a 9-digit local number gets the +998 prefix."""
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 9:
        digits = "998" + digits
    if len(digits) != 12 or not digits.startswith("998"):
        return None
    return "+" + digits


def _check(post, model, extra_fields):
    """Shared validation. Returns (ok, errors, values, phone); ok without errors and phone=None means «pretend sent»."""
    values = {
        "name": (post.get("name") or "").strip()[:100],
        "phone": (post.get("phone") or "").strip()[:30],
        "message": (post.get("message") or "").strip()[:1000],
    }
    for field, allowed in extra_fields.items():
        value = (post.get(field) or "").strip()
        values[field] = value if value in allowed else ""
    if post.get(HONEYPOT):
        return True, {}, values, None

    errors = {}
    if len(values["name"]) < 2:
        errors["name"] = _("Ismingizni yozing")
    phone = normalize_phone(values["phone"])
    if not phone:
        errors["phone"] = _("Telefon raqamni to‘liq yozing, masalan +998 90 123 45 67")
    if errors:
        return False, errors, values, None

    now = timezone.now()
    if model.objects.filter(phone=phone, created_at__gte=now - timedelta(days=1)).exists():
        return True, {}, values, None
    if model.objects.filter(created_at__gte=now - timedelta(hours=1)).count() >= MAX_PER_HOUR:
        return False, {"form": _("Hozir so‘rovlar juda ko‘p. Iltimos, bizga qo‘ng‘iroq qiling.")}, values, None
    return True, {}, values, phone


def handle_consult_form(post):
    """Home page sign-up. Returns (ok, errors, values); ok=True means show «sent»."""
    ok, errors, values, phone = _check(post, ConsultRequest, {"category": CATEGORIES})
    if ok and phone:
        ConsultRequest.objects.create(
            first_name=values["name"], phone=phone, category=values["category"], message=values["message"],
        )
    return ok, errors, values


def handle_contact_form(post):
    """Contact page message. Returns (ok, errors, values); ok=True means show «sent»."""
    ok, errors, values, phone = _check(post, ContactMessage, {"topic": CONTACT_SUBJECTS})
    if ok and phone:
        ContactMessage.objects.create(
            name=values["name"], phone=phone, subject=CONTACT_SUBJECTS[values["topic"] or "other"],
            message=values["message"],
        )
    return ok, errors, values
