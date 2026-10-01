"""Student account rules: phone format, password generation and the create/edit form."""
import re
import secrets
from datetime import datetime, time

from django import forms
from django.utils import timezone

from .models import StudyGroup, User, normalize_phone

PHONE_DIGITS = 9
MIN_PASSWORD_LENGTH = 6
NAME_PART_LENGTH = 4

_CYRILLIC_TO_LATIN = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo", "ж": "j", "з": "z",
    "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r",
    "с": "s", "т": "t", "у": "u", "ф": "f", "х": "x", "ц": "s", "ч": "ch", "ш": "sh", "щ": "sh",
    "ъ": "", "ы": "i", "ь": "", "э": "e", "ю": "yu", "я": "ya", "ў": "o", "қ": "q", "ғ": "g",
    "ҳ": "h",
}


def generate_password(first_name="", birth_date=None, *, randomize=False):
    """Short memorable password: first letters of the name + birth year (Abdu2006).

    Falls back to four random digits when the year is unknown or `randomize` is set,
    so the teacher can always get a different suggestion.
    """
    latin = "".join(_CYRILLIC_TO_LATIN.get(c, c) for c in (first_name or "").strip().lower())
    letters = re.sub(r"[^a-z]", "", latin)[:NAME_PART_LENGTH].capitalize() or "Talaba"
    if birth_date and not randomize:
        return f"{letters}{birth_date.year}"
    return f"{letters}{secrets.randbelow(9000) + 1000}"


def group_label(group):
    """«52 · B · Ibrat Karimov · Du-Ju 18:00» — enough to pick the right group at a glance."""
    teacher = group.teacher.get_full_name() or group.teacher.username if group.teacher_id else "o‘qituvchisiz"
    parts = [group.name, group.category, teacher, group.lesson_time]
    return " · ".join(p for p in parts if p)


class StudentForm(forms.ModelForm):
    phone = forms.CharField(label="Telefon raqami", max_length=12)
    password = forms.CharField(label="Parol", min_length=MIN_PASSWORD_LENGTH, max_length=64)
    account_expires_at = forms.DateField(
        label="Kirish muddati (gacha)",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        help_text="Bo‘sh qoldirilsa — muddatsiz.",
    )

    class Meta:
        model = User
        fields = ("first_name", "last_name", "phone", "group", "group_language", "birth_date")
        widgets = {"birth_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].label = "Ism"
        self.fields["last_name"].label = "Familiya"
        self.fields["group"].label = "O‘quv guruhi"
        self.fields["first_name"].required = True
        self.fields["last_name"].required = True
        self.fields["group"].queryset = StudyGroup.objects.select_related("branch", "teacher")
        self.fields["group"].empty_label = "— Guruhsiz —"
        self.fields["group"].label_from_instance = group_label
        if self.instance.pk:
            self.fields["group"].label = "Boshqa guruhga o‘tkazish"
            self.fields["group"].help_text = (
                "Yangi guruhni tanlab saqlang — guruh, o‘qituvchi va dars vaqti avtomatik yangilanadi."
            )
        if self.instance.pk:
            self.initial["phone"] = self.instance.phone_display
            self.initial["password"] = self.instance.initial_password
            if not self.instance.unlimited and self.instance.account_expires_at:
                self.initial["account_expires_at"] = timezone.localtime(self.instance.account_expires_at).date()

    def clean_phone(self):
        digits = normalize_phone(self.cleaned_data["phone"])
        if not re.fullmatch(rf"\d{{{PHONE_DIGITS}}}", digits):
            raise forms.ValidationError("Telefon raqami 99-999-99-99 ko‘rinishida bo‘lishi kerak.")
        if User.objects.exclude(pk=self.instance.pk).filter(username=digits).exists():
            raise forms.ValidationError("Bu telefon raqami boshqa foydalanuvchida mavjud.")
        return digits

    def clean_password(self):
        return self.cleaned_data["password"].strip()

    def save(self, commit=True):
        student = super().save(commit=False)
        student.username = student.phone
        student.is_staff = False
        student.initial_password = self.cleaned_data["password"]
        student.set_password(student.initial_password)

        expires = self.cleaned_data["account_expires_at"]
        student.unlimited = expires is None
        if expires:
            end_of_day = datetime.combine(expires, time.max)
            student.account_expires_at = timezone.make_aware(end_of_day)
            student.account_started_at = student.account_started_at or timezone.now()
        else:
            student.account_expires_at = None
        if commit:
            student.save()
            student.sync_active_status()
        return student
