"""Student-facing leaderboard: rank inside the group and among all students."""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .leaderboard import PERIODS, SORTS, build, split_podium
from .models import User

TOP_CHOICES = (10, 20, 50)
METRICS = {key: value for key, value in SORTS.items() if key != "name"}


def _rank_of(rows, user):
    return next((row for row in rows if row.student.pk == user.pk), None)


@login_required
def student_leaderboard(request):
    user = request.user
    everyone = User.objects.filter(is_staff=False, is_superuser=False).select_related("group")
    has_group = bool(user.group_id)

    scope = request.GET.get("scope") or ("group" if has_group else "all")
    if scope == "group" and not has_group:
        scope = "all"
    period = request.GET.get("period") if request.GET.get("period") in PERIODS else "all"
    metric = request.GET.get("metric") if request.GET.get("metric") in METRICS else "points"
    top = int(request.GET["top"]) if request.GET.get("top") in map(str, TOP_CHOICES) else TOP_CHOICES[0]
    query = request.GET.get("q", "").strip().lower()

    overall = build(everyone, period, metric)
    in_group = build(everyone.filter(group_id=user.group_id), period, metric) if has_group else []
    rows = in_group if scope == "group" else overall
    me = _rank_of(rows, user)

    if query:
        rows = [r for r in rows if query in r.public_name.lower()]
        podium, rest = [], rows[:top]
    else:
        podium, rest = split_podium(rows)
        rest = rest[:max(top - len(podium), 0)]
    return render(request, "dashboard/leaderboard.html", {
        "podium": podium, "rest": rest,
        "me": me, "me_outside": me is not None and me not in podium + rest,
        "my_group_rank": _rank_of(in_group, user), "group_size": len(in_group),
        "my_overall_rank": _rank_of(overall, user), "overall_size": len(overall),
        "scope": scope, "has_group": has_group, "period": period, "periods": PERIODS,
        "metric": metric, "metrics": METRICS, "top": top, "top_choices": TOP_CHOICES, "query": query,
    })
