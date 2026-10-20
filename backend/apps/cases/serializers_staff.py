from datetime import datetime, timedelta

from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.accounts.models import User
from apps.concerns.models import Category, Concern, ConcernAttachment, StatusHistory, Subcategory
from apps.concerns.serializers import AFFECTED_BUCKETS, PublicConcernCreateSerializer
from apps.concerns.services import on_concern_submitted

from . import deadlines, evidence
from .models import (
    AccomplishmentReport, Case, CaseNote, Department, Division, Endorsement, EndorsementFollowUp, PriorityLevel,
)
from .scoping import permissions_for
from .services import breaches, suggest_priority, suggested_route

MAX_PHOTOS = 3


def _name(u):
    return (u.get_full_name() or u.username) if u else None


def _end_of_day(d):
    return timezone.make_aware(datetime.combine(d, deadlines.END_OF_DAY), timezone.get_current_timezone())


# ---------- Lookups ----------

class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ["id", "code", "name", "kind"]


class PriorityLevelSerializer(serializers.ModelSerializer):
    class Meta:
        model = PriorityLevel
        fields = ["id", "code", "name", "name_fil", "description", "response_hours", "response_working_days",
                  "resolution_cap_days", "color"]


class DivisionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Division
        fields = ["id", "code", "name", "department"]


class StaffUserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    role_display = serializers.CharField(source="get_role_display")

    class Meta:
        model = User
        fields = ["id", "username", "full_name", "role", "role_display", "department", "division"]

    def get_full_name(self, obj) -> str:
        return _name(obj)


# ---------- List ----------

class StaffConcernListSerializer(serializers.ModelSerializer):
    category = serializers.CharField(source="category.name", default=None)
    subcategory = serializers.CharField(source="subcategory.name", default=None)
    barangay = serializers.CharField(source="barangay.name")
    status_display = serializers.CharField(source="get_status_display")
    priority_score = serializers.FloatField()
    priority_tier = serializers.CharField()
    is_overdue = serializers.BooleanField()
    level = serializers.CharField(source="case.level", default=None)
    stage = serializers.CharField(source="case.stage", default=None)
    department = serializers.CharField(source="case.department.name", default=None)
    department_is_external = serializers.BooleanField(source="case.department.is_external", default=False)
    division = serializers.CharField(source="case.division.name", default=None)
    assigned_to = serializers.SerializerMethodField()
    due_at = serializers.DateTimeField(source="case.due_at", default=None)
    extended = serializers.SerializerMethodField()
    escalation_level = serializers.IntegerField(source="case.escalation_level", default=0)
    duplicate_count = serializers.IntegerField(read_only=True, default=0)
    channel_display = serializers.CharField(source="get_channel_display")
    priority_code = serializers.CharField(source="case.priority_level.code", default=None)
    priority_name = serializers.CharField(source="case.priority_level.name", default=None)
    priority_color = serializers.CharField(source="case.priority_level.color", default=None)
    response_due_at = serializers.DateTimeField(source="case.response_due_at", default=None)
    responded_at = serializers.DateTimeField(source="case.responded_at", default=None)
    acceptance_due_at = serializers.DateTimeField(source="case.acceptance_due_at", default=None)
    return_reason = serializers.CharField(source="case.return_reason", default=None)

    class Meta:
        model = Concern
        fields = [
            "id", "reference_no", "title", "category", "subcategory", "barangay", "location_description",
            "status", "status_display", "priority_score", "priority_tier", "danger_now", "is_verified",
            "is_overdue", "involves_barangay_officials", "channel", "channel_display", "created_at",
            "level", "stage", "department", "department_is_external", "division", "assigned_to",
            "due_at", "extended", "escalation_level", "duplicate_count",
            "external_ticket_no", "external_feedback_due_at", "external_feedback_sent_at",
            "priority_code", "priority_name", "priority_color", "response_due_at", "responded_at",
            "acceptance_due_at", "return_reason",
        ]

    def get_assigned_to(self, obj) -> str | None:
        case = getattr(obj, "case", None)
        return _name(case.assigned_to) if case else None

    def get_extended(self, obj) -> bool:
        case = getattr(obj, "case", None)
        return bool(case and case.extended_at)


# ---------- Detail ----------

