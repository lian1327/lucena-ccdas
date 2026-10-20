import re

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.geo.models import Barangay

from .models import Category, Concern, ConcernAttachment, StatusHistory, Subcategory
from .services import on_concern_submitted

MAX_IMAGES = 3
MAX_IMAGE_MB = 5


# ---------- Public reference data ----------

class PublicSubcategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Subcategory
        fields = ["code", "name", "name_fil"]


class PublicCategorySerializer(serializers.ModelSerializer):
    subcategories = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ["code", "name", "name_fil", "description", "icon", "subcategories"]

    @extend_schema_field(PublicSubcategorySerializer(many=True))
    def get_subcategories(self, obj):
        subs = [s for s in obj.subcategories.all() if s.is_active]
        return PublicSubcategorySerializer(subs, many=True).data


class PublicBarangaySerializer(serializers.ModelSerializer):
    class Meta:
        model = Barangay
        fields = ["id", "name", "center_lat", "center_lng"]


# ---------- Public submission ----------

PH_MOBILE_RE = re.compile(r"^(09|\+639|639)\d{9}$")

# What citizens pick ("Ilan ang apektado?") → stored estimate. Buckets beat a raw number nobody knows.
AFFECTED_BUCKETS = {"self": 1, "household": 5, "street": 50, "barangay": 500}


