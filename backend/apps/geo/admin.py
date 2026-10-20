from django.contrib import admin

from .models import Barangay, Purok


@admin.register(Barangay)
class BarangayAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "population", "center_lat", "center_lng")
    search_fields = ("name", "code")



@admin.register(Purok)
class PurokAdmin(admin.ModelAdmin):
    list_display = ["name", "barangay", "is_zone", "area_ha"]
    list_filter = ["barangay", "is_zone"]
    search_fields = ["name", "barangay__name"]
    exclude = ["boundary_geojson"]
    readonly_fields = ["center_lat", "center_lng", "min_lat", "max_lat", "min_lng", "max_lng"]
