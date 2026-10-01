from django.urls import path

from . import group_views as views

app_name = "groups"

urlpatterns = [
    path("", views.group_list, name="list"),
    path("new/", views.group_form, name="create"),
    path("<int:pk>/", views.group_detail, name="detail"),
    path("<int:pk>/edit/", views.group_form, name="edit"),
    path("<int:pk>/delete/", views.group_delete, name="delete"),
]
