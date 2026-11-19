"""The public home page's «sign me up» form.

Spam guards, all database-based so they hold across Gunicorn workers:
- a hidden «website» field people never see; a bot that fills it is told «sent» and nothing is saved;
- the same phone number is saved at most once a day (a repeat still shows «sent», the school already has it);
- at most MAX_PER_HOUR requests are saved per hour in total, so a flood cannot fill the database.
"""
import re
from datetime import timedelta

from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .models import ConsultRequest

HONEYPOT = "website"
MAX_PER_HOUR = 40
CATEGORIES = ("A", "B", "BC", "C", "D")


def normalize_phone(raw):
    """«+998 (90) 123-45-67» → «+998901234567»; a 9-digit local number gets the +998 prefix."""
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 9:
        digits = "998" + digits
    if len(digits) != 12 or not digits.startswith("998"):
        return None
    return "+" + digits


def handle_consult_form(post):
    """Validate and save a request. Returns (ok, errors, values); ok=True means show «sent»."""
    values = {
        "name": (post.get("name") or "").strip()[:100],
        "phone": (post.get("phone") or "").strip()[:30],
        "category": (post.get("category") or "").strip(),
        "message": (post.get("message") or "").strip()[:1000],
    }
    if post.get(HONEYPOT):
        return True, {}, values

    errors = {}
    if len(values["name"]) < 2:
        errors["name"] = _("Ismingizni yozing")
    phone = normalize_phone(values["phone"])
    if not phone:
        errors["phone"] = _("Telefon raqamni to‘liq yozing, masalan +998 90 123 45 67")
    if values["category"] not in CATEGORIES:
        values["category"] = ""
    if errors:
        return False, errors, values

    now = timezone.now()
    if ConsultRequest.objects.filter(phone=phone, created_at__gte=now - timedelta(days=1)).exists():
        return True, {}, values
    if ConsultRequest.objects.filter(created_at__gte=now - timedelta(hours=1)).count() >= MAX_PER_HOUR:
        return False, {"form": _("Hozir so‘rovlar juda ko‘p. Iltimos, bizga qo‘ng‘iroq qiling.")}, values

    ConsultRequest.objects.create(
        first_name=values["name"], phone=phone, category=values["category"], message=values["message"],
    )
    return True, {}, values