class EvidenceFlagSerializer(serializers.Serializer):
    code = serializers.CharField()
    level = serializers.ChoiceField(choices=["red", "amber", "info"])
    label = serializers.CharField()


class AttachmentSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()
    uploaded_by = serializers.SerializerMethodField()
    flags = serializers.SerializerMethodField()

    class Meta:
        model = ConcernAttachment
        fields = ["id", "kind", "url", "caption", "uploaded_at", "uploaded_by", "report_id",
                  "taken_at", "time_source", "latitude", "longitude", "gps_source", "gps_accuracy_m", "distance_m", "flags"]

    def get_url(self, obj) -> str:
        return obj.file.url

    def get_uploaded_by(self, obj) -> str | None:
        return _name(obj.uploaded_by)

    @extend_schema_field(EvidenceFlagSerializer(many=True))
    def get_flags(self, obj):
        return evidence.flag_list(obj.flags or [])


class MaterialSerializer(serializers.Serializer):
    item = serializers.CharField(max_length=120)
    qty = serializers.FloatField(required=False, allow_null=True)
    unit = serializers.CharField(max_length=30, required=False, allow_blank=True)


class AccomplishmentReportSerializer(serializers.ModelSerializer):
    submitted_by = serializers.SerializerMethodField()
    reviewed_by = serializers.SerializerMethodField()
    crew = serializers.SerializerMethodField()
    materials = MaterialSerializer(many=True)
    status_display = serializers.CharField(source="get_status_display")
    headcount = serializers.IntegerField()
    man_hours = serializers.FloatField(allow_null=True)

    class Meta:
        model = AccomplishmentReport
        fields = ["id", "status", "status_display", "submitted_by", "submitted_at", "work_done", "started_at", "finished_at",
                  "crew", "other_workers", "headcount", "man_hours", "materials", "equipment",
                  "reviewed_by", "reviewed_at", "review_remarks", "override_reason"]

    def get_submitted_by(self, obj) -> str | None:
        return _name(obj.submitted_by)

    def get_reviewed_by(self, obj) -> str | None:
        return _name(obj.reviewed_by)

    def get_crew(self, obj) -> list[str]:
        return [_name(u) for u in obj.crew.all()]


class EvidenceSummarySerializer(serializers.Serializer):
    before = serializers.IntegerField()
    after = serializers.IntegerField()
    located = serializers.IntegerField()
    has_before_after = serializers.BooleanField()
    verified = serializers.BooleanField()
    red_flags = EvidenceFlagSerializer(many=True)
    amber_flags = EvidenceFlagSerializer(many=True)


class TrailStepSerializer(serializers.Serializer):
    key = serializers.CharField()
    label = serializers.CharField()
    who = serializers.CharField(allow_null=True)
    at = serializers.DateTimeField(allow_null=True)
    detail = serializers.CharField(allow_blank=True)
    ok = serializers.BooleanField(allow_null=True)


class HistorySerializer(serializers.ModelSerializer):
    status = serializers.ChoiceField(source="to_status", choices=Concern.Status.choices)
    status_display = serializers.CharField(source="get_to_status_display")
    changed_by = serializers.SerializerMethodField()

    class Meta:
        model = StatusHistory
        fields = ["id", "from_status", "status", "status_display", "remarks", "is_public", "changed_by", "created_at"]

    def get_changed_by(self, obj) -> str:
        return _name(obj.changed_by) or "System"


class NoteSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()

    class Meta:
        model = CaseNote
        fields = ["id", "author", "body", "created_at"]

    def get_author(self, obj) -> str:
        return _name(obj.author) or "System"


class FollowUpSerializer(serializers.ModelSerializer):
    by = serializers.SerializerMethodField()

    class Meta:
        model = EndorsementFollowUp
        fields = ["id", "at", "by", "method", "notes"]

    def get_by(self, obj) -> str:
        return _name(obj.by) or "System"


