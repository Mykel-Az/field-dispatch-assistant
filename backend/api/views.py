from django.views.decorators.csrf import ensure_csrf_cookie
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

# Create your views here.
from .models import Skill
from .serializers import (
    HealthSerializer,
    RegisterSerializer,
    SkillSerializer,
    UserLoginSerializer,
    UserSerializer,
)
from .services.accounts import login, logout


@extend_schema(responses=HealthSerializer)
@api_view(["GET"])
@permission_classes([AllowAny])
def health_check(request):
    """
    Health check endpoint to verify the API is running.
    """
    return Response({"status": "ok"}, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([AllowAny])
@ensure_csrf_cookie
def get_csrf_token(request):
    """Get a CSRF token. Responds with 204 No Content."""
    return Response(status=status.HTTP_204_NO_CONTENT)


class Registerview(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class Loginview(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle]

    def post(self, request):

        user = UserLoginSerializer(data=request.data)
        if user.is_valid():
            login(request, user)
            return Response(UserSerializer(user).data, status=status.HTTP_200_OK)
        return Response(
            {"detail": "Invalid email or password"}, status=status.HTTP_401_UNAUTHORIZED
        )


class Logoutview(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)


class SkillViewSet(generics.ListAPIView):
    """
    API endpoint that allows skills to be viewed or created.
    """

    queryset = Skill.objects.all()
    serializer_class = SkillSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None  # Disable pagination for this view
