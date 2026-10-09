import dj_database_url
from .base import *

SECRET_KEY = "test-only-secret-key"

DATABASES = {"default": dj_database_url.config(default="sqlite:///:memory:")}