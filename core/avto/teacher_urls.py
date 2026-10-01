from django.urls import path

from . import teacher_views as views

app_name = "teachers"

urlpatterns = [
    path("", views.teacher_list, name="list"),
    path("new/", views.teacher_form, name="create"),
    path("<int:pk>/", views.teacher_form, name="edit"),
    path("<int:pk>/toggle/", views.teacher_toggle, name="toggle"),
    path("<int:pk>/delete/", views.teacher_delete, name="delete"),
]
