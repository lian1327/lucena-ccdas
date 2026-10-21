"""Domain services for concerns. Views stay thin; workflow logic lives here."""
import math
import re
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.priority.services import compute_priority

from .models import Concern, StatusHistory

EARTH_RADIUS_M = 6_371_000


def haversine_m(lat1, lng1, lat2, lng2):
    lat1, lng1, lat2, lng2 = map(lambda v: math.radians(float(v)), (lat1, lng1, lat2, lng2))
    a = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def find_master_duplicate(concern):
    """
    Earliest open, non-duplicate concern of the same category within DUPLICATE_RADIUS_M
    and DUPLICATE_WINDOW_DAYS. Uses a bounding-box prefilter in SQL, exact haversine in Python.
    """
    cfg = getattr(settings, "DUPLICATE_DETECTION", {})
    radius_m = cfg.get("RADIUS_M", 100)
    window_days = cfg.get("WINDOW_DAYS", 14)

    if not (concern.category_id and concern.latitude is not None and concern.longitude is not None):
        return None

    dlat = radius_m / 111_320
    dlng = radius_m / (111_320 * max(math.cos(math.radians(float(concern.latitude))), 0.01))
    candidates = (
        Concern.objects.filter(
            category_id=concern.category_id,
            status__in=Concern.OPEN_STATUSES,
            duplicate_of__isnull=True,
            created_at__gte=timezone.now() - timedelta(days=window_days),
            latitude__range=(float(concern.latitude) - dlat, float(concern.latitude) + dlat),
            longitude__range=(float(concern.longitude) - dlng, float(concern.longitude) + dlng),
        )
        .exclude(pk=concern.pk)
        .order_by("created_at")
    )
    for c in candidates:
        if haversine_m(concern.latitude, concern.longitude, c.latitude, c.longitude) <= radius_m:
            return c
    return None


def tag_purok(concern, user=None):
    """Pin → purok (inside the chosen barangay). Without a pin, keep the purok the reporter/encoder picked."""
    from apps.geo.locate import find_purok

    fields = []
    if concern.latitude is not None:
        p, _ = find_purok(concern.latitude, concern.longitude, concern.barangay_id)
        if p:
            concern.purok, concern.purok_source = p, "pin"
            fields = ["purok", "purok_source"]
    if not fields and concern.purok_id and not concern.purok_source:
        concern.purok_source = "staff" if (user and user.is_authenticated and user.role != "citizen") else "reporter"
        fields = ["purok_source"]
    if fields:
        concern.save(update_fields=fields)


RECURRENCE_RADIUS_M = 75
RECURRENCE_WINDOW_DAYS = 30


def find_recurrence(concern, now=None):
    """
    A concern marked fixed (resolved/closed) within the last 30 days, same problem type, within 75 m.
    This is the "fake fix" signal: the pothole that was "patched" and is back three weeks later.
    """
    if not (concern.category_id and concern.latitude is not None and concern.longitude is not None):
        return None
    now = now or concern.created_at or timezone.now()
    dlat = RECURRENCE_RADIUS_M / 111_320
    dlng = RECURRENCE_RADIUS_M / (111_320 * max(math.cos(math.radians(float(concern.latitude))), 0.01))
    qs = Concern.objects.filter(
        category_id=concern.category_id, status__in=Concern.DONE_STATUSES, duplicate_of__isnull=True,
        resolved_at__gte=now - timedelta(days=RECURRENCE_WINDOW_DAYS), resolved_at__lte=now,
        latitude__range=(float(concern.latitude) - dlat, float(concern.latitude) + dlat),
        longitude__range=(float(concern.longitude) - dlng, float(concern.longitude) + dlng),
    ).exclude(pk=concern.pk).exclude(status=S.REJECTED).order_by("-resolved_at")
    if concern.subcategory_id:
        qs = qs.filter(subcategory_id=concern.subcategory_id)
    for c in qs:
        if haversine_m(concern.latitude, concern.longitude, c.latitude, c.longitude) <= RECURRENCE_RADIUS_M:
            return c
    return None


@transaction.atomic
def on_concern_submitted(concern, user=None):
    """Called right after a concern is created (any channel)."""
    StatusHistory.objects.create(
        concern=concern, from_status="", to_status=concern.status,
        remarks="Concern received.", changed_by=user if (user and user.is_authenticated) else None,
    )

    from apps.classifier.services import apply_ai

    apply_ai(concern)  # Module 3: suggestion always stored; category auto-filled only if none chosen and confident
    tag_purok(concern, user)
    master = find_master_duplicate(concern)
    if master:
        concern.duplicate_of = master
        concern.save(update_fields=["duplicate_of"])
        compute_priority(master)  # more reports → master's priority rises
    else:
        fixed = find_recurrence(concern)
        if fixed:  # "fixed" last month, broken again: counts against the office that fixed it
            concern.recurrence_of = fixed
            concern.save(update_fields=["recurrence_of"])

    # Hook for Module 3 (AI classification) — will be replaced by a Celery task:
    # classify_concern.delay(concern.pk)

    compute_priority(concern)
    if concern.danger_now and not master:
        from apps.notifications.models import StaffAlert
        from apps.notifications.services import alert, pacd_staff

        alert(pacd_staff(), StaffAlert.Kind.DANGER, concern, f"May panganib ngayon: {concern.reference_no}",
              f"{concern.title} · Brgy. {concern.barangay.name}", urgent=True)
    return master


S = Concern.Status

