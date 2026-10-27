"""Imtihonga yo‘l: the bilets laid out as a road of four seasons that ends at the real exam.

Everything here is derived from finished test sessions, so the journey can never disagree with
the student's real results:

* Stage   — one bilet. Cleared by a full practice run of it with at most 2 mistakes (the real exam
            rule); stars: 3 = no mistakes, 2 = one, 1 = two. The best run counts.
* Season  — a quarter of the bilets in order (Bahor, Yoz, Kuz, Qish). A season opens when the one
            before it is fully cleared; bilets cleared earlier on the Shablon page still count.
* Final   — every season cleared and two real exams passed in a row. Earns the readiness certificate.
* Readiness — 75 % bilet mastery (average best score over all bilets, untried = 0) plus 25 % exam
            form (passes among the last three real exams). It reaches 100 only with the certificate.
"""
from collections import defaultdict
from math import ceil

from django.utils import timezone
from django.utils.translation import gettext as _

from . import real_exam
from .models import TestCategory, TestSession, UserAnswer

ALLOWED_MISTAKES = 2
RUN_KEY = "journey_run"  # django-session key: the bilet run started from the road
SEASON_KEYS = ("spring", "summer", "autumn", "winter")
FINAL_STREAK = 2
FORM_WINDOW = 3
MASTERY_WEIGHT = 0.75


def _season_names():
    return {
        "spring": (_("Bahor"), _("Yo‘lga chiqish")),
        "summer": (_("Yoz"), _("Tezlikni oshirish")),
        "autumn": (_("Kuz"), _("Ishonch")),
        "winter": (_("Qish"), _("Mahorat sinovi")),
    }


def stars_for(correct, size):
    mistakes = size - correct
    return 3 - mistakes if mistakes <= ALLOWED_MISTAKES else 0


def _bilets():
    return list(TestCategory.objects.filter(aktiv=True, show_in_shablon=True).order_by("tartib", "id"))


def _bilet_runs(user, bilet_ids):
    """Every finished, full-length practice run of a bilet: (category_id, correct, size, finished_at)."""
    sessions = list(
        TestSession.objects
        .filter(user=user, test_kind="shablon", source__in=("shablon", "ohshash"), topic__isnull=True,
                category_id__in=bilet_ids, finished_at__isnull=False)
        .values("id", "category_id", "question_order", "finished_at")
    )
    correct = defaultdict(int)
    for session_id in UserAnswer.objects.filter(session_id__in=[s["id"] for s in sessions], is_correct=True) \
            .values_list("session_id", flat=True):
        correct[session_id] += 1
    return [(s["category_id"], correct[s["id"]], len(s["question_order"]), s["finished_at"]) for s in sessions]


