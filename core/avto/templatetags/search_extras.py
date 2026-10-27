"""Showing where a search query was found: the text around the first match, every match marked."""
import re

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def highlight(text, query, length=160):
    """`text` escaped, cut to about `length` characters around the first match, with each match in <mark>."""
    text, query = str(text or ""), str(query or "").strip()
    found = re.search(re.escape(query), text, re.IGNORECASE) if query else None
    if len(text) > length:
        start = max(0, found.start() - length // 3) if found else 0
        end = start + length
        text = ("…" if start else "") + text[start:end] + ("…" if end < len(text) else "")
    if not query:
        return escape(text)
    parts = re.split(f"({re.escape(query)})", text, flags=re.IGNORECASE)
    return mark_safe("".join(f"<mark>{escape(p)}</mark>" if i % 2 else escape(p) for i, p in enumerate(parts)))
