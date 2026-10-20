from datetime import datetime, timedelta

from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.accounts.models import User
from apps.concerns.models import Category, Concern, ConcernAttachment, StatusHistory, Subcategory
from apps.concerns.serializers import AFFECTED_BUCKETS, PublicConcernCreateSerializer
from apps.concerns.services import on_concern_submitted

from . import deadlines
from .models import Case, CaseNote, Department, Division, Endorsement, EndorsementFollowUp, PriorityLevel
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

class AttachmentSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = ConcernAttachment
        fields = ["id", "kind", "url", "caption", "uploaded_at"]

    def get_url(self, obj) -> str:
        return obj.file.url


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
            "breaches",
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

    class Meta(StaffConcernListSerializer.Meta):
        fields = StaffConcernListSerializer.Meta.fields + [
            "description", "category_code", "subcategory_code", "severity", "severity_display",
            "affected_count", "latitude", "longitude",
            "reporter_name", "reporter_contact", "reporter_email", "is_anonymous",
            "source_reference", "encoded_by", "external_feedback",
            "verified_by", "verified_at", "acknowledged_at", "resolved_at",
            "duplicate_of", "duplicates", "attachments", "history", "case", "notes",
            "priority", "permissions", "suggested_route", "suggested_priority",
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


class RespondSerializer(serializers.Serializer):
    remarks = serializers.CharField(max_length=1000)
    photos = serializers.ListField(child=serializers.ImageField(), required=False, max_length=MAX_PHOTOS)


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

    def validate_scheduled_for(self, v):
        if v and v < timezone.localdate():
            raise serializers.ValidationError("Schedule date is in the past.")
        return v


class CompleteSerializer(serializers.Serializer):
    remarks = serializers.CharField(max_length=1000)
    photos = serializers.ListField(child=serializers.ImageField(), required=False, max_length=MAX_PHOTOS)


class ValidateSerializer(serializers.Serializer):
    approve = serializers.BooleanField()
    remarks = serializers.CharField(required=False, allow_blank=True, max_length=1000)
    photos = serializers.ListField(child=serializers.ImageField(), required=False, max_length=MAX_PHOTOS)


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
