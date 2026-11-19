"""Small display helpers for the admin pages."""
from django import template

register = template.Library()

_SYSTEMS = (("iPhone", "iPhone"), ("iPad", "iPad"), ("Android", "Android"), ("Windows", "Windows"),
            ("Mac OS", "Mac"), ("CrOS", "Chromebook"), ("Linux", "Linux"))
_BROWSERS = (("Edg/", "Edge"), ("OPR/", "Opera"), ("YaBrowser", "Yandex"), ("Firefox", "Firefox"),
             ("Chrome", "Chrome"), ("Safari", "Safari"))


@register.filter
def device_name(user_agent):
    """«Android · Chrome» from a browser's user-agent string."""
    ua = user_agent or ""
    system = next((name for key, name in _SYSTEMS if key in ua), "Noma’lum qurilma")
    browser = next((name for key, name in _BROWSERS if key in ua), "")
    return f"{system} · {browser}" if browser else system


@register.filter
def som(amount):
    """4500000 → «4 500 000» (non-breaking spaces between thousands, as prices are written in Uzbekistan)."""
    try:
        return f"{int(amount):,}".replace(",", " ")
    except (TypeError, ValueError):
        return amount
