from django.db.models import Count, F, Q
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
from .models import Case, CaseNote, Department, Division, PriorityLevel
from .scoping import is_admin, permissions_for, scoped_concerns
from .serializers_staff import (
    AcceptSerializer,
    AssignDivisionSerializer,
    AssignPersonSerializer,
    CompleteSerializer,
    DepartmentSerializer,
    DivisionSerializer,
    EndorsementFollowUpSerializer,
    EndorseSerializer,
    EscalateSerializer,
    ExtendSerializer,
    Feedback8888Serializer,
    InspectSerializer,
    LinkDuplicateSerializer,
    NoteCreateSerializer,
    OptionalRemarksSerializer,
    PriorityLevelSerializer,
    RemarksSerializer,
    RespondSerializer,
    ReturnSerializer,
    SetPrioritySerializer,
    RouteSerializer,
    StaffConcernDetailSerializer,
    StaffConcernListSerializer,
    StaffEncodeSerializer,
    StaffSummarySerializer,
    StaffUserSerializer,
    ValidateSerializer,
    VerifySerializer,
)

IsStaff = HasRole(*STAFF_ROLES)
R = User.Role
TABS = ["triage", "to_route", "for_acceptance", "mine", "validation", "endorsed", "overdue", "open", "closed", "all"]
OPEN = Concern.OPEN_STATUSES


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


def my_queue_q(user):
    """'Ako ang susunod na kikilos' — what this person should act on next."""
    now = timezone.now()
    for_validation = Q(case__work_completed_at__isnull=False, case__validated_at__isnull=True)
    awaiting = Q(case__level=Case.Level.CITY, case__accepted_at__isnull=True, case__department__isnull=False)
    if user.role == R.OFFICE_DESK:
        return Q(case__department_id=user.department_id) & (awaiting | Q(case__division__isnull=True))
    if user.role == R.DEPT_HEAD:
        return Q(case__department_id=user.department_id) & (
            awaiting | Q(case__division__isnull=True) | for_validation
        )
    if user.role == R.DIVISION_CHIEF:
        mine = Q(case__division_id=user.division_id) | Q(case__department_id=user.department_id, case__division__isnull=True)
        return mine & (Q(case__assigned_to__isnull=True) | for_validation)
    if user.role == R.DEPT_STAFF:
        return Q(case__assigned_to=user, case__work_completed_at__isnull=True)
    if user.role == R.BARANGAY:
        return Q(case__level=Case.Level.BARANGAY)
    # PACD / admin: close the loop, 8888 feedback, endorsement follow-ups
    return (
        Q(status=Concern.Status.RESOLVED)
        | Q(channel=Concern.Channel.HOTLINE_8888, external_feedback_sent_at__isnull=True)
        | Q(case__level=Case.Level.EXTERNAL, case__endorsements__next_follow_up_at__lte=now)
    )


def apply_tab(qs, tab, user):
    now = timezone.now()
    if tab == "triage":
        return qs.filter(is_verified=False, status__in=OPEN)
    if tab == "to_route":  # verified but not yet routed, or returned by an office
        return qs.filter(
            Q(case__isnull=True) | Q(case__level=Case.Level.CITY, case__department__isnull=True),
            is_verified=True, status__in=OPEN,
        )
    if tab == "for_acceptance":
        return qs.filter(status__in=OPEN, case__level=Case.Level.CITY, case__department__isnull=False,
                         case__accepted_at__isnull=True)
    if tab == "mine":
        q = my_queue_q(user)
        # resolved concerns only matter in PACD's queue (to close); everyone else: open only
        if user.role in (R.PACD, R.CITY_ADMIN) or user.is_superuser:
            return qs.filter(q).exclude(status__in=[Concern.Status.CLOSED, Concern.Status.REJECTED]).distinct()
        return qs.filter(q, status__in=OPEN).distinct()
    if tab == "validation":
        return qs.filter(status__in=OPEN, case__work_completed_at__isnull=False, case__validated_at__isnull=True)
    if tab == "endorsed":
        return qs.filter(status__in=OPEN, case__level=Case.Level.EXTERNAL)
    if tab == "overdue":
        return qs.filter(status__in=OPEN, case__due_at__lt=now)
    if tab == "open":
        return qs.filter(status__in=OPEN)
    if tab == "closed":
        return qs.exclude(status__in=OPEN)
    return qs


