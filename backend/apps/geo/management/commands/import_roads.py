"""
Import road lines (Step 20) from a GeoJSON file: the DPWH road inventory, or an OpenStreetMap export.

    python manage.py import_roads national_roads.geojson --kind national --source "DPWH road inventory 2026"
    python manage.py import_roads osm_export.geojson --osm            # keeps only OSM ways with an N-route ref
    python manage.py import_roads national_roads.geojson --replace     # delete roads of that kind first

Getting national roads from OpenStreetMap (overpass-turbo.eu), then Export -> GeoJSON:
    [out:json];
    area["name"="Lucena"]["boundary"="administrative"]->.a;
    way(area.a)["highway"~"trunk|primary|secondary"]["ref"~"^N[0-9]"];
    out geom;
OpenStreetMap is volunteer data: check it against the City Engineering / DPWH list before relying on it.
"""
import json

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.geo.geometry import line_bbox
from apps.geo.models import Road


def features(data):
    if data.get("type") == "FeatureCollection":
        return data.get("features", [])
    if data.get("type") == "Feature":
        return [data]
    raise CommandError("Expected a GeoJSON Feature or FeatureCollection.")


class Command(BaseCommand):
    help = "Import road lines (national / city / barangay) from GeoJSON."

    def add_arguments(self, parser):
        parser.add_argument("path")
        parser.add_argument("--kind", default=Road.Kind.NATIONAL, choices=[k for k, _ in Road.Kind.choices])
        parser.add_argument("--source", default="")
        parser.add_argument("--osm", action="store_true", help="OpenStreetMap export: keep ways whose ref starts with N.")
        parser.add_argument("--replace", action="store_true", help="Delete existing roads of this kind first.")

    @transaction.atomic
    def handle(self, path, kind, source, osm, replace, **kw):
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        if replace:
            n, _ = Road.objects.filter(kind=kind).delete()
            self.stdout.write(f"Deleted {n} existing {kind} road(s).")
        made = skipped = 0
        for f in features(data):
            geom, props = f.get("geometry") or {}, f.get("properties") or {}
            tags = props.get("tags", props)  # overpass-turbo puts OSM tags at top level or under "tags"
            if geom.get("type") not in ("LineString", "MultiLineString"):
                skipped += 1
                continue
            ref = str(tags.get("ref", "") or "")
            if osm and not ref.upper().startswith("N"):
                skipped += 1
                continue
            mn_lat, mx_lat, mn_lng, mx_lng = line_bbox(geom)
            Road.objects.create(
                name=str(tags.get("name", "") or "")[:160], ref=ref[:40], kind=kind, geometry=geom,
                source=source or ("OpenStreetMap" if osm else ""), min_lat=mn_lat, max_lat=mx_lat,
                min_lng=mn_lng, max_lng=mx_lng,
            )
            made += 1
        self.stdout.write(self.style.SUCCESS(f"Imported {made} road line(s) as {kind}; skipped {skipped}."))
