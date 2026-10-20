"""
GIS endpoints (Module 5). Everything is role-scoped through cases.scoping, so a barangay user only maps
their barangay, an office only its cases, and the City Administrator / Mayor see the whole city.
"""
import statistics
from collections import Counter, defaultdict
from datetime import timedelta

from django.db.models import Count, IntegerField, OuterRef, Q, Subquery
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.utils.dateparse import parse_date
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import STAFF_ROLES, HasRole
from apps.cases.scoping import scoped_concerns
from apps.concerns.models import Concern

from . import hotspots
from .models import Barangay

IsStaff = HasRole(*STAFF_ROLES)
OPEN = Concern.OPEN_STATUSES

FILTER_PARAMS = [
    OpenApiParameter("days", int, description="Look-back window in days (default 90). Ignored if date_from is set."),
    OpenApiParameter("date_from", str, description="YYYY-MM-DD"),
    OpenApiParameter("date_to", str, description="YYYY-MM-DD"),
    OpenApiParameter("category", str), OpenApiParameter("subcategory", str),
    OpenApiParameter("status", enum=["all", "open", "resolved"]),
    OpenApiParameter("priority", str, description="P1..P4"),
    OpenApiParameter("department", int),
    OpenApiParameter("barangay", int),
]


def filtered(request):
    """Original reports (not linked duplicates) matching the map filters, with their duplicate counts."""
    p = request.query_params
    # drop scoped_concerns' joins here: they bloat the GROUP BY of the duplicate count below
    qs = scoped_concerns(request.user).select_related(None) \
        .filter(duplicate_of__isnull=True).exclude(status=Concern.Status.REJECTED)
    if p.get("date_from"):
        qs = qs.filter(created_at__date__gte=parse_date(p["date_from"]))
        if p.get("date_to"):
            qs = qs.filter(created_at__date__lte=parse_date(p["date_to"]))
    else:
        days = int(p.get("days") or 90)
        qs = qs.filter(created_at__gte=timezone.now() - timedelta(days=days))
    if p.get("category"):
        qs = qs.filter(category__code=p["category"])
    if p.get("subcategory"):
        qs = qs.filter(subcategory__code=p["subcategory"])
    status = p.get("status", "all")
    if status == "open":
        qs = qs.filter(status__in=OPEN)
    elif status == "resolved":
        qs = qs.filter(status__in=Concern.DONE_STATUSES)
    if p.get("priority"):
        qs = qs.filter(case__priority_level__code=p["priority"])
    if p.get("department"):
        qs = qs.filter(case__department_id=p["department"])
    if p.get("barangay"):
        qs = qs.filter(barangay_id=p["barangay"])
    dup_counts = Concern.objects.filter(duplicate_of=OuterRef("pk")).order_by().values("duplicate_of") \
        .annotate(n=Count("id")).values("n")
    return qs.annotate(dups=Coalesce(Subquery(dup_counts, output_field=IntegerField()), 0))


# ---------------- schema serializers ----------------

class MapPointSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    ref = serializers.CharField()
    lat = serializers.FloatField()
    lng = serializers.FloatField()
    category = serializers.CharField(allow_null=True)
    subcategory = serializers.CharField(allow_null=True)
    status = serializers.CharField()
    priority = serializers.CharField(allow_null=True)
    reports = serializers.IntegerField(help_text="1 + linked duplicate reports")
    overdue = serializers.BooleanField()
    created_at = serializers.DateTimeField()
    barangay = serializers.CharField()


class MapPointsSerializer(serializers.Serializer):
    points = MapPointSerializer(many=True)
    total = serializers.IntegerField()
    unpinned = serializers.IntegerField(help_text="Matching reports without a map pin (counted in barangay stats only)")


class IssueCountSerializer(serializers.Serializer):
    name = serializers.CharField()
    count = serializers.IntegerField()


class BarangayStatSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    lat = serializers.FloatField(allow_null=True)
    lng = serializers.FloatField(allow_null=True)
    population = serializers.IntegerField()
    concerns = serializers.IntegerField()
    reports = serializers.IntegerField()
    open = serializers.IntegerField()
    overdue = serializers.IntegerField()
    per_10k = serializers.FloatField(allow_null=True)
    median_days_to_resolve = serializers.FloatField(allow_null=True)
    top_issues = IssueCountSerializer(many=True)


class HotspotSerializer(serializers.Serializer):
    lat = serializers.FloatField()
    lng = serializers.FloatField()
    radius_m = serializers.IntegerField()
    count = serializers.IntegerField(help_text="Distinct problems (original reports) in the cluster")
    reports = serializers.IntegerField(help_text="Including duplicate reports from other residents")
    open = serializers.IntegerField()
    top_issue = serializers.CharField()
    top_issue_share = serializers.IntegerField()
    issues = IssueCountSerializer(many=True)
    barangay = serializers.CharField()
    landmark = serializers.CharField()
    months_active = serializers.IntegerField(help_text="Distinct months with reports: recurrence")
    first_report = serializers.DateTimeField()
    last_report = serializers.DateTimeField()
    concern_ids = serializers.ListField(child=serializers.IntegerField())


