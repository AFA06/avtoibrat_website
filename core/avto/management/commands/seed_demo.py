"""Create (or reset) the demo student used on the hosted demo.

    DEMO_PASSWORD=... python manage.py seed_demo
"""
import os

# The login form takes a full 9-digit number (99-999-99-99), so the demo uses one too.
DEMO_PHONE = "999999999"

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create or update the demo student account from the DEMO_PASSWORD environment variable."

    def handle(self, *args, **options):
        password = os.environ.get("DEMO_PASSWORD")
        if not password:
            raise CommandError("Set DEMO_PASSWORD first.")
        User = get_user_model()
        user, _ = User.objects.get_or_create(
            username="demo_student",
            defaults={"first_name": "Demo", "last_name": "Talaba", "unlimited": True},
        )
        user.phone = DEMO_PHONE
        user.set_password(password)
        user.is_active = True
        user.save()
        self.stdout.write("demo student ready (phone 99-999-99-99)")
