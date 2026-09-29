"""Create (or reset) the demo student used on the hosted demo.

    DEMO_PASSWORD=... python manage.py seed_demo
"""
import os

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
            defaults={"first_name": "Demo", "last_name": "Talaba", "phone": "9999999", "unlimited": True},
        )
        user.set_password(password)
        user.is_active = True
        user.save()
        self.stdout.write("demo student ready (phone 9999999)")
