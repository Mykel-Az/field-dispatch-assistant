import pytest
from rest_framework.test import APIClient

from .models import Skill

# Create your tests here.


@pytest.mark.django_db
def test_seed_skills_present():
    names = set(Skill.objects.values_list("name", flat=True))
    assert {"HVAC", "Electrical", "Appliance Repair"} <= names


def test_health_check():
    response = APIClient().get("/api/health/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.django_db
def test_get_skills():
    response = APIClient().get("/api/skills/")
    assert response.status_code == 200
    assert len(response.json()) >= 3