class EndorsementSerializer(serializers.ModelSerializer):
    agency = serializers.CharField(source="agency.name")
    status_display = serializers.CharField(source="get_status_display")
    endorsed_by = serializers.SerializerMethodField()
    follow_ups = FollowUpSerializer(many=True, read_only=True)
    follow_up_due = serializers.SerializerMethodField()

    class Meta:
        model = Endorsement
        fields = [
            "id", "agency", "status", "status_display", "endorsed_at", "endorsed_by", "letter_reference",
            "contact_person", "agency_response", "next_follow_up_at", "follow_up_due", "follow_up_count", "follow_ups",
        ]

    def get_endorsed_by(self, obj) -> str | None:
        return _name(obj.endorsed_by)

    def get_follow_up_due(self, obj) -> bool:
        return bool(obj.next_follow_up_at and obj.next_follow_up_at <= timezone.now())


class CaseInfoSerializer(serializers.ModelSerializer):
    level_display = serializers.CharField(source="get_level_display")
    department = serializers.CharField(source="department.name", default=None)
    division = serializers.CharField(source="division.name", default=None)
    assigned_to = serializers.SerializerMethodField()
    inspected_by = serializers.SerializerMethodField()
    work_completed_by = serializers.SerializerMethodField()
    validated_by = serializers.SerializerMethodField()
    escalation_level_display = serializers.CharField(source="get_escalation_level_display")
    stage = serializers.CharField()
    max_extension_due = serializers.SerializerMethodField()
    endorsements = EndorsementSerializer(many=True, read_only=True)
    priority_level = PriorityLevelSerializer(read_only=True, default=None)
    accepted_by = serializers.SerializerMethodField()
    responded_by = serializers.SerializerMethodField()
    screening_checklist = serializers.SerializerMethodField()
    breaches = serializers.SerializerMethodField()
    reports = AccomplishmentReportSerializer(many=True, read_only=True)
    evidence = serializers.SerializerMethodField()

    class Meta:
        model = Case
        fields = [
            "level", "level_display", "stage", "department_id", "department", "division_id", "division",
            "assigned_to_id", "assigned_to", "assigned_at",
            "due_at", "original_due_at", "extended_at", "extension_reason", "max_extension_due",
            "inspected_at", "inspected_by", "inspection_findings", "action_plan", "scheduled_for",
            "work_completed_at", "work_completed_by", "completion_remarks",
            "validated_at", "validated_by",
            "escalation_level", "escalation_level_display", "escalated_at", "escalation_reason",
            "resolution_summary", "resolved_at", "endorsements",
            "routed_at", "accepted_at", "accepted_by", "acceptance_due_at", "screening", "screening_checklist",
            "returned_at", "return_reason", "return_count",
            "priority_level", "priority_reason", "response_due_at", "responded_at", "responded_by", "response_remarks",
            "breaches", "reports", "evidence",
        ]

    def get_assigned_to(self, obj) -> str | None:
        return _name(obj.assigned_to)

    def get_inspected_by(self, obj) -> str | None:
        return _name(obj.inspected_by)

    def get_work_completed_by(self, obj) -> str | None:
        return _name(obj.work_completed_by)

    def get_validated_by(self, obj) -> str | None:
        return _name(obj.validated_by)

    def get_accepted_by(self, obj) -> str | None:
        return _name(obj.accepted_by)

    def get_responded_by(self, obj) -> str | None:
        return _name(obj.responded_by)

    def get_screening_checklist(self, obj) -> list[str]:
        return list(obj.department.screening_checklist or []) if obj.department else []

    def get_breaches(self, obj) -> list[str]:
        return breaches(obj) if obj.concern.is_open else []

    @extend_schema_field(EvidenceSummarySerializer(allow_null=True))
    def get_evidence(self, obj):
        return evidence.summary(obj)

    def get_max_extension_due(self, obj) -> str | None:
        if not obj.due_at or obj.extended_at:
            return None
        return deadlines.max_extension_due(obj).isoformat()


class PriorityBreakdownSerializer(serializers.Serializer):
    severity_component = serializers.FloatField()
    affected_component = serializers.FloatField()
    duplicate_component = serializers.FloatField()
    delay_component = serializers.FloatField()
    duplicate_count = serializers.IntegerField()
    days_open = serializers.FloatField()
    total = serializers.FloatField()


class LinkedReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Concern
        fields = ["id", "reference_no", "status", "created_at", "channel"]