class PublicConcernCreateSerializer(serializers.ModelSerializer):
    category = serializers.SlugRelatedField(
        slug_field="code", queryset=Category.objects.filter(is_active=True),
        required=False, allow_null=True,
    )
    subcategory = serializers.SlugRelatedField(
        slug_field="code", queryset=Subcategory.objects.filter(is_active=True).select_related("category"),
        required=False, allow_null=True,
    )
    barangay = serializers.PrimaryKeyRelatedField(queryset=Barangay.objects.all())
    affected_scale = serializers.ChoiceField(
        choices=list(AFFECTED_BUCKETS), write_only=True, required=False, default="street"
    )
    images = serializers.ListField(
        child=serializers.ImageField(), write_only=True, required=False, max_length=MAX_IMAGES,
        error_messages={"max_length": f"Hanggang {MAX_IMAGES} litrato lang. (Up to {MAX_IMAGES} photos.)"},
    )

    # read-only response fields
    reference_no = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    linked_to_existing = serializers.SerializerMethodField()

    class Meta:
        model = Concern
        fields = [
            "title", "description", "category", "subcategory", "danger_now", "affected_scale",
            "involves_barangay_officials",
            "barangay", "latitude", "longitude", "location_description",
            "reporter_name", "reporter_contact", "reporter_email", "is_anonymous", "consent_given",
            "images",
            "reference_no", "status", "created_at", "linked_to_existing",
        ]
        extra_kwargs = {
            "title": {"required": False, "allow_blank": True},
            "location_description": {
                "required": True, "allow_blank": False,
                "error_messages": {
                    "blank": "Ilagay ang palatandaan o kalye. (Add a landmark or street.)",
                    "required": "Ilagay ang palatandaan o kalye. (Add a landmark or street.)",
                },
            },
            "reporter_name": {"write_only": True},
            "reporter_contact": {"write_only": True},
            "reporter_email": {"write_only": True},
            "is_anonymous": {"write_only": True},
            "consent_given": {"write_only": True},
            "danger_now": {"write_only": True},
            "involves_barangay_officials": {"write_only": True},
        }

    def get_linked_to_existing(self, obj) -> bool:
        return obj.duplicate_of_id is not None

    def validate_title(self, v):
        return v.strip()

    def validate_description(self, v):
        v = v.strip()
        if len(v) < 10:
            raise serializers.ValidationError("Pakilarawan nang kaunti pa ang problema. (Please add a bit more detail.)")
        return v

    def validate_location_description(self, v):
        v = v.strip()
        if len(v) < 4:
            raise serializers.ValidationError(
                "Ilagay ang palatandaan o kalye, hal. 'tapat ng chapel sa Purok 3'. (Add a landmark or street.)"
            )
        return v

    def validate_reporter_contact(self, v):
        v = re.sub(r"[\s-]", "", v or "")
        if v and not PH_MOBILE_RE.match(v):
            raise serializers.ValidationError("Gumamit ng 11-digit na mobile number, hal. 09171234567.")
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

        sub = attrs.get("subcategory")
        if sub:
            if attrs.get("category") and attrs["category"].pk != sub.category_id:
                raise serializers.ValidationError({"subcategory": "This sub-type does not belong to the chosen category."})
            attrs["category"] = sub.category

        lat, lng = attrs.get("latitude"), attrs.get("longitude")
        if (lat is None) != (lng is None):
            raise serializers.ValidationError({"latitude": "Provide both latitude and longitude, or neither."})
        if lat is not None:
            b = getattr(settings, "SERVICE_AREA_BOUNDS", {"lat": (4.5, 21.5), "lng": (116.0, 127.0)})
            if not (b["lat"][0] <= float(lat) <= b["lat"][1] and b["lng"][0] <= float(lng) <= b["lng"][1]):
                raise serializers.ValidationError({"latitude": "Ang naka-pin na lokasyon ay labas sa sakop ng lungsod."})

        request = self.context.get("request")
        logged_in = bool(request and request.user and request.user.is_authenticated)
        if attrs.get("is_anonymous"):
            for f in ("reporter_name", "reporter_contact", "reporter_email"):
                attrs[f] = ""
        elif not logged_in:
            if not attrs.get("reporter_name"):
                raise serializers.ValidationError({"reporter_name": "Ilagay ang pangalan, o piliin ang 'Anonymous'."})
            if not (attrs.get("reporter_contact") or attrs.get("reporter_email")):
                raise serializers.ValidationError(
                    {"reporter_contact": "Ilagay ang mobile number para ma-update ka namin sa SMS."}
                )
        return attrs

    @staticmethod
    def _auto_title(attrs):
        what = (attrs.get("subcategory") or attrs.get("category"))
        what = (what.name_fil or what.name) if what else "Concern"
        return f"{what} – {attrs['location_description']}"[:150]

    @transaction.atomic
    def create(self, validated):
        images = validated.pop("images", [])
        scale = validated.pop("affected_scale", "street")
        request = self.context.get("request")
        user = request.user if (request and request.user.is_authenticated) else None

        if not validated.get("title"):
            validated["title"] = self._auto_title(validated)

        concern = Concern.objects.create(
            **validated,
            affected_count=AFFECTED_BUCKETS[scale],
            # Citizen input is a hint only; staff set the real severity during triage.
            severity=Concern.Severity.SEVERE if validated.get("danger_now") else Concern.Severity.MODERATE,
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
    subcategory = serializers.CharField(source="subcategory.name", default=None)
    barangay = serializers.CharField(source="barangay.name")
    status_display = serializers.CharField(source="get_status_display")
    assigned_office = serializers.SerializerMethodField()
    timeline = serializers.SerializerMethodField()
    linked_to_reference = serializers.CharField(source="duplicate_of.reference_no", default=None)
    resolution_photos = serializers.SerializerMethodField()
    target_date = serializers.SerializerMethodField()
    deadline_extended = serializers.SerializerMethodField()
    endorsed_to = serializers.SerializerMethodField()
    priority_level = serializers.SerializerMethodField()

    class Meta:
        model = Concern
        read_only_fields = ["status"]
        fields = [
            "reference_no", "title", "category", "subcategory", "barangay", "status", "status_display",
            "assigned_office", "linked_to_reference", "created_at", "resolved_at", "timeline",
            "resolution_photos", "target_date", "deadline_extended", "endorsed_to", "priority_level",
        ]

    def get_assigned_office(self, obj) -> str | None:
        case = self._case(obj)
        if not case:
            return None
        if case.level == "barangay":
            return f"Barangay {obj.barangay.name}"
        return case.department.name if case.department else None

    def _case(self, obj):
        case = getattr(obj, "case", None)
        if not case and obj.duplicate_of_id:
            case = getattr(obj.duplicate_of, "case", None)
        return case

    def get_target_date(self, obj) -> str | None:
        """ARTA transparency: the citizen sees the committed date."""
        case = self._case(obj)
        return case.due_at.isoformat() if case and case.due_at and obj.is_open else None

    def get_deadline_extended(self, obj) -> bool:
        case = self._case(obj)
        return bool(case and case.extended_at)

    def get_priority_level(self, obj) -> str | None:
        case = self._case(obj)
        lvl = case.priority_level if case else None
        return (lvl.name_fil or lvl.name) if lvl and obj.is_open else None

    def get_endorsed_to(self, obj) -> str | None:
        case = self._case(obj)
        return case.department.name if case and case.level == "external" and case.department else None

    def get_resolution_photos(self, obj) -> list[str]:
        """Proof-of-fix photos from staff. Citizen-uploaded photos are never public (faces, homes, plates)."""
        source = obj.duplicate_of if obj.duplicate_of_id else obj
        return [a.file.url for a in source.attachments.all() if a.kind == "resolution"]

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
