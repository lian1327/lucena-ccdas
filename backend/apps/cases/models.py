from django.conf import settings
from django.db import models


class Department(models.Model):
    """An LGU office (internal) or a partner agency the LGU endorses concerns to (external, e.g. DPWH)."""

    class Kind(models.TextChoices):
        INTERNAL = "internal", "LGU office"
        EXTERNAL = "external", "External agency (endorsement only)"

    name = models.CharField(max_length=150, unique=True)
    code = models.CharField(max_length=20, unique=True)
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.INTERNAL)
    head = models.CharField(max_length=150, blank=True)
    contact = models.CharField(max_length=200, blank=True, help_text="For external agencies: office address / email / phone.")
    screening_checklist = models.JSONField(
        default=list, blank=True,
        help_text='Office-specific checks done on receipt, e.g. ["Nasa city road (hindi national road)?", ...]',
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["kind", "name"]

    def __str__(self):
        return self.name

    @property
    def is_external(self):
        return self.kind == self.Kind.EXTERNAL


class Division(models.Model):
    """Unit inside an office that does the actual work (e.g. CEO › Road, Drainage & Bridges Maintenance)."""

    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name="divisions")
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=30, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["department__name", "name"]
        unique_together = [("department", "name")]

    def __str__(self):
        return f"{self.department.code} › {self.name}"


class PriorityLevel(models.Model):
    """
    LGU service standard for urgency. ARTA (RA 11032) sets the legal MAXIMUM by complexity (3/7/20 working days);
    a priority level can only make the target shorter: resolution target = min(resolution_cap_days, ARTA class).
    The response target is the time to first field action (inspection or make-safe).
    """

    code = models.CharField(max_length=4, unique=True)  # P1..P4
    name = models.CharField(max_length=40)
    name_fil = models.CharField(max_length=40, blank=True)
    description = models.CharField(max_length=255, blank=True)
    response_hours = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="Calendar hours (emergencies don't wait for working days).",
    )
    response_working_days = models.PositiveSmallIntegerField(null=True, blank=True)
    resolution_cap_days = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="Working days. Empty = use the ARTA class maximum.",
    )
    color = models.CharField(max_length=20, default="secondary", help_text="Bootstrap color: danger, warning, info, secondary")
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order"]

    def __str__(self):
        return f"{self.code} · {self.name}"


class Holiday(models.Model):
    """Non-working days, so ARTA deadlines count working days. Add proclamations (Holy Week, special days) yearly."""

    date = models.DateField(unique=True)
    name = models.CharField(max_length=120)

    class Meta:
        ordering = ["date"]

    def __str__(self):
        return f"{self.date} {self.name}"


