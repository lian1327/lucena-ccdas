from rest_framework import serializers

from .models import Notification, StaffAlert


class StaffAlertSerializer(serializers.ModelSerializer):
    reference_no = serializers.CharField(source="concern.reference_no", default=None)
    concern_id = serializers.IntegerField(source="concern.id", default=None)
    kind_display = serializers.CharField(source="get_kind_display")

    class Meta:
        model = StaffAlert
        fields = ["id", "kind", "kind_display", "title", "body", "is_urgent", "reference_no", "concern_id",
                  "read_at", "created_at"]


class StaffAlertListSerializer(serializers.Serializer):
    unread = serializers.IntegerField()
    urgent_unread = serializers.IntegerField()
    results = StaffAlertSerializer(many=True)


class NotificationSerializer(serializers.ModelSerializer):
    reference_no = serializers.CharField(source="concern.reference_no")
    concern_id = serializers.IntegerField(source="concern.id")
    recipient = serializers.CharField(source="masked_recipient")
    event_display = serializers.CharField(source="get_event_display")
    status_display = serializers.CharField(source="get_status_display")
    can_retry = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = ["id", "reference_no", "concern_id", "channel", "event", "event_display", "recipient", "subject",
                  "body", "segments", "status", "status_display", "provider", "provider_status", "network",
                  "attempts", "error", "scheduled_for", "sent_at", "created_at", "can_retry"]

    def get_can_retry(self, obj) -> bool:
        return obj.status == Notification.Status.FAILED and bool(obj.recipient)


class NotificationStatsSerializer(serializers.Serializer):
    provider = serializers.CharField()
    sender_name = serializers.CharField()
    credit_balance = serializers.FloatField(allow_null=True)
    month_sms = serializers.IntegerField()
    month_credits = serializers.IntegerField()
    month_email = serializers.IntegerField()
    delivered_rate = serializers.FloatField(allow_null=True)
    failed = serializers.IntegerField()
    queued = serializers.IntegerField()
    opted_out = serializers.IntegerField()
    reach_rate = serializers.FloatField(allow_null=True, help_text="Share of this month's reports that can receive updates.")


class NotificationPageSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    results = NotificationSerializer(many=True)


class PublicNotifyPrefsSerializer(serializers.Serializer):
    sms = serializers.BooleanField()
    mobile_last4 = serializers.RegexField(r"^\d{4}$")
