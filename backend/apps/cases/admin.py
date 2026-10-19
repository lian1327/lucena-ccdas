from django.contrib import admin

from .models import Case, CaseNote, Department, Division, Endorsement, EndorsementFollowUp, Holiday


class DivisionInline(admin.TabularInline):
    model = Division
    extra = 0


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "kind", "head", "is_active")
    list_filter = ("kind", "is_active")
    inlines = [DivisionInline]


@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):
    list_display = ("date", "name")
    date_hierarchy = "date"


class NoteInline(admin.TabularInline):
    model = CaseNote
    extra = 0


class FollowUpInline(admin.TabularInline):
    model = EndorsementFollowUp
    extra = 0


@admin.register(Endorsement)
class EndorsementAdmin(admin.ModelAdmin):
    list_display = ("case", "agency", "status", "endorsed_at", "follow_up_count", "next_follow_up_at")
    list_filter = ("agency", "status")
    inlines = [FollowUpInline]


@admin.register(Case)
class CaseAdmin(admin.ModelAdmin):
    list_display = ("concern", "level", "department", "division", "assigned_to", "due_at",
                    "extended_at", "escalation_level", "validated_at")
    list_filter = ("level", "department", "escalation_level")
    raw_id_fields = ("concern", "assigned_to", "assigned_by")
    inlines = [NoteInline]
