from django.urls import path

from . import question_views as views

app_name = "questions"

urlpatterns = [
    path("", views.question_list, name="list"),
    path("new/", views.question_form, name="create"),
    path("<int:pk>/", views.question_form, name="edit"),
    path("<int:pk>/picture/", views.question_picture, name="picture"),
    path("<int:pk>/audio/<str:language>/", views.question_audio, name="audio"),
    path("<int:pk>/audio/<str:language>/delete/", views.question_audio_delete, name="audio_delete"),
    path("<int:pk>/delete/", views.question_delete, name="delete"),
]
