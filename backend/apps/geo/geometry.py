"""
Dependency-free geometry for barangay/purok lookup (no GDAL/PostGIS/shapely needed on the LGU server).
Polygons are GeoJSON geometries in WGS84: coordinates are [lng, lat].
"""
import math

M_PER_DEG_LAT = 111_320


def _polys(geom):
    if not geom:
        return []
    if geom["type"] == "Polygon":
        return [geom["coordinates"]]
    if geom["type"] == "MultiPolygon":
        return geom["coordinates"]
    return []


def _in_ring(lng, lat, ring):
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > lat) != (yj > lat) and lng < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-15) + xi:
            inside = not inside
        j = i
    return inside


def contains(geom, lat, lng):
    """Point in (multi)polygon, holes respected."""
    for rings in _polys(geom):
        if rings and _in_ring(lng, lat, rings[0]) and not any(_in_ring(lng, lat, h) for h in rings[1:]):
            return True
    return False


def distance_m(geom, lat, lng):
    """Distance in meters from a point to the polygon outline (0 if inside)."""
    if contains(geom, lat, lng):
        return 0.0
    kx = M_PER_DEG_LAT * math.cos(math.radians(lat))
    best = float("inf")
    for rings in _polys(geom):
        for ring in rings:
            for (x1, y1), (x2, y2) in zip(ring, ring[1:]):
                ax, ay = (x1 - lng) * kx, (y1 - lat) * M_PER_DEG_LAT
                bx, by = (x2 - lng) * kx, (y2 - lat) * M_PER_DEG_LAT
                dx, dy = bx - ax, by - ay
                t = max(0.0, min(1.0, -(ax * dx + ay * dy) / ((dx * dx + dy * dy) or 1e-12)))
                best = min(best, math.hypot(ax + t * dx, ay + t * dy))
    return best


def bbox(geom):
    xs, ys = [], []
    for rings in _polys(geom):
        for x, y in rings[0]:
            xs.append(x)
            ys.append(y)
    return min(ys), max(ys), min(xs), max(xs)
