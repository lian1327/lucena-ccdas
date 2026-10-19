from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.permissions import STAFF_ROLES, HasRole
from apps.concerns.models import Concern
from apps.concerns.services import InvalidTransition

from . import services
from .models import CaseNote, Department
from .scoping import can_act, can_resolve, scoped_concerns
from .serializers_staff import (
    AssignSerializer,
    DepartmentSerializer,
    EscalateSerializer,
    LinkDuplicateSerializer,
    NoteCreateSerializer,
    StaffConcernDetailSerializer,
    StaffConcernListSerializer,
    StaffEncodeSerializer,
    StaffSummarySerializer,
    StaffUserSerializer,
    StatusUpdateSerializer,
    VerifySerializer,
)

IsStaff = HasRole(*STAFF_ROLES)
TABS = ["triage", "mine", "overdue", "open", "closed", "all"]


def _multipart_lists(request, *list_keys):
    """multipart repeats keys for files; DRF ListField needs a real list."""
    data = request.data
    if not hasattr(data, "getlist"):
        return data
    out = {k: data.get(k) for k in data.keys() if k not in list_keys}
    for k in list_keys:
        files = request.FILES.getlist(k)
        if files:
            out[k] = files
    return out


def apply_tab(qs, tab, user):
    now = timezone.now()
    if tab == "triage":
        return qs.filter(is_verified=False, status__in=Concern.OPEN_STATUSES)
    if tab == "mine":
        q = Q(case__assigned_to=user)
        if user.role == User.Role.DEPT_STAFF and user.department_id:
            q |= Q(case__department_id=user.department_id, case__assigned_to__isnull=True)
        return qs.filter(q, status__in=Concern.OPEN_STATUSES)
    if tab == "overdue":
        return qs.filter(status__in=Concern.OPEN_STATUSES, case__due_at__lt=now)
    if tab == "open":
        return qs.filter(status__in=Concern.OPEN_STATUSES)
    if tab == "closed":
        return qs.exclude(status__in=Concern.OPEN_STATUSES)
    return qs


