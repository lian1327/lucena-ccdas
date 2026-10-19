import secrets

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

REF_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I to avoid misreading


class Category(models.Model):
    """Concern category (Road Damage, Streetlight, ...). Also the ML label set."""

    code = models.SlugField(max_length=40, unique=True)
    name = models.CharField(max_length=80)
    name_fil = models.CharField("Name (Filipino)", max_length=80, blank=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True, help_text="Bootstrap Icons name, e.g. 'cone-striped'")
    default_department = models.ForeignKey(
        "cases.Department", null=True, blank=True, on_delete=models.SET_NULL, related_name="default_categories"
    )
    severity_weight = models.DecimalField(
        max_digits=3, decimal_places=2, default=1.00,
        validators=[MinValueValidator(0.5), MaxValueValidator(1.5)],
        help_text="Multiplier for the severity component of the priority score (0.50–1.50).",
    )
    sla_days = models.PositiveSmallIntegerField(default=7, help_text="Target resolution time in days.")
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class Subcategory(models.Model):
    """Second level of the taxonomy (e.g. Drainage → Clogged canal). Citizens tap these instead of typing."""

    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="subcategories")
    code = models.SlugField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    name_fil = models.CharField("Name (Filipino)", max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["category__sort_order", "sort_order", "name"]
        verbose_name_plural = "subcategories"

    def __str__(self):
        return f"{self.category.name} › {self.name}"


class Concern(models.Model):
    class Status(models.TextChoices):
        SUBMITTED = "submitted", "Submitted"
        UNDER_REVIEW = "under_review", "Under Review"
        ASSIGNED = "assigned", "Assigned"
        IN_PROGRESS = "in_progress", "In Progress"
        RESOLVED = "resolved", "Resolved"
        CLOSED = "closed", "Closed"
        REJECTED = "rejected", "Rejected"

    OPEN_STATUSES = [Status.SUBMITTED, Status.UNDER_REVIEW, Status.ASSIGNED, Status.IN_PROGRESS]
    DONE_STATUSES = [Status.RESOLVED, Status.CLOSED]

    class Channel(models.TextChoices):
        WEB = "web", "Web Portal"
        FACEBOOK = "facebook", "Facebook Comment"
        MESSENGER = "messenger", "Messenger"
        WALK_IN = "walk_in", "Walk-in"
        BARANGAY = "barangay", "Barangay Report"
        HOTLINE = "hotline", "Hotline / Call"

    class Severity(models.IntegerChoices):
        MINOR = 1, "Minor"
        MODERATE = 2, "Moderate"
        SERIOUS = 3, "Serious"
        SEVERE = 4, "Severe"
        CRITICAL = 5, "Critical"

    class CategorySource(models.TextChoices):
        CITIZEN = "citizen", "Selected by citizen"
        ML = "ml", "AI classification"
        STAFF = "staff", "Set by staff"

    # Identity
    reference_no = models.CharField(max_length=20, unique=True, editable=False)
    title = models.CharField(max_length=150)
    description = models.TextField()

    # Classification
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.PROTECT, related_name="concerns")
    subcategory = models.ForeignKey(
        Subcategory, null=True, blank=True, on_delete=models.PROTECT, related_name="concerns"
    )
    category_source = models.CharField(max_length=10, choices=CategorySource.choices, default=CategorySource.CITIZEN)
    predicted_category = models.ForeignKey(
        Category, null=True, blank=True, on_delete=models.SET_NULL, related_name="predicted_concerns"
    )
    prediction_confidence = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)

    # Intake
    channel = models.CharField(max_length=20, choices=Channel.choices, default=Channel.WEB)
    source_reference = models.CharField(
        max_length=300, blank=True, help_text="Where staff got it: FB post/comment link, logbook entry no., caller name, etc."
    )
    encoded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="encoded_concerns",
        help_text="Staff who encoded a walk-in/FB/barangay report on the citizen's behalf.",
    )
    severity = models.PositiveSmallIntegerField(choices=Severity.choices, default=Severity.MODERATE)
    affected_count = models.PositiveIntegerField(default=1, help_text="Estimated number of affected citizens.")
    danger_now = models.BooleanField(
        default=False, help_text="Citizen answered: is anyone in danger right now? (severity hint, not a score)"
    )
    involves_barangay_officials = models.BooleanField(
        default=False, help_text="Complaint concerns barangay officials — hidden from barangay personnel, routed to City."
    )

    # Location
    barangay = models.ForeignKey("geo.Barangay", on_delete=models.PROTECT, related_name="concerns")
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    location_description = models.CharField(max_length=255, blank=True, help_text="Landmark / street")

    # Reporter (RA 10173: collect only what is needed, with consent)
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="concerns"
    )
    reporter_name = models.CharField(max_length=150, blank=True)
    reporter_contact = models.CharField(max_length=20, blank=True)
    reporter_email = models.EmailField(blank=True)
    is_anonymous = models.BooleanField(default=False)
    consent_given = models.BooleanField(default=False)
    consent_at = models.DateTimeField(null=True, blank=True)

    # Workflow
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SUBMITTED, db_index=True)
    duplicate_of = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="duplicates",
        help_text="Master report this one was linked to.",
    )
    priority_score = models.DecimalField(max_digits=5, decimal_places=2, default=0, db_index=True)

    # Triage: analytics count only verified concerns (staff-confirmed category, sub-type, severity)
    is_verified = models.BooleanField(default=False, db_index=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    verified_at = models.DateTimeField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["barangay", "category"]),
            models.Index(fields=["status", "-priority_score"]),
        ]

    def __str__(self):
        return f"{self.reference_no} – {self.title}"

    def save(self, *args, **kwargs):
        if not self.reference_no:
            self.reference_no = self._generate_reference()
        super().save(*args, **kwargs)

    @classmethod
    def _generate_reference(cls):
        year = timezone.now().year
        while True:
            ref = f"CCD-{year}-" + "".join(secrets.choice(REF_ALPHABET) for _ in range(6))
            if not cls.objects.filter(reference_no=ref).exists():
                return ref

    @property
    def is_open(self):
        return self.status in self.OPEN_STATUSES

    @property
    def is_overdue(self):
        case = getattr(self, "case", None)
        return bool(self.is_open and case and case.due_at and case.due_at < timezone.now())

    @property
    def priority_tier(self):
        s = float(self.priority_score)
        if s >= 75:
            return "critical"
        if s >= 50:
            return "high"
        if s >= 25:
            return "medium"
        return "low"


