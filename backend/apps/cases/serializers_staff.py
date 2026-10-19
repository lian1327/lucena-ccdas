from django.conf import settings
from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.accounts.models import User
from apps.concerns.models import Category, Concern, ConcernAttachment, StatusHistory, Subcategory
from apps.concerns.serializers import AFFECTED_BUCKETS, PublicConcernCreateSerializer
from apps.concerns.services import TRANSITIONS, on_concern_submitted

from .models import Case, CaseNote, Department
from .scoping import can_act, can_assign_any, can_resolve

MAX_RESOLUTION_PHOTOS = 3


def _name(u):
    return (u.get_full_name() or u.username) if u else None


# ---------- Lookups ----------

class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ["id", "code", "name"]


class StaffUserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "full_name", "department"]

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
    department = serializers.CharField(source="case.department.name", default=None)
    assigned_to = serializers.SerializerMethodField()
    due_at = serializers.DateTimeField(source="case.due_at", default=None)
    escalation_level = serializers.IntegerField(source="case.escalation_level", default=0)
    duplicate_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Concern
        fields = [
            "id", "reference_no", "title", "category", "subcategory", "barangay", "location_description",
            "status", "status_display", "priority_score", "priority_tier", "danger_now", "is_verified",
            "is_overdue", "involves_barangay_officials", "channel", "created_at",
            "department", "assigned_to", "due_at", "escalation_level", "duplicate_count",
        ]

    def get_assigned_to(self, obj) -> str | None:
        case = getattr(obj, "case", None)
        return _name(case.assigned_to) if case else None


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

    def get_changed_by(self, obj) -> str | None:
        return _name(obj.changed_by) or "System"


class NoteSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()

    class Meta:
        model = CaseNote
        fields = ["id", "author", "body", "created_at"]

    def get_author(self, obj) -> str:
        return _name(obj.author) or "System"


class CaseInfoSerializer(serializers.ModelSerializer):
    department = serializers.CharField(source="department.name")
    assigned_to = serializers.SerializerMethodField()
    escalation_level_display = serializers.CharField(source="get_escalation_level_display")

    class Meta:
        model = Case
        fields = [
            "department_id", "department", "assigned_to_id", "assigned_to", "assigned_at", "due_at",
            "escalation_level", "escalation_level_display", "escalated_at", "escalation_reason",
            "resolution_summary", "resolved_at",
        ]

    def get_assigned_to(self, obj) -> str | None:
        return _name(obj.assigned_to)


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
    can_verify = serializers.BooleanField()
    can_assign = serializers.BooleanField()
    can_assign_any = serializers.BooleanField()
    can_resolve = serializers.BooleanField()


class StaffConcernDetailSerializer(StaffConcernListSerializer):
    category_code = serializers.CharField(source="category.code", default=None)
    subcategory_code = serializers.CharField(source="subcategory.code", default=None)
    severity_display = serializers.CharField(source="get_severity_display")
    channel_display = serializers.CharField(source="get_channel_display")
    encoded_by = serializers.SerializerMethodField()
    verified_by = serializers.SerializerMethodField()
    duplicate_of = serializers.CharField(source="duplicate_of.reference_no", default=None)
    attachments = AttachmentSerializer(many=True, read_only=True)
    history = HistorySerializer(many=True, read_only=True)
    case = CaseInfoSerializer(read_only=True, default=None)
    notes = serializers.SerializerMethodField()
    duplicates = LinkedReportSerializer(many=True, read_only=True)
    priority = serializers.SerializerMethodField()
    allowed_transitions = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()

    class Meta(StaffConcernListSerializer.Meta):
        fields = StaffConcernListSerializer.Meta.fields + [
            "description", "category_code", "subcategory_code", "severity", "severity_display",
            "affected_count", "latitude", "longitude",
            "reporter_name", "reporter_contact", "reporter_email", "is_anonymous",
            "channel_display", "source_reference", "encoded_by",
            "verified_by", "verified_at", "acknowledged_at", "resolved_at",
            "duplicate_of", "duplicates", "attachments", "history", "case", "notes",
            "priority", "allowed_transitions", "permissions",
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

    @extend_schema_field(serializers.ListField(child=serializers.ChoiceField(choices=Concern.Status.choices)))
    def get_allowed_transitions(self, obj):
        return sorted(TRANSITIONS.get(obj.status, set()))

    @extend_schema_field(PermissionsSerializer)
    def get_permissions(self, obj):
        u = self.context["request"].user
        act = can_act(u)
        return {
            "can_act": act,
            "can_verify": act,
            "can_assign": act and (can_assign_any(u) or u.role == User.Role.DEPT_STAFF),
            "can_assign_any": can_assign_any(u),
            "can_resolve": can_resolve(u),
        }


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


class AssignSerializer(serializers.Serializer):
    department = serializers.PrimaryKeyRelatedField(queryset=Department.objects.filter(is_active=True))
    assigned_to = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(is_active=True), required=False, allow_null=True
    )
    due_at = serializers.DateTimeField(required=False, allow_null=True)
    remarks = serializers.CharField(required=False, allow_blank=True, max_length=500)

    def validate(self, attrs):
        user = self.context["request"].user
        dept, person = attrs["department"], attrs.get("assigned_to")
        if person and person.department_id != dept.pk:
            raise serializers.ValidationError({"assigned_to": "This person is not in the selected office."})
        if not can_assign_any(user) and dept.pk != user.department_id:
            raise serializers.ValidationError(
                {"department": "Only the City Administrator's office can route to another office."}
            )
        if attrs.get("due_at") and attrs["due_at"] < timezone.now():
            raise serializers.ValidationError({"due_at": "Due date is in the past."})
        return attrs


class StatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Concern.Status.choices)
    remarks = serializers.CharField(required=False, allow_blank=True, max_length=1000)
    is_public = serializers.BooleanField(default=True)
    photos = serializers.ListField(
        child=serializers.ImageField(), required=False, max_length=MAX_RESOLUTION_PHOTOS
    )

    def validate(self, attrs):
        s, remarks = attrs["status"], attrs.get("remarks", "").strip()
        if s in (Concern.Status.RESOLVED, Concern.Status.REJECTED) and not remarks:
            raise serializers.ValidationError({"remarks": "Explain what was done (or why it was rejected)."})
        if (
            s == Concern.Status.RESOLVED
            and getattr(settings, "REQUIRE_RESOLUTION_PHOTO", True)
            and not attrs.get("photos")
        ):
            raise serializers.ValidationError(
                {"photos": "Attach at least one photo of the completed work — it's what the citizen will see."}
            )
        if s in (Concern.Status.RESOLVED, Concern.Status.REJECTED):
            attrs["is_public"] = True  # outcomes are always shown to the citizen
        return attrs


class EscalateSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500)


class NoteCreateSerializer(serializers.Serializer):
    body = serializers.CharField(max_length=2000)


class LinkDuplicateSerializer(serializers.Serializer):
    master_reference = serializers.CharField(max_length=20)


class StaffSummarySerializer(serializers.Serializer):
    triage = serializers.IntegerField()
    danger_unverified = serializers.IntegerField()
    mine = serializers.IntegerField()
    overdue = serializers.IntegerField()
    open = serializers.IntegerField()
    resolved_this_month = serializers.IntegerField()


# ---------- Staff intake (walk-in, FB, Messenger, barangay logbook, hotline) ----------

class StaffEncodeSerializer(PublicConcernCreateSerializer):
    channel = serializers.ChoiceField(choices=Concern.Channel.choices)
    source_reference = serializers.CharField(required=False, allow_blank=True, max_length=300)

    class Meta(PublicConcernCreateSerializer.Meta):
        fields = ["channel", "source_reference"] + PublicConcernCreateSerializer.Meta.fields

    def validate_channel(self, v):
        if v == Concern.Channel.WEB:
            raise serializers.ValidationError("Web reports come from the public portal. Pick where you received it.")
        return v

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if not attrs.get("is_anonymous") and not attrs.get("reporter_name"):
            raise serializers.ValidationError({"reporter_name": "Name is required unless anonymous."})
        return attrs

    @transaction.atomic
    def create(self, validated):
        images = validated.pop("images", [])
        scale = validated.pop("affected_scale", "street")
        user = self.context["request"].user
        if not validated.get("title"):
            validated["title"] = self._auto_title(validated)
        concern = Concern.objects.create(
            **validated,
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
