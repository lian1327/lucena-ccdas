from django.conf import settings
from django.db import models


class Department(models.Model):
    name = models.CharField(max_length=150, unique=True)
    code = models.CharField(max_length=20, unique=True)
    head = models.CharField(max_length=150, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Case(models.Model):
    """Internal handling record for a concern (Module 2: Case Management)."""

    class EscalationLevel(models.IntegerChoices):
        NONE = 0, "Not escalated"
        DEPARTMENT_HEAD = 1, "Department Head"
        CITY_ADMIN = 2, "City Administrator"
        MAYOR = 3, "Mayor's Office"

    concern = models.OneToOneField("concerns.Concern", on_delete=models.CASCADE, related_name="case")
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="cases")
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_cases"
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    due_at = models.DateTimeField(null=True, blank=True)

    escalation_level = models.PositiveSmallIntegerField(
        choices=EscalationLevel.choices, default=EscalationLevel.NONE
    )
    escalated_at = models.DateTimeField(null=True, blank=True)
    escalation_reason = models.TextField(blank=True)

    resolution_summary = models.TextField(blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-assigned_at"]

    def __str__(self):
        return f"Case {self.concern.reference_no} → {self.department.code}"


class CaseNote(models.Model):
    """Internal staff notes; never exposed to the public."""

    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="notes")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
