# api/authentication.py
from drf_spectacular.extensions import OpenApiAuthenticationExtension
from rest_framework.authentication import SessionAuthentication


class CustomSessionAuthentication(SessionAuthentication):
    def authenticate_header(self, request):
        """
        Return a string value that will be used in the WWW-Authenticate
        header of the response. This forces Django REST Framework to
        return a 401 Unauthorized status instead of 403 Forbidden.
        """
        return "Session"


class CustomSessionAuthenticationScheme(OpenApiAuthenticationExtension):
    """Tells drf-spectacular how to describe our session-cookie auth in schema.yml."""

    target_class = "api.authentication.CustomSessionAuthentication"
    name = "sessionAuth"

    def get_security_definition(self, auto_schema):
        return {"type": "apiKey", "in": "cookie", "name": "sessionid"}