class PermissionsSerializer(serializers.Serializer):
    can_act = serializers.BooleanField()
    verify = serializers.BooleanField()
    route = serializers.BooleanField()
    route_any_office = serializers.BooleanField()
    endorse = serializers.BooleanField()
    accept = serializers.BooleanField()
    return_to_pacd = serializers.BooleanField()
    set_priority = serializers.BooleanField()
    respond = serializers.BooleanField()
    assign_division = serializers.BooleanField()
    assign_person = serializers.BooleanField()
    inspect = serializers.BooleanField()
    complete = serializers.BooleanField()
    validate = serializers.BooleanField()
    extend = serializers.BooleanField()
    escalate = serializers.BooleanField()
    reject = serializers.BooleanField()
    close = serializers.BooleanField()
    reopen = serializers.BooleanField()
    notes = serializers.BooleanField()
    link = serializers.BooleanField()
    feedback_8888 = serializers.BooleanField()
    follow_up = serializers.BooleanField()


class SuggestedRouteSerializer(serializers.Serializer):
    department_id = serializers.IntegerField(allow_null=True)
    department = serializers.CharField(allow_null=True)
    division_id = serializers.IntegerField(allow_null=True)


class StaffConcernDetailSerializer(StaffConcernListSerializer):
    category_code = serializers.CharField(source="category.code", default=None)
    subcategory_code = serializers.CharField(source="subcategory.code", default=None)
    severity_display = serializers.CharField(source="get_severity_display")
    encoded_by = serializers.SerializerMethodField()
    verified_by = serializers.SerializerMethodField()
    duplicate_of = serializers.CharField(source="duplicate_of.reference_no", default=None)
    attachments = AttachmentSerializer(many=True, read_only=True)
    history = HistorySerializer(many=True, read_only=True)
    case = CaseInfoSerializer(read_only=True, default=None)
    notes = serializers.SerializerMethodField()
    duplicates = LinkedReportSerializer(many=True, read_only=True)
    priority = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()
    suggested_route = serializers.SerializerMethodField()
    suggested_priority = serializers.SerializerMethodField()
    trail = serializers.SerializerMethodField()
    recurrence_of = serializers.CharField(source="recurrence_of.reference_no", default=None)
    purok_name = serializers.CharField(source="purok.name", default=None)
    ai_category = serializers.CharField(source="ai_category.code", default=None)
    ai_category_name = serializers.CharField(source="ai_category.name", default=None)
    ai_subcategory = serializers.CharField(source="ai_subcategory.code", default=None)
    ai_subcategory_name = serializers.CharField(source="ai_subcategory.name", default=None)
    ai_model_version = serializers.IntegerField(source="ai_model.version", default=None)
    recurrences = LinkedReportSerializer(many=True, read_only=True)

    class Meta(StaffConcernListSerializer.Meta):
        fields = StaffConcernListSerializer.Meta.fields + [
            "description", "category_code", "subcategory_code", "severity", "severity_display",
            "affected_count", "latitude", "longitude",
            "reporter_name", "reporter_contact", "reporter_email", "is_anonymous",
            "source_reference", "encoded_by", "external_feedback",
            "verified_by", "verified_at", "acknowledged_at", "resolved_at",
            "duplicate_of", "duplicates", "attachments", "history", "case", "notes",
            "priority", "permissions", "suggested_route", "suggested_priority",
            "purok", "purok_name", "purok_source", "category_source",
            "ai_category", "ai_category_name", "ai_subcategory", "ai_subcategory_name", "ai_confidence", "ai_model_version",
            "trail", "citizen_confirmation", "citizen_confirmed_at", "citizen_feedback", "recurrence_of", "recurrences",
        ]

    def get_encoded_by(self, obj) -> str | None:
        return _name(obj.encoded_by)

    def get_verified_by(self, obj) -> str | None:
        return _name(obj.verified_by)

    @extend_schema_field(NoteSerializer(many=True))
    def get_notes(self, obj):
        case = getattr(obj, "case", None)
        return NoteSerializer(case.notes.all(), many=True).data if case else []

    @extend_schema_field(PriorityBreakdownSerializer(allow_null=True))
    def get_priority(self, obj):
        p = getattr(obj, "priority", None)
        return PriorityBreakdownSerializer(p).data if p else None

    @extend_schema_field(PermissionsSerializer)
    def get_permissions(self, obj):
        return permissions_for(self.context["request"].user, obj)

    @extend_schema_field(PriorityLevelSerializer(allow_null=True))
    def get_suggested_priority(self, obj):
        lvl = suggest_priority(obj)
        return PriorityLevelSerializer(lvl).data if lvl else None

    @extend_schema_field(TrailStepSerializer(many=True))
    def get_trail(self, obj):
        return accountability_trail(obj)

    @extend_schema_field(SuggestedRouteSerializer)
    def get_suggested_route(self, obj):
        dept, div = suggested_route(obj)
        return {"department_id": dept.id if dept else None, "department": dept.name if dept else None,
                "division_id": div.id if div else None}


