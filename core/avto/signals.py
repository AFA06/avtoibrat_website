from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from .models import LoginEvent


@receiver(user_logged_in)
def record_student_login(sender, user, **kwargs):
    if not (user.is_staff or user.is_superuser):
        LoginEvent.objects.create(user=user)
