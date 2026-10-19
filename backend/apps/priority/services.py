"""
Priority Scoring Engine (Module 4)

    P = 100 × ( wS·S + wA·A + wD·D + wT·T )

    S  severity    = min( (severity / 5) × category.severity_weight , 1 )
    A  affected    = min( ln(1 + affected) / ln(1 + AFFECTED_CAP) , 1 )   # log: 10→50 matters more than 900→940
    D  duplicates  = min( duplicate_reports / DUPLICATE_CAP , 1 )
    T  delay       = min( days_open / category.sla_days , 1 )             # 1.0 once SLA is breached

Default weights: wS=0.35, wA=0.25, wD=0.20, wT=0.20 (sum = 1.0) — override in settings.PRIORITY_SCORING.
Tiers: ≥75 critical, ≥50 high, ≥25 medium, else low.
"""
import math
from decimal import Decimal

from django.conf import settings
from django.utils import timezone

from .models import PriorityScore

DEFAULTS = {
    "WEIGHTS": {"severity": 0.35, "affected": 0.25, "duplicates": 0.20, "delay": 0.20},
    "AFFECTED_CAP": 1000,
    "DUPLICATE_CAP": 10,
    "DEFAULT_SLA_DAYS": 7,
}


def _cfg():
    cfg = {**DEFAULTS, **getattr(settings, "PRIORITY_SCORING", {})}
    cfg["WEIGHTS"] = {**DEFAULTS["WEIGHTS"], **cfg.get("WEIGHTS", {})}
    return cfg


def _q(x, places="0.0001"):
    return Decimal(str(x)).quantize(Decimal(places))


def compute_priority(concern, save=True):
    cfg = _cfg()
    w = cfg["WEIGHTS"]
    category = concern.category

    severity_weight = float(category.severity_weight) if category else 1.0
    sla_days = (category.sla_days if category else None) or cfg["DEFAULT_SLA_DAYS"]

    S = min((concern.severity / 5) * severity_weight, 1.0)
    A = min(math.log1p(max(concern.affected_count, 0)) / math.log1p(cfg["AFFECTED_CAP"]), 1.0)
    dup_count = concern.duplicates.count() if concern.pk else 0
    D = min(dup_count / cfg["DUPLICATE_CAP"], 1.0)

    end = concern.resolved_at or timezone.now()
    days_open = max((end - concern.created_at).total_seconds() / 86400, 0) if concern.created_at else 0
    T = min(days_open / sla_days, 1.0)

    total = 100 * (w["severity"] * S + w["affected"] * A + w["duplicates"] * D + w["delay"] * T)
    total = _q(min(total, 100), "0.01")

    if save:
        PriorityScore.objects.update_or_create(
            concern=concern,
            defaults=dict(
                severity_component=_q(S), affected_component=_q(A),
                duplicate_component=_q(D), delay_component=_q(T),
                duplicate_count=dup_count, days_open=_q(days_open, "0.01"), total=total,
            ),
        )
        type(concern).objects.filter(pk=concern.pk).update(priority_score=total)
        concern.priority_score = total
    return total


def recompute_open_concerns():
    """Run nightly (Celery beat) — the delay component grows every day a concern stays open."""
    from apps.concerns.models import Concern

    qs = Concern.objects.filter(status__in=Concern.OPEN_STATUSES, duplicate_of__isnull=True).select_related("category")
    n = 0
    for concern in qs.iterator():
        compute_priority(concern)
        n += 1
    return n
