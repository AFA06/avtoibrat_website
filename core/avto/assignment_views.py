"""Admin panel: daily test tasks for Express students or a group (/admin/assignments/)."""
from django import forms
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .assignments import progress, summary
from .models import Assignment, StudyGroup
from .student_views import _page


class AssignmentForm(forms.ModelForm):
    class Meta:
        model = Assignment
        fields = ("title", "audience", "group", "tests_per_day", "start_date", "end_date", "note", "is_active")
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "end_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "note": forms.Textarea(attrs={"rows": 3, "placeholder": "Masalan: har kuni kechgacha, xatolar ustida ishlang"}),
            "title": forms.TextInput(attrs={"placeholder": "Masalan: Kunlik 25 ta test"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["group"].queryset = StudyGroup.objects.select_related("branch")
        self.fields["group"].empty_label = "— Guruhni tanlang —"
        self.fields["group"].label_from_instance = lambda g: f"{g.name} · {g.category}"
        self.fields["group"].required = False
        self.fields["audience"].widget = forms.RadioSelect(choices=Assignment.AUDIENCE_CHOICES)


def _with_summary(assignment, today):
    rows = progress(assignment, today=today)
    assignment.summary = summary(rows)
    assignment.running = assignment.runs_on(today)
    return assignment


@staff_member_required
def assignment_list(request):
    today = timezone.localdate()
    assignments = [_with_summary(a, today) for a in Assignment.objects.select_related("group")]
    return render(request, "admin/assignments/list.html", _page(
        request, "Vazifalar", assignments=assignments,
        running_count=sum(1 for a in assignments if a.running),
    ))


@staff_member_required
def assignment_form(request, pk=None):
    assignment = get_object_or_404(Assignment, pk=pk) if pk else None
    form = AssignmentForm(request.POST or None, instance=assignment)
    if request.method == "POST" and form.is_valid():
        saved = form.save(commit=False)
        saved.created_by = saved.created_by or request.user
        saved.save()
        messages.success(request, f"«{saved.title}» vazifasi saqlandi.")
        return redirect("assignments:detail", pk=saved.pk)
    return render(request, "admin/assignments/form.html", _page(
        request, assignment.title if assignment else "Yangi vazifa", form=form, assignment=assignment,
    ))


@staff_member_required
def assignment_detail(request, pk):
    assignment = get_object_or_404(Assignment.objects.select_related("group"), pk=pk)
    today = timezone.localdate()
    rows = progress(assignment, today=today)
    return render(request, "admin/assignments/detail.html", _page(
        request, assignment.title,
        assignment=assignment, rows=rows, stats=summary(rows), running=assignment.runs_on(today), today=today,
    ))


@staff_member_required
@require_POST
def assignment_delete(request, pk):
    assignment = get_object_or_404(Assignment, pk=pk)
    title = assignment.title
    assignment.delete()
    messages.success(request, f"«{title}» vazifasi o‘chirildi.")
    return redirect("assignments:list")
