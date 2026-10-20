"""Pin → barangay and purok."""
from . import geometry
from .models import Barangay, Purok

SNAP_M = 30          # a pin up to 30 m outside every purok (GPS drift, digitizing gaps) snaps to the nearest one
PAD = 0.0004         # ≈ 45 m bbox padding for the SQL prefilter


def find_purok(lat, lng, barangay_id=None):
    """
    Purok containing the point. Restricted to the given barangay when known: the barangay the citizen chose wins,
    because neighbouring boundaries overlap/gap by a few meters. Residential puroks win over land-use zones.
    Returns (purok, distance_m) or (None, None).
    """
    if lat is None or lng is None:
        return None, None
    lat, lng = float(lat), float(lng)
    qs = Purok.objects.filter(min_lat__lte=lat + PAD, max_lat__gte=lat - PAD, min_lng__lte=lng + PAD, max_lng__gte=lng - PAD)
    if barangay_id:
        qs = qs.filter(barangay_id=barangay_id)
    best = None
    for p in sorted(qs, key=lambda p: (p.is_zone, p.area_ha)):  # smaller, residential first
        if geometry.contains(p.boundary_geojson, lat, lng):
            return p, 0.0
        d = geometry.distance_m(p.boundary_geojson, lat, lng)
        if d <= SNAP_M and (best is None or d < best[1]):
            best = (p, d)
    return best if best else (None, None)


def find_barangay(lat, lng):
    """Barangay whose outline contains the point (or within 30 m). Used to pre-fill the report form from the pin."""
    if lat is None or lng is None:
        return None
    lat, lng = float(lat), float(lng)
    p, _ = find_purok(lat, lng)
    if p:
        return p.barangay
    for b in Barangay.objects.exclude(boundary_geojson=None):
        if geometry.contains(b.boundary_geojson, lat, lng):
            return b
    return None
