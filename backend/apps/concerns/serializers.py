from django.conf import settings
from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.geo.models import Barangay

from .models import Category, Concern, ConcernAttachment, StatusHistory
from .services import on_concern_submitted

MAX_IMAGES = 5
MAX_IMAGE_MB = 5


# ---------- Public reference data ----------

class PublicCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["code", "name", "name_fil", "description", "icon"]


class PublicBarangaySerializer(serializers.ModelSerializer):
    class Meta:
        model = Barangay
        fields = ["id", "name", "center_lat", "center_lng"]


# ---------- Public submission ----------

class PublicConcernCreateSerializer(serializers.ModelSerializer):
    category = serializers.SlugRelatedField(
        slug_field="code", queryset=Category.objects.filter(is_active=True),
        required=False, allow_null=True,
    )
    barangay = serializers.PrimaryKeyRelatedField(queryset=Barangay.objects.all())
    images = serializers.ListField(
        child=serializers.ImageField(), write_only=True, required=False, max_length=MAX_IMAGES
    )

    # read-only response fields
    reference_no = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    linked_to_existing = serializers.SerializerMethodField()

    class Meta:
        model = Concern
        fields = [
            "title", "description", "category", "severity", "affected_count",
            "barangay", "latitude", "longitude", "location_description",
            "reporter_name", "reporter_contact", "reporter_email", "is_anonymous", "consent_given",
            "images",
            "reference_no", "status", "created_at", "linked_to_existing",
        ]
        extra_kwargs = {
            "reporter_name": {"write_only": True},
            "reporter_contact": {"write_only": True},
            "reporter_email": {"write_only": True},
            "is_anonymous": {"write_only": True},
            "consent_given": {"write_only": True},
            "severity": {"required": False},
            "affected_count": {"required": False},
        }

    def get_linked_to_existing(self, obj) -> bool:
        return obj.duplicate_of_id is not None

    def validate_title(self, v):
        v = v.strip()
        if len(v) < 5:
            raise serializers.ValidationError("Please give a short but clear title (at least 5 characters).")
        return v

    def validate_description(self, v):
        v = v.strip()
        if len(v) < 15:
            raise serializers.ValidationError("Please describe the concern in a bit more detail.")
        return v

    def validate_affected_count(self, v):
        if v < 1 or v > 100_000:
            raise serializers.ValidationError("Enter a value between 1 and 100,000.")
        return v

    def validate_images(self, files):
        for f in files:
            if f.size > MAX_IMAGE_MB * 1024 * 1024:
                raise serializers.ValidationError(f"Each image must be {MAX_IMAGE_MB} MB or smaller.")
        return files

    def validate(self, attrs):
        if not attrs.get("consent_given"):
            raise serializers.ValidationError(
                {"consent_given": "You must agree to the Data Privacy Notice to submit a concern."}
            )

        lat, lng = attrs.get("latitude"), attrs.get("longitude")
        if (lat is None) != (lng is None):
            raise serializers.ValidationError({"latitude": "Provide both latitude and longitude, or neither."})
        if lat is not None:
            b = getattr(settings, "SERVICE_AREA_BOUNDS", {"lat": (4.5, 21.5), "lng": (116.0, 127.0)})
            if not (b["lat"][0] <= float(lat) <= b["lat"][1] and b["lng"][0] <= float(lng) <= b["lng"][1]):
                raise serializers.ValidationError({"latitude": "The pinned location is outside the service area."})

        request = self.context.get("request")
        logged_in = bool(request and request.user and request.user.is_authenticated)
        if attrs.get("is_anonymous"):
            for f in ("reporter_name", "reporter_contact", "reporter_email"):
                attrs[f] = ""
        elif not logged_in:
            if not attrs.get("reporter_name"):
                raise serializers.ValidationError({"reporter_name": "Name is required unless reporting anonymously."})
            if not (attrs.get("reporter_contact") or attrs.get("reporter_email")):
                raise serializers.ValidationError(
                    {"reporter_contact": "Give a contact number or email so we can update you."}
                )
        return attrs

    @transaction.atomic
    def create(self, validated):
        images = validated.pop("images", [])
        request = self.context.get("request")
        user = request.user if (request and request.user.is_authenticated) else None

        concern = Concern.objects.create(
            **validated,
            channel=Concern.Channel.WEB,
            category_source=Concern.CategorySource.CITIZEN,
            reporter=None if validated.get("is_anonymous") else user,
            consent_at=timezone.now(),
        )
        for img in images:
            ConcernAttachment.objects.create(concern=concern, file=img, uploaded_by=user)

        on_concern_submitted(concern, user=user)
        concern.refresh_from_db()
        return concern


# ---------- Public tracking ----------

class PublicTimelineSerializer(serializers.ModelSerializer):
    status = serializers.ChoiceField(source="to_status", choices=Concern.Status.choices)
    status_display = serializers.CharField(source="get_to_status_display")

    class Meta:
        model = StatusHistory
        fields = ["status", "status_display", "remarks", "created_at"]


class PublicTrackSerializer(serializers.ModelSerializer):
    """Only non-personal fields. No reporter data, no staff names, no internal notes."""

    category = serializers.CharField(source="category.name", default=None)
    barangay = serializers.CharField(source="barangay.name")
    status_display = serializers.CharField(source="get_status_display")
    assigned_office = serializers.SerializerMethodField()
    timeline = serializers.SerializerMethodField()
    linked_to_reference = serializers.CharField(source="duplicate_of.reference_no", default=None)

    class Meta:
        model = Concern
        read_only_fields = ["status"]
        fields = [
            "reference_no", "title", "category", "barangay", "status", "status_display",
            "assigned_office", "linked_to_reference", "created_at", "resolved_at", "timeline",
        ]

    def get_assigned_office(self, obj) -> str | None:
        case = getattr(obj, "case", None)
        return case.department.name if case else None

    @extend_schema_field(PublicTimelineSerializer(many=True))
    def get_timeline(self, obj):
        return PublicTimelineSerializer(obj.history.filter(is_public=True), many=True).data


# ---------- Public stats (schema only; the view builds plain dicts) ----------

class PublicStatsTotalsSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    open = serializers.IntegerField()
    resolved = serializers.IntegerField()
    this_month = serializers.IntegerField()
    resolved_this_month = serializers.IntegerField()
    avg_resolution_hours = serializers.FloatField(allow_null=True)
    resolution_rate = serializers.FloatField()
    reports_received = serializers.IntegerField()


class PublicStatsCategorySerializer(serializers.Serializer):
    code = serializers.CharField()
    name = serializers.CharField()
    count = serializers.IntegerField()


class PublicStatsBarangaySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    center_lat = serializers.FloatField(allow_null=True)
    center_lng = serializers.FloatField(allow_null=True)
    open = serializers.IntegerField()
    total_90d = serializers.IntegerField()


class PublicStatsSerializer(serializers.Serializer):
    totals = PublicStatsTotalsSerializer()
    by_category = PublicStatsCategorySerializer(many=True)
    by_barangay = PublicStatsBarangaySerializer(many=True)
    generated_at = serializers.DateTimeField()
