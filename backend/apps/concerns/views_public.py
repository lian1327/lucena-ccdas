"""
Public (no-login) endpoints for the landing page and citizen portal.
Authentication is disabled here so a stale/expired JWT in the browser never blocks a citizen.
"""
from datetime import timedelta

from django.core.cache import cache
from django.db.models import Avg, Count, DurationField, ExpressionWrapper, F, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.geo.models import Barangay

from .models import Category, Concern
from .serializers import (
    PublicBarangaySerializer,
    PublicCategorySerializer,
    PublicConcernCreateSerializer,
    PublicStatsSerializer,
    PublicTrackSerializer,
)


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


class PublicTrackView(PublicMixin, generics.RetrieveAPIView):
    serializer_class = PublicTrackSerializer
    throttle_scope = "public_track"

    def get_object(self):
        ref = self.kwargs["reference_no"].strip().upper()
        return get_object_or_404(
            Concern.objects.select_related("category", "subcategory", "barangay", "duplicate_of", "case__department"),
            reference_no=ref,
        )


class PublicStatsView(PublicMixin, APIView):
    """Transparency stats for the landing page. Aggregates only — no individual records. Cached 5 min."""

    CACHE_KEY = "public_stats_v1"
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
