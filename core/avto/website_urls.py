from django.urls import path
from . import website_views as views

app_name = 'website'
urlpatterns = [
    path('', views.overview, name='overview'),
    path('<str:kind>/', views.listing, name='list'),
    path('<str:kind>/edit/', views.edit, name='edit'),
    path('<str:kind>/new/', views.edit, name='create'),
    path('<str:kind>/<int:pk>/edit/', views.edit, name='update'),
    path('<str:kind>/<int:pk>/delete/', views.delete, name='delete'),
    path('<str:kind>/<int:pk>/visibility/', views.toggle, name='toggle'),
]