@extend_schema(parameters=[
    OpenApiParameter("tab", enum=TABS, description="Inbox view (default: open)"),
    OpenApiParameter("q", str, description="Search reference no., title, landmark, description"),
    OpenApiParameter("category", str), OpenApiParameter("barangay", int),
    OpenApiParameter("include_duplicates", bool),
])
class StaffConcernViewSet(mixins.CreateModelMixin, viewsets.ReadOnlyModelViewSet):
    """Staff case inbox and workflow. Visibility and every action are decided in scoping.py."""

    permission_classes = [IsStaff]
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    queryset = Concern.objects.none()  # schema typing only

    def get_queryset(self):
        user = self.request.user
        qs = scoped_concerns(user).annotate(duplicate_count=Count("duplicates", distinct=True))
        if self.action != "list":
            return qs.prefetch_related(
                "attachments", "history__changed_by", "duplicates", "case__notes__author",
                "case__endorsements__follow_ups__by", "case__endorsements__agency",
            )
        p = self.request.query_params
        if p.get("include_duplicates") not in ("1", "true"):
            qs = qs.filter(duplicate_of__isnull=True)
        tab = p.get("tab", "open")
        qs = apply_tab(qs, tab, user)
        if p.get("category"):
            qs = qs.filter(category__code=p["category"])
        if p.get("barangay"):
            qs = qs.filter(barangay_id=p["barangay"])
        if q := p.get("q", "").strip():
            qs = qs.filter(
                Q(reference_no__icontains=q) | Q(title__icontains=q) | Q(external_ticket_no__icontains=q)
                | Q(location_description__icontains=q) | Q(description__icontains=q)
            )
        if tab in ("triage", "to_route"):
            return qs.order_by("-danger_now", "-priority_score", "created_at")
        # Work queues: urgency level first (P1 before P2…), then score, then oldest first
        return qs.order_by(F("case__priority_level__sort_order").asc(nulls_last=True), "-priority_score", "created_at")

    def get_serializer_class(self):
        if self.action == "list":
            return StaffConcernListSerializer
        if self.action == "create":
            return StaffEncodeSerializer
        return StaffConcernDetailSerializer

    # ----- helpers -----
    def _guard(self, perm):
        concern = self.get_object()
        if not permissions_for(self.request.user, concern).get(perm):
            raise PermissionDenied("Hindi ito pinapayagan para sa iyong role o sa yugto ng kasong ito.")
        return concern

    def _run(self, perm, ser_cls, fn, *, files=None, map_kwargs=None):
        concern = self._guard(perm)
        data = _multipart_lists(self.request, *(files or ())) if files else self.request.data
        ser = ser_cls(data=data)
        ser.is_valid(raise_exception=True)
        kwargs = dict(ser.validated_data)
        if map_kwargs:
            kwargs = map_kwargs(kwargs)
        try:
            fn(concern, self.request.user, **kwargs)
        except (services.WorkflowError, InvalidTransition) as e:
            raise ValidationError({"detail": str(e)})
        return self._detail(concern)

    def _detail(self, concern, code=status.HTTP_200_OK):
        # The action may move the case out of this user's scope (e.g. re-routed); still return the result.
        concern = self.get_queryset().filter(pk=concern.pk).first() or (
            Concern.objects.annotate(duplicate_count=Count("duplicates", distinct=True)).get(pk=concern.pk)
        )
        return Response(StaffConcernDetailSerializer(concern, context={"request": self.request}).data, status=code)

    # ----- intake -----
    @extend_schema(request={"multipart/form-data": StaffEncodeSerializer}, responses=StaffConcernDetailSerializer)
    def create(self, request, *args, **kwargs):
        if request.user.role == R.MAYOR:
            raise PermissionDenied("Read-only role.")
        ser = StaffEncodeSerializer(data=_multipart_lists(request, "images"), context={"request": request})
        ser.is_valid(raise_exception=True)
        return self._detail(ser.save(), status.HTTP_201_CREATED)

    @extend_schema(request=VerifySerializer, responses=StaffConcernDetailSerializer)
    @action(detail=True, methods=["post"])
    def verify(self, request, pk=None):
        return self._run("verify", VerifySerializer, services.verify)

    @extend_schema(request=RouteSerializer, responses=StaffConcernDetailSerializer)
    @action(detail=True, methods=["post"])
    def route(self, request, pk=None):
        user = request.user

        def check(kw):
            if user.role == R.BARANGAY and kw["level"] == Case.Level.CITY and kw.get("department"):
                kw["department"] = None  # barangays elevate to City Hall; PACD/default routing decides the office
                kw["division"] = None
            return kw

        return self._run("route", RouteSerializer, services.route, map_kwargs=check)

    @extend_schema(request=EndorseSerializer, responses=StaffConcernDetailSerializer)
    @action(detail=True, methods=["post"])
    def endorse(self, request, pk=None):
        return self._run("endorse", EndorseSerializer, services.endorse)

    # ----- office receiving & screening -----
    @extend_schema(request=AcceptSerializer, responses=StaffConcernDetailSerializer)
    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        return self._run("accept", AcceptSerializer, services.accept)

    @extend_schema(request=ReturnSerializer, responses=StaffConcernDetailSerializer)
    @action(detail=True, methods=["post"], url_path="return-to-pacd")
    def return_to_pacd(self, request, pk=None):
        return self._run("return_to_pacd", ReturnSerializer, services.return_to_pacd)

    @extend_schema(request=SetPrioritySerializer, responses=StaffConcernDetailSerializer)
    @action(detail=True, methods=["post"], url_path="set-priority")
    def set_priority(self, request, pk=None):
        return self._run("set_priority", SetPrioritySerializer, services.set_priority)

    @extend_schema(request={"multipart/form-data": RespondSerializer}, responses=StaffConcernDetailSerializer)
    @action(detail=True, methods=["post"])
    def respond(self, request, pk=None):
        return self._run("respond", RespondSerializer, services.respond, files=["photos"],
                         map_kwargs=lambda kw: {**kw, "photos": kw.get("photos", [])})

    # ----- inside the office -----
    @extend_schema(request=AssignDivisionSerializer, responses=StaffConcernDetailSerializer)
    @action(detail=True, methods=["post"], url_path="assign-division")
    def assign_division(self, request, pk=None):
        return self._run("assign_division", AssignDivisionSerializer, services.assign_division)

    @extend_schema(request=AssignPersonSerializer, responses=StaffConcernDetailSerializer)
    @action(detail=True, methods=["post"], url_path="assign-person")
    def assign_person(self, request, pk=None):
        user = request.user

        def check(kw):
            person = kw["person"]
            if user.role == R.DIVISION_CHIEF and person.division_id not in (None, user.division_id):
                raise ValidationError({"person": "You can only assign people in your division."})
            return kw

        return self._run("assign_person", AssignPersonSerializer, services.assign_person, map_kwargs=check)

    @extend_schema(request=InspectSerializer, responses=StaffConcernDetailSerializer)
    @action(detail=True, methods=["post"])
    def inspect(self, request, pk=None):
        return self._run("inspect", InspectSerializer, services.inspect)

    @extend_schema(request={"multipart/form-data": CompleteSerializer}, responses=StaffConcernDetailSerializer)
    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        return self._run("complete", CompleteSerializer, services.complete_work, files=["photos"],
                         map_kwargs=lambda kw: {**kw, "photos": kw.get("photos", [])})

    @extend_schema(request={"multipart/form-data": ValidateSerializer}, responses=StaffConcernDetailSerializer)
    @action(detail=True, methods=["post"])
    def validate(self, request, pk=None):
        return self._run("validate", ValidateSerializer, services.validate, files=["photos"],
                         map_kwargs=lambda kw: {**kw, "photos": kw.get("photos", [])})

    @extend_schema(request=ExtendSerializer, responses=StaffConcernDetailSerializer)
    @action(detail=True, methods=["post"])
    def extend(self, request, pk=None):
        return self._run("extend", ExtendSerializer, services.extend_deadline)

    # ----- external / 8888 -----
    @extend_schema(request=EndorsementFollowUpSerializer, responses=StaffConcernDetailSerializer)
    @action(detail=True, methods=["post"], url_path="follow-up")
    def follow_up(self, request, pk=None):
        return self._run("follow_up", EndorsementFollowUpSerializer, services.endorsement_follow_up)

    @extend_schema(request=Feedback8888Serializer, responses=StaffConcernDetailSerializer)
    @action(detail=True, methods=["post"], url_path="feedback-8888")
    def feedback_8888(self, request, pk=None):
        return self._run("feedback_8888", Feedback8888Serializer, services.record_8888_feedback)

    # ----- outcomes -----
    @extend_schema(request=RemarksSerializer, responses=StaffConcernDetailSerializer)
    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        return self._run("reject", RemarksSerializer, services.reject)

    @extend_schema(request=OptionalRemarksSerializer, responses=StaffConcernDetailSerializer)
    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        return self._run("close", OptionalRemarksSerializer, services.close)

    @extend_schema(request=RemarksSerializer, responses=StaffConcernDetailSerializer)
    @action(detail=True, methods=["post"])
    def reopen(self, request, pk=None):
        return self._run("reopen", RemarksSerializer, services.reopen)

    @extend_schema(request=EscalateSerializer, responses=StaffConcernDetailSerializer)
    @action(detail=True, methods=["post"])
    def escalate(self, request, pk=None):
        return self._run("escalate", EscalateSerializer, services.escalate)

    @extend_schema(request=NoteCreateSerializer, responses=StaffConcernDetailSerializer)
    @action(detail=True, methods=["post"])
    def notes(self, request, pk=None):
        concern = self._guard("notes")
        ser = NoteCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        CaseNote.objects.create(case=concern.case, author=request.user, body=ser.validated_data["body"])
        return self._detail(concern)

    @extend_schema(request=LinkDuplicateSerializer, responses=StaffConcernDetailSerializer)
    @action(detail=True, methods=["post"], url_path="link-duplicate")
    def link_duplicate(self, request, pk=None):
        concern = self._guard("link")
        ser = LinkDuplicateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        master = get_object_or_404(scoped_concerns(request.user),
                                   reference_no=ser.validated_data["master_reference"].strip().upper())
        try:
            services.link_duplicate(concern, master, request.user)
        except services.WorkflowError as e:
            raise ValidationError({"master_reference": str(e)})
        return self._detail(concern)

    @extend_schema(request=None, responses=StaffConcernDetailSerializer)
    @action(detail=True, methods=["post"], url_path="unlink-duplicate")
    def unlink_duplicate(self, request, pk=None):
        concern = self._guard("link")
        services.unlink_duplicate(concern, request.user)
        return self._detail(concern)


