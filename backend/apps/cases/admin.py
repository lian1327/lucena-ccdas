from django.contrib import admin

from .models import Case, CaseNote, Department


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "head", "is_active")


class NoteInline(admin.TabularInline):
    model = CaseNote
    extra = 0


@admin.register(Case)
class CaseAdmin(admin.ModelAdmin):
    list_display = ("concern", "department", "assigned_to", "escalation_level", "due_at", "resolved_at")
    list_filter = ("department", "escalation_level")
    raw_id_fields = ("concern", "assigned_to", "assigned_by")
    inlines = [NoteInline]
