"""
Report screening (Step 17). Signals that help the PACD decide what to look at first. Nothing here rejects a
report: only a person does, after looking (and an office, after going to the site).

Design rule: flag only what is strong evidence. A photo with no camera data is normal (Facebook, Messenger,
and phone privacy settings strip it), so it is never flagged.

Photo signals (citizen photos)
  c_reused   red    same photo as a report about a DIFFERENT place or problem
  c_shared   info   same photo as a nearby report of the same problem (a shared group-chat photo is normal)
  c_far      amber  the photo's own GPS is more than 1 km from the pin
  c_old      amber  the photo's own date is more than 30 days before the report
  c_live     good   taken with "Kunan ngayon", phone location within 300 m of the pin
Reporter signals (the report)
  repeat_unfounded  amber  this mobile/email had 3+ reports closed as unfounded in the last 90 days
  burst             amber  4+ reports from the same network in one barangay within an hour
"""
import hashlib
import hmac
from datetime import timedelta

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

FAR_M = 1000
LIVE_NEAR_M = 300
OLD_DAYS = 30
SHARED_NEAR_M = 300
REPEAT_DAYS, REPEAT_COUNT = 90, 3
BURST_MINUTES, BURST_COUNT = 60, 4

FLAGS = {
    "c_reused": ("red", "Parehong litrato sa report ng ibang lugar/problema"),
    "c_shared": ("info", "Parehong litrato ng kalapit na report (karaniwang ibinahagi)"),
    "c_far": ("amber", "Ayon sa GPS ng litrato, higit 1 km mula sa pin"),
    "c_old": ("amber", "Ayon sa petsa ng litrato, higit 30 araw bago ang report"),
    "c_live": ("good", "Kinunan ngayon sa mismong lugar"),
    "repeat_unfounded": ("amber", "3+ report ng numerong ito ang walang natagpuan (90 araw)"),
    "burst": ("amber", "Maraming report mula sa iisang network sa loob ng 1 oras"),
}


def flag_list(codes):
    return [{"code": c, "level": FLAGS[c][0], "label": FLAGS[c][1]} for c in codes if c in FLAGS]


def _hash(value):
    if not value:
        return ""
    return hmac.new(settings.SECRET_KEY.encode(), str(value).encode(), hashlib.sha256).hexdigest()[:32]


def reporter_key(concern):
    """Same person → same key, without storing a readable list of 'bad numbers'."""
    from apps.notifications.sms import normalize_ph_mobile

    if concern.is_anonymous:
        return ""
    if concern.reporter_id:
        return _hash(f"u:{concern.reporter_id}")
    mobile = normalize_ph_mobile(concern.reporter_contact)
    if mobile:
        return _hash(f"m:{mobile}")
    if concern.reporter_email:
        return _hash(f"e:{concern.reporter_email.strip().lower()}")
    return ""


def client_ip(request):
    if request is None:
        return ""
    fwd = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return fwd.split(",")[0].strip() if fwd else request.META.get("REMOTE_ADDR", "")


def ip_hash(request):
    return _hash(f"ip:{client_ip(request)}") if request is not None else ""


# ---------------------------------------------------------------- photos

def save_citizen_photos(concern, images, metas=(), user=None):
    """Store report photos with what the browser read before compressing them, then check each one."""
    from apps.cases import evidence
    from apps.concerns.models import ConcernAttachment

    metas = list(metas or [])
    saved = []
    for i, f in enumerate(images):
        meta = metas[i] if i < len(metas) and isinstance(metas[i], dict) else {}
        m = evidence.build_metadata(f, meta)
        att = ConcernAttachment(
            concern=concern, file=f, uploaded_by=user, kind=ConcernAttachment.Kind.REPORT,
            latitude=evidence.to_decimal(m["latitude"]), longitude=evidence.to_decimal(m["longitude"]),
            gps_source=m["gps_source"], gps_accuracy_m=m["gps_accuracy_m"],
            taken_at=m["taken_at"], time_source=m["time_source"], phash=m["phash"],
        )
        att.uploaded_at = timezone.now()
        check_photo(att, concern, live=bool(meta.get("live")))
        att.save()
        saved.append(att)
    return saved


