from django.conf import settings
from django.db import models


class Notification(models.Model):
    """
    One message to one citizen on one channel (SMS or email): the outbox and the delivery log in one table.
    Rendered when queued, so the log shows exactly what the citizen received.
    RA 10173: `recipient` is personal data; `purge_notifications` blanks it after the retention period.
    """

    class Channel(models.TextChoices):
        SMS = "sms", "SMS"
        EMAIL = "email", "Email"

    class Event(models.TextChoices):
        RECEIVED = "received", "Report received"
        ASSIGNED = "assigned", "Routed to office"
        IN_PROGRESS = "in_progress", "Work started"
        EXTENDED = "extended", "Deadline extended"
        RESOLVED = "resolved", "Resolved"
        REMINDER = "reminder", "Confirm-fix reminder"
        REOPENED = "reopened", "Reopened"
        CLOSED = "closed", "Closed"
        REJECTED = "rejected", "Rejected"

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        SENT = "sent", "Sent to provider"
        DELIVERED = "delivered", "Delivered to network"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"

    concern = models.ForeignKey("concerns.Concern", on_delete=models.CASCADE, related_name="notifications")
    history = models.ForeignKey("concerns.StatusHistory", null=True, blank=True, on_delete=models.SET_NULL,
                                related_name="notifications")
    channel = models.CharField(max_length=5, choices=Channel.choices)
    event = models.CharField(max_length=12, choices=Event.choices)
    dedupe_key = models.CharField(max_length=60, help_text="Stops the same update going out twice.")
    recipient = models.CharField(max_length=254, blank=True)
    subject = models.CharField(max_length=200, blank=True)
    body = models.TextField()
    segments = models.PositiveSmallIntegerField(default=1, help_text="SMS parts billed (1 credit each).")

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.QUEUED, db_index=True)
    scheduled_for = models.DateTimeField(db_index=True, help_text="Not sent before this (quiet hours).")
    attempts = models.PositiveSmallIntegerField(default=0)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    provider = models.CharField(max_length=20, blank=True)
    provider_message_id = models.CharField(max_length=64, blank=True, db_index=True)
    provider_status = models.CharField(max_length=30, blank=True)
    network = models.CharField(max_length=30, blank=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["concern", "channel", "dedupe_key"], name="uniq_notification_per_update"),
        ]
        indexes = [models.Index(fields=["status", "scheduled_for"])]

    def __str__(self):
        return f"{self.get_channel_display()} {self.event} → {self.concern.reference_no} ({self.status})"

    @property
    def masked_recipient(self):
        r = self.recipient
        if not r:
            return ""
        if "@" in r:
            name, _, dom = r.partition("@")
            return f"{name[:2]}***@{dom}"
        local = "0" + r[2:] if r.startswith("63") else r  # 639171234567 → 09171234567
        return f"{local[:4]}***{local[-4:]}" if len(local) >= 8 else "***"


class StaffAlert(models.Model):
    """In-app bell for staff: something now needs this person's action."""

    class Kind(models.TextChoices):
        NEW_CASE = "new_case", "New case for your office"
        ASSIGNED = "assigned", "Assigned to you"
        RETURNED = "returned", "Returned to PACD"
        DANGER = "danger", "Report says there is danger now"
        FOR_VALIDATION = "for_validation", "Work done, needs validation"
        SENT_BACK = "sent_back", "Work returned by supervisor"
        ESCALATED = "escalated", "Escalated to you"
        DISPUTED = "disputed", "Citizen says not fixed"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="alerts")
    kind = models.CharField(max_length=16, choices=Kind.choices)
    concern = models.ForeignKey("concerns.Concern", null=True, blank=True, on_delete=models.CASCADE,
                                related_name="staff_alerts")
    title = models.CharField(max_length=160)
    body = models.CharField(max_length=300, blank=True)
    is_urgent = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "read_at"])]

    def __str__(self):
        return f"{self.user} · {self.title}"