class StaffSummaryView(APIView):
    permission_classes = [IsStaff]

    @extend_schema(responses=StaffSummarySerializer)
    def get(self, request):
        user = request.user
        now = timezone.now()
        base = scoped_concerns(user).filter(duplicate_of__isnull=True)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        triage = apply_tab(base, "triage", user)
        endorsed = apply_tab(base, "endorsed", user)
        open_ = base.filter(status__in=OPEN)
        return Response({
            "triage": triage.count(),
            "for_acceptance": apply_tab(base, "for_acceptance", user).count(),
            "returned": open_.filter(case__level=Case.Level.CITY, case__department__isnull=True).count(),
            "response_overdue": open_.filter(case__responded_at__isnull=True, case__response_due_at__lt=now).count(),
            "p1_open": open_.filter(case__priority_level__code="P1").count(),
            "to_route": apply_tab(base, "to_route", user).count(),
            "danger_unverified": triage.filter(danger_now=True).count(),
            "mine": apply_tab(base, "mine", user).count(),
            "validation": apply_tab(base, "validation", user).count(),
            "endorsed": endorsed.count(),
            "follow_up_due": endorsed.filter(case__endorsements__next_follow_up_at__lte=now).distinct().count(),
            "feedback_8888_due": base.filter(
                channel=Concern.Channel.HOTLINE_8888, external_feedback_sent_at__isnull=True
            ).count(),
            "overdue": apply_tab(base, "overdue", user).count(),
            "open": apply_tab(base, "open", user).count(),
            "resolved_this_month": base.filter(resolved_at__gte=month_start).count(),
        })


