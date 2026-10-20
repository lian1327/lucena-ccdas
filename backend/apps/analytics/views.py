"""
Office performance analytics. Access:
  City Administrator, Mayor's Office ─ all offices
  Department Head, Office Receiving  ─ their own office (+ city-wide benchmark row)
  Everyone else                      ─ no access (403)
"""
import csv

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_date
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.cases.models import Department

from . import accountability, kpis

R = User.Role
PERIOD_PARAMS = [
    OpenApiParameter("period", enum=["this_month", "last_month", "quarter", "90d", "12m", "custom"]),
    OpenApiParameter("date_from", str, description="YYYY-MM-DD (period=custom)"),
    OpenApiParameter("date_to", str, description="YYYY-MM-DD (period=custom)"),
]


class CanViewAnalytics(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and (
            u.is_superuser or u.role in (R.CITY_ADMIN, R.MAYOR)
            or (u.role in (R.DEPT_HEAD, R.OFFICE_DESK) and u.department_id)
        ))


def allowed_departments(user):
    if user.is_superuser or user.role in (R.CITY_ADMIN, R.MAYOR):
        return None  # all
    return [user.department_id]


def bounds(request):
    p = request.query_params
    return kpis.period_bounds(p.get("period", "90d"), parse_date(p.get("date_from") or ""), parse_date(p.get("date_to") or ""))


# ---------------- schema ----------------

class KpiSerializer(serializers.Serializer):
    received = serializers.IntegerField()
    resolved = serializers.IntegerField()
    on_time = serializers.IntegerField()
    on_time_rate = serializers.FloatField(allow_null=True)
    acceptance_rate = serializers.FloatField(allow_null=True)
    response_rate = serializers.FloatField(allow_null=True)
    p1_cases = serializers.IntegerField()
    p1_make_safe_rate = serializers.FloatField(allow_null=True)
    median_days = serializers.FloatField(allow_null=True)
    p90_days = serializers.FloatField(allow_null=True)
    backlog = serializers.IntegerField()
    overdue = serializers.IntegerField()
    aging_30 = serializers.IntegerField()
    extension_rate = serializers.FloatField(allow_null=True)
    escalation_rate = serializers.FloatField(allow_null=True)
    reopen_rate = serializers.FloatField(allow_null=True)
    returned = serializers.IntegerField()
    proof_rate = serializers.FloatField(allow_null=True)
    overrides = serializers.IntegerField()
    recurrence_rate = serializers.FloatField(allow_null=True)
    citizen_answered = serializers.IntegerField()
    citizen_not_fixed = serializers.IntegerField()
    not_fixed_rate = serializers.FloatField(allow_null=True)
    quality_rate = serializers.FloatField(allow_null=True)
    index = serializers.FloatField(allow_null=True)
    grade = serializers.ChoiceField(choices=["good", "watch", "attention", "insufficient"])
    flags = serializers.ListField(child=serializers.CharField())


class OfficeRowSerializer(KpiSerializer):
    department_id = serializers.IntegerField()
    code = serializers.CharField()
    name = serializers.CharField()
    rank = serializers.IntegerField(allow_null=True)


class PeriodSerializer(serializers.Serializer):
    label = serializers.CharField()
    start = serializers.DateTimeField()
    end = serializers.DateTimeField()


class ScorecardSerializer(serializers.Serializer):
    period = PeriodSerializer()
    city = KpiSerializer()
    offices = OfficeRowSerializer(many=True)
    weights = serializers.DictField(child=serializers.FloatField())
    targets = serializers.DictField(child=serializers.FloatField())
    min_sample = serializers.IntegerField()


class TrendPointSerializer(serializers.Serializer):
    month = serializers.CharField()
    label = serializers.CharField()
    received = serializers.IntegerField()
    resolved = serializers.IntegerField()
    on_time_rate = serializers.FloatField(allow_null=True)


class DivisionRowSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    received = serializers.IntegerField()
    resolved = serializers.IntegerField()
    on_time_rate = serializers.FloatField(allow_null=True)
    response_rate = serializers.FloatField(allow_null=True)
    median_days = serializers.FloatField(allow_null=True)
    backlog = serializers.IntegerField()
    overdue = serializers.IntegerField()
    aging_30 = serializers.IntegerField()
    proof_rate = serializers.FloatField(allow_null=True)


class NamedCountSerializer(serializers.Serializer):
    name = serializers.CharField()
    count = serializers.IntegerField()


class AgingSerializer(serializers.Serializer):
    bucket = serializers.CharField()
    count = serializers.IntegerField()


class OverdueCaseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    reference_no = serializers.CharField()
    title = serializers.CharField()
    barangay = serializers.CharField()
    priority = serializers.CharField(allow_null=True)
    due_at = serializers.DateTimeField()
    days_overdue = serializers.IntegerField()
    escalation_level = serializers.IntegerField()
    stage = serializers.CharField()


class WorkloadSerializer(serializers.Serializer):
    name = serializers.CharField()
    open = serializers.IntegerField()


class DeptRefSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    code = serializers.CharField()
    name = serializers.CharField()


class OfficeDetailSerializer(serializers.Serializer):
    period = PeriodSerializer()
    department = DeptRefSerializer()
    kpis = KpiSerializer()
    city = KpiSerializer()
    divisions = DivisionRowSerializer(many=True)
    aging = AgingSerializer(many=True)
    top_issues = NamedCountSerializer(many=True)
    trend = TrendPointSerializer(many=True)
    city_trend = TrendPointSerializer(many=True)
    oldest_overdue = OverdueCaseSerializer(many=True)
    workload = WorkloadSerializer(many=True)


# ---------------- views ----------------

class OfficeScorecardView(APIView):
    permission_classes = [CanViewAnalytics]

    @extend_schema(parameters=PERIOD_PARAMS, responses=ScorecardSerializer, operation_id="analytics_office_scorecard")
    def get(self, request):
        start, end, label = bounds(request)
        allowed = allowed_departments(request.user)
        rows, city = kpis.scorecard(start, end, allowed)
        if allowed is not None:
            _, city = kpis.scorecard(start, end, None)  # benchmark is always the whole LGU
        return Response({
            "period": {"label": label, "start": start, "end": end},
            "city": city, "offices": rows,
            "weights": kpis.WEIGHTS, "targets": kpis.TARGETS, "min_sample": kpis.MIN_SAMPLE,
        })


class OfficeDetailView(APIView):
    permission_classes = [CanViewAnalytics]

    @extend_schema(parameters=PERIOD_PARAMS, responses=OfficeDetailSerializer, operation_id="analytics_office_detail")
    def get(self, request, pk):
        allowed = allowed_departments(request.user)
        if allowed is not None and pk not in allowed:
            raise PermissionDenied("You can only view your own office's performance.")
        dept = get_object_or_404(Department, pk=pk, kind=Department.Kind.INTERNAL)
        start, end, label = bounds(request)
        data = kpis.office_detail(dept, start, end)
        _, city = kpis.scorecard(start, end, None)
        if request.user.role == R.OFFICE_DESK:
            data["workload"] = []  # staff workload is for heads and the City Administrator
        return Response({"period": {"label": label, "start": start, "end": end}, "city": city, **data})