def _stage(bilet, runs, number):
    full = [(c, size, at) for c, size, at in runs if size >= bilet.question_count]
    best = max((c * 100 // size for c, size, _at in full), default=None)
    best_stars = max((stars_for(c, size) for c, size, _at in full), default=0)
    first_clear = min((at for c, size, at in full if stars_for(c, size)), default=None)
    return {
        "id": bilet.id,
        "number": number,
        "name": bilet.nomi,
        "attempts": len(runs),
        "best": best,
        "stars": best_stars,
        "cleared": best_stars > 0,
        "cleared_at": first_clear,
    }


def _real_exams(user):
    """Finished real exams, oldest first, with whether each one was passed."""
    sessions = list(
        TestSession.objects.filter(user=user, test_kind="real", finished_at__isnull=False)
        .order_by("finished_at").values("id", "question_order", "finished_at")
    )
    tally = defaultdict(lambda: [0, 0])  # session -> [answered, wrong]
    for session_id, is_correct in UserAnswer.objects.filter(
        session_id__in=[s["id"] for s in sessions], selected_answer__isnull=False,
    ).values_list("session_id", "is_correct"):
        tally[session_id][0] += 1
        tally[session_id][1] += 0 if is_correct else 1
    return [
        {"passed": real_exam.passed(len(s["question_order"]), tally[s["id"]][1], tally[s["id"]][0]),
         "at": s["finished_at"]}
        for s in sessions
    ]


def _first_streak_end(exams, length):
    """When the student first passed `length` real exams in a row, or None."""
    run = 0
    for exam in exams:
        run = run + 1 if exam["passed"] else 0
        if run >= length:
            return exam["at"]
    return None


def _tier(percent):
    if percent >= 100:
        return "ready", _("Imtihonga tayyor")
    if percent >= 75:
        return "close", _("Deyarli tayyor")
    if percent >= 40:
        return "rising", _("O‘sib bormoqda")
    return "start", _("Boshlang‘ich")


def build(user):
    bilets = _bilets()
    runs = defaultdict(list)
    for category_id, correct, size, at in _bilet_runs(user, [b.id for b in bilets]):
        runs[category_id].append((correct, size, at))
    stages = [_stage(b, runs[b.id], i + 1) for i, b in enumerate(bilets)]

    per_season = ceil(len(stages) / len(SEASON_KEYS)) if stages else 0
    names = _season_names()
    seasons, previous_done = [], True
    for index, key in enumerate(SEASON_KEYS):
        chunk = stages[index * per_season:(index + 1) * per_season]
        cleared = sum(s["cleared"] for s in chunk)
        done = bool(chunk) and cleared == len(chunk)
        unlocked = previous_done
        current = next((s for s in chunk if not s["cleared"]), None) if unlocked and not done else None
        title, motto = names[key]
        seasons.append({
            "key": key, "index": index + 1, "title": title, "motto": motto,
            "stages": chunk, "cleared": cleared, "total": len(chunk),
            "stars": sum(s["stars"] for s in chunk), "max_stars": 3 * len(chunk),
            "done": done, "unlocked": unlocked,
            "current_id": current["id"] if current else None,
            "done_at": max((s["cleared_at"] for s in chunk), default=None) if done else None,
            "percent": round(cleared * 100 / len(chunk)) if chunk else 0,
            "first": chunk[0]["number"] if chunk else None,
            "last": chunk[-1]["number"] if chunk else None,
        })
        previous_done = done

    exams = _real_exams(user)
    seasons_done = bool(stages) and all(s["done"] for s in seasons)
    streak_at = _first_streak_end(exams, FINAL_STREAK)
    certified = seasons_done and streak_at is not None
    current_streak = 0
    for exam in reversed(exams):
        if not exam["passed"]:
            break
        current_streak += 1

    mastery = sum((s["best"] or 0) for s in stages) / (100 * len(stages)) if stages else 0
    recent = exams[-FORM_WINDOW:]
    form = sum(e["passed"] for e in recent) / FORM_WINDOW
    readiness = 100 if certified else min(99, round(100 * (MASTERY_WEIGHT * mastery + (1 - MASTERY_WEIGHT) * form)))
    tier, tier_label = _tier(readiness)

    week_ago = timezone.now() - timezone.timedelta(days=7)
    active = next((s for s in seasons if s["unlocked"] and not s["done"]), None)
    next_stage = next((st for st in active["stages"] if st["id"] == active["current_id"]), None) if active else None

    return {
        "seasons": seasons,
        "active_key": active["key"] if active else ("final" if seasons_done else SEASON_KEYS[0]),
        "next_stage": next_stage,
        "active_season": active,
        "seasons_done": sum(s["done"] for s in seasons),
        "stages_total": len(stages),
        "stages_cleared": sum(s["cleared"] for s in stages),
        "stars": sum(s["stars"] for s in stages),
        "max_stars": 3 * len(stages),
        "week_cleared": sum(1 for s in stages if s["cleared_at"] and s["cleared_at"] >= week_ago),
        "readiness": readiness,
        "mastery": round(mastery * 100),
        "form_passes": sum(e["passed"] for e in recent),
        "form_window": FORM_WINDOW,
        "tier": tier,
        "tier_label": tier_label,
        "final": {
            "unlocked": seasons_done,
            "streak": min(current_streak, FINAL_STREAK),
            "needed": FINAL_STREAK,
            "certified": certified,
            "certified_at": max(streak_at, max(s["done_at"] for s in seasons)) if certified else None,
            "certificate_no": f"AI-{user.pk:05d}-{len(stages):02d}",
        },
    }


def client_data(journey):
    """The part of the journey the map script needs, as plain JSON."""
    return {
        "active": journey["active_key"],
        "seasons": [
            {
                "key": s["key"], "title": str(s["title"]), "motto": str(s["motto"]),
                "unlocked": s["unlocked"], "done": s["done"], "current": s["current_id"],
                "stars": s["stars"], "max_stars": s["max_stars"],
                "stages": [
                    {"id": st["id"], "n": st["number"], "stars": st["stars"], "cleared": st["cleared"],
                     "best": st["best"], "attempts": st["attempts"]}
                    for st in s["stages"]
                ],
            }
            for s in journey["seasons"]
        ],
        "cleared": journey["stages_cleared"],
        "readiness": journey["readiness"],
        "certified": journey["final"]["certified"],
    }
