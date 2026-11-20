"""Which road is a pin on? Used to suggest who maintains it (Step 20). Bounding-box prefilter in SQL, exact in Python."""
from .geometry import M_PER_DEG_LAT, line_distance_m
from .models import Road

ROAD_MATCH_M = 25  # a pin this close to a road centerline is treated as on that road (GPS + road width)


def nearest_road(lat, lng, kind=Road.Kind.NATIONAL, max_m=ROAD_MATCH_M):
    """(road, distance_m) for the closest road of this kind within max_m, else (None, None)."""
    if lat is None or lng is None:
        return None, None
    lat, lng = float(lat), float(lng)
    pad = max_m / M_PER_DEG_LAT * 1.5
    best, best_d = None, None
    for road in Road.objects.filter(kind=kind, min_lat__lte=lat + pad, max_lat__gte=lat - pad,
                                    min_lng__lte=lng + pad, max_lng__gte=lng - pad):
        d = line_distance_m(road.geometry, lat, lng)
        if d <= max_m and (best_d is None or d < best_d):
            best, best_d = road, d
    return best, (round(best_d, 1) if best else None)
