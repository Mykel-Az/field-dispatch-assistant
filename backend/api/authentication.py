# api/authentication.py
from rest_framework.authentication import SessionAuthentication


class CustomSessionAuthentication(SessionAuthentication):
    def authenticate_header(self, request):
        """
        Return a string value that will be used in the WWW-Authenticate
        header of the response. This forces Django REST Framework to
        return a 401 Unauthorized status instead of 403 Forbidden.
        """
        return "Session"
