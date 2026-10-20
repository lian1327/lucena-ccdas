from django.db import models


class Barangay(models.Model):
    name = models.CharField(max_length=120, unique=True)
    code = models.CharField(max_length=20, unique=True)
    population = models.PositiveIntegerField(default=0)
    center_lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    center_lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    boundary_geojson = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Purok(models.Model):
    """
    Sub-barangay area. Polygons come from the barangay/purok GeoJSON (see import_boundaries).
    is_zone = a land-use polygon in the purok layer (fishpond, port, dumpsite, riceland) rather than a purok.
    """

    barangay = models.ForeignKey(Barangay, on_delete=models.CASCADE, related_name="puroks")
    name = models.CharField(max_length=120)
    is_zone = models.BooleanField(default=False, help_text="Fishpond / port / dumpsite / riceland, not a residential purok.")
    boundary_geojson = models.JSONField(help_text="GeoJSON Polygon/MultiPolygon geometry, WGS84 (lng, lat).")
    center_lat = models.DecimalField(max_digits=9, decimal_places=6)
    center_lng = models.DecimalField(max_digits=9, decimal_places=6)
    area_ha = models.FloatField(default=0)
    # bounding box: cheap SQL prefilter before the exact point-in-polygon test
    min_lat = models.FloatField(db_index=True)
    max_lat = models.FloatField(db_index=True)
    min_lng = models.FloatField(db_index=True)
    max_lng = models.FloatField(db_index=True)

    class Meta:
        ordering = ["barangay__name", "name"]
        unique_together = [("barangay", "name")]

    def __str__(self):
        return f"{self.name}, {self.barangay.name}"
