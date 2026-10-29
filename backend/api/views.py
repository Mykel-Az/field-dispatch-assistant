from django.contrib.auth import login, logout, update_session_auth_hash
from django.db import transaction
from django.db.models import Prefetch
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from drf_spectacular.utils import extend_schema
from rest_framework import generics, mixins, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .exceptions import Conflict
from .mixins import TenantScopedViewMixin
from .models import (
    GeocodeStatus,
    Job,
    JobStatusHistory,
    Organization,
    Skill,
    Technician,
)
from .permissions import IsDispatcher, IsHeadDispatcher, IsSignedInMember
from .serializers import (
    GENERIC_LOGIN_ERROR,
    ChangePasswordSerializer,
    HealthSerializer,
    JobCancelSerializer,
    JobCreateSerializer,
    JobDetailSerializer,
    JobFilterSerializer,
    JobSerializer,
    JobUpdateSerializer,
    LoginSerializer,
    OrganizationSerializer,
    RegisterSerializer,
    SetPasswordSerializer,
    SkillSerializer,
    StaffCreateSerializer,
    TechnicianDetailSerializer,
    TechnicianUpdateSerializer,
    UserSerializer,
    UserUpdateSerializer,
)
from .services import accounts
from .services import jobs as job_service
from .services.accounts import (
    CannotChangeOwnPasswordHereError,
    EmailUnavailableError,
    HasOngoingJobError,
    LastHeadError,
    User,
)
from .versioning import check_and_bump_version


@extend_schema(responses=HealthSerializer)
@api_view(["GET"])
@permission_classes([AllowAny])
def health_check(request):
    """
    Health check endpoint to verify the API is running.
    """
    return Response({"status": "ok"}, status=status.HTTP_200_OK)


@extend_schema(responses={204: None})
@api_view(["GET"])
@permission_classes([AllowAny])
@ensure_csrf_cookie
def get_csrf_token(request):
    """Get a CSRF token. Responds with 204 No Content."""
    return Response(status=status.HTTP_204_NO_CONTENT)


@method_decorator(csrf_protect, name="dispatch")
class RegisterView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "register"

    @extend_schema(request=RegisterSerializer, responses={201: UserSerializer})
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = serializer.save()
        except EmailUnavailableError:
            raise ValidationError(
                {"email": ["Email unavailable."]}
            ) from None  # why from None
        login(request, user)
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    @extend_schema(request=LoginSerializer, responses={200: UserSerializer})
    def post(self, request):
        serialzer = LoginSerializer(
            data=request.data, context={"request": request._request}
        )
        if not serialzer.is_valid():
            return Response(
                {"detail": GENERIC_LOGIN_ERROR}, status=status.HTTP_400_BAD_REQUEST
            )
        user = serialzer.validated_data["user"]
        login(request, user)
        return Response(UserSerializer(user).data, status=status.HTTP_200_OK)


class LogoutView(APIView):
    permission_classes = [IsSignedInMember]

    @extend_schema(request=None, responses={204: None})
    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    permission_classes = [IsSignedInMember]

    @extend_schema(responses=UserSerializer)
    def get(self, request):
        return Response(UserSerializer(request.user).data)