class OfficeScorecardCSV(APIView):
    """Spreadsheet export of the scorecard (opens in Excel / Google Sheets)."""

    permission_classes = [CanViewAnalytics]

    @extend_schema(parameters=PERIOD_PARAMS, responses={(200, "text/csv"): str}, operation_id="analytics_office_scorecard_csv")
    def get(self, request):
        start, end, label = bounds(request)
        allowed = allowed_departments(request.user)
        rows, city = kpis.scorecard(start, end, allowed)
        if allowed is not None:
            _, city = kpis.scorecard(start, end, None)
        resp = HttpResponse(content_type="text/csv; charset=utf-8")
        resp["Content-Disposition"] = f'attachment; filename="ccadss-office-kpis-{start:%Y%m%d}-{end:%Y%m%d}.csv"'
        resp.write("﻿")  # BOM so Excel reads UTF-8
        w = csv.writer(resp)
        w.writerow([f"CCADSS Office Performance — {label}"])
        cols = ["rank", "code", "name", "index", "grade", "received", "resolved", "on_time_rate", "response_rate",
                "acceptance_rate", "p1_make_safe_rate", "median_days", "backlog", "overdue", "aging_30",
                "extension_rate", "escalation_rate", "reopen_rate", "returned",
                "proof_rate", "overrides", "recurrence_rate", "citizen_answered", "citizen_not_fixed", "flags"]
        w.writerow(cols)
        for r in rows + [{"rank": "", "code": "CITY", "name": "City-wide", **city}]:
            w.writerow([("; ".join(r[c]) if c == "flags" else ("" if r.get(c) is None else r.get(c))) for c in cols])
        return resp


# ================= Accountability (Step 10) =================

class FlagSerializer(serializers.Serializer):
    code = serializers.CharField()
    level = serializers.CharField()
    label = serializers.CharField()


class OfficeProofRowSerializer(serializers.Serializer):
    department_id = serializers.IntegerField()
    code = serializers.CharField()
    name = serializers.CharField()
    resolved = serializers.IntegerField()
    before_after = serializers.IntegerField()
    verified_proof = serializers.IntegerField()
    proof_rate = serializers.FloatField(allow_null=True)
    photos = serializers.IntegerField()
    red_flag_photos = serializers.IntegerField()
    reports = serializers.IntegerField()
    reports_returned = serializers.IntegerField()
    overrides = serializers.IntegerField()
    citizen_answered = serializers.IntegerField()
    citizen_fixed = serializers.IntegerField()
    citizen_not_fixed = serializers.IntegerField()
    recurrences = serializers.IntegerField()


class WatchItemSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=["pending_red", "override", "disputed", "recurrence"])
    label = serializers.CharField()
    level = serializers.CharField()
    at = serializers.DateTimeField()
    who = serializers.CharField(allow_null=True)
    detail = serializers.CharField(allow_blank=True)
    concern_id = serializers.IntegerField()
    reference_no = serializers.CharField()
    title = serializers.CharField()
    barangay = serializers.CharField()
    office = serializers.CharField(allow_null=True)


class AccountabilitySerializer(serializers.Serializer):
    period = PeriodSerializer()
    offices = OfficeProofRowSerializer(many=True)
    watchlist = WatchItemSerializer(many=True)
    proof_target = serializers.FloatField()


class PersonActionsSerializer(serializers.Serializer):
    accepted = serializers.IntegerField()
    responded = serializers.IntegerField()
    inspected = serializers.IntegerField()
    submitted = serializers.IntegerField()
    crew = serializers.IntegerField()
    validated = serializers.IntegerField()
    returned = serializers.IntegerField()
    overrides = serializers.IntegerField()


class PersonRowSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    role = serializers.CharField()
    role_display = serializers.CharField()
    division = serializers.CharField(allow_null=True)
    actions = PersonActionsSerializer()
    total_actions = serializers.IntegerField()
    open_assigned = serializers.IntegerField()
    photos = serializers.IntegerField()
    red_flag_photos = serializers.IntegerField()
    located_rate = serializers.FloatField(allow_null=True)
    reports_returned = serializers.IntegerField()
    citizen_not_fixed = serializers.IntegerField()
    recurrences = serializers.IntegerField()


class PeopleSerializer(serializers.Serializer):
    period = PeriodSerializer()
    department = DeptRefSerializer()
    people = PersonRowSerializer(many=True)


class LedgerPhotoSerializer(serializers.Serializer):
    url = serializers.CharField()
    kind = serializers.CharField()
    distance_m = serializers.FloatField(allow_null=True)
    gps_source = serializers.CharField()
    flags = FlagSerializer(many=True)


