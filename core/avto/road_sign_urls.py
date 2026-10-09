from django.urls import path

from . import road_sign_views as views

app_name = "signs"

urlpatterns = [
    path("", views.overview, name="list"),
    path("categories/new/", views.category_form, name="category_create"),
    path("categories/<int:pk>/", views.category_detail, name="category"),
    path("categories/<int:pk>/edit/", views.category_form, name="category_edit"),
    path("categories/<int:pk>/move/<str:direction>/", views.category_move, name="category_move"),
    path("categories/<int:pk>/delete/", views.category_delete, name="category_delete"),
    path("new/", views.sign_form, name="sign_create"),
    path("<int:pk>/", views.sign_form, name="sign_edit"),
    path("<int:pk>/delete/", views.sign_delete, name="sign_delete"),
]
