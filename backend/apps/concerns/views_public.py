"""
Public (no-login) endpoints for the landing page and citizen portal.
Authentication is disabled here so a stale/expired JWT in the browser never blocks a citizen.
"""
from datetime import timedelta

from django.core.cache import cache
from django.db.models import Avg, Count, DurationField, ExpressionWrapper, F, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.geo.models import Barangay, Purok

from .models import Category, Concern
from .serializers import (
    PublicBarangaySerializer,
    PublicCategorySerializer,
    PublicConcernCreateSerializer,
    LocateSerializer,
    PublicConfirmSerializer,
    PublicPurokSerializer,
    PublicStatsSerializer,
    PublicTrackSerializer,
    RecentFixSerializer,
)
from apps.notifications.serializers import PublicNotifyPrefsSerializer


class PublicMixin:
    permission_classes = [AllowAny]
    authentication_classes = []


class PublicCategoryListView(PublicMixin, generics.ListAPIView):
    serializer_class = PublicCategorySerializer
    queryset = Category.objects.filter(is_active=True).prefetch_related("subcategories")
    pagination_class = None


class PublicBarangayListView(PublicMixin, generics.ListAPIView):
    serializer_class = PublicBarangaySerializer
    queryset = Barangay.objects.all()
    pagination_class = None


class PublicConcernCreateView(PublicMixin, generics.CreateAPIView):
    """Citizen submission. Accepts multipart/form-data (with `images`) or JSON (without)."""

    serializer_class = PublicConcernCreateSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    throttle_scope = "public_submit"

    def create(self, request, *args, **kwargs):
        # multipart sends repeated `images` keys; DRF ListField needs getlist()
        data = request.data
        if hasattr(data, "getlist"):
            data = {k: data.get(k) for k in data.keys() if k != "images"}
            images = request.FILES.getlist("images")
            if images:
                data["images"] = images
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class PublicPurokListView(PublicMixin, generics.ListAPIView):
    """Puroks of a barangay, for the report form when the citizen doesn't drop a pin."""

    serializer_class = PublicPurokSerializer
    pagination_class = None

    def get_queryset(self):
        return Purok.objects.filter(barangay_id=self.kwargs["pk"]).order_by("is_zone", "name")


class PublicLocateView(PublicMixin, APIView):
    """Pin → barangay + purok, so the form can fill them in for the citizen."""

    throttle_scope = "public_track"

    @extend_schema(parameters=[OpenApiParameter("lat", float), OpenApiParameter("lng", float)], responses=LocateSerializer)
    def get(self, request):
        from apps.geo.locate import find_barangay, find_purok

        try:
            lat, lng = float(request.query_params["lat"]), float(request.query_params["lng"])
        except (KeyError, ValueError):
            return Response({"detail": "lat and lng are required."}, status=status.HTTP_400_BAD_REQUEST)
        b = find_barangay(lat, lng)
        p, _ = find_purok(lat, lng, b.id if b else None)
        return Response({"barangay_id": b.id if b else None, "barangay": b.name if b else None,
                         "purok_id": p.id if p else None, "purok": p.name if p else None})


class PublicTrackView(PublicMixin, generics.RetrieveAPIView):
    serializer_class = PublicTrackSerializer
    throttle_scope = "public_track"

    def get_object(self):
        ref = self.kwargs["reference_no"].strip().upper()
        return get_object_or_404(
            Concern.objects.select_related("category", "subcategory", "barangay", "duplicate_of", "case__department"),
            reference_no=ref,
        )


class PublicConfirmView(PublicMixin, APIView):
    """
    "Naayos ba talaga?" — the reporter confirms or disputes the fix (within 30 days, once).
    Not fixed → the case reopens for the office and counts against it. Throttled like submissions.
    """

    throttle_scope = "public_submit"

    @extend_schema(request=PublicConfirmSerializer, responses=PublicTrackSerializer)
    def post(self, request, reference_no):
        from apps.cases.services import WorkflowError, citizen_confirm

        concern = get_object_or_404(Concern, reference_no=reference_no.strip().upper())
        ser = PublicConfirmSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        if concern.reporter_contact:
            digits = "".join(ch for ch in concern.reporter_contact if ch.isdigit())
            if ser.validated_data.get("mobile_last4") != digits[-4:]:
                return Response({"detail": "Hindi tugma ang huling 4 na numero ng mobile na ginamit sa report."},
                                status=status.HTTP_400_BAD_REQUEST)
        try:
            citizen_confirm(concern, fixed=ser.validated_data["fixed"], feedback=ser.validated_data.get("feedback", ""))
        except WorkflowError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        concern.refresh_from_db()
        return Response(PublicTrackSerializer(concern, context={"request": request}).data)


