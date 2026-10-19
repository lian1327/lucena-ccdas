from django.contrib import admin

from .models import Barangay


@admin.register(Barangay)
class BarangayAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "population", "center_lat", "center_lng")
    search_fields = ("name", "code")
