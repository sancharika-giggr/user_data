# myapp/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('api/', views.api_handler, name='api_handler'),
    path('view/', views.my_view, name='my_view'),
    path('profile/', views.linkedin_profile, name='linkedin_profile'),
    path('cdn/', views.cdn, name='cdn'),
]
