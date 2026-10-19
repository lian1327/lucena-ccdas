from django.contrib import admin

from .models import Category, Concern, ConcernAttachment, StatusHistory, Subcategory


class SubcategoryInline(admin.TabularInline):
    model = Subcategory
    extra = 0
    prepopulated_fields = {"code": ("name",)}


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    inlines = [SubcategoryInline]
    list_display = ("name", "code", "default_department", "severity_weight", "sla_days", "is_active", "sort_order")
    list_editable = ("severity_weight", "sla_days", "is_active", "sort_order")
    prepopulated_fields = {"code": ("name",)}


class AttachmentInline(admin.TabularInline):
    model = ConcernAttachment
    extra = 0
    readonly_fields = ("uploaded_by", "uploaded_at")


class HistoryInline(admin.TabularInline):
    model = StatusHistory
    extra = 0
    readonly_fields = ("from_status", "to_status", "remarks", "is_public", "changed_by", "created_at")
    can_delete = False


@admin.register(Concern)
class ConcernAdmin(admin.ModelAdmin):
    list_display = ("reference_no", "title", "category", "subcategory", "barangay", "status",
                    "is_verified", "danger_now", "priority_score", "channel", "created_at")
    list_filter = ("status", "is_verified", "danger_now", "involves_barangay_officials",
                   "category", "channel", "severity", "barangay")
    search_fields = ("reference_no", "title", "description", "reporter_name")
    readonly_fields = ("reference_no", "priority_score", "created_at", "updated_at", "consent_at",
                       "verified_by", "verified_at")
    raw_id_fields = ("duplicate_of", "reporter")
    inlines = [AttachmentInline, HistoryInline]
    date_hierarchy = "created_at"
