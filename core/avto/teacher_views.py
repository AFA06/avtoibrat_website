"""Admin panel: teachers (staff accounts that can be assigned to groups). Superusers only."""
from django import forms
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import User, normalize_phone
from .student_forms import MIN_PASSWORD_LENGTH, PHONE_DIGITS, generate_password
from .student_views import _page


def superuser_required(view):
    """Only admins manage teachers — a teacher must not be able to delete the admin."""
    @staff_member_required
    def wrapped(request, *args, **kwargs):
        if not request.user.is_superuser:
            messages.error(request, "Bu bo‘lim faqat administrator uchun.")
            return redirect("admin:index")
        return view(request, *args, **kwargs)
    wrapped.__name__ = view.__name__
    return wrapped


def _teachers():
    return User.objects.filter(is_staff=True, is_superuser=False)


class TeacherForm(forms.ModelForm):
    phone = forms.CharField(label="Telefon raqami", max_length=12, required=False)
    password = forms.CharField(label="Parol", min_length=MIN_PASSWORD_LENGTH, max_length=64)

    class Meta:
        model = User
        fields = ("first_name", "last_name", "username", "phone")
        labels = {"first_name": "Ism", "last_name": "Familiya", "username": "Login (foydalanuvchi nomi)"}
        help_texts = {"username": "O‘qituvchi shu nom bilan kiradi (lotin harflari, raqamlar)."}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].required = self.fields["last_name"].required = True
        self.instance.is_staff = True  # so model validation treats this as staff (phone optional)
        if self.instance.pk:
            self.initial["phone"] = self.instance.phone_display
            self.initial["password"] = self.instance.initial_password

    def clean_phone(self):
        digits = normalize_phone(self.cleaned_data["phone"])
        if digits and len(digits) != PHONE_DIGITS:
            raise forms.ValidationError("Telefon raqami 99-999-99-99 ko‘rinishida bo‘lishi kerak.")
        return digits

    def save(self, commit=True):
        teacher = super().save(commit=False)
        teacher.is_staff = True
        teacher.unlimited = True
        teacher.initial_password = self.cleaned_data["password"].strip()
        teacher.set_password(teacher.initial_password)
        if commit:
            teacher.save()
        return teacher


@superuser_required
def teacher_list(request):
    query = request.GET.get("q", "").strip()
    teachers = _teachers().annotate(group_count=Count("taught_groups"))
    if query:
        teachers = teachers.filter(
            Q(first_name__icontains=query) | Q(last_name__icontains=query) | Q(username__icontains=query)
        )
    return render(request, "admin/teachers/list.html", _page(
        request, "O‘qituvchilar", teachers=teachers.order_by("first_name"), query=query,
        total=_teachers().count(),
    ))


@superuser_required
def teacher_form(request, pk=None):
    teacher = get_object_or_404(_teachers(), pk=pk) if pk else None
    form = TeacherForm(request.POST or None, instance=teacher)
    if request.method == "POST" and form.is_valid():
        saved = form.save()
        messages.success(request, f"{saved.get_full_name()} saqlandi. Login: {saved.username}, parol: {saved.initial_password}")
        return redirect("teachers:list")
    return render(request, "admin/teachers/form.html", _page(
        request, teacher.get_full_name() if teacher else "Yangi o‘qituvchi", form=form, teacher=teacher,
    ))


@superuser_required
@require_POST
def teacher_toggle(request, pk):
    teacher = get_object_or_404(_teachers(), pk=pk)
    teacher.is_blocked = not teacher.is_blocked
    teacher.save(update_fields=["is_blocked"])
    teacher.sync_active_status()
    messages.success(request, f"{teacher.get_full_name()} {'bloklandi' if teacher.is_blocked else 'faollashtirildi'}.")
    return redirect("teachers:list")


@superuser_required
@require_POST
def teacher_delete(request, pk):
    teacher = get_object_or_404(_teachers(), pk=pk)
    name = teacher.get_full_name()
    teacher.delete()
    messages.success(request, f"{name} o‘chirildi. Uning guruhlari o‘qituvchisiz qoldi.")
    return redirect("teachers:list")