# ---------- Action inputs ----------

class VerifySerializer(serializers.Serializer):
    category = serializers.SlugRelatedField(slug_field="code", queryset=Category.objects.filter(is_active=True))
    subcategory = serializers.SlugRelatedField(
        slug_field="code", queryset=Subcategory.objects.filter(is_active=True), required=False, allow_null=True
    )
    severity = serializers.ChoiceField(choices=Concern.Severity.choices)
    remarks = serializers.CharField(required=False, allow_blank=True, max_length=500)

    def validate(self, attrs):
        sub = attrs.get("subcategory")
        if sub and sub.category_id != attrs["category"].pk:
            raise serializers.ValidationError({"subcategory": "Sub-type does not belong to the category."})
        return attrs


class RouteSerializer(serializers.Serializer):
    level = serializers.ChoiceField(choices=[Case.Level.CITY, Case.Level.BARANGAY])
    department = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.filter(is_active=True, kind=Department.Kind.INTERNAL), required=False, allow_null=True
    )
    division = serializers.PrimaryKeyRelatedField(
        queryset=Division.objects.filter(is_active=True), required=False, allow_null=True
    )
    remarks = serializers.CharField(required=False, allow_blank=True, max_length=500)


class AcceptSerializer(serializers.Serializer):
    priority_level = serializers.PrimaryKeyRelatedField(queryset=PriorityLevel.objects.all())
    priority_reason = serializers.CharField(required=False, allow_blank=True, max_length=300)
    screening = serializers.DictField(child=serializers.BooleanField(), required=False)
    division = serializers.PrimaryKeyRelatedField(queryset=Division.objects.filter(is_active=True), required=False, allow_null=True)
    remarks = serializers.CharField(required=False, allow_blank=True, max_length=500)


class ReturnSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500)


class SetPrioritySerializer(serializers.Serializer):
    priority_level = serializers.PrimaryKeyRelatedField(queryset=PriorityLevel.objects.all())
    reason = serializers.CharField(max_length=300)


class PhotoMetaSerializer(serializers.Serializer):
    """Sent by the browser for each photo, read BEFORE compression strips the EXIF."""
    exif_lat = serializers.FloatField(required=False, allow_null=True)
    exif_lng = serializers.FloatField(required=False, allow_null=True)
    exif_time = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    device_lat = serializers.FloatField(required=False, allow_null=True)
    device_lng = serializers.FloatField(required=False, allow_null=True)
    device_accuracy = serializers.FloatField(required=False, allow_null=True)


class JSONListField(serializers.JSONField):
    """Accepts a real JSON list (application/json) or a JSON string (multipart/form-data)."""

    def to_internal_value(self, data):
        if isinstance(data, (bytes, str)):
            import json
            try:
                data = json.loads(data or "[]")
            except ValueError:
                raise serializers.ValidationError("Invalid JSON.")
        return data


def _meta_field():
    return JSONListField(required=False, default=list,
                                 help_text="JSON list aligned with the photos: [{exif_lat, exif_lng, exif_time, device_lat, ...}]")


def _clean_meta(v):
    if isinstance(v, dict):
        v = [v]
    if not isinstance(v, list):
        raise serializers.ValidationError("Must be a JSON list.")
    out = []
    for item in v[:MAX_PHOTOS * 2]:
        ser = PhotoMetaSerializer(data=item if isinstance(item, dict) else {})
        out.append(ser.validated_data if ser.is_valid() else {})
    return out


class RespondSerializer(serializers.Serializer):
    remarks = serializers.CharField(max_length=1000)
    photos = serializers.ListField(child=serializers.ImageField(), required=False, max_length=MAX_PHOTOS)
    photo_meta = _meta_field()

    def validate_photo_meta(self, v):
        return _clean_meta(v)


