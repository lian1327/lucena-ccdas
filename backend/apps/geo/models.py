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


class Road(models.Model):
    """
    Step 20: road lines used to tell who maintains what at a pin, e.g. a streetlight on a national road is the
    electric utility's (endorse), on a city or barangay road it is the City's (route to GSO).
    Imported from the DPWH road inventory or OpenStreetMap with: manage.py import_roads <file.geojson>
    """

    class Kind(models.TextChoices):
        NATIONAL = "national", "National road"
        CITY = "city", "City road"
        BARANGAY = "barangay", "Barangay road"

    name = models.CharField(max_length=160, blank=True)
    ref = models.CharField(max_length=40, blank=True, help_text="Route number, e.g. N1")
    kind = models.CharField(max_length=12, choices=Kind.choices, default=Kind.NATIONAL, db_index=True)
    geometry = models.JSONField(help_text="GeoJSON LineString/MultiLineString, WGS84 (lng, lat).")
    source = models.CharField(max_length=80, blank=True, help_text="DPWH road inventory, OpenStreetMap, …")
    min_lat = models.FloatField(db_index=True)
    max_lat = models.FloatField(db_index=True)
    min_lng = models.FloatField(db_index=True)
    max_lng = models.FloatField(db_index=True)

    class Meta:
        ordering = ["kind", "name"]

    def __str__(self):
        return f"{self.name or self.ref or 'Road'} ({self.get_kind_display()})"
