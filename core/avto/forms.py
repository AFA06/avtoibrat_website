from django.contrib.auth.forms import UserCreationForm
from django import forms
from .models import User

class UserCreateForm(UserCreationForm):
    password1 = forms.CharField(
        label="Parol",
        widget=forms.TextInput(attrs={
            "type": "text",
            "class": "vTextField",
        })
    )

    password2 = forms.CharField(
        label="Parolni tasdiqlash",
        widget=forms.TextInput(attrs={
            "type": "text",
            "class": "vTextField",
        })
    )

    device_limit = forms.IntegerField(
        label="Qurilmalar limiti",
        min_value=1,
        max_value=30,
        initial=1,
        help_text="User nechta qurilmadan login qila oladi"
    )

    class Meta:
        model = User
        fields = ("username", "phone", "device_limit")

