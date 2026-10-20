"""
Proof-of-work checks for staff photos (Step 10).

Every before/after photo carries where and when it was taken:
  1. Camera metadata (EXIF GPS + DateTimeOriginal), read in the browser before compression and, as a fallback,
     from the uploaded file itself.
  2. Otherwise the phone's location at the moment of upload (browser geolocation; needs HTTPS on a real phone).
Then each photo is checked against the case:
  FAR             taken more than EVIDENCE_MAX_DISTANCE_M from the reported location           (red)
  BEFORE_ROUTING  an "after" photo taken before the office even received the case            (red)
  REUSED          the same picture (perceptual hash) was already used as proof on another case (red)
  SAME_AS_BEFORE  the "after" photo is the same picture as the "before" photo                  (red)
  STALE           camera time is more than EVIDENCE_MAX_AGE_DAYS before upload                  (amber)
  NO_GPS          no location at all                                                           (amber)
  NO_SITE         the report itself has no pin, so distance can't be checked                  (info)

Red flags don't block submission (the field can be wrong for honest reasons: GPS drift under a roof,
a phone with location off). They block a one-click approval: the validator must write why they approve anyway,
and that override is recorded against their name.

Honest limitation (say this at the defense): metadata can be edited by a determined person. These checks
catch the common shortcuts (old photo, photo from the office, same photo for many cases), and every approval
has a named validator who is accountable for it.
"""
import json
import math
from datetime import datetime, timedelta
from decimal import Decimal

from django.conf import settings
from django.utils import timezone

MAX_DISTANCE_M = getattr(settings, "EVIDENCE_MAX_DISTANCE_M", 150)
MAX_AGE_DAYS = getattr(settings, "EVIDENCE_MAX_AGE_DAYS", 3)
REUSE_HAMMING = 6  # out of 64 bits

RED = {"far", "before_routing", "reused", "same_as_before"}
FLAGS = {
    "far": ("red", "Kinuha malayo sa lugar ng report"),
    "before_routing": ("red", "Kinuha bago pa natanggap ng opisina ang kaso"),
    "reused": ("red", "Parehong litrato na ginamit sa ibang kaso"),
    "same_as_before": ("red", "Ang 'after' ay kapareho ng 'before' na litrato"),
    "stale": ("amber", f"Lumang litrato (higit {MAX_AGE_DAYS} araw bago i-upload)"),
    "no_gps": ("amber", "Walang lokasyon ang litrato"),
    "no_site": ("info", "Walang pin ang report; hindi masukat ang layo"),
}


def haversine_m(lat1, lng1, lat2, lng2):
    r = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


# ---------------------------------------------------------------- reading metadata
def _ratio(v):
    try:
        return float(v)
    except TypeError:
        n, d = v
        return n / d if d else 0.0


def read_exif(fileobj):
    """(lat, lng, taken_at) from the file's own EXIF, if it still has any (compressed uploads usually don't)."""
    try:
        from PIL import Image
        from PIL.ExifTags import IFD

        pos = fileobj.tell()
        im = Image.open(fileobj)
        exif = im.getexif()
        gps = exif.get_ifd(IFD.GPSInfo) or {}
        sub = exif.get_ifd(IFD.Exif) or {}
        fileobj.seek(pos)
        lat = lng = taken = None
        if gps.get(2) and gps.get(4):
            lat = sum(_ratio(x) / 60 ** i for i, x in enumerate(gps[2])) * (-1 if gps.get(1) == "S" else 1)
            lng = sum(_ratio(x) / 60 ** i for i, x in enumerate(gps[4])) * (-1 if gps.get(3) == "W" else 1)
        raw = sub.get(36867) or exif.get(306)  # DateTimeOriginal, DateTime
        if raw:
            taken = timezone.make_aware(datetime.strptime(str(raw).strip("\x00"), "%Y:%m:%d %H:%M:%S"))
        return lat, lng, taken
    except Exception:  # noqa: BLE001 — unreadable metadata is simply "no metadata"
        try:
            fileobj.seek(0)
        except Exception:  # noqa: BLE001
            pass
        return None, None, None


def dhash(fileobj):
    """64-bit difference hash: survives re-compression and resizing, changes when the scene changes."""
    try:
        from PIL import Image

        pos = fileobj.tell()
        im = Image.open(fileobj).convert("L").resize((9, 8))
        fileobj.seek(pos)
        px = list(im.getdata())
        bits = 0
        for row in range(8):
            for col in range(8):
                bits = (bits << 1) | (px[row * 9 + col] > px[row * 9 + col + 1])
        return f"{bits:016x}"
    except Exception:  # noqa: BLE001
        return ""


def hamming(a, b):
    return bin(int(a, 16) ^ int(b, 16)).count("1") if a and b else 64


def parse_meta(raw):
    """Client metadata: JSON list aligned with the uploaded files (or a single dict)."""
    if not raw:
        return []
    if isinstance(raw, (list, tuple)) and raw and isinstance(raw[0], str):
        raw = raw[0]
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except ValueError:
        return []
    return data if isinstance(data, list) else [data]


