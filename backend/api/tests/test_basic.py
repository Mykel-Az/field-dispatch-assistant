import pytest
from rest_framework.test import APIClient

from api.models import Skill

# Create your tests here.


@pytest.mark.django_db
def test_seed_skills_present():
    names = set(Skill.objects.values_list("name", flat=True))
    assert names == {
        "Contractors & Handymen",
        "Plumbers",
        "Electricians",
        "Heating & Air Conditioning",
        "Appliances and Repair",
        "Roofing",
        "Locksmiths",
        "Painters",
        "Landscaping",
        "Nurseries & Gardening",
        "Florists",
        "Tree Services",
        "Home Cleaning",
        "Furniture Stores",
        "Movers",
    }


def test_health_check():
    response = APIClient().get("/api/health/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
