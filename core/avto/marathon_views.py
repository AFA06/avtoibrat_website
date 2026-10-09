"""Student-facing marathon: pick a range, start, resume (/marafon/)."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from . import marathon
from .models import TestSession, UserAnswer

HISTORY_LIMIT = 5


def _history(user):
    sessions = (
        TestSession.objects.filter(user=user, source=marathon.SOURCE, finished_at__isnull=False)
        .order_by("-finished_at")[:HISTORY_LIMIT]
    )
    rows = []
    for session in sessions:
        total = len(session.question_order)
        correct = UserAnswer.objects.filter(session=session, is_correct=True).count()
        rows.append({
            "session": session, "total": total, "correct": correct,
            "percent": round(correct * 100 / total) if total else 0,
        })
    return rows


@login_required
def marathon_page(request):
    available = marathon.question_pool().count()
    active = marathon.active_session(request.user)
    return render(request, "dashboard/marathon.html", {
        "options": [
            {**o, "label": marathon.duration_label(o["minutes"])} for o in marathon.size_options(available)
        ],
        "available": available,
        "active": active,
        "active_total": len(active.question_order) if active else 0,
        "active_answered": UserAnswer.objects.filter(session=active).count() if active else 0,
        "history": _history(request.user),
    })


@login_required
@require_POST
def start_marathon(request):
    try:
        size = int(request.POST.get("size", ""))
        session = marathon.start(request.user, size)
    except ValueError:
        messages.error(request, _("Bu miqdordagi savollar hozircha yetarli emas."))
        return redirect("marathon")
    return redirect("test_page", session_id=session.id)