class HotspotsSerializer(serializers.Serializer):
    hotspots = HotspotSerializer(many=True)
    eps_m = serializers.IntegerField()
    min_samples = serializers.IntegerField()
    points_considered = serializers.IntegerField()
    noise = serializers.IntegerField(help_text="Isolated reports not in any hotspot")


# ---------------- views ----------------

class MapPointsView(APIView):
    """Pinned reports for markers and the heatmap (weight = number of residents who reported it)."""

    permission_classes = [IsStaff]

    @extend_schema(parameters=FILTER_PARAMS, responses=MapPointsSerializer)
    def get(self, request):
        now = timezone.now()
        qs = filtered(request)
        total = qs.count()
        rows = qs.filter(latitude__isnull=False, longitude__isnull=False).values(
            "id", "reference_no", "latitude", "longitude", "status", "created_at", "dups",
            "category__code", "category__name", "subcategory__name", "barangay__name",
            "case__priority_level__code", "case__due_at",
        )
        points = [{
            "id": r["id"], "ref": r["reference_no"], "lat": float(r["latitude"]), "lng": float(r["longitude"]),
            "category": r["category__code"], "subcategory": r["subcategory__name"] or r["category__name"],
            "status": r["status"], "priority": r["case__priority_level__code"], "reports": 1 + r["dups"],
            "overdue": bool(r["status"] in OPEN and r["case__due_at"] and r["case__due_at"] < now),
            "created_at": r["created_at"], "barangay": r["barangay__name"],
        } for r in rows]
        return Response({"points": points, "total": total, "unpinned": total - len(points)})


class BarangayStatsView(APIView):
    """Per-barangay load, including reports without a pin (located by barangay)."""

    permission_classes = [IsStaff]

    @extend_schema(parameters=FILTER_PARAMS, responses=BarangayStatSerializer(many=True))
    def get(self, request):
        now = timezone.now()
        rows = defaultdict(lambda: {"concerns": 0, "reports": 0, "open": 0, "overdue": 0, "issues": Counter(), "days": []})
        qs = filtered(request).select_related("category", "subcategory", "case")
        for c in qs:
            r = rows[c.barangay_id]
            r["concerns"] += 1
            r["reports"] += 1 + c.dups
            if c.status in OPEN:
                r["open"] += 1
                case = getattr(c, "case", None)
                if case and case.due_at and case.due_at < now:
                    r["overdue"] += 1
            elif c.resolved_at:
                r["days"].append((c.resolved_at - c.created_at).total_seconds() / 86400)
            r["issues"][c.subcategory.name if c.subcategory else (c.category.name if c.category else "—")] += 1
        out = []
        for b in Barangay.objects.filter(id__in=rows.keys()):
            r = rows[b.id]
            out.append({
                "id": b.id, "name": b.name,
                "lat": float(b.center_lat) if b.center_lat is not None else None,
                "lng": float(b.center_lng) if b.center_lng is not None else None,
                "population": b.population,
                "concerns": r["concerns"], "reports": r["reports"], "open": r["open"], "overdue": r["overdue"],
                "per_10k": round(r["concerns"] / b.population * 10_000, 1) if b.population else None,
                "median_days_to_resolve": round(statistics.median(r["days"]), 1) if r["days"] else None,
                "top_issues": [{"name": k, "count": v} for k, v in r["issues"].most_common(3)],
            })
        return Response(sorted(out, key=lambda x: -x["concerns"]))


class HotspotsView(APIView):
    """
    DBSCAN hotspots over distinct problems (original reports, not duplicates), so one problem reported
    by many people doesn't masquerade as a recurring hotspot. Recurrence = distinct months active.
    """

    permission_classes = [IsStaff]

    @extend_schema(parameters=FILTER_PARAMS + [
        OpenApiParameter("eps_m", int, description="Cluster radius in meters (default 75)"),
        OpenApiParameter("min_samples", int, description="Minimum distinct reports per hotspot (default 4)"),
    ], responses=HotspotsSerializer)
    def get(self, request):
        p = request.query_params
        eps_m = max(20, min(500, int(p.get("eps_m") or 75)))
        min_samples = max(2, min(50, int(p.get("min_samples") or 4)))
        qs = filtered(request).filter(latitude__isnull=False, longitude__isnull=False) \
            .select_related("category", "subcategory", "barangay")
        pts = [{
            "id": c.id, "lat": float(c.latitude), "lng": float(c.longitude), "status": c.status,
            "category": c.category.name if c.category else None,
            "subcategory": c.subcategory.name if c.subcategory else None,
            "created_at": c.created_at, "barangay": c.barangay.name, "landmark": c.location_description,
            "dups": c.dups,
        } for c in qs]
        clusters = hotspots.detect(pts, eps_m=eps_m, min_samples=min_samples)
        out = []
        for cl in clusters:
            s = hotspots.summarize(cl, OPEN)
            s["reports"] = sum(1 + m["dups"] for m in cl["members"])
            out.append(s)
        out.sort(key=lambda h: (-h["count"], -h["open"]))
        clustered = sum(h["count"] for h in out)
        return Response({"hotspots": out, "eps_m": eps_m, "min_samples": min_samples,
                         "points_considered": len(pts), "noise": len(pts) - clustered})
