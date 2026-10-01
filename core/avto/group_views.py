"""Admin panel: study groups (list, create, edit, delete, group page) and the leaderboard."""
from django import forms
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, F, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .leaderboard import PERIODS, SORTS, build, sort_rows
from .models import StudyGroup, User
from .student_views import _page, _students


def _time_choices(first=7, last=22):
    slots = [f"{h:02d}:{m:02d}" for h in range(first, last + 1) for m in (0, 30) if (h, m) <= (last, 0)]
    return [("", "— Tanlang —")] + [(t, t) for t in slots]


class GroupForm(forms.ModelForm):
    lesson_days = forms.MultipleChoiceField(
        label="Dars kunlari", required=False, choices=StudyGroup.LESSON_DAYS,
        widget=forms.CheckboxSelectMultiple,
    )
    lesson_start = forms.TimeField(label="Boshlanishi", required=False, widget=forms.Select(choices=_time_choices()))
    lesson_end = forms.TimeField(label="Tugashi", required=False, widget=forms.Select(choices=_time_choices()))

    class Meta:
        model = StudyGroup
        fields = ("name", "category", "branch", "teacher", "lesson_start", "lesson_end")
        labels = {
            "name": "Guruh raqami yoki nomi", "category": "Ta’lim toifasi",
            "branch": "Filial", "teacher": "O‘qituvchi",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["teacher"].queryset = User.objects.filter(is_staff=True).order_by("first_name")
        self.fields["teacher"].empty_label = "— Biriktirilmagan —"
        self.fields["teacher"].label_from_instance = lambda u: u.get_full_name() or u.username
        if self.instance.pk:
            self.initial["lesson_days"] = [str(n) for n in self.instance.lesson_day_numbers]
            for name in ("lesson_start", "lesson_end"):
                value = getattr(self.instance, name)
                self.initial[name] = f"{value:%H:%M}" if value else ""

    def clean(self):
        data = super().clean()
        start, end = data.get("lesson_start"), data.get("lesson_end")
        if bool(start) != bool(end):
            raise forms.ValidationError("Dars boshlanishi va tugashini ikkalasini ham tanlang.")
        if start and end and end <= start:
            self.add_error("lesson_end", "Tugash vaqti boshlanishdan keyin bo‘lishi kerak.")
        return data

    def save(self, commit=True):
        group = super().save(commit=False)
        group.lesson_days = "".join(sorted(self.cleaned_data["lesson_days"]))
        if commit:
            group.save()
        return group


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
        form=form, group=group,
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
        candidates=_students().exclude(group=group).order_by(F("group").asc(nulls_first=True), "first_name"),
        solved_total=sum(r.solved for r in rows),
        active_count=sum(1 for r in rows if r.tests),
    ))


@staff_member_required
@require_POST
def group_add_students(request, pk):
    group = get_object_or_404(StudyGroup, pk=pk)
    moved = _students().filter(pk__in=request.POST.getlist("students")).update(group=group)
    if moved:
        messages.success(request, f"{moved} ta talaba «{group.name}» guruhiga qo‘shildi.")
    else:
        messages.error(request, "Hech kim tanlanmadi.")
    return redirect("groups:detail", pk=group.pk)


@staff_member_required
@require_POST
def group_remove_student(request, pk, student_id):
    group = get_object_or_404(StudyGroup, pk=pk)
    _students().filter(pk=student_id, group=group).update(group=None)
    messages.success(request, "Talaba guruhdan chiqarildi.")
    return redirect("groups:detail", pk=group.pk)


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