class AssignDivisionSerializer(serializers.Serializer):
    division = serializers.PrimaryKeyRelatedField(queryset=Division.objects.filter(is_active=True))
    remarks = serializers.CharField(required=False, allow_blank=True, max_length=500)


class AssignPersonSerializer(serializers.Serializer):
    person = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(is_active=True))
    remarks = serializers.CharField(required=False, allow_blank=True, max_length=500)


class InspectSerializer(serializers.Serializer):
    findings = serializers.CharField(max_length=2000)
    action_plan = serializers.CharField(required=False, allow_blank=True, max_length=2000)
    scheduled_for = serializers.DateField(required=False, allow_null=True)
    public_message = serializers.CharField(required=False, allow_blank=True, max_length=500)
    photos = serializers.ListField(child=serializers.ImageField(), required=False, max_length=MAX_PHOTOS,
                                   help_text="BEFORE photos of the site.")
    photo_meta = _meta_field()

    def validate_photo_meta(self, v):
        return _clean_meta(v)

    def validate_scheduled_for(self, v):
        if v and v < timezone.localdate():
            raise serializers.ValidationError("Schedule date is in the past.")
        return v


class CompleteSerializer(serializers.Serializer):
    """Accomplishment report + before/after photos."""
    remarks = serializers.CharField(max_length=1000, help_text="Work done (shown to the citizen once validated).")
    photos = serializers.ListField(child=serializers.ImageField(), required=False, max_length=MAX_PHOTOS,
                                   help_text="AFTER photos.")
    photo_meta = _meta_field()
    before_photos = serializers.ListField(child=serializers.ImageField(), required=False, max_length=MAX_PHOTOS)
    before_meta = _meta_field()
    started_at = serializers.DateTimeField(required=False, allow_null=True)
    finished_at = serializers.DateTimeField(required=False, allow_null=True)
    crew = JSONListField(required=False, default=list, help_text="JSON list of user ids.")
    other_workers = serializers.CharField(required=False, allow_blank=True, max_length=300)
    materials = JSONListField(required=False, default=list,
                                      help_text='JSON list: [{"item": "Cold mix", "qty": 4, "unit": "sacks"}]')
    equipment = serializers.CharField(required=False, allow_blank=True, max_length=300)

    def validate_photo_meta(self, v):
        return _clean_meta(v)

    def validate_before_meta(self, v):
        return _clean_meta(v)

    def validate_crew(self, v):
        if not isinstance(v, list):
            raise serializers.ValidationError("Must be a JSON list of user ids.")
        users = list(User.objects.filter(pk__in=[i for i in v if isinstance(i, int)], is_active=True))
        return users

    def validate_materials(self, v):
        if not isinstance(v, list):
            raise serializers.ValidationError("Must be a JSON list.")
        ser = MaterialSerializer(data=[m for m in v if isinstance(m, dict)][:20], many=True)
        ser.is_valid(raise_exception=True)
        return ser.validated_data

    def validate(self, attrs):
        dept_id = self.context.get("department_id")
        if dept_id:
            bad = [u for u in attrs.get("crew", []) if u.department_id != dept_id]
            if bad:
                raise serializers.ValidationError({"crew": "Crew must be from the handling office."})
        return attrs


class ValidateSerializer(serializers.Serializer):
    approve = serializers.BooleanField()
    remarks = serializers.CharField(required=False, allow_blank=True, max_length=1000)
    photos = serializers.ListField(child=serializers.ImageField(), required=False, max_length=MAX_PHOTOS)
    photo_meta = _meta_field()
    override_reason = serializers.CharField(required=False, allow_blank=True, max_length=1000,
                                            help_text="Required when the photo checks raised a red flag.")

    def validate_photo_meta(self, v):
        return _clean_meta(v)


class ExtendSerializer(serializers.Serializer):
    new_due_date = serializers.DateField()
    reason = serializers.CharField(max_length=500)

    def validate(self, attrs):
        attrs["new_due"] = _end_of_day(attrs.pop("new_due_date"))
        return attrs


