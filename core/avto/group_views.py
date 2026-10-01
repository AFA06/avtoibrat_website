"""Admin panel: study groups (list, create, edit, delete, group page) and the leaderboard."""
from django import forms
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .leaderboard import PERIODS, SORTS, build, sort_rows
from .models import Branch, StudyGroup, User
from .student_views import _page, _students


class GroupForm(forms.ModelForm):
    class Meta:
        model = StudyGroup
        fields = ("name", "category", "branch", "teacher")
        labels = {
            "name": "Guruh raqami yoki nomi", "category": "Ta’lim toifasi",
            "branch": "Filial", "teacher": "O‘qituvchi",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["teacher"].empty_label = "— Biriktirilmagan —"
        self.fields["teacher"].label_from_instance = lambda u: u.get_full_name() or u.username


def _summaries(groups):
    """Per-group student count, average accuracy, total points and current leader."""
    ranked = build(_students())
    by_group = {}
    for row in ranked:
        by_group.setdefault(row.student.group_id, []).append(row)
    for group in groups:
        rows = by_group.get(group.pk, [])
        accuracies = [r.accuracy for r in rows if r.accuracy is not None]
        group.leader = rows[0] if rows and rows[0].points else None
        group.points_total = sum(r.points for r in rows)
        group.accuracy_avg = round(sum(accuracies) / len(accuracies)) if accuracies else None
    return groups


@staff_member_required
def group_list(request):
    query = request.GET.get("q", "").strip()
    category = request.GET.get("category", "")
    groups = StudyGroup.objects.select_related("branch", "teacher").annotate(
        student_count=Count("students", filter=Q(students__is_staff=False)),
    )
    if query:
        groups = groups.filter(Q(name__icontains=query) | Q(teacher__first_name__icontains=query)
                               | Q(teacher__last_name__icontains=query) | Q(branch__name__icontains=query))
    if category in dict(StudyGroup.CATEGORY_CHOICES):
        groups = groups.filter(category=category)
    return render(request, "admin/groups/list.html", _page(
        request, "Guruhlar",
        groups=_summaries(list(groups.order_by("name"))),
        query=query, category=category, categories=StudyGroup.CATEGORY_CHOICES,
        total=StudyGroup.objects.count(),
        ungrouped=_students().filter(group__isnull=True).count(),
    ))


@staff_member_required
def group_form(request, pk=None):
    group = get_object_or_404(StudyGroup, pk=pk) if pk else None
    form = GroupForm(request.POST or None, instance=group)
    if request.method == "POST" and form.is_valid():
        saved = form.save()
        messages.success(request, f"«{saved.name}» guruhi saqlandi.")
        return redirect("groups:detail", pk=saved.pk)
    return render(request, "admin/groups/form.html", _page(
        request, group.name if group else "Yangi guruh",
        form=form, group=group, has_branches=Branch.objects.exists(),
    ))


@staff_member_required
def group_detail(request, pk):
    group = get_object_or_404(StudyGroup.objects.select_related("branch", "teacher"), pk=pk)
    period = request.GET.get("period", "all")
    sort = request.GET.get("sort", "points")
    rows = build(_students().filter(group=group), period)
    accuracies = [r.accuracy for r in rows if r.accuracy is not None]
    return render(request, "admin/groups/detail.html", _page(
        request, group.name,
        group=group, rows=sort_rows(rows, sort), period=period, sort=sort,
        periods=PERIODS, sorts=SORTS, period_label=PERIODS.get(period, PERIODS['all'])[0].lower(),
        accuracy_avg=round(sum(accuracies) / len(accuracies)) if accuracies else None,
        solved_total=sum(r.solved for r in rows),
        active_count=sum(1 for r in rows if r.tests),
    ))


@staff_member_required
@require_POST
def group_delete(request, pk):
    group = get_object_or_404(StudyGroup, pk=pk)
    name = group.name
    group.delete()
    messages.success(request, f"«{name}» guruhi o‘chirildi. Talabalar guruhsiz qoldi.")
    return redirect("groups:list")


@staff_member_required
def leaderboard(request):
    group_id = request.GET.get("group", "")
    period = request.GET.get("period", "all")
    sort = request.GET.get("sort", "points")
    query = request.GET.get("q", "").strip()

    students = _students()
    if group_id.isdigit():
        students = students.filter(group_id=group_id)
    rows = build(students, period)
    if query:
        rows = [r for r in rows if query.lower() in r.student.get_full_name().lower()]
    return render(request, "admin/groups/leaderboard.html", _page(
        request, "Reyting",
        rows=sort_rows(rows, sort), group_id=group_id, period=period, sort=sort, query=query,
        groups=StudyGroup.objects.select_related("branch"), periods=PERIODS, sorts=SORTS,
    ))
