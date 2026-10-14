"""Terms of use and the user guide (public pages), and the record of a user accepting the terms."""
from django.utils import timezone

# Date of the current terms. Change it whenever the terms text changes, so new acceptances are told apart.
TERMS_VERSION = "2026-10-14"
TERMS_FIELD = "accept_terms"


def accepted(post_data):
    return post_data.get(TERMS_FIELD) == "1"


def record_acceptance(user):
    type(user).objects.filter(pk=user.pk).update(terms_accepted_at=timezone.now(), terms_version=TERMS_VERSION)