class EndorseSerializer(serializers.Serializer):
    agency = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.filter(is_active=True, kind=Department.Kind.EXTERNAL)
    )
    letter_reference = serializers.CharField(required=False, allow_blank=True, max_length=120)
    contact_person = serializers.CharField(required=False, allow_blank=True, max_length=150)
    remarks = serializers.CharField(required=False, allow_blank=True, max_length=500)


class EndorsementFollowUpSerializer(serializers.Serializer):
    method = serializers.ChoiceField(choices=["call", "letter", "email", "visit", "meeting"])
    notes = serializers.CharField(max_length=1000)
    status = serializers.ChoiceField(choices=Endorsement.Status.choices, required=False, allow_null=True)
    agency_response = serializers.CharField(required=False, allow_blank=True, max_length=1000)
    public_message = serializers.CharField(required=False, allow_blank=True, max_length=500)


class Feedback8888Serializer(serializers.Serializer):
    feedback = serializers.CharField(max_length=2000)

    def validate_feedback(self, v):
        if len(v.strip()) < 30:
            raise serializers.ValidationError("8888 requires a concrete and specific action report, not a one-liner.")
        return v.strip()


class RemarksSerializer(serializers.Serializer):
    remarks = serializers.CharField(max_length=1000)


class OptionalRemarksSerializer(serializers.Serializer):
    remarks = serializers.CharField(required=False, allow_blank=True, max_length=1000)


class EscalateSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500)


class NoteCreateSerializer(serializers.Serializer):
    body = serializers.CharField(max_length=2000)


class SimilarReportSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    reference_no = serializers.CharField()
    title = serializers.CharField()
    status = serializers.CharField()
    created_at = serializers.DateTimeField()
    category = serializers.CharField(allow_null=True)
    distance_m = serializers.IntegerField(allow_null=True)
    score = serializers.FloatField()
    reasons = serializers.ListField(child=serializers.CharField())
    reporters = serializers.IntegerField()


class LinkDuplicateSerializer(serializers.Serializer):
    master_reference = serializers.CharField(max_length=20)


class StaffSummarySerializer(serializers.Serializer):
    triage = serializers.IntegerField()
    for_acceptance = serializers.IntegerField()
    returned = serializers.IntegerField()
    response_overdue = serializers.IntegerField()
    p1_open = serializers.IntegerField()
    to_route = serializers.IntegerField()
    danger_unverified = serializers.IntegerField()
    mine = serializers.IntegerField()
    validation = serializers.IntegerField()
    endorsed = serializers.IntegerField()
    follow_up_due = serializers.IntegerField()
    feedback_8888_due = serializers.IntegerField()
    overdue = serializers.IntegerField()
    open = serializers.IntegerField()
    resolved_this_month = serializers.IntegerField()


# ---------- Staff intake (walk-in, FB, Messenger, barangay logbook, hotline, 8888) ----------

class StaffEncodeSerializer(PublicConcernCreateSerializer):
    channel = serializers.ChoiceField(choices=Concern.Channel.choices)
    source_reference = serializers.CharField(required=False, allow_blank=True, max_length=300)
    external_ticket_no = serializers.CharField(required=False, allow_blank=True, max_length=60)
    received_at = serializers.DateTimeField(required=False, allow_null=True, write_only=True,
                                            help_text="When the LGU received it (8888: endorsement time).")

    class Meta(PublicConcernCreateSerializer.Meta):
        fields = ["channel", "source_reference", "external_ticket_no", "received_at"] + PublicConcernCreateSerializer.Meta.fields

    def validate_channel(self, v):
        if v == Concern.Channel.WEB:
            raise serializers.ValidationError("Web reports come from the public portal. Pick where you received it.")
        return v

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if not attrs.get("is_anonymous") and not attrs.get("reporter_name"):
            raise serializers.ValidationError({"reporter_name": "Name is required unless anonymous."})
        if attrs.get("channel") == Concern.Channel.HOTLINE_8888 and not attrs.get("external_ticket_no"):
            raise serializers.ValidationError({"external_ticket_no": "Enter the 8888 ticket number."})
        return attrs

    @transaction.atomic
    def create(self, validated):
        images = validated.pop("images", [])
        scale = validated.pop("affected_scale", "street")
        received = validated.pop("received_at", None) or timezone.now()
        user = self.context["request"].user
        if not validated.get("title"):
            validated["title"] = self._auto_title(validated)
        extra = {}
        if validated.get("channel") == Concern.Channel.HOTLINE_8888:
            extra["external_feedback_due_at"] = received + timedelta(hours=deadlines.HOTLINE_8888_HOURS)
        concern = Concern.objects.create(
            **validated, **extra,
            affected_count=AFFECTED_BUCKETS[scale],
            severity=Concern.Severity.SEVERE if validated.get("danger_now") else Concern.Severity.MODERATE,
            category_source=Concern.CategorySource.STAFF,
            encoded_by=user,
            consent_at=timezone.now(),
        )
        for img in images:
            ConcernAttachment.objects.create(concern=concern, file=img, uploaded_by=user)
        on_concern_submitted(concern, user=user)
        concern.refresh_from_db()
        return concern


