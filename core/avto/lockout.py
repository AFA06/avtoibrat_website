"""Locks an account after repeated wrong passwords.

4 wrong passwords within an hour lock the account for 5 minutes; failing again after a lock makes the
next lock longer (15 minutes, then 1 hour at most). A correct password clears the count, and a day
without failures forgets earlier locks.

Locks are per account, never per IP: students share school computers behind one address, and an IP
lock would shut out a whole classroom. While an account is locked even the right password is refused,
so guessing cannot continue. The lock lives in the authentication backend, so the student/staff form
and Django's /admin/login/ are both covered.
"""
from datetime import timedelta
import math

from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.signals import user_login_failed
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.dispatch import receiver
from django.utils import timezone

MAX_FAILURES = 4
FAILURE_WINDOW = timedelta(hours=1)  # failures older than this no longer count
LOCK_STEPS = (timedelta(minutes=5), timedelta(minutes=15), timedelta(hours=1))
FORGET_AFTER = timedelta(days=1)  # a quiet day resets the lock level


def _key(username):
    return (username or "").strip().lower()


def locked_for(username):
    """Seconds left on this account's lock, or 0 when it may sign in."""
    from .models import LoginLock

    lock = LoginLock.objects.filter(username=_key(username)).first()
    if not lock or not lock.locked_until:
        return 0
    return max(0, math.ceil((lock.locked_until - timezone.now()).total_seconds()))


def minutes_left(username):
    return math.ceil(locked_for(username) / 60)


def record_failure(username):
    """Count one wrong password; lock the account when the limit is reached."""
    from .models import LoginLock

    from django.contrib.auth import get_user_model

    key = _key(username)
    # Only real accounts get a row: guessing random usernames must not fill the table.
    if not key or not get_user_model().objects.filter(username__iexact=key).exists():
        return
    now = timezone.now()
    with transaction.atomic():
        lock, _ = LoginLock.objects.select_for_update().get_or_create(username=key)
        if lock.locked_until and lock.locked_until > now:
            return  # attempts during a lock are refused anyway; they don't stretch it
        if lock.last_failure and now - lock.last_failure > FORGET_AFTER:
            lock.level = 0
        if not lock.last_failure or now - lock.last_failure > FAILURE_WINDOW:
            lock.failures = 0
        lock.failures += 1
        lock.last_failure = now
        if lock.failures >= MAX_FAILURES:
            lock.locked_until = now + LOCK_STEPS[min(lock.level, len(LOCK_STEPS) - 1)]
            lock.level += 1
            lock.failures = 0
        lock.save()


def clear(username):
    from .models import LoginLock

    LoginLock.objects.filter(username=_key(username)).delete()


class LockoutBackend(ModelBackend):
    """The normal username/password check, refused while the account is locked."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get("phone") or kwargs.get(self._username_field())
        if username and locked_for(username):
            raise PermissionDenied  # stops authenticate() without trying the password
        user = super().authenticate(request, username=username, password=password, **kwargs)
        if user is not None:
            clear(username)
        return user

    @staticmethod
    def _username_field():
        from django.contrib.auth import get_user_model

        return get_user_model().USERNAME_FIELD


@receiver(user_login_failed)
def _count_failure(sender, credentials, request=None, **kwargs):
    record_failure(credentials.get("username"))
