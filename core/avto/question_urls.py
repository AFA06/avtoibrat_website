from django.urls import path

from . import question_views as views

app_name = "questions"

urlpatterns = [
    path("", views.question_list, name="list"),
    path("new/", views.question_form, name="create"),
    path("<int:pk>/", views.question_form, name="edit"),
    path("<int:pk>/audio/<str:language>/", views.question_audio, name="audio"),
    path("<int:pk>/delete/", views.question_delete, name="delete"),
]