@extend_schema(parameters=[
    OpenApiParameter("tab", enum=TABS, description="Inbox view (default: open)"),
    OpenApiParameter("q", str, description="Search reference no., title, landmark, description"),
    OpenApiParameter("category", str), OpenApiParameter("barangay", int),
    OpenApiParameter("include_duplicates", bool),
])
class StaffConcernViewSet(mixins.CreateModelMixin, viewsets.ReadOnlyModelViewSet):
    """
    Staff case inbox. Scope is enforced by role (see scoping.py):
    barangay → own barangay (minus complaints about barangay officials); dept staff → own office;
    city admin / mayor → everything. Mayor's office is read-only.
    """

    permission_classes = [IsStaff]
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    queryset = Concern.objects.none()  # schema typing only; real scope comes from get_queryset()

    def get_queryset(self):
        user = self.request.user
        qs = scoped_concerns(user).annotate(duplicate_count=Count("duplicates", distinct=True))
        if self.action != "list":
            return qs.prefetch_related("attachments", "history__changed_by", "duplicates", "case__notes__author")

        p = self.request.query_params
        if p.get("include_duplicates") not in ("1", "true"):
            qs = qs.filter(duplicate_of__isnull=True)
        qs = apply_tab(qs, p.get("tab", "open"), user)
        if p.get("category"):
            qs = qs.filter(category__code=p["category"])
        if p.get("barangay"):
            qs = qs.filter(barangay_id=p["barangay"])
        if q := p.get("q", "").strip():
            qs = qs.filter(
                Q(reference_no__icontains=q) | Q(title__icontains=q)
                | Q(location_description__icontains=q) | Q(description__icontains=q)
            )
        if p.get("tab") == "triage":
            return qs.order_by("-danger_now", "-priority_score", "created_at")
        return qs.order_by("-priority_score", "created_at")

    def get_serializer_class(self):
        if self.action == "list":
            return StaffConcernListSerializer
        if self.action == "create":
            return StaffEncodeSerializer
        return StaffConcernDetailSerializer

    # ----- helpers -----
    def _obj_for_action(self, need=can_act):
        concern = self.get_object()
        if not need(self.request.user):
            raise PermissionDenied("Your role can view this case but not change it.")
        return concern

    def _detail(self, concern, code=status.HTTP_200_OK):
        concern = self.get_queryset().get(pk=concern.pk)
        return Response(StaffConcernDetailSerializer(concern, context={"request": self.request}).data, status=code)

    # ----- intake -----
    @extend_schema(request=StaffEncodeSerializer, responses=StaffConcernDetailSerializer)
    def create(self, request, *args, **kwargs):
        if not can_act(request.user):
            raise PermissionDenied("Your role cannot encode concerns.")
        ser = StaffEncodeSerializer(data=_multipart_lists(request, "images"), context={"request": request})
        ser.is_valid(raise_exception=True)
        concern = ser.save()
        return self._detail(concern, status.HTTP_201_CREATED)

    # ----- workflow actions -----
    @extend_schema(request=VerifySerializer, responses=StaffConcernDetailSerializer)
    @action(detail=True, methods=["post"])
    def verify(self, request, pk=None):
        concern = self._obj_for_action()
        ser = VerifySerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        services.verify(concern, request.user, **ser.validated_data)
        return self._detail(concern)

    @extend_schema(request=AssignSerializer, responses=StaffConcernDetailSerializer)
    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        concern = self._obj_for_action()
        ser = AssignSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        try:
            services.assign(concern, request.user, **ser.validated_data)
        except InvalidTransition as e:
            raise ValidationError({"status": str(e)})
        return self._detail(concern)

    @extend_schema(request={"multipart/form-data": StatusUpdateSerializer}, responses=StaffConcernDetailSerializer)
    @action(detail=True, methods=["post"], url_path="status")
    def set_status(self, request, pk=None):
        ser = StatusUpdateSerializer(data=_multipart_lists(request, "photos"))
        ser.is_valid(raise_exception=True)
        need = can_resolve if ser.validated_data["status"] in Concern.DONE_STATUSES else can_act
        concern = self._obj_for_action(need)
        try:
            services.update_status(concern, request.user, **ser.validated_data)
        except InvalidTransition as e:
            raise ValidationError({"status": str(e)})
        return self._detail(concern)

    @extend_schema(request=EscalateSerializer, responses=StaffConcernDetailSerializer)
    @action(detail=True, methods=["post"])
    def escalate(self, request, pk=None):
        concern = self._obj_for_action()
        if not hasattr(concern, "case"):
            raise ValidationError({"detail": "Assign the concern to an office before escalating."})
        ser = EscalateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        services.escalate(concern, request.user, reason=ser.validated_data["reason"])
        return self._detail(concern)

    @extend_schema(request=NoteCreateSerializer, responses=StaffConcernDetailSerializer)
    @action(detail=True, methods=["post"])
    def notes(self, request, pk=None):
        concern = self._obj_for_action()
        if not hasattr(concern, "case"):
            raise ValidationError({"detail": "Internal notes are available once the concern is assigned."})
        ser = NoteCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        CaseNote.objects.create(case=concern.case, author=request.user, body=ser.validated_data["body"])
        return self._detail(concern)

    @extend_schema(request=LinkDuplicateSerializer, responses=StaffConcernDetailSerializer)
    @action(detail=True, methods=["post"], url_path="link-duplicate")
    def link_duplicate(self, request, pk=None):
        concern = self._obj_for_action()
        ser = LinkDuplicateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        master = get_object_or_404(scoped_concerns(request.user),
                                   reference_no=ser.validated_data["master_reference"].strip().upper())
        try:
            services.link_duplicate(concern, master, request.user)
        except ValueError as e:
            raise ValidationError({"master_reference": str(e)})
        return self._detail(concern)

    @extend_schema(request=None, responses=StaffConcernDetailSerializer)
    @action(detail=True, methods=["post"], url_path="unlink-duplicate")
    def unlink_duplicate(self, request, pk=None):
        concern = self._obj_for_action()
        services.unlink_duplicate(concern, request.user)
        return self._detail(concern)


class StaffSummaryView(APIView):
    permission_classes = [IsStaff]

    @extend_schema(responses=StaffSummarySerializer)
    def get(self, request):
        user = request.user
        base = scoped_concerns(user).filter(duplicate_of__isnull=True)
        month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        triage = apply_tab(base, "triage", user)
        return Response({
            "triage": triage.count(),
            "danger_unverified": triage.filter(danger_now=True).count(),
            "mine": apply_tab(base, "mine", user).count(),
            "overdue": apply_tab(base, "overdue", user).count(),
            "open": apply_tab(base, "open", user).count(),
            "resolved_this_month": base.filter(resolved_at__gte=month_start).count(),
        })


class DepartmentListView(generics.ListAPIView):
    permission_classes = [IsStaff]
    serializer_class = DepartmentSerializer
    queryset = Department.objects.filter(is_active=True).order_by("name")
    pagination_class = None


@extend_schema(parameters=[OpenApiParameter("department", int, required=True)])
class StaffUserListView(generics.ListAPIView):
    """People in an office, for the 'assign to' dropdown."""

    permission_classes = [IsStaff]
    serializer_class = StaffUserSerializer
    pagination_class = None

    def get_queryset(self):
        dept = self.request.query_params.get("department")
        if not dept:
            return User.objects.none()
        return User.objects.filter(
            is_active=True, role=User.Role.DEPT_STAFF, department_id=dept
        ).order_by("first_name", "username")
