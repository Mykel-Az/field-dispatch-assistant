from django.contrib.auth import login, logout
from django.views.decorators.csrf import ensure_csrf_cookie
from drf_spectacular.utils import extend_schema
from rest_framework import generics, mixins, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from api.mixins import TenantScopedViewMixin
from api.permissions import IsHeadDispatcher
from api.services.accounts import LastHeadError, create_staff_user, deactivate_user

# Create your views here.
from .models import Skill
from .serializers import (
    HealthSerializer,
    RegisterSerializer,
    SkillSerializer,
    StaffCreateSerializer,
    User,
    UserLoginSerializer,
    UserSerializer,
)


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
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "register"

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class Loginview(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):

        serialzer = UserLoginSerializer(
            data=request.data, context={"request": request._request}
        )
        if serialzer.is_valid():
            authenticated_user = serialzer.context["user"]
            login(request, authenticated_user)
            return Response(
                UserSerializer(authenticated_user).data, status=status.HTTP_200_OK
            )
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


class UserViewSet(
    TenantScopedViewMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = User.objects.all()
    permission_classes = [IsHeadDispatcher]

    def get_serializer_class(self):
        return StaffCreateSerializer if self.action == "create" else UserSerializer

    def perform_create(self, serializer):
        serializer.instance = create_staff_user(
            creator=self.request.user, **serializer.validated_data
        )

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        target = self.get_object()  # 404 for another org
        try:
            deactivate_user(actor=request.user, target=target)
        except LastHeadError:
            return Response({"detail": "Last active head dispatcher."}, status=409)
        return Response(UserSerializer(target).data)


class SkillViewSet(generics.ListAPIView):
    """
    API endpoint that allows skills to be viewed or created.
    """

    queryset = Skill.objects.all()
    serializer_class = SkillSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None  # Disable pagination for this view