def check_photo(att, concern, live=False, now=None):
    from apps.cases.evidence import REUSE_HAMMING, hamming, haversine_m
    from apps.concerns.models import ConcernAttachment

    now = now or timezone.now()
    flags = []
    pin = (float(concern.latitude), float(concern.longitude)) if concern.latitude is not None else None
    att.distance_m = None
    if pin and att.latitude is not None:
        att.distance_m = round(haversine_m(float(att.latitude), float(att.longitude), *pin), 1)
    # GPS from the camera itself is evidence; phone location is only meaningful for a live capture
    if att.gps_source == "exif" and att.distance_m is not None and att.distance_m > FAR_M + min(att.gps_accuracy_m or 0, 200):
        flags.append("c_far")
    if att.time_source == "exif" and att.taken_at and now - att.taken_at > timedelta(days=OLD_DAYS):
        flags.append("c_old")
    if live and att.gps_source == "device" and att.distance_m is not None and att.distance_m <= LIVE_NEAR_M:
        flags.append("c_live")
    if att.phash:
        others = (ConcernAttachment.objects.exclude(concern_id=concern.id).exclude(phash="")
                  .filter(uploaded_at__gte=now - timedelta(days=365))  # bounded: last year of photos
                  .select_related("concern").only("phash", "concern__id", "concern__category_id",
                                                  "concern__latitude", "concern__longitude", "concern__duplicate_of_id"))
        for o in others.iterator():
            if hamming(att.phash, o.phash) > REUSE_HAMMING:
                continue
            oc = o.concern
            mine = concern.duplicate_of_id or concern.id   # the master of each report's group
            theirs = oc.duplicate_of_id or oc.id
            same_group = mine == theirs
            near = (pin and oc.latitude is not None
                    and haversine_m(float(oc.latitude), float(oc.longitude), *pin) <= SHARED_NEAR_M)
            if same_group or (near and oc.category_id == concern.category_id):
                flags.append("c_shared")
            else:
                flags.append("c_reused")
            break
    att.flags = flags
    return att


# ---------------------------------------------------------------- the report

def assess(concern, now=None):
    """Recompute the report's screening flags (photo summary + reporter signals). Called at submission."""
    from apps.concerns.models import Concern

    now = now or timezone.now()
    flags = set()
    for a in concern.attachments.filter(kind="report"):
        flags.update(f for f in (a.flags or []) if f in ("c_reused", "c_far", "c_old", "c_live"))
    if concern.reporter_key:
        unfounded = (Concern.objects.filter(reporter_key=concern.reporter_key, rejection_kind="unfounded",
                                            history__to_status="rejected",
                                            history__created_at__gte=now - timedelta(days=REPEAT_DAYS))
                     .exclude(pk=concern.pk).values("pk").distinct().count())
        if unfounded >= REPEAT_COUNT:
            flags.add("repeat_unfounded")
    if concern.submit_ip_hash:
        recent = Concern.objects.filter(
            submit_ip_hash=concern.submit_ip_hash, barangay_id=concern.barangay_id,
            created_at__gte=(concern.created_at or now) - timedelta(minutes=BURST_MINUTES),
        ).count()
        if recent >= BURST_COUNT:
            flags.add("burst")
    order = list(FLAGS)
    concern.review_flags = sorted(flags, key=order.index)
    concern.save(update_fields=["review_flags"])
    return concern.review_flags


def report_card(since=None):
    """For the study: how often reports are unfounded, and whether flagged reports were unfounded more often."""
    from apps.concerns.models import Concern

    qs = Concern.objects.filter(is_synthetic=False, duplicate_of__isnull=True)
    if since:
        qs = qs.filter(created_at__gte=since)
    decided = qs.filter(Q(status__in=Concern.DONE_STATUSES) | Q(status=Concern.Status.REJECTED))
    out = {"decided": decided.count(), "unfounded": decided.filter(rejection_kind="unfounded").count(), "by_flag": {}}
    for code in FLAGS:
        with_flag = [c for c in decided.only("review_flags", "rejection_kind") if code in (c.review_flags or [])]
        n = len(with_flag)
        u = sum(1 for c in with_flag if c.rejection_kind == "unfounded")
        out["by_flag"][code] = {"reports": n, "unfounded": u, "unfounded_rate": round(u / n, 3) if n else None}
    out["unfounded_rate"] = round(out["unfounded"] / out["decided"], 3) if out["decided"] else None
    return out
