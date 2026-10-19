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
