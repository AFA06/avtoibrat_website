from django.urls import path
from . import lecture_admin_views as v
app_name = 'lectures'
urlpatterns = [
    path('', v.overview, name='list'),
    path('new/', v.topic_form, name='new'),
    path('<int:pk>/edit/', v.topic_form, name='edit'),
    path('<int:pk>/action/<str:action>/', v.topic_action, name='action'),
    path('<int:pk>/<str:lang>/', v.detail, name='topic'),
    path('<int:pk>/<str:lang>/new/', v.page_form, name='page_new'),
    path('<int:pk>/<str:lang>/upload/', v.upload, name='upload'),
    path('<int:pk>/<str:lang>/<int:page_id>/edit/', v.page_form, name='page_edit'),
    path('<int:pk>/<str:lang>/action/<str:action>/', v.page_action, name='page_action'),
]
