"""Student account rules: phone format, password generation and the create/edit form."""
import re
import secrets
from datetime import datetime, time

from django import forms
from django.utils import timezone

from .models import StudyGroup, User, normalize_phone

PHONE_DIGITS = 9
MIN_PASSWORD_LENGTH = 6


def generate_password():
    """Generate an unpredictable temporary password."""
    return secrets.token_urlsafe(15)


def group_label(group):
    """«52 · B · Ibrat Karimov · Du-Ju 18:00» — enough to pick the right group at a glance."""
    teacher = group.teacher.get_full_name() or group.teacher.username if group.teacher_id else "o‘qituvchisiz"
    parts = [group.name, group.category, teacher, group.lesson_time]
    return " · ".join(p for p in parts if p)


class StudentForm(forms.ModelForm):
    phone = forms.CharField(label="Telefon raqami", max_length=12)
    password = forms.CharField(label="Vaqtinchalik parol", min_length=MIN_PASSWORD_LENGTH, max_length=64, required=False)
    account_expires_at = forms.DateField(
        label="Kirish muddati (gacha)",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        help_text="Bo‘sh qoldirilsa — muddatsiz.",
    )

    class Meta:
        model = User
        fields = ("first_name", "last_name", "phone", "group", "group_language", "birth_date", "device_limit")
        widgets = {"birth_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}

    def __init__(self, *args, groups=None, require_group=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].label = "Ism"
        self.fields["last_name"].label = "Familiya"
        self.fields["group"].label = "O‘quv guruhi"
        self.fields["first_name"].required = True
        self.fields["last_name"].required = True
        self.fields["group"].queryset = (groups if groups is not None else StudyGroup.objects.all()).select_related("branch", "teacher")
        self.fields["group"].required = require_group
        self.fields["group"].empty_label = "— Guruhsiz —"
        self.fields["group"].label_from_instance = group_label
        self.fields["device_limit"].required = False
        self.fields["device_limit"].widget.attrs.update({"min": 1, "max": 30})
        if self.instance.pk:
            self.fields["group"].label = "Boshqa guruhga o‘tkazish"
            self.fields["group"].help_text = (
                "Yangi guruhni tanlab saqlang — guruh, o‘qituvchi va dars vaqti avtomatik yangilanadi."
            )
        if self.instance.pk:
            self.initial["phone"] = self.instance.phone_display
            if not self.instance.unlimited and self.instance.account_expires_at:
                self.initial["account_expires_at"] = timezone.localtime(self.instance.account_expires_at).date()

    def clean_phone(self):
        digits = normalize_phone(self.cleaned_data["phone"])
        if not re.fullmatch(rf"\d{{{PHONE_DIGITS}}}", digits):
            raise forms.ValidationError("Telefon raqami 99-999-99-99 ko‘rinishida bo‘lishi kerak.")
        if User.objects.exclude(pk=self.instance.pk).filter(username=digits).exists():
            raise forms.ValidationError("Bu telefon raqami boshqa foydalanuvchida mavjud.")
        return digits

    def clean_account_expires_at(self):
        expires = self.cleaned_data["account_expires_at"]
        if expires and expires < timezone.localdate() and expires != self._saved_expiry():
            raise forms.ValidationError("Muddat o‘tib ketgan sana bo‘lishi mumkin emas — talaba kira olmaydi.")
        return expires

    def _saved_expiry(self):
        """Editing keeps an already-expired date as is; only a newly typed past date is rejected."""
        return self.initial.get("account_expires_at")

    def clean_device_limit(self):
        # Left empty: keep what the student has (3 for a new one).
        return self.cleaned_data.get("device_limit") or self.instance.device_limit or 3

    def save(self, commit=True):
        student = super().save(commit=False)
        student.username = student.phone
        student.is_staff = False
        self.temporary_password = self.cleaned_data["password"] or (generate_password() if student._state.adding else "")
        if self.temporary_password:
            student.set_password(self.temporary_password)
            student.must_change_password = True

        expires = self.cleaned_data["account_expires_at"]
        student.unlimited = expires is None
        if expires:
            end_of_day = datetime.combine(expires, time.max)
            student.account_expires_at = timezone.make_aware(end_of_day)
            student.account_started_at = student.account_started_at or timezone.now()
        else:
            student.account_expires_at = None
        if commit:
            if student._state.adding:
                student.save()
            else:
                fields = (*self._meta.fields, "username", "unlimited", "account_expires_at", "account_started_at")
                if self.temporary_password:
                    fields += ("password", "must_change_password")
                student.save(update_fields=fields)
            student.sync_active_status()
        return student