class ChangePasswordView(APIView):
    permission_classes = [IsSignedInMember]

    @extend_schema(request=ChangePasswordSerializer, responses={204: None})
    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save(update_fields=["password"])
        update_session_auth_hash(request, request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class UserViewSet(
    TenantScopedViewMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    """Head dispatchers manage the users of their own organization."""

    queryset = User.objects.order_by("full_name", "id")
    permission_classes = [IsHeadDispatcher]
    serializer_class = UserSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        qs = super().get_queryset()
        role = self.request.query_params.get("role")
        if role:
            qs = qs.filter(role=role)
        is_active = self.request.query_params.get("is_active")
        if is_active in ("true", "false"):
            qs = qs.filter(is_active=(is_active == "true"))
        return qs

    @extend_schema(request=StaffCreateSerializer, responses={201: UserSerializer})
    def create(self, request):
        serializer = StaffCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = accounts.create_staff_user(
                creator=request.user, **serializer.validated_data
            )
        except EmailUnavailableError:
            raise ValidationError({"email": ["Email unavailable."]}) from None
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=UserUpdateSerializer, responses=UserSerializer)
    def partial_update(self, request, pk=None):
        user = self.get_object()  # 404 for another organization
        serializer = UserUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user.full_name = serializer.validated_data["full_name"]
        user.save(update_fields=["full_name"])
        return Response(UserSerializer(user).data)

    @extend_schema(request=None, responses=UserSerializer)
    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        target = self.get_object()
        try:
            target = accounts.deactivate_user(actor=request.user, target=target)
        except LastHeadError:
            raise Conflict(
                "An organization needs at least one active head dispatcher.",
                code="last_head",
            ) from None
        except HasOngoingJobError:
            raise Conflict(
                "This technician has a job in progress. Finish or reassign it first.",
                code="has_ongoing_job",
            ) from None
        return Response(UserSerializer(target).data)

    @extend_schema(request=None, responses=UserSerializer)
    @action(detail=True, methods=["post"])
    def reactivate(self, request, pk=None):
        target = self.get_object()
        target = accounts.reactivate_user(actor=request.user, target=target)
        return Response(UserSerializer(target).data)

    @extend_schema(request=SetPasswordSerializer, responses={204: None})
    @action(detail=True, methods=["post"], url_path="set-password")
    def set_password(self, request, pk=None):
        target = self.get_object()
        serializer = SetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            accounts.set_password(
                actor=request.user,
                target=target,
                new_password=serializer.validated_data["new_password"],
            )
        except CannotChangeOwnPasswordHereError:
            raise ValidationError(
                {"detail": "Use /auth/change-password/ for your own password."}
            ) from None
        return Response(status=status.HTTP_204_NO_CONTENT)


class OrganizationView(generics.RetrieveUpdateAPIView):
    """The requester's own organization. There is no id in the URL on purpose."""

    serializer_class = OrganizationSerializer
    permission_classes = [IsDispatcher]  # read: dispatcher and head
    http_method_names = ["get", "patch", "head", "options"]

    def get_permissions(self):
        if self.request.method == "PATCH":
            return [IsHeadDispatcher()]  # write: head only
        return super().get_permissions()

    def get_object(self):
        return self.request.user.organization

    def perform_update(self, serializer):  # race conditions
        with transaction.atomic():
            org = Organization.objects.select_for_update().get(
                pk=serializer.instance.pk
            )
            data = dict(serializer.validated_data)
            check_and_bump_version(org, data.pop("version"))
            serializer.instance = org
            if data.get("lat") is not None and data.get("lng") is not None:
                data["geocode_status"] = GeocodeStatus.MANUAL
            for field, value in data.items():
                setattr(org, field, value)
            org.save()


class TechnicianViewSet(
    TenantScopedViewMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Dispatchers and heads read technicians; only heads edit them."""

    queryset = (
        Technician.objects.select_related("user__organization")
        .prefetch_related("skills")
        .order_by("user__full_name", "id")
    )
    permission_classes = [IsDispatcher]
    serializer_class = TechnicianDetailSerializer
    pagination_class = None
    http_method_names = ["get", "patch", "head", "options"]

    def get_permissions(self):
        if self.action == "partial_update":
            return [IsHeadDispatcher()]
        return super().get_permissions()

    def get_serializer_class(self):
        if self.action == "partial_update":
            return TechnicianUpdateSerializer
        return TechnicianDetailSerializer

    @extend_schema(
        request=TechnicianUpdateSerializer, responses=TechnicianDetailSerializer
    )
    def partial_update(self, request, *args, **kwargs):
        technician = self.get_object()  # scoped queryset: another org's id -> 404
        serializer = self.get_serializer(technician, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(TechnicianDetailSerializer(technician).data)


class SkillViewSet(generics.ListAPIView):
    """
    API endpoint that allows skills to be viewed or created.
    """

    queryset = Skill.objects.all()
    serializer_class = SkillSerializer
    permission_classes = [IsDispatcher]
    pagination_class = None  # Disable pagination for this view


DETAIL_ACTIONS = {"retrieve", "create", "partial_update", "cancel"}


class JobViewSet(
    TenantScopedViewMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    """Dispatchers and heads manage jobs. There is no DELETE: terminal jobs
    stay for the audit trail. Technicians get their own endpoint in Sprint 2."""

    queryset = Job.objects.select_related("technician__user").order_by(
        "-is_urgent", "scheduled_date", "slot_start", "id"
    )
    permission_classes = [IsDispatcher]
    serializer_class = JobSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.action in DETAIL_ACTIONS:
            return qs.prefetch_related(
                "acceptable_skills",
                Prefetch(
                    "history",
                    queryset=JobStatusHistory.objects.select_related("changed_by"),
                ),
            )
        if self.action == "list":
            filters = JobFilterSerializer(data=self.request.query_params)
            filters.is_valid(raise_exception=True)
            for name, value in filters.validated_data.items():
                qs = qs.filter(**{name: value})
        return qs

    def get_serializer_class(self):
        if self.action in DETAIL_ACTIONS:
            return JobDetailSerializer
        return JobSerializer

    def _detail(self, job, status_code=status.HTTP_200_OK):
        fresh = self.get_queryset().get(pk=job.pk)
        return Response(JobDetailSerializer(fresh).data, status=status_code)

    @extend_schema(
        parameters=[JobFilterSerializer],
        responses=JobSerializer(many=True),
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(request=JobCreateSerializer, responses={201: JobDetailSerializer})
    def create(self, request, *args, **kwargs):
        serializer = JobCreateSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        job = serializer.save()
        return self._detail(job, status.HTTP_201_CREATED)

    @extend_schema(request=JobUpdateSerializer, responses=JobDetailSerializer)
    def partial_update(self, request, pk=None):
        job = self.get_object()  # 404 for another organization
        serializer = JobUpdateSerializer(job, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        try:
            updated = job_service.update_job(
                job=job, client_version=data.pop("version"), **data
            )
        except job_service.JobNotEditable:
            raise Conflict(
                "This job is already planned. Unassign it before changing its "
                "address, time or skills.",
                code="job_not_editable",
            ) from None
        return self._detail(updated)

    @extend_schema(request=JobCancelSerializer, responses=JobDetailSerializer)
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        job = self.get_object()
        serializer = JobCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            canceled = job_service.cancel_job(
                job=job, actor=request.user, reason=serializer.validated_data["reason"]
            )
        except job_service.IllegalJobTransition:
            raise Conflict(
                f"A {job.status} job cannot be canceled.", code="illegal_transition"
            ) from None
        return self._detail(canceled)