class LedgerItemSerializer(serializers.Serializer):
    at = serializers.DateTimeField()
    kind = serializers.CharField()
    label = serializers.CharField()
    concern_id = serializers.IntegerField()
    reference_no = serializers.CharField()
    title = serializers.CharField()
    barangay = serializers.CharField()
    detail = serializers.CharField(allow_blank=True)
    ok = serializers.BooleanField(allow_null=True)
    flags = FlagSerializer(many=True)
    photos = LedgerPhotoSerializer(many=True)


class PersonRefSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    role_display = serializers.CharField()
    department = serializers.CharField(allow_null=True)
    department_id = serializers.IntegerField(allow_null=True)
    division = serializers.CharField(allow_null=True)


class LedgerSerializer(serializers.Serializer):
    period = PeriodSerializer()
    person = PersonRefSerializer()
    summary = PersonRowSerializer(allow_null=True)
    items = LedgerItemSerializer(many=True)


def _period(request):
    start, end, label = bounds(request)
    return start, end, {"label": label, "start": start, "end": end}


class AccountabilityView(APIView):
    """Proof-of-work quality per office + the supervisor watchlist."""

    permission_classes = [CanViewAnalytics]

    @extend_schema(parameters=PERIOD_PARAMS, responses=AccountabilitySerializer, operation_id="analytics_accountability")
    def get(self, request):
        start, end, period = _period(request)
        allowed = allowed_departments(request.user)
        return Response({
            "period": period,
            "offices": accountability.office_proof(start, end, allowed),
            "watchlist": accountability.watchlist(start, end, allowed),
            "proof_target": kpis.TARGETS["proof"],
        })


def _people_scope(user, dept):
    """None = whole office; a division id = only that division; raises if not allowed."""
    if user.is_superuser or user.role in (R.CITY_ADMIN, R.MAYOR):
        return None
    if user.department_id == dept.id and user.role == R.DEPT_HEAD:
        return None
    if user.department_id == dept.id and user.role == R.DIVISION_CHIEF and user.division_id:
        return user.division_id
    raise PermissionDenied("Only the City Administrator, the Mayor's Office, the Department Head or a Division Chief can view this.")


class OfficePeopleView(APIView):
    """What each person in an office did, and the quality of their proof. Sorted by name, not ranked."""

    @extend_schema(parameters=PERIOD_PARAMS, responses=PeopleSerializer, operation_id="analytics_office_people")
    def get(self, request, pk):
        dept = get_object_or_404(Department, pk=pk, kind=Department.Kind.INTERNAL)
        division_id = _people_scope(request.user, dept)
        start, end, period = _period(request)
        return Response({
            "period": period, "department": {"id": dept.id, "code": dept.code, "name": dept.name},
            "people": accountability.people(dept, start, end, division_id),
        })


class PersonLedgerView(APIView):
    """One person's actions with the evidence for each. Anyone may view their own."""

    @extend_schema(parameters=PERIOD_PARAMS, responses=LedgerSerializer, operation_id="analytics_person_ledger")
    def get(self, request, pk):
        person = get_object_or_404(User.objects.select_related("department", "division"), pk=pk)
        u = request.user
        if not u.is_authenticated or u.role == R.CITIZEN:
            raise PermissionDenied()
        if u.id != person.id:
            if not person.department_id:
                if not (u.is_superuser or u.role in (R.CITY_ADMIN, R.MAYOR)):
                    raise PermissionDenied()
            else:
                division_id = _people_scope(u, person.department)
                if division_id and person.division_id != division_id:
                    raise PermissionDenied("This person is not in your division.")
        start, end, period = _period(request)
        summary = None
        if person.department_id and person.department.kind == Department.Kind.INTERNAL:
            summary = next((p for p in accountability.people(person.department, start, end) if p["id"] == person.id), None)
        return Response({
            "period": period,
            "person": {"id": person.id, "name": person.get_full_name() or person.username,
                       "role_display": person.get_role_display(),
                       "department": person.department.name if person.department else None,
                       "department_id": person.department_id,
                       "division": person.division.name if person.division else None},
            "summary": summary,
            "items": accountability.ledger(person, start, end),
        })


# ================= Executive (Step 11) =================
from . import executive  # noqa: E402