def _dt(v):
    if not v:
        return None
    try:
        d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        return d if timezone.is_aware(d) else timezone.make_aware(d)
    except ValueError:
        return None


def _num(v):
    try:
        f = float(v)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def build_metadata(fileobj, meta):
    """Combine the file's EXIF with what the browser sent. Camera data wins over phone location."""
    meta = meta or {}
    f_lat, f_lng, f_time = read_exif(fileobj)
    lat, lng = _num(meta.get("exif_lat")), _num(meta.get("exif_lng"))
    if lat is None and f_lat is not None:
        lat, lng = f_lat, f_lng
    out = {"phash": dhash(fileobj)}
    if lat is not None and lng is not None:
        out.update(latitude=lat, longitude=lng, gps_source="exif", gps_accuracy_m=None)
    elif _num(meta.get("device_lat")) is not None and _num(meta.get("device_lng")) is not None:
        out.update(latitude=_num(meta["device_lat"]), longitude=_num(meta["device_lng"]), gps_source="device",
                   gps_accuracy_m=_num(meta.get("device_accuracy")))
    else:
        out.update(latitude=None, longitude=None, gps_source="none", gps_accuracy_m=None)
    taken = _dt(meta.get("exif_time")) or f_time
    out.update(taken_at=taken, time_source="exif" if taken else "upload")
    return out


# ---------------------------------------------------------------- checks
def check(att, case=None, before_hashes=(), scan_reuse=True):
    """Compute distance + flags for one staff photo (does not save)."""
    from apps.concerns.models import ConcernAttachment

    concern = att.concern
    case = case or getattr(concern, "case", None)
    flags = []
    att.distance_m = None
    if att.latitude is None:
        flags.append("no_gps")
    elif concern.latitude is None:
        flags.append("no_site")
    else:
        att.distance_m = round(haversine_m(float(att.latitude), float(att.longitude),
                                           float(concern.latitude), float(concern.longitude)), 1)
        slack = min(att.gps_accuracy_m or 0, 100)  # don't punish a poor GPS fix up to 100 m
        if att.distance_m > MAX_DISTANCE_M + slack:
            flags.append("far")
    uploaded = att.uploaded_at or timezone.now()
    if att.taken_at:
        if uploaded - att.taken_at > timedelta(days=MAX_AGE_DAYS):
            flags.append("stale")
        start = case.routed_at if case else None
        if att.kind == ConcernAttachment.Kind.RESOLUTION and start and att.taken_at < start - timedelta(hours=1):
            flags.append("before_routing")
    if att.phash:
        if att.kind == ConcernAttachment.Kind.RESOLUTION and any(hamming(att.phash, h) <= REUSE_HAMMING for h in before_hashes):
            flags.append("same_as_before")
        others = [] if not scan_reuse else (ConcernAttachment.objects.exclude(concern_id=concern.id).exclude(phash="")
                  .filter(kind__in=["before", "progress", "resolution"]).exclude(pk=att.pk)
                  .values_list("phash", "concern__reference_no"))
        if scan_reuse and concern.duplicate_of_id:
            others = others.exclude(concern_id=concern.duplicate_of_id)
        for h, ref in (others.iterator() if scan_reuse else []):
            if hamming(att.phash, h) <= REUSE_HAMMING:
                flags.append("reused")
                att.caption = (att.caption or f"Kapareho ng litrato sa {ref}")[:150]
                break
    att.flags = flags
    return att


def red_flags(atts):
    return sorted({f for a in atts for f in (a.flags or []) if f in RED})


def flag_list(codes):
    return [{"code": c, "level": FLAGS[c][0], "label": FLAGS[c][1]} for c in codes if c in FLAGS]


def summary(case):
    """Evidence status for a case: used by the case page, the validator and the KPIs."""
    from apps.concerns.models import ConcernAttachment

    if case is None:
        return None
    atts = list(case.concern.attachments.all())
    before = [a for a in atts if a.kind == ConcernAttachment.Kind.BEFORE]
    after = [a for a in atts if a.kind == ConcernAttachment.Kind.RESOLUTION]
    staff = before + after + [a for a in atts if a.kind == ConcernAttachment.Kind.PROGRESS]
    located = [a for a in before + after if a.gps_source != "none" and "far" not in (a.flags or [])]
    reds = red_flags(before + after)
    return {
        "before": len(before),
        "after": len(after),
        "located": len(located),
        "has_before_after": bool(before and after),
        "red_flags": flag_list(reds),
        "amber_flags": flag_list(sorted({f for a in staff for f in (a.flags or []) if FLAGS.get(f, ("",))[0] == "amber"})),
        "verified": bool(before and after) and not reds and len(located) == len(before) + len(after),
    }


def is_verified_proof(case, atts):
    """Same rule as summary()['verified'], over a prefetched list (for KPIs)."""
    before = [a for a in atts if a.kind == "before"]
    after = [a for a in atts if a.kind == "resolution"]
    if not (before and after):
        return False
    return all(a.gps_source != "none" and not (set(a.flags or []) & RED) for a in before + after)


def to_decimal(v):
    return None if v is None else Decimal(str(round(v, 6)))
