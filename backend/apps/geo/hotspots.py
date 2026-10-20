"""
Hotspot detection (Module 5): DBSCAN on great-circle distance.

Why DBSCAN: it needs no preset number of clusters, finds irregular shapes along streets/canals, and
labels isolated one-off reports as noise instead of forcing them into a cluster. Distance is haversine
on (lat, lng) in radians, so eps is a real radius on the ground.

Parameters (defaults tuned for barangay-scale problems):
  eps_m       = 75 m   reports within ~1 block of each other
  min_samples = 4      at least 4 reports (incl. duplicates) to call it a hotspot
"""
import math
from collections import Counter

import numpy as np
from sklearn.cluster import DBSCAN

EARTH_RADIUS_M = 6_371_000


def detect(points, eps_m=75, min_samples=4):
    """
    points: list of dicts with lat, lng, and any attributes (id, subcategory, status, created_at, barangay...).
    Returns clusters sorted by size: [{"members": [point, ...]}, ...]
    """
    if len(points) < min_samples:
        return []
    coords = np.radians([[p["lat"], p["lng"]] for p in points])
    labels = DBSCAN(eps=eps_m / EARTH_RADIUS_M, min_samples=min_samples, metric="haversine",
                    algorithm="ball_tree").fit(coords).labels_
    groups = {}
    for p, label in zip(points, labels):
        if label >= 0:
            groups.setdefault(int(label), []).append(p)
    return sorted(({"members": m} for m in groups.values()), key=lambda c: -len(c["members"]))


def summarize(cluster, open_statuses):
    m = cluster["members"]
    lat = sum(p["lat"] for p in m) / len(m)
    lng = sum(p["lng"] for p in m) / len(m)
    radius = max(_dist_m(lat, lng, p["lat"], p["lng"]) for p in m)
    subs = Counter(p["subcategory"] or p["category"] or "—" for p in m)
    top, top_n = subs.most_common(1)[0]
    months = {p["created_at"].strftime("%Y-%m") for p in m}
    brgy = Counter(p["barangay"] for p in m).most_common(1)[0][0]
    landmark = Counter(p["landmark"] for p in m if p["landmark"]).most_common(1)
    return {
        "lat": round(lat, 6), "lng": round(lng, 6), "radius_m": round(max(radius, 25)),
        "count": len(m),
        "open": sum(1 for p in m if p["status"] in open_statuses),
        "top_issue": top, "top_issue_share": round(top_n / len(m) * 100),
        "issues": [{"name": k, "count": v} for k, v in subs.most_common(4)],
        "barangay": brgy,
        "landmark": landmark[0][0] if landmark else "",
        "months_active": len(months),
        "first_report": min(p["created_at"] for p in m).isoformat(),
        "last_report": max(p["created_at"] for p in m).isoformat(),
        "concern_ids": [p["id"] for p in sorted(m, key=lambda p: p["created_at"], reverse=True)][:50],
    }


def _dist_m(lat1, lng1, lat2, lng2):
    lat1, lng1, lat2, lng2 = map(math.radians, (lat1, lng1, lat2, lng2))
    a = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))