# Allowed transitions. Anything else is rejected, so the audit trail always tells a coherent story.
TRANSITIONS = {
    S.SUBMITTED: {S.UNDER_REVIEW, S.ASSIGNED, S.REJECTED},
    S.UNDER_REVIEW: {S.ASSIGNED, S.REJECTED},
    S.ASSIGNED: {S.IN_PROGRESS, S.RESOLVED, S.REJECTED},
    S.IN_PROGRESS: {S.RESOLVED, S.ASSIGNED},
    S.RESOLVED: {S.CLOSED, S.IN_PROGRESS},  # in_progress = reopen
    S.CLOSED: set(),
    S.REJECTED: {S.UNDER_REVIEW},  # reconsider
}


class InvalidTransition(Exception):
    pass


def can_transition(old, new):
    return new in TRANSITIONS.get(old, set())


@transaction.atomic
def change_status(concern, new_status, user=None, remarks="", is_public=True, enforce=True, cascade=True):
    """
    Single entry point for every status transition.
    cascade=True: linked duplicate reports follow the master, so every citizen who reported the
    same problem sees the same progress on their own reference number.
    """
    old = concern.status
    if old == new_status:
        return concern
    if enforce and not can_transition(old, new_status):
        raise InvalidTransition(f"Cannot move from '{old}' to '{new_status}'.")

    concern.status = new_status
    now = timezone.now()
    fields = ["status", "updated_at"]
    if new_status == S.UNDER_REVIEW and not concern.acknowledged_at:
        concern.acknowledged_at = now
        fields.append("acknowledged_at")
    if new_status in Concern.DONE_STATUSES and not concern.resolved_at:
        concern.resolved_at = now
        fields.append("resolved_at")
    if new_status in Concern.OPEN_STATUSES and concern.resolved_at:  # reopened
        concern.resolved_at = None
        fields.append("resolved_at")
    concern.save(update_fields=fields)
    StatusHistory.objects.create(
        concern=concern, from_status=old, to_status=new_status,
        remarks=remarks, is_public=is_public, changed_by=user,
    )
    compute_priority(concern)

    if cascade:
        note = f"Kasama sa report {concern.reference_no}. " + (remarks if is_public else "")
        for dup in concern.duplicates.exclude(status__in=[S.REJECTED]).exclude(status=new_status):
            change_status(dup, new_status, user=user, remarks=note.strip(),
                          is_public=is_public, enforce=False, cascade=False)
    return concern


_WORD = re.compile(r"[a-zñ]{3,}")
_STOP = {"ang", "mga", "may", "sa", "na", "ng", "at", "po", "kami", "namin", "dito", "the", "and", "lang", "pa", "din",
         "rin", "yung", "iyong", "for", "ito", "nang", "kasi", "kapag", "para", "wala", "walang", "naman", "sila", "tapat",
         "malapit", "sira", "sirang", "kanto", "harap", "likod", "brgy", "barangay", "st", "rd", "road", "street"}


def _tokens(text):
    return {w for w in _WORD.findall((text or "").lower()) if w not in _STOP}


def similar_reports(concern, limit=5):
    """
    "Posibleng kapareho" for PACD triage: open originals in the same barangay from the last 14 days that may be the
    same problem even when auto-linking couldn't decide (no pin, or a different category picked by the citizen).
    Score: same category +3, same sub-type +2, within 100 m +3 (300 m +1), shared words up to +4, same day +1.
    The system only suggests; a person decides whether to link.
    """
    if concern.duplicate_of_id:
        return []
    since = concern.created_at - timedelta(days=14)
    qs = (Concern.objects.filter(barangay_id=concern.barangay_id, duplicate_of__isnull=True, created_at__gte=since,
                                 created_at__lte=concern.created_at + timedelta(days=14), status__in=Concern.OPEN_STATUSES)
          .exclude(pk=concern.pk).select_related("category", "subcategory")
          .order_by("-created_at")[:200])
    place = _tokens(concern.barangay.name)
    mine = _tokens(f"{concern.title} {concern.description} {concern.location_description}") - place
    out = []
    for c in qs:
        score, why = 0.0, []
        if concern.category_id and c.category_id == concern.category_id:
            score += 3
            why.append("parehong kategorya")
        if concern.subcategory_id and c.subcategory_id == concern.subcategory_id:
            score += 2
            why.append("parehong uri")
        dist = None
        if None not in (concern.latitude, concern.longitude, c.latitude, c.longitude):
            dist = round(haversine_m(concern.latitude, concern.longitude, c.latitude, c.longitude))
            if dist <= 100:
                score += 3
                why.append(f"{dist} m ang layo")
            elif dist <= 300:
                score += 1
                why.append(f"{dist} m ang layo")
            elif dist > 1000:
                score -= 3
        theirs = _tokens(f"{c.title} {c.description} {c.location_description}") - place
        shared = mine & theirs
        if shared:
            j = len(shared) / max(1, len(mine | theirs))
            score += min(4, 10 * j)
            if j >= .1:
                why.append("magkatulad na salita: " + ", ".join(sorted(shared)[:4]))
        if abs((c.created_at - concern.created_at).total_seconds()) < 86400:
            score += 1
        if score >= 4:
            out.append({"id": c.id, "reference_no": c.reference_no, "title": c.title, "status": c.status,
                        "created_at": c.created_at, "category": c.category.name if c.category else None,
                        "distance_m": dist, "score": round(score, 1), "reasons": why,
                        "reporters": 1 + c.duplicates.count()})
    out.sort(key=lambda x: -x["score"])
    return out[:limit]
