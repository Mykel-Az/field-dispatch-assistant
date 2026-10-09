from django.urls import path
from .views import health_check, skills

urlpatterns = [
    path('health/', health_check, name='health_check'),
    path('skills/', skills, name='skills'),
]