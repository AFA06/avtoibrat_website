from django.urls import path

from . import monitoring_views as views

app_name = "monitoring"

urlpatterns = [
    path("", views.overview, name="overview"),
    path("group/<int:pk>/", views.group_monitor, name="group"),
    path("group/ungrouped/", views.group_monitor, name="ungrouped"),
    path("student/<int:pk>/", views.student_monitor, name="student"),
    path("session/<int:pk>/", views.session_detail, name="session"),
]
