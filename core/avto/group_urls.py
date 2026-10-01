from django.urls import path

from . import group_views as views

app_name = "groups"

urlpatterns = [
    path("", views.group_list, name="list"),
    path("new/", views.group_form, name="create"),
    path("<int:pk>/", views.group_detail, name="detail"),
    path("<int:pk>/edit/", views.group_form, name="edit"),
    path("<int:pk>/students/add/", views.group_add_students, name="add_students"),
    path("<int:pk>/students/<int:student_id>/remove/", views.group_remove_student, name="remove_student"),
    path("<int:pk>/delete/", views.group_delete, name="delete"),
]
