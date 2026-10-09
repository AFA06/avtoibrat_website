from django.urls import path

from . import assignment_views as views

app_name = "assignments"

urlpatterns = [
    path("", views.assignment_list, name="list"),
    path("new/", views.assignment_form, name="create"),
    path("<int:pk>/", views.assignment_detail, name="detail"),
    path("<int:pk>/edit/", views.assignment_form, name="edit"),
    path("<int:pk>/delete/", views.assignment_delete, name="delete"),
]
