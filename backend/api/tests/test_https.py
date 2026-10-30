"""Behind Render's proxy: plain http is redirected to https, except the health check.

The test settings leave the redirect off, so these tests switch on the same
settings config/settings/prod.py uses.
"""

import pytest
from django.test import Client


@pytest.fixture
def prod_https(settings):
    settings.SECURE_SSL_REDIRECT = True
    settings.SECURE_REDIRECT_EXEMPT = [r"^api/health/$"]
    settings.SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    settings.ALLOWED_HOSTS = ["testserver"]


def test_http_requests_are_redirected_to_https(prod_https):
    response = Client().get("/api/skills/")
    assert response.status_code == 301
    assert response["Location"].startswith("https://")


def test_the_health_check_answers_over_plain_http(prod_https):
    assert Client().get("/api/health/").status_code == 200


def test_requests_the_proxy_marks_as_https_are_not_redirected(prod_https):
    response = Client().get("/api/skills/", HTTP_X_FORWARDED_PROTO="https")
    assert response.status_code == 401  # reached the API: signed-out, not redirected