def attachment_path(instance, filename):
    now = timezone.now()
    return f"concerns/{now:%Y/%m}/{instance.concern.reference_no}_{filename}"


class ConcernAttachment(models.Model):
    class Kind(models.TextChoices):
        REPORT = "report", "Report photo (from reporter)"
        RESOLUTION = "resolution", "Resolution photo (proof of fix)"

    concern = models.ForeignKey(Concern, on_delete=models.CASCADE, related_name="attachments")
    kind = models.CharField(max_length=12, choices=Kind.choices, default=Kind.REPORT)
    file = models.ImageField(upload_to=attachment_path)
    caption = models.CharField(max_length=150, blank=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Attachment for {self.concern.reference_no}"


class StatusHistory(models.Model):
    """Audit trail of every status change. is_public=False entries never reach the citizen."""

    concern = models.ForeignKey(Concern, on_delete=models.CASCADE, related_name="history")
    from_status = models.CharField(max_length=20, choices=Concern.Status.choices, blank=True)
    to_status = models.CharField(max_length=20, choices=Concern.Status.choices)
    remarks = models.TextField(blank=True)
    is_public = models.BooleanField(default=True)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name_plural = "status history"

    def __str__(self):
        return f"{self.concern.reference_no}: {self.from_status or '—'} → {self.to_status}"
