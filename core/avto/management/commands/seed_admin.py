"""Create (or reset) the admin account used on the hosted site.

    ADMIN_USERNAME=admin ADMIN_PASSWORD=... python manage.py seed_admin
"""
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create or update the superuser from ADMIN_USERNAME / ADMIN_PASSWORD environment variables."

    def handle(self, *args, **options):
        username = os.environ.get("ADMIN_USERNAME", "admin")
        password = os.environ.get("ADMIN_PASSWORD")
        if not password:
            raise CommandError("Set ADMIN_PASSWORD first.")
        User = get_user_model()
        user, _ = User.objects.get_or_create(username=username)
        user.is_staff = user.is_superuser = user.is_active = True
        user.set_password(password)
        user.save()
        self.stdout.write(f"admin ready (username {username})")