class Case(models.Model):
    """Internal handling record for a concern (Module 2: Case Management)."""

    class Level(models.TextChoices):
        CITY = "city", "City office"
        BARANGAY = "barangay", "Barangay-level"
        EXTERNAL = "external", "Endorsed to external agency"

    class EscalationLevel(models.IntegerChoices):
        NONE = 0, "Not escalated"
        DEPARTMENT_HEAD = 1, "Department Head"
        CITY_ADMIN = 2, "City Administrator"
        MAYOR = 3, "Mayor's Office"

    concern = models.OneToOneField("concerns.Concern", on_delete=models.CASCADE, related_name="case")
    level = models.CharField(max_length=10, choices=Level.choices, default=Level.CITY)
    department = models.ForeignKey(
        Department, null=True, blank=True, on_delete=models.PROTECT, related_name="cases",
        help_text="Empty for barangay-level cases.",
    )
    division = models.ForeignKey(Division, null=True, blank=True, on_delete=models.SET_NULL, related_name="cases")
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_cases"
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    routed_at = models.DateTimeField(null=True, blank=True, help_text="When the current office received it (clock start).")

    # Office receiving & screening: the office confirms the case is theirs before work starts
    accepted_at = models.DateTimeField(null=True, blank=True)
    accepted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    acceptance_due_at = models.DateTimeField(null=True, blank=True)
    screening = models.JSONField(default=dict, blank=True, help_text="Answers to the office's screening checklist.")
    returned_at = models.DateTimeField(null=True, blank=True)
    return_reason = models.TextField(blank=True)
    return_count = models.PositiveSmallIntegerField(default=0)

    # Priority (urgency) — sets response target and caps the resolution target within ARTA
    priority_level = models.ForeignKey(PriorityLevel, null=True, blank=True, on_delete=models.PROTECT, related_name="cases")
    priority_reason = models.CharField(max_length=300, blank=True)
    response_due_at = models.DateTimeField(null=True, blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    responded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    response_remarks = models.TextField(blank=True)

    # ARTA (RA 11032): working-day deadline; one written extension, notified before the original lapses
    due_at = models.DateTimeField(null=True, blank=True)
    original_due_at = models.DateTimeField(null=True, blank=True)
    extended_at = models.DateTimeField(null=True, blank=True)
    extension_reason = models.TextField(blank=True)

    # Field work (mirrors Citizen's Charter steps: inspect → schedule → execute)
    inspected_at = models.DateTimeField(null=True, blank=True)
    inspected_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    inspection_findings = models.TextField(blank=True)
    action_plan = models.TextField(blank=True)
    scheduled_for = models.DateField(null=True, blank=True)

    work_completed_at = models.DateTimeField(null=True, blank=True)
    work_completed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    completion_remarks = models.TextField(blank=True)

    # Two-person rule: someone other than the doer confirms the fix before the citizen sees "Resolved"
    validated_at = models.DateTimeField(null=True, blank=True)
    validated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    escalation_level = models.PositiveSmallIntegerField(choices=EscalationLevel.choices, default=EscalationLevel.NONE)
    escalated_at = models.DateTimeField(null=True, blank=True)
    escalation_reason = models.TextField(blank=True)
    next_escalation_at = models.DateTimeField(
        null=True, blank=True, help_text="Earliest time the next automatic escalation may fire (targets never move).",
    )

    resolution_summary = models.TextField(blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-assigned_at"]

    def __str__(self):
        where = self.department.code if self.department else "Barangay"
        return f"Case {self.concern.reference_no} → {where}"

    @property
    def stage(self):
        """Where the work stands, for queues and the UI stepper."""
        if self.validated_at:
            return "validated"
        if self.work_completed_at:
            return "for_validation"
        if self.level == self.Level.EXTERNAL:
            return "endorsed"
        if self.level == self.Level.CITY and (self.department_id is None):
            return "returned"
        if self.level == self.Level.CITY and not self.accepted_at:
            return "for_acceptance"
        if self.inspected_at:
            return "scheduled"
        if self.assigned_to_id or self.level == self.Level.BARANGAY:
            return "assigned"
        if self.division_id:
            return "with_division"
        return "with_department"


class Endorsement(models.Model):
    """
    Concerns outside LGU jurisdiction (e.g. national roads → DPWH). The agency won't use the platform,
    so the LGU logs the endorsement and every follow-up, keeping the citizen's case visible and accountable.
    """

    class Status(models.TextChoices):
        ENDORSED = "endorsed", "Endorsed, awaiting response"
        ACKNOWLEDGED = "acknowledged", "Acknowledged by agency"
        SCHEDULED = "scheduled", "Agency scheduled action"
        COMPLETED = "completed", "Agency reports completed"
        DECLINED = "declined", "Declined / not their jurisdiction"

    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="endorsements")
    agency = models.ForeignKey(Department, on_delete=models.PROTECT, limit_choices_to={"kind": "external"})
    endorsed_at = models.DateTimeField(auto_now_add=True)
    endorsed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    letter_reference = models.CharField(max_length=120, blank=True, help_text="Endorsement letter / memo no.")
    contact_person = models.CharField(max_length=150, blank=True)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.ENDORSED)
    agency_response = models.TextField(blank=True)
    next_follow_up_at = models.DateTimeField(null=True, blank=True)
    follow_up_count = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["-endorsed_at"]

    def __str__(self):
        return f"{self.case.concern.reference_no} → {self.agency.code} ({self.status})"


class EndorsementFollowUp(models.Model):
    endorsement = models.ForeignKey(Endorsement, on_delete=models.CASCADE, related_name="follow_ups")
    at = models.DateTimeField(auto_now_add=True)
    by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    method = models.CharField(max_length=30, blank=True, help_text="call / letter / email / visit / meeting")
    notes = models.TextField()

    class Meta:
        ordering = ["at"]


class CaseNote(models.Model):
    """Internal staff notes; never exposed to the public."""

    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="notes")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
