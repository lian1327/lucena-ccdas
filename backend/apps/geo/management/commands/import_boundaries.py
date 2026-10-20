"""
Load barangay outlines and purok polygons.

    python manage.py import_boundaries                       # bundled Lucena file (apps/geo/data/lucena_boundaries.geojson)
    python manage.py import_boundaries --file my.geojson     # your own, same format, WGS84
    python manage.py import_boundaries --assign              # also tag existing reports with their purok

File format: one FeatureCollection, WGS84 (EPSG:4326). Each feature's properties:
    kind: "purok" | "barangay", barangay: "<name as in the Barangay table>", name: "<purok name>" (puroks),
    is_zone: true for fishpond/port/dumpsite/riceland polygons, center: [lat, lng] (optional), area_ha (optional)
The bundled file was converted from the original PRS92 / Philippines zone III (EPSG:3123) files.
Barangay centers are replaced by a point inside the real outline.
"""
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.concerns.models import Concern
from apps.geo import geometry
from apps.geo.locate import find_purok
from apps.geo.models import Barangay, Purok

DEFAULT = Path(__file__).resolve().parents[2] / "data" / "lucena_boundaries.geojson"


class Command(BaseCommand):
    help = "Import barangay outlines + purok polygons (WGS84 GeoJSON)."

    def add_arguments(self, p):
        p.add_argument("--file", default=str(DEFAULT))
        p.add_argument("--assign", action="store_true", help="Tag existing pinned reports with their purok.")

    def handle(self, *a, o=None, **opts):
        data = json.loads(Path(opts["file"]).read_text(encoding="utf-8"))
        brgys = {self._key(b.name): b for b in Barangay.objects.all()}
        missing = set()
        n_p = n_b = 0
        with transaction.atomic():
            Purok.objects.all().delete()
            for f in data["features"]:
                p, g = f["properties"], f["geometry"]
                b = brgys.get(self._key(p["barangay"]))
                if not b:
                    missing.add(p["barangay"])
                    continue
                lat0, lat1, lng0, lng1 = geometry.bbox(g)
                center = p.get("center") or [(lat0 + lat1) / 2, (lng0 + lng1) / 2]
                if p.get("kind") == "barangay":
                    b.boundary_geojson = g
                    b.center_lat, b.center_lng = round(center[0], 6), round(center[1], 6)
                    b.save(update_fields=["boundary_geojson", "center_lat", "center_lng"])
                    n_b += 1
                else:
                    name, k = p["name"].strip(), 1
                    while Purok.objects.filter(barangay=b, name=name).exists():  # repeated names (e.g. "Fishpond")
                        k += 1
                        name = f"{p['name'].strip()} {k}"
                    Purok.objects.create(barangay=b, name=name, is_zone=bool(p.get("is_zone")),
                                         boundary_geojson=g, center_lat=round(center[0], 6), center_lng=round(center[1], 6),
                                         area_ha=p.get("area_ha") or 0, min_lat=lat0, max_lat=lat1, min_lng=lng0, max_lng=lng1)
                    n_p += 1
        if missing:
            self.stdout.write(self.style.WARNING(f"Not in the Barangay table (skipped): {', '.join(sorted(missing))}"))
        self.stdout.write(self.style.SUCCESS(f"Imported {n_b} barangay outlines and {n_p} puroks/zones."))
        if opts["assign"]:
            self.stdout.write(f"  tagged {assign_all()} pinned reports with a purok")

    @staticmethod
    def _key(name):
        return name.lower().replace("-", " ").replace("barangay ", "").replace("marketview", "market view").strip()


def assign_all(qs=None):
    qs = qs if qs is not None else Concern.objects.all()
    n = 0
    for c in qs.filter(latitude__isnull=False).only("id", "latitude", "longitude", "barangay_id").iterator():
        p, _ = find_purok(c.latitude, c.longitude, c.barangay_id)
        if p:
            Concern.objects.filter(pk=c.pk).update(purok=p, purok_source="pin")
            n += 1
    return n
