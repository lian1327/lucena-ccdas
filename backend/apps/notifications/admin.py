from django.contrib import admin

from .models import Notification, StaffAlert


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["created_at", "concern", "channel", "event", "status", "segments", "provider_status", "attempts"]
    list_filter = ["channel", "event", "status", "provider"]
    search_fields = ["concern__reference_no", "provider_message_id"]
    readonly_fields = [f.name for f in Notification._meta.fields]


@admin.register(StaffAlert)
class StaffAlertAdmin(admin.ModelAdmin):
    list_display = ["created_at", "user", "kind", "title", "is_urgent", "read_at"]
    list_filter = ["kind", "is_urgent"]
    search_fields = ["title", "user__username"]