class IsExecutive(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and (u.is_superuser or u.role in (R.CITY_ADMIN, R.MAYOR)))


class ExecCategorySerializer(serializers.Serializer):
    code = serializers.CharField()
    name = serializers.CharField()
    name_en = serializers.CharField()
    count = serializers.IntegerField()
    prev = serializers.IntegerField()
    change = serializers.FloatField(allow_null=True)
    avg3 = serializers.FloatField()


class ExecBarangaySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    rank = serializers.IntegerField(allow_null=True)
    name = serializers.CharField()
    population = serializers.IntegerField(allow_null=True)
    count = serializers.IntegerField()
    prev = serializers.IntegerField()
    change = serializers.FloatField(allow_null=True)
    per_1000 = serializers.FloatField(allow_null=True)
    open_now = serializers.IntegerField()
    overdue_now = serializers.IntegerField()
    top_issue = serializers.CharField(allow_null=True)
    cells = serializers.DictField(child=serializers.IntegerField())


class RankItemSerializer(serializers.Serializer):
    barangay = serializers.CharField()
    barangay_id = serializers.IntegerField()
    count = serializers.IntegerField()
    prev = serializers.IntegerField()
    share = serializers.FloatField(allow_null=True)


class RankingSerializer(serializers.Serializer):
    code = serializers.CharField()
    name = serializers.CharField()
    total = serializers.IntegerField()
    top = RankItemSerializer(many=True)


class RangeSerializer(serializers.Serializer):
    estimate = serializers.FloatField()
    low = serializers.IntegerField()
    high = serializers.IntegerField()
    method = serializers.CharField()
    method_label = serializers.CharField()
    backtest_mape = serializers.FloatField(allow_null=True)
    naive_mape = serializers.FloatField(allow_null=True)


class ForecastCategorySerializer(RangeSerializer):
    code = serializers.CharField()
    name = serializers.CharField()
    series = serializers.ListField(child=serializers.IntegerField())


class ForecastSerializer(serializers.Serializer):
    month = serializers.CharField()
    label = serializers.CharField()
    months = serializers.ListField(child=serializers.CharField())
    month_labels = serializers.ListField(child=serializers.CharField())
    categories = ForecastCategorySerializer(many=True)
    method = serializers.CharField()
    backtest_mape = serializers.FloatField(allow_null=True)
    naive_mape = serializers.FloatField(allow_null=True)


class FocusSerializer(serializers.Serializer):
    barangay = serializers.CharField()
    count = serializers.IntegerField()


class ResourceSerializer(serializers.Serializer):
    department_id = serializers.IntegerField()
    code = serializers.CharField()
    name = serializers.CharField()
    forecast = RangeSerializer()
    capacity = serializers.FloatField()
    backlog = serializers.IntegerField()
    overdue = serializers.IntegerField()
    field_staff = serializers.IntegerField()
    per_staff = serializers.FloatField(allow_null=True)
    demand = serializers.FloatField()
    gap = serializers.FloatField()
    extra_staff = serializers.IntegerField()
    status = serializers.ChoiceField(choices=["ok", "short"])
    focus_barangays = FocusSerializer(many=True)
    text = serializers.CharField()
    text_en = serializers.CharField()


class InsightSerializer(serializers.Serializer):
    kind = serializers.CharField()
    level = serializers.ChoiceField(choices=["red", "amber", "info"])
    text = serializers.CharField()
    text_en = serializers.CharField()
    value = serializers.FloatField(allow_null=True)
    barangay_id = serializers.IntegerField(allow_null=True)
    category = serializers.CharField(allow_null=True)


class ExecTotalsSerializer(serializers.Serializer):
    problems = serializers.IntegerField()
    prev = serializers.IntegerField()
    change = serializers.FloatField(allow_null=True)
    reports = serializers.IntegerField()
    resolved = serializers.IntegerField()
    open_now = serializers.IntegerField()
    overdue_now = serializers.IntegerField()
    barangays_reporting = serializers.IntegerField()


