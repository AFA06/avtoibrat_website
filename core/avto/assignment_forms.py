"""Audience and exact-content validation for the school task editor."""
from django import forms
from django.db.models import Q

from .admin_access import groups_for, students_for
from .models import Assignment, TestCategory, Topic, User

DATE_WIDGETS = {
    "start_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    "end_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    "note": forms.Textarea(attrs={"rows": 3}),
}


class LegacyAssignmentForm(forms.ModelForm):
    """Keep existing daily plans editable without silently changing their meaning."""
    class Meta:
        model = Assignment
        fields = ("title", "audience", "group", "tests_per_day", "start_date", "end_date", "note", "is_active")
        widgets = DATE_WIDGETS

    def __init__(self, *args, staff, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["group"].queryset = groups_for(staff)
        choices = [("express", "Express kursi"), ("group", "Guruh")]
        if not staff.is_superuser:
            choices = [("group", "Guruh")]
        self.fields["audience"].widget = forms.RadioSelect(choices=choices)
        self.fields["audience"].choices = choices


class StudentChoices(forms.ModelMultipleChoiceField):
    def label_from_instance(self, student):
        name = student.get_full_name() or student.username
        detail = f" · {student.phone_display}" if student.phone else f" · {student.username}"
        return name + detail + (f" · Guruh {student.group.name}" if student.group_id else "")


class TopicChoices(forms.ModelMultipleChoiceField):
    def label_from_instance(self, topic):
        return f"{topic.group.nomi_uzb} — {topic.nomi_uzb}"


class AssignmentForm(forms.ModelForm):
    express_students = StudentChoices(queryset=User.objects.none(), required=False, label="Express talabalarini tanlang", widget=forms.CheckboxSelectMultiple)
    individual_students = StudentChoices(queryset=User.objects.none(), required=False, label="Talabalarni tanlang", widget=forms.CheckboxSelectMultiple)
    topics = TopicChoices(queryset=Topic.objects.none(), required=False, label="Mavzularni tanlang", widget=forms.CheckboxSelectMultiple)

    class Meta:
        model = Assignment
        fields = ("title", "audience", "group", "recipient_scope", "content_type", "bilets", "topics", "start_date", "end_date", "note", "is_active")
        widgets = {
            **DATE_WIDGETS,
            "audience": forms.RadioSelect,
            "recipient_scope": forms.RadioSelect,
            "content_type": forms.RadioSelect,
            "bilets": forms.CheckboxSelectMultiple,
            "title": forms.TextInput(attrs={"placeholder": "Masalan: Dushanba kungi vazifa"}),
        }

    def __init__(self, *args, staff, **kwargs):
        super().__init__(*args, **kwargs)
        self.staff = staff
        self.fields["recipient_scope"].required = False
        self.fields["title"].required = False
        self.fields["title"].label = "Vazifa nomi (ixtiyoriy)"
        self.fields["end_date"].label = "Oxirgi topshirish kuni (ixtiyoriy)"
        self.fields["content_type"].choices = [("bilet", "Biletlar"), ("topic", "Mavzulashtirilgan testlar")]
        self.fields["content_type"].initial = "bilet"
        if not self.instance.pk:
            self.initial.update(content_type="bilet", audience="express" if staff.is_superuser else "group", recipient_scope="all")
        elif not self.instance.is_selection:
            self.initial["content_type"] = "bilet"
        self.fields["group"].queryset = groups_for(staff).select_related("branch")
        self.fields["group"].label_from_instance = lambda group: f"{group.name} · {group.category} · {group.branch.name}"
        self.fields["group"].empty_label = "Guruhni tanlang"
        if not staff.is_superuser:
            self.fields["audience"].choices = [("express", "Express kursi talabalari"), ("group", "Bitta guruh")]
            self.fields["recipient_scope"].choices = [("all", "Mening barcha Express talabalarim"), ("selected", "Faqat tanlangan talabalar")]
        visible = students_for(staff).filter(archived_at__isnull=True).select_related("group").order_by("first_name", "last_name", "pk")
        self.fields["express_students"].queryset = visible.filter(is_express=True)
        self.fields["individual_students"].queryset = visible.filter(group__isnull=True, is_express=False)
        self.fields["bilets"].queryset = TestCategory.objects.filter(
            aktiv=True, show_in_shablon=True, question__is_archived=False,
        ).distinct().order_by("tartib", "pk")
        self.fields["bilets"].label = "Biletlarni tanlang"
        self.fields["topics"].queryset = Topic.objects.filter(aktiv=True).filter(
            Q(questions__is_archived=False, questions__kategoriya__aktiv=True)
            | Q(extra_questions__is_archived=False, extra_questions__kategoriya__aktiv=True)
        ).select_related("group").distinct().order_by("group__tartib", "tartib", "pk")
        for field in ("express_students", "individual_students", "bilets", "topics"):
            self.fields[field].error_messages["invalid_choice"] = "Tanlangan yozuv mavjud emas yoki sizga ruxsat berilmagan. Ro‘yxatdan qayta tanlang."
        if self.instance.pk:
            recipient_ids = list(self.instance.recipients.values_list("pk", flat=True))
            self.initial["express_students"] = self.initial["individual_students"] = recipient_ids

    def clean(self):
        data = super().clean()
        audience = data.get("audience")
        scope = data.get("recipient_scope") or "all"
        data["recipient_scope"] = scope
        recipients = User.objects.none()
        if audience == "group":
            if not data.get("group"):
                self.add_error("group", "Vazifa beriladigan guruhni tanlang.")
            data["recipient_scope"] = "all"
        elif audience == "express":
            data["group"] = None
            if scope == "selected":
                recipients = data.get("express_students", User.objects.none())
                if not recipients:
                    self.add_error("express_students", "Kamida bitta Express talabasini tanlang.")
            else:
                recipients = self.fields["express_students"].queryset
                if not recipients.exists():
                    self.add_error("audience", "Express kursida siz vazifa bera oladigan talabalar yo‘q.")
            # Teachers' all-Express choice is a bounded selection of their own students.
            if not self.staff.is_superuser:
                data["recipient_scope"] = "selected"
        elif audience == "individual":
            data["group"] = None
            data["recipient_scope"] = "selected"
            recipients = data.get("individual_students", User.objects.none())
            if not recipients:
                self.add_error("individual_students", "Kamida bitta guruhsiz, Express kursida bo‘lmagan talabani tanlang.")
        data["_recipients"] = recipients
        kind = data.get("content_type")
        if kind in ("bilet", "topic"):
            field = "bilets" if kind == "bilet" else "topics"
            chosen = data.get(field)
            if not chosen:
                self.add_error(field, "Kamida bitta biletni tanlang." if kind == "bilet" else "Kamida bitta mavzuni tanlang.")
            other = "topics" if field == "bilets" else "bilets"
            data[other] = self.fields[other].queryset.none()
            if not data.get("title"):
                data["title"] = f"{'Biletlar' if kind == 'bilet' else 'Mavzular'} · {len(chosen) if chosen is not None else 0} ta test"
        return data

    def _save_m2m(self):
        super()._save_m2m()
        recipients = self.cleaned_data["_recipients"]
        if self.instance.audience == "group" or (self.instance.audience == "express" and self.instance.recipient_scope == "all"):
            recipients = User.objects.none()
        self.instance.recipients.set(recipients)