@extend_schema(parameters=[OpenApiParameter("kind", enum=["internal", "external"])])
class DepartmentListView(generics.ListAPIView):
    permission_classes = [IsStaff]
    serializer_class = DepartmentSerializer
    pagination_class = None

    def get_queryset(self):
        qs = Department.objects.filter(is_active=True)
        if kind := self.request.query_params.get("kind"):
            qs = qs.filter(kind=kind)
        return qs.order_by("kind", "name")


@extend_schema(parameters=[OpenApiParameter("department", int, required=True)])
class DivisionListView(generics.ListAPIView):
    permission_classes = [IsStaff]
    serializer_class = DivisionSerializer
    pagination_class = None

    def get_queryset(self):
        dept = self.request.query_params.get("department")
        return Division.objects.filter(is_active=True, department_id=dept) if dept else Division.objects.none()


@extend_schema(parameters=[OpenApiParameter("department", int, required=True), OpenApiParameter("division", int)])
class StaffUserListView(generics.ListAPIView):
    """People in an office (optionally a division), for the 'assign to' dropdown."""

    permission_classes = [IsStaff]
    serializer_class = StaffUserSerializer
    pagination_class = None

    def get_queryset(self):
        p = self.request.query_params
        if not p.get("department"):
            return User.objects.none()
        qs = User.objects.filter(
            is_active=True, department_id=p["department"], role__in=[R.DEPT_STAFF, R.DIVISION_CHIEF]
        )
        if p.get("division"):
            qs = qs.filter(Q(division_id=p["division"]) | Q(division__isnull=True))
        return qs.order_by("role", "first_name", "username")


class PriorityLevelListView(generics.ListAPIView):
    permission_classes = [IsStaff]
    serializer_class = PriorityLevelSerializer
    pagination_class = None
    queryset = PriorityLevel.objects.all()
