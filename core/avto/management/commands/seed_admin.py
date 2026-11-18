"""Create the initial admin account used on the hosted site.

    ADMIN_USERNAME=admin ADMIN_PASSWORD=... python manage.py seed_admin
"""
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create the initial superuser from ADMIN_USERNAME / ADMIN_PASSWORD environment variables."

    def handle(self, *args, **options):
        username = os.environ.get("ADMIN_USERNAME", "admin")
        User = get_user_model()
        if User.objects.filter(username=username).exists():
            self.stdout.write("Initial admin already exists.")
            return
        password = os.environ.get("ADMIN_PASSWORD")
        if not password:
            raise CommandError("Set ADMIN_PASSWORD first.")
        User.objects.create_superuser(username=username, password=password)
        self.stdout.write(f"admin ready (username {username})")
