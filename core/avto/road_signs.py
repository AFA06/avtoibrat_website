"""Road-sign ordering and slugs, shared by the student pages and the admin «Belgilar» section."""
import re

from django.db.models import Max
from django.utils.text import slugify

from .models import RoadSign, RoadSignCategory

_NUMBER_PART = re.compile(r"\d+")


def sign_sort_key(sign):
    """1.2 < 1.10 < 2.1 — numbers compare part by part; unnumbered signs go last, in upload order."""
    parts = tuple(int(p) for p in _NUMBER_PART.findall(sign.number))
    return (not parts, parts, sign.order, sign.pk)


def sorted_signs(category):
    return sorted(category.signs.all(), key=sign_sort_key)


def ordered_categories():
    """Categories in the teacher's order. Explicit order_by: annotated queries ignore Meta.ordering."""
    return RoadSignCategory.objects.order_by("order", "id")


def unique_slug(model, text, fallback="belgi"):
    base = slugify(text, allow_unicode=False) or fallback
    slug, n = base, 2
    while model.objects.filter(slug=slug).exists():
        slug, n = f"{base}-{n}", n + 1
    return slug


def next_order(model, **filters):
    return (model.objects.filter(**filters).aggregate(last=Max("order"))["last"] or 0) + 1
