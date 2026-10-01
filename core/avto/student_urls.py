from django.urls import path

from . import student_views as views

app_name = "students"

urlpatterns = [
    path("", views.student_list, name="list"),
    path("new/", views.student_create, name="create"),
    path("suggest-password/", views.suggest_password, name="suggest_password"),
    path("<int:pk>/", views.student_edit, name="edit"),
    path("<int:pk>/toggle/", views.student_toggle, name="toggle"),
    path("<int:pk>/reset-password/", views.student_reset_password, name="reset_password"),
    path("<int:pk>/delete/", views.student_delete, name="delete"),
]