class PublicRecentFixesView(PublicMixin, APIView):
    """
    A few recent, verified fixes with before/after photos for the landing page ("proof it gets done").
    Infrastructure problems only (roads, lights, drainage, garbage) and no reference numbers, landmarks or
    reporter data, so no neighbour dispute or private complaint is ever shown publicly. Cached 10 minutes.
    """

    PUBLIC_CATEGORIES = ["road_damage", "streetlight", "drainage", "solid_waste"]

    @extend_schema(responses=RecentFixSerializer(many=True))
    def get(self, request):
        data = cache.get("public_recent_fixes_v1")
        if data is None:
            data = self._build()
            cache.set("public_recent_fixes_v1", data, 600)
        return Response(data)

    def _build(self):
        from apps.concerns.models import ConcernAttachment

        qs = (Concern.objects.filter(duplicate_of__isnull=True, status__in=Concern.DONE_STATUSES,
                                     category__code__in=self.PUBLIC_CATEGORIES, attachments__kind="before")
              .filter(attachments__kind="resolution").exclude(citizen_confirmation="not_fixed")
              .select_related("category", "subcategory", "barangay", "purok", "case__department")
              .distinct().order_by("-resolved_at")[:6])
        out = []
        for c in qs:
            atts = {a.kind: a for a in c.attachments.filter(kind__in=["before", "resolution"]).order_by("uploaded_at")}
            case = getattr(c, "case", None)
            out.append({
                "problem": (c.subcategory.name_fil or c.subcategory.name) if c.subcategory else (c.category.name_fil or c.category.name),
                "category": c.category.code, "barangay": c.barangay.name, "purok": c.purok.name if c.purok_id else None,
                "office": case.department.name if case and case.department else None,
                "reported_at": c.created_at, "routed_at": case.routed_at if case else None,
                "inspected_at": case.inspected_at if case else None, "resolved_at": c.resolved_at,
                "days": round((c.resolved_at - c.created_at).total_seconds() / 86400, 1),
                "on_time": bool(case and case.due_at and case.validated_at and case.validated_at <= case.due_at),
                "citizen_confirmed": c.citizen_confirmation == "fixed",
                "before_url": atts["before"].file.url if "before" in atts else None,
                "after_url": atts["resolution"].file.url if "resolution" in atts else None,
            })
        return out


class PublicStatsView(PublicMixin, APIView):
    """Transparency stats for the landing page. Aggregates only — no individual records. Cached 5 min."""

    CACHE_KEY = "public_stats_v2"
    CACHE_SECONDS = 300

    @extend_schema(responses=PublicStatsSerializer)
    def get(self, request):
        data = cache.get(self.CACHE_KEY)
        if data is None:
            data = self._build()
            cache.set(self.CACHE_KEY, data, self.CACHE_SECONDS)
        return Response(data)

    def _build(self):
        now = timezone.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        masters = Concern.objects.filter(duplicate_of__isnull=True).exclude(status=Concern.Status.REJECTED)

        agg = masters.aggregate(
            total=Count("id"),
            open=Count("id", filter=Q(status__in=Concern.OPEN_STATUSES)),
            resolved=Count("id", filter=Q(status__in=Concern.DONE_STATUSES)),
            this_month=Count("id", filter=Q(created_at__gte=month_start)),
            resolved_this_month=Count("id", filter=Q(resolved_at__gte=month_start)),
        )
        avg = masters.filter(resolved_at__isnull=False).aggregate(
            v=Avg(ExpressionWrapper(F("resolved_at") - F("created_at"), output_field=DurationField()))
        )["v"]
        agg["avg_resolution_hours"] = round(avg.total_seconds() / 3600, 1) if avg else None
        agg["resolution_rate"] = round(agg["resolved"] / agg["total"] * 100, 1) if agg["total"] else 0.0
        agg["reports_received"] = Concern.objects.count()  # includes linked duplicates

        last_90 = now - timedelta(days=90)
        done_90 = list(masters.filter(resolved_at__gte=last_90, status__in=Concern.DONE_STATUSES)
                       .values_list("created_at", "resolved_at", "case__due_at"))
        days = sorted((r - c).total_seconds() / 86400 for c, r, _ in done_90)
        agg["median_days_90d"] = round(days[len(days) // 2], 1) if days else None
        with_due = [(r, d) for _, r, d in done_90 if d]
        agg["on_time_rate_90d"] = round(sum(1 for r, d in with_due if r <= d) / len(with_due) * 100, 1) if with_due else None
        agg["resolved_90d"] = len(done_90)
        by_category = list(
            masters.filter(created_at__gte=last_90, category__isnull=False)
            .values(code=F("category__code"), name=F("category__name"))
            .annotate(count=Count("id"))
            .order_by("-count")
        )
        by_barangay = list(
            Barangay.objects.annotate(
                open=Count("concerns", filter=Q(
                    concerns__status__in=Concern.OPEN_STATUSES, concerns__duplicate_of__isnull=True
                )),
                total_90d=Count("concerns", filter=Q(
                    concerns__created_at__gte=last_90, concerns__duplicate_of__isnull=True
                )),
            )
            .filter(total_90d__gt=0)
            .values("id", "name", "center_lat", "center_lng", "open", "total_90d")
            .order_by("-total_90d")
        )
        for b in by_barangay:
            b["center_lat"] = float(b["center_lat"]) if b["center_lat"] is not None else None
            b["center_lng"] = float(b["center_lng"]) if b["center_lng"] is not None else None

        return {
            "totals": agg,
            "by_category": by_category,
            "by_barangay": by_barangay,
            "generated_at": now.isoformat(),
        }


class PublicNotifyPrefsView(PublicMixin, APIView):
    """Reporter turns SMS updates off (or back on) from the tracking page. Needs the last 4 digits of the number."""

    throttle_scope = "public_submit"

    @extend_schema(request=PublicNotifyPrefsSerializer, responses=PublicTrackSerializer)
    def post(self, request, reference_no):
        concern = get_object_or_404(Concern, reference_no=reference_no.strip().upper())
        ser = PublicNotifyPrefsSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        digits = "".join(ch for ch in concern.reporter_contact if ch.isdigit())
        if not digits or ser.validated_data["mobile_last4"] != digits[-4:]:
            return Response({"detail": "Hindi tugma ang huling 4 na numero ng mobile na ginamit sa report."},
                            status=status.HTTP_400_BAD_REQUEST)
        concern.notify_sms = ser.validated_data["sms"]
        concern.save(update_fields=["notify_sms", "updated_at"])
        return Response(PublicTrackSerializer(concern, context={"request": request}).data)
