"""Use the active model on a new report, and measure how often PACD agreed with it."""
from collections import Counter, defaultdict

from django.db.models.functions import TruncMonth

from . import pipeline


def apply_ai(concern, save=True):
    """
    Classify a new report from its description. The suggestion is always stored (ai_*). The category itself is
    only filled in when the citizen didn't choose one AND the model is confident (≥ ML_AUTO_ASSIGN_THRESHOLD).
    PACD verifies every report either way, so the AI never has the final word.
    """
    from apps.concerns.models import Category, Concern, Subcategory

    try:
        res = pipeline.classify(concern.description)
    except Exception:  # noqa: BLE001 — a broken model must never block a citizen's report
        return None
    if not res:
        return None
    cats = {c.code: c for c in Category.objects.filter(code__in=[t["category"] for t in res["top"]])}
    concern.ai_category = cats.get(res["category"])
    concern.ai_subcategory = Subcategory.objects.filter(code=res["subcategory"]).first() if res["subcategory"] else None
    concern.ai_confidence = res["confidence"]
    concern.ai_top = res["top"]
    concern.ai_model_id = pipeline.active_artifact()[0].id
    fields = ["ai_category", "ai_subcategory", "ai_confidence", "ai_top", "ai_model"]
    if not concern.category_id and res["auto"] and concern.ai_category:
        concern.category = concern.ai_category
        concern.subcategory = concern.ai_subcategory
        concern.category_source = Concern.CategorySource.ML
        fields += ["category", "subcategory", "category_source"]
    if save and concern.pk:
        concern.save(update_fields=fields)
    return res


def live_stats(months=12):
    """
    Agreement between the AI's suggestion and the category PACD confirmed, on real submissions.
    This is the honest production metric: it only counts reports the model saw before any human labelled them.
    """
    from apps.concerns.models import Concern

    qs = Concern.objects.filter(is_verified=True, ai_category__isnull=False, category__isnull=False, duplicate_of__isnull=True)
    rows = list(qs.annotate(m=TruncMonth("created_at")).values("m", "ai_category__code", "category__code",
                                                                "ai_subcategory__code", "subcategory__code",
                                                                "ai_confidence", "category_source"))
    by_month = defaultdict(lambda: [0, 0])
    by_cat = defaultdict(lambda: [0, 0])
    confusions = Counter()
    auto = [0, 0]
    sub_ok = sub_n = 0
    for r in rows:
        ok = r["ai_category__code"] == r["category__code"]
        k = r["m"].strftime("%Y-%m")
        by_month[k][0] += ok
        by_month[k][1] += 1
        by_cat[r["category__code"]][0] += ok
        by_cat[r["category__code"]][1] += 1
        if not ok:
            confusions[(r["category__code"], r["ai_category__code"])] += 1
        if (r["ai_confidence"] or 0) >= pipeline.AUTO_THRESHOLD:
            auto[0] += ok
            auto[1] += 1
        if ok and r["subcategory__code"]:
            sub_n += 1
            sub_ok += r["ai_subcategory__code"] == r["subcategory__code"]
    n = len(rows)
    return {
        "n": n,
        "agreement": round(sum(v[0] for v in by_month.values()) / n, 4) if n else None,
        "sub_agreement": round(sub_ok / sub_n, 4) if sub_n else None,
        "auto_eligible": auto[1], "auto_agreement": round(auto[0] / auto[1], 4) if auto[1] else None,
        "by_month": [{"month": k, "n": v[1], "agreement": round(v[0] / v[1], 4)} for k, v in sorted(by_month.items())][-months:],
        "by_category": [{"code": k, "n": v[1], "agreement": round(v[0] / v[1], 4)} for k, v in sorted(by_cat.items())],
        "top_confusions": [{"actual": a, "predicted": p, "count": c} for (a, p), c in confusions.most_common(8)],
    }
