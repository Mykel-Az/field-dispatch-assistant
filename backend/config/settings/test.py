import dj_database_url

from .base import *

SECRET_KEY = "test-only-secret-key"

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

DATABASES = {"default": dj_database_url.config(default="sqlite:///:memory:")}

GEOCODER_CLASS = "geocoding.fake.FakeGeocoder"