# ---------- Accountability trail ----------

def accountability_trail(concern):
    """Who did each step, when, and whether it met its commitment. One row per step, in order."""
    case = getattr(concern, "case", None)
    rows = [{"key": "verified", "label": "Na-verify (PACD)", "who": _name(concern.verified_by), "at": concern.verified_at,
             "detail": "", "ok": None}]
    if not case:
        return rows
    lv = case.priority_level

    def ok(done, due):
        return None if not (done and due) else done <= due

    routed = next((h for h in reversed(list(concern.history.all()))
                   if h.to_status == Concern.Status.ASSIGNED and h.from_status != Concern.Status.ASSIGNED), None)
    rows += [
        {"key": "routed", "label": "Naipasa sa opisina", "who": _name(routed.changed_by) if routed else None,
         "at": case.routed_at, "detail": case.department.name if case.department else "", "ok": None},
        {"key": "accepted", "label": "Tinanggap ng opisina", "who": _name(case.accepted_by), "at": case.accepted_at,
         "detail": f"{lv.code} · {lv.name}" if lv else "", "ok": ok(case.accepted_at, case.acceptance_due_at)},
        {"key": "assigned", "label": "Itinalaga", "who": _name(case.assigned_by) if case.assigned_to else None, "at": None,
         "detail": (f"kay {_name(case.assigned_to)}" if case.assigned_to else "")
                   + (f" · {case.division.name}" if case.division else ""), "ok": None},
        {"key": "responded", "label": "Unang aksyon", "who": _name(case.responded_by), "at": case.responded_at,
         "detail": case.response_remarks[:120], "ok": ok(case.responded_at, case.response_due_at)},
        {"key": "inspected", "label": "Inspeksyon", "who": _name(case.inspected_by), "at": case.inspected_at,
         "detail": case.inspection_findings[:120], "ok": None},
    ]
    for r in reversed(list(case.reports.all())):
        crew = ", ".join(filter(None, [_name(u) for u in r.crew.all()] + [r.other_workers]))
        rows.append({"key": f"report-{r.id}", "label": "Accomplishment report", "who": _name(r.submitted_by),
                     "at": r.submitted_at, "detail": f"Crew: {crew}" if crew else "", "ok": None})
        if r.status != AccomplishmentReport.Status.SUBMITTED:
            approved = r.status == AccomplishmentReport.Status.APPROVED
            rows.append({"key": f"review-{r.id}", "label": "Na-validate" if approved else "Ibinalik sa crew",
                         "who": _name(r.reviewed_by), "at": r.reviewed_at,
                         "detail": (f"Override: {r.override_reason}" if r.override_reason else r.review_remarks)[:200],
                         "ok": (ok(r.reviewed_at, case.due_at) if approved else False)})
    if case.validated_at and not case.reports.exists():
        rows.append({"key": "validated", "label": "Na-validate", "who": _name(case.validated_by), "at": case.validated_at,
                     "detail": "", "ok": ok(case.validated_at, case.due_at)})
    if concern.citizen_confirmation:
        fixed = concern.citizen_confirmation == Concern.Confirmation.FIXED
        rows.append({"key": "citizen", "label": "Kumpirmasyon ng nag-report", "who": "Nag-report",
                     "at": concern.citizen_confirmed_at,
                     "detail": ("Naayos na" if fixed else "HINDI pa naayos") + (f": {concern.citizen_feedback}" if concern.citizen_feedback else ""),
                     "ok": fixed})
    return rows
