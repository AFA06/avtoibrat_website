"""Student-facing marathon: pick a section size, then a section; questions keep a fixed order (/marafon/)."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from . import marathon
from .models import UserAnswer


def _size_label(size):
    return _("Barcha savollar") if size == marathon.ALL else _("%(n)s talik") % {"n": size}


@login_required
def marathon_page(request):
    available = marathon.question_pool().count()
    active = marathon.active_session(request.user)
    return render(request, "dashboard/marathon.html", {
        "options": [{**o, "label": _size_label(o["size"])} for o in marathon.size_options(available)],
        "available": available,
        "all_size": marathon.ALL,
        "active": active,
        "all_active": active if active and active.marathon_size == marathon.ALL else None,
        "active_total": len(active.question_order) if active else 0,
        "active_answered": UserAnswer.objects.filter(session=active).count() if active else 0,
    })


@login_required
def marathon_sections(request, size):
    if not marathon.is_valid_size(size):
        raise Http404
    if size == marathon.ALL:  # one run, nothing to pick: started from the size page
        return redirect("marathon")
    if size != marathon.ALL and size > marathon.question_pool().count():
        return redirect("marathon")
    rows = marathon.sections(request.user, size)
    if not rows:
        return redirect("marathon")
    for row in rows:
        row["time"] = marathon.duration_label(row["minutes"])
    return render(request, "dashboard/marathon_sections.html", {
        "size": size,
        "size_label": _size_label(size),
        "sections": rows,
        "done_count": sum(row["state"] == "done" for row in rows),
        "total_questions": sum(row["total"] for row in rows),
    })


@login_required
@require_POST
def start_marathon(request):
    try:
        size = int(request.POST.get("size", ""))
        number = int(request.POST.get("section", ""))
        session = marathon.start(request.user, size, number)
    except ValueError:
        messages.error(request, _("Bunday bo‘lim topilmadi."))
        return redirect("marathon")
    return redirect("test_page", session_id=session.id)