class CohortSerializer(serializers.Serializer):
    received = serializers.IntegerField()
    accomplished = serializers.IntegerField()
    open = serializers.IntegerField()
    accomplished_rate = serializers.FloatField(allow_null=True)
    within_30d = serializers.IntegerField()
    within_30d_rate = serializers.FloatField(allow_null=True)
    on_time_rate = serializers.FloatField(allow_null=True)
    median_days = serializers.FloatField(allow_null=True)


class CohortBlockSerializer(CohortSerializer):
    has_data = serializers.BooleanField()
    label = serializers.CharField()


class CohortYearSerializer(CohortSerializer):
    year = serializers.IntegerField()
    partial = serializers.BooleanField()


class YoyPointSerializer(serializers.Serializer):
    month = serializers.CharField()
    label = serializers.CharField()
    this_year = CohortSerializer()
    last_year = CohortSerializer(allow_null=True)


class YoyIssueSerializer(serializers.Serializer):
    code = serializers.CharField()
    name = serializers.CharField()
    name_en = serializers.CharField()
    this_year = CohortSerializer()
    last_year = CohortSerializer()


class AccomplishmentSerializer(serializers.Serializer):
    month = CohortBlockSerializer()
    month_last_year = CohortBlockSerializer()
    ytd = CohortBlockSerializer()
    ytd_last_year = CohortBlockSerializer()
    trend = YoyPointSerializer(many=True)
    by_issue = YoyIssueSerializer(many=True)
    years = CohortYearSerializer(many=True)
    mature_days = serializers.IntegerField()


class ExecutiveSerializer(serializers.Serializer):
    month = serializers.CharField()
    label = serializers.CharField()
    partial = serializers.BooleanField()
    start = serializers.DateTimeField()
    end = serializers.DateTimeField()
    prev_label = serializers.CharField()
    totals = ExecTotalsSerializer()
    categories = ExecCategorySerializer(many=True)
    barangays = ExecBarangaySerializer(many=True)
    rankings = RankingSerializer(many=True)
    forecast = ForecastSerializer()
    resources = ResourceSerializer(many=True)
    insights = InsightSerializer(many=True)
    offices = OfficeRowSerializer(many=True)
    city = KpiSerializer()
    accomplishment = AccomplishmentSerializer()


class ExecutiveView(APIView):
    """The Mayor's monthly picture. ?month=YYYY-MM (default: last complete month)."""

    permission_classes = [IsExecutive]

    @extend_schema(parameters=[OpenApiParameter("month", str, description="YYYY-MM")], responses=ExecutiveSerializer,
                   operation_id="analytics_executive")
    def get(self, request):
        data = executive.overview(request.query_params.get("month"))
        rows, city = kpis.scorecard(data["start"], data["end"], None)
        acc = executive.accomplishment(request.query_params.get("month"))
        return Response({**data, "offices": rows, "city": city, "accomplishment": acc})


class ExecutiveBarangayCSV(APIView):
    permission_classes = [IsExecutive]

    @extend_schema(parameters=[OpenApiParameter("month", str)], responses={(200, "text/csv"): str},
                   operation_id="analytics_executive_barangays_csv")
    def get(self, request):
        data = executive.overview(request.query_params.get("month"))
        codes = [c["code"] for c in data["categories"]]
        resp = HttpResponse(content_type="text/csv; charset=utf-8")
        resp["Content-Disposition"] = f'attachment; filename="ccadss-barangays-{data["month"]}.csv"'
        resp.write("﻿")
        w = csv.writer(resp)
        w.writerow([f"CCADSS Barangay × issue — {data['label']} (problems, duplicates merged)"])
        w.writerow(["rank", "barangay", "population", "problems", "per_1000", "prev_month", "change", "open_now", "overdue_now"]
                   + [c["name_en"] for c in data["categories"]])
        for b in data["barangays"]:
            w.writerow([b["rank"] or "", b["name"], b["population"] or "", b["count"], b["per_1000"] or "", b["prev"],
                        "" if b["change"] is None else b["change"], b["open_now"], b["overdue_now"]] + [b["cells"][c] for c in codes])
        return resp
