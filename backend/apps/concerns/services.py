"""Domain services for concerns. Views stay thin; workflow logic lives here."""
import math
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


@transaction.atomic
def on_concern_submitted(concern, user=None):
    """Called right after a concern is created (any channel)."""
    StatusHistory.objects.create(
        concern=concern, from_status="", to_status=concern.status,
        remarks="Concern received.", changed_by=user if (user and user.is_authenticated) else None,
    )

    master = find_master_duplicate(concern)
    if master:
        concern.duplicate_of = master
        concern.save(update_fields=["duplicate_of"])
        compute_priority(master)  # more reports → master's priority rises

    # Hook for Module 3 (AI classification) — will be replaced by a Celery task:
    # classify_concern.delay(concern.pk)

    compute_priority(concern)
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
