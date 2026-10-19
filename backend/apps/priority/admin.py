from django.contrib import admin

from .models import PriorityScore


@admin.register(PriorityScore)
class PriorityScoreAdmin(admin.ModelAdmin):
    list_display = ("concern", "total", "severity_component", "affected_component",
                    "duplicate_component", "delay_component", "duplicate_count", "computed_at")
    ordering = ("-total",)
    readonly_fields = [f.name for f in PriorityScore._meta.fields]
