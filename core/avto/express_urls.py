from django.urls import path

from . import express_views as views

app_name = "express"

urlpatterns = [
    path("", views.express_list, name="list"),
    path("add/", views.express_add, name="add"),
    path("<int:pk>/remove/", views.express_remove, name="remove"),
]
