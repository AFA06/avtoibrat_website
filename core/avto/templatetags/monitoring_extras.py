from django import template

register = template.Library()


@register.filter
def duration(seconds):
    """3725 -> «1 soat 2 daq», 95 -> «1 daq 35 s», 40 -> «40 s», empty -> «—»."""
    if not seconds:
        return "—"
    hours, rest = divmod(int(seconds), 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours} soat {minutes} daq"
    return f"{minutes} daq {secs} s" if minutes else f"{secs} s"
