"""
Executive Decision Support (Module 7) + AI Insights (Module 8) — Step 11.

Everything here counts PROBLEMS, not reports: verified, non-duplicate, non-rejected concerns. A pothole reported by
six people is one problem; the six reporters show up separately as "reports" (a measure of how many people it hurt).

  overview(month)  ─ the Mayor's monthly picture:
      totals, category change vs last month, barangay × issue matrix, top barangays per issue,
      insights (plain-language findings with the numbers behind them), next-month forecast with a range and
      its measured accuracy, and per-office resource recommendations.

Forecast method (say this at the defense): for each issue, four simple methods are back-tested on the last 4 months
(one step ahead each time) and the most accurate one is used:
  naive (same as last month) · 3-month average · simple exponential smoothing · Holt (level + trend)
A seasonal factor from the same month last year is applied once ≥ 24 months of data exist. The range is
±1.28 × the standard deviation of that method's past errors (≈ 80% band). The panel shows the chosen method's error
next to the naive guess, so nobody has to take the forecast on faith. Months before data collection began are dropped.
"""
import math
import re
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from django.utils import timezone

from apps.accounts.models import User
from apps.cases.models import Case, Department
from apps.concerns.models import Category, Concern
from apps.geo.models import Barangay

S = Concern.Status
ALPHA, BETA = 0.5, 0.2
MIN_INSIGHT = 5          # don't talk about changes on tiny numbers
SPIKE_RATIO = 1.5        # +50%
CITY_CHANGE = 0.20       # ±20% city-wide


# ---------------------------------------------------------------- months
def month_start(d):
    d = timezone.localtime(d)
    return d.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def add_months(d, n):
    y, m = divmod(d.month - 1 + n, 12)
    return d.replace(year=d.year + y, month=m + 1, day=1)


def parse_month(value, now=None):
    """'YYYY-MM' → (start, end, is_partial). Default: the last complete month."""
    now = timezone.localtime(now or timezone.now())
    this = month_start(now)
    if value and re.fullmatch(r"\d{4}-\d{2}", value):
        y, m = map(int, value.split("-"))
        start = timezone.make_aware(datetime(y, m, 1), timezone.get_current_timezone())
        start = min(start, this)
    else:
        start = add_months(this, -1)
    end = add_months(start, 1)
    partial = end > now
    return start, min(end, now), partial


def label(d):
    return d.strftime("%B %Y")


# ---------------------------------------------------------------- forecasting
def holt(series, alpha=ALPHA, beta=BETA):
    """One-step-ahead fitted values and the next forecast. series: list of counts (oldest → newest)."""
    if not series:
        return [], 0.0
    if len(series) == 1:
        return [series[0]], float(series[0])
    level, trend = float(series[0]), float(series[1] - series[0])
    fitted = [float(series[0])]
    for y in series[1:]:
        pred = level + trend
        fitted.append(pred)
        new_level = alpha * y + (1 - alpha) * (level + trend)
        trend = beta * (new_level - level) + (1 - beta) * trend
        level = new_level
    return fitted, max(0.0, level + trend)


def ses(series, alpha=0.4):
    level = float(series[0])
    fitted = [level]
    for y in series[1:]:
        fitted.append(level)
        level = alpha * y + (1 - alpha) * level
    return fitted, max(0.0, level)


def naive(series):
    return [float(series[0])] + [float(y) for y in series[:-1]], float(series[-1])


def mean3(series):
    fitted = [float(series[0])] + [statistics.mean(series[max(0, i - 3):i]) for i in range(1, len(series))]
    return fitted, statistics.mean(series[-3:])


METHODS = {"naive": ("Same as last month", naive), "mean3": ("3-month average", mean3),
           "ses": ("Exponential smoothing", ses), "holt": ("Holt (level + trend)", holt)}


def seasonal_factor(series, months_back=12):
    """Same month last year ÷ last year's average (needs ≥ 24 points), else 1."""
    if len(series) < 24:
        return 1.0
    last_year = series[-24:-12]
    avg = statistics.mean(last_year) or 1
    return max(.3, min(3.0, series[-12] / avg))  # month being forecast, one year earlier


def backtest(series, fn, k=4):
    """Mean absolute % error of one-step-ahead predictions over the last k months (skips zero months)."""
    errs = []
    for i in range(max(3, len(series) - k), len(series)):
        if series[i] == 0:
            continue
        _, pred = fn(series[:i])
        errs.append(abs(series[i] - pred) / series[i])
    return round(statistics.mean(errs), 3) if errs else None


def forecast(series):
    """Pick the method with the lowest back-test error; return estimate, 80% range and the errors."""
    series = [int(x) for x in series]
    if len(series) < 4:
        v = float(series[-1]) if series else 0.0
        return {"estimate": v, "low": 0, "high": math.ceil(v * 1.5 + 1), "method": "naive", "method_label": METHODS["naive"][0],
                "backtest_mape": None, "naive_mape": None}
    scores = {k: backtest(series, fn) for k, (_, fn) in METHODS.items()}
    best = min((k for k in scores if scores[k] is not None), key=lambda k: scores[k], default="naive")
    fitted, nxt = METHODS[best][1](series)
    nxt *= seasonal_factor(series)
    errors = [y - f for y, f in zip(series[1:], fitted[1:])]
    sd = statistics.pstdev(errors) if len(errors) >= 3 else max(1.0, nxt * .3)
    return {"estimate": round(nxt, 1), "low": max(0, math.floor(nxt - 1.28 * sd)), "high": math.ceil(nxt + 1.28 * sd),
            "method": best, "method_label": METHODS[best][0],
            "backtest_mape": scores[best], "naive_mape": scores["naive"]}


def _trim(series, months, first_data):
    """Drop months that ended before, or began before, data collection started (they'd look like a fake surge)."""
    if not first_data:
        return series
    keep = [i for i, m in enumerate(months) if m >= month_start(first_data) and not (m < first_data - timedelta(days=1))]
    i0 = keep[0] if keep else 0
    if months[i0] < first_data - timedelta(days=1):
        i0 += 1
    return series[i0:]


# ---------------------------------------------------------------- data
def _problems(start, end):
    return Concern.objects.filter(
        is_verified=True, duplicate_of__isnull=True, created_at__gte=start, created_at__lt=end,
    ).exclude(status=S.REJECTED)


def _pct_change(cur, prev):
    if prev == 0:
        return None if cur == 0 else 1.0
    return round((cur - prev) / prev, 3)


def _fmt_change(ch):
    return f"{'+' if ch >= 0 else ''}{round(ch * 100)}%"


def overview(month_value=None, now=None):
    now = now or timezone.now()
    start, end, partial = parse_month(month_value, now)
    span = end - start
    prev_start = add_months(start, -1)
    prev_end = prev_start + span if partial else start  # compare like-for-like days when the month isn't over
    hist_start = add_months(start, -11)

    cats = list(Category.objects.filter(is_active=True).order_by("id"))
    cat_by_id = {c.id: c for c in cats}
    brgys = {b.id: b for b in Barangay.objects.all()}

    rows = list(_problems(hist_start, end).values("id", "created_at", "barangay_id", "category_id", "status"))
    cur = [r for r in rows if r["created_at"] >= start]
    prev = [r for r in rows if prev_start <= r["created_at"] < prev_end]
    prev_full = [r for r in rows if prev_start <= r["created_at"] < start]
    # reports = every person who reported (originals + linked duplicates) this month
    reports = Concern.objects.filter(created_at__gte=start, created_at__lt=end).exclude(status=S.REJECTED).count()

    # ---- monthly series per category (12 months ending with the selected month)
    months = [add_months(hist_start, i) for i in range(12)]
    series = {c.id: [0] * 12 for c in cats}
    for r in rows:
        i = (timezone.localtime(r["created_at"]).year - months[0].year) * 12 + timezone.localtime(r["created_at"]).month - months[0].month
        if 0 <= i < 12 and r["category_id"] in series:
            series[r["category_id"]][i] += 1
    if partial:  # scale the running month up so the forecast isn't dragged down by an unfinished month
        days = (add_months(start, 1) - start).days
        frac = max(span.total_seconds() / 86400 / days, .1)
        for s in series.values():
            s[-1] = round(s[-1] / frac)

    # ---- categories
    cur_c, prev_c = Counter(r["category_id"] for r in cur), Counter(r["category_id"] for r in prev)
    avg3 = {cid: statistics.mean(series[cid][-4:-1]) if len(series[cid]) >= 4 else 0 for cid in series}
    categories = []
    for c in cats:
        n, p = cur_c.get(c.id, 0), prev_c.get(c.id, 0)
        categories.append({"code": c.code, "name": c.name_fil or c.name, "name_en": c.name, "count": n, "prev": p,
                           "change": _pct_change(n, p), "avg3": round(avg3[c.id], 1)})

    # ---- barangay × issue matrix
    cell = Counter((r["barangay_id"], r["category_id"]) for r in cur)
    cell_prev = Counter((r["barangay_id"], r["category_id"]) for r in prev)
    b_tot, b_prev = Counter(r["barangay_id"] for r in cur), Counter(r["barangay_id"] for r in prev)
    open_now = Counter(Concern.objects.filter(is_verified=True, duplicate_of__isnull=True, status__in=Concern.OPEN_STATUSES)
                       .values_list("barangay_id", flat=True))
    overdue_now = Counter(Case.objects.filter(concern__status__in=Concern.OPEN_STATUSES, concern__duplicate_of__isnull=True,
                                              due_at__lt=now).values_list("concern__barangay_id", flat=True))
    barangays = []
    for bid, b in brgys.items():
        n = b_tot.get(bid, 0)
        top = max(cats, key=lambda c: cell.get((bid, c.id), 0)) if n else None
        barangays.append({
            "id": bid, "name": b.name, "population": b.population or None,
            "count": n, "prev": b_prev.get(bid, 0), "change": _pct_change(n, b_prev.get(bid, 0)),
            "per_1000": round(n / b.population * 1000, 2) if b.population else None,
            "open_now": open_now.get(bid, 0), "overdue_now": overdue_now.get(bid, 0),
            "top_issue": (top.name_fil or top.name) if top else None,
            "cells": {c.code: cell.get((bid, c.id), 0) for c in cats},
        })
    barangays.sort(key=lambda x: (-x["count"], x["name"]))
    for i, b in enumerate(barangays, 1):
        b["rank"] = i if b["count"] else None

    rankings = []
    for c in cats:
        tot = cur_c.get(c.id, 0)
        top = sorted(((cell.get((bid, c.id), 0), bid) for bid in brgys), reverse=True)[:5]
        rankings.append({"code": c.code, "name": c.name_fil or c.name, "total": tot, "top": [
            {"barangay": brgys[bid].name, "barangay_id": bid, "count": n, "prev": cell_prev.get((bid, c.id), 0),
             "share": round(n / tot, 3) if tot else None}
            for n, bid in top if n]})

    # ---- forecast (next month after the selected one)
    nxt = add_months(start, 1)
    first = Concern.objects.filter(is_verified=True).order_by("created_at").values_list("created_at", flat=True).first()
    first = timezone.localtime(first) if first else None
    trimmed_from = None
    fc = []
    model_err, naive_err = [], []
    for c in cats:
        s_use = _trim(series[c.id], months, first)
        trimmed_from = 12 - len(s_use)
        f = forecast(s_use)
        if f["backtest_mape"] is not None:
            model_err.append(f["backtest_mape"])
            naive_err.append(f["naive_mape"])
        fc.append({"code": c.code, "name": c.name_fil or c.name, **f, "series": series[c.id]})
    forecast_block = {
        "month": nxt.strftime("%Y-%m"), "label": label(nxt),
        "months": [m.strftime("%Y-%m") for m in months], "month_labels": [m.strftime("%b %Y") for m in months],
        "categories": fc,
        "method": "Per issue, the most accurate of: same as last month, 3-month average, exponential smoothing, "
                  "Holt (level + trend), back-tested on the last 4 months; ±80% band from that method's past errors"
                  + (f". First {trimmed_from} month(s) excluded (data collection had not fully started)." if trimmed_from else "."),
        "backtest_mape": round(statistics.mean(model_err), 3) if model_err else None,
        "naive_mape": round(statistics.mean(naive_err), 3) if naive_err else None,
    }

    totals = {
        "problems": len(cur), "prev": len(prev), "change": _pct_change(len(cur), len(prev)),
        "reports": reports,
        "resolved": Concern.objects.filter(duplicate_of__isnull=True, is_verified=True, resolved_at__gte=start, resolved_at__lt=end)
        .exclude(status=S.REJECTED).count(),
        "open_now": sum(open_now.values()), "overdue_now": sum(overdue_now.values()),
        "barangays_reporting": sum(1 for b in barangays if b["count"]),
    }
    out = {
        "month": start.strftime("%Y-%m"), "label": label(start), "partial": partial,
        "start": start, "end": end, "prev_label": label(prev_start) + (" (parehong bilang ng araw)" if partial else ""),
        "totals": totals, "categories": categories, "barangays": barangays, "rankings": rankings,
        "forecast": forecast_block,
        "resources": resources(start, end, now, nxt),
    }
    out["insights"] = insights(out, cats, brgys, cell, cell_prev, series, prev_full)
    return out


# ---------------------------------------------------------------- resources
def resources(start, end, now, nxt):
    """
    Per internal office: is current capacity enough for next month's expected cases + clearing the backlog in 3 months?
    capacity  = average cases resolved per month over the last 3 months
    demand    = forecast of cases the office will receive next month + backlog ÷ 3
    gap       = demand − capacity → extra crew-equivalents = gap ÷ (cases per field staff per month)
    These are planning estimates for discussion, not staffing orders.
    """
    out = []
    since = add_months(start, -11)
    for d in Department.objects.filter(kind=Department.Kind.INTERNAL, is_active=True).order_by("name"):
        cases = list(Case.objects.filter(department=d, level=Case.Level.CITY, concern__duplicate_of__isnull=True)
                     .filter(routed_at__gte=since).values("routed_at", "validated_at", "concern__barangay__name",
                                                           "concern__status", "due_at"))
        recv = [0] * 12
        done = [0] * 12
        for k in cases:
            for field, arr in (("routed_at", recv), ("validated_at", done)):
                t = k[field]
                if t and since <= t < end:
                    t = timezone.localtime(t)
                    i = (t.year - since.year) * 12 + t.month - since.month
                    if 0 <= i < 12:
                        arr[i] += 1
        backlog = Case.objects.filter(department=d, level=Case.Level.CITY, concern__duplicate_of__isnull=True,
                                      concern__status__in=Concern.OPEN_STATUSES)
        n_backlog = backlog.count()
        n_overdue = backlog.filter(due_at__lt=now).count()
        if not any(recv) and not n_backlog:
            continue
        first = next((i for i, v in enumerate(recv) if v), 0)
        f = forecast(recv[first + 1:] if first < 10 else recv)  # skip the partial first month of data
        capacity = round(statistics.mean(done[-3:]), 1)
        crew = User.objects.filter(department=d, is_active=True, role=User.Role.DEPT_STAFF).count()
        per_crew = round(capacity / crew, 1) if crew else None
        demand = round(f["estimate"] + n_backlog / 3, 1)
        gap = round(demand - capacity, 1)
        extra = math.ceil(gap / per_crew) if (gap >= max(2.0, .10 * capacity) and per_crew) else 0
        recent = Counter(k["concern__barangay__name"] for k in cases if k["routed_at"] >= add_months(start, -2))
        focus = [{"barangay": n, "count": c} for n, c in recent.most_common(3)]
        if gap >= max(2.0, .10 * capacity):
            status = "short"
            text = (f"Inaasahang ~{round(f['estimate'])} bagong kaso sa {label(nxt)} at {n_backlog} pa ang bukas "
                    f"({n_overdue} overdue). Kaya ng opisina ang ~{capacity} kaso/buwan, kaya kulang ng ~{round(gap)} kaso/buwan"
                    + (f": katumbas ng {extra} dagdag na field staff, o ilipat ang tauhan pansamantala." if extra
                       else ". Unahin ang overdue at ang mga barangay na nasa ibaba."))
            text_en = (f"About {round(f['estimate'])} new cases expected in {label(nxt)} with {n_backlog} still open "
                       f"({n_overdue} overdue). Capacity is ~{capacity}/month, a shortfall of ~{round(gap)}/month"
                       + (f", about {extra} more field staff (or a temporary reassignment)." if extra else "."))
        else:
            status = "ok"
            text = f"Sapat ang kapasidad (~{capacity}/buwan) para sa inaasahang ~{round(f['estimate'])} kaso at sa {n_backlog} bukas."
            text_en = f"Capacity (~{capacity}/month) covers the expected ~{round(f['estimate'])} cases and the {n_backlog} open."
        out.append({
            "department_id": d.id, "code": d.code, "name": d.name, "forecast": f, "capacity": capacity, "backlog": n_backlog,
            "overdue": n_overdue, "field_staff": crew, "per_staff": per_crew, "demand": demand, "gap": gap,
            "extra_staff": extra, "status": status, "focus_barangays": focus, "text": text, "text_en": text_en,
        })
    out.sort(key=lambda r: -r["gap"])
    return out


# ---------------------------------------------------------------- insights
def insights(o, cats, brgys, cell, cell_prev, series, prev_full):
    """Plain-language findings, each with the numbers behind it. Threshold rules keep noise out."""
    found = []
    month, prev_label = o["label"], o["prev_label"]

    def add(kind, level, text, text_en, value=None, barangay_id=None, category=None):
        found.append({"kind": kind, "level": level, "text": text, "text_en": text_en, "value": value,
                      "barangay_id": barangay_id, "category": category})

    t = o["totals"]
    if t["change"] is not None and max(t["problems"], t["prev"]) >= 20 and abs(t["change"]) >= .15:
        up = t["change"] > 0
        add("city", "amber" if up else "info",
            f"{'Tumaas' if up else 'Bumaba'} ng {abs(round(t['change'] * 100))}% ang kabuuang problema "
            f"({t['prev']} → {t['problems']}) kumpara sa {prev_label}.",
            f"Total problems {'rose' if up else 'fell'} {abs(round(t['change'] * 100))}% ({t['prev']} → {t['problems']}) vs {prev_label}.",
            t["change"])
    for c in o["categories"]:
        if c["change"] is None or max(c["count"], c["prev"]) < 10 or abs(c["change"]) < CITY_CHANGE:
            continue
        up = c["change"] > 0
        add("category", "amber" if up else "info",
            f"{'Tumaas' if up else 'Bumaba'} ng {abs(round(c['change'] * 100))}% ang reklamo sa {c['name']} "
            f"sa buong lungsod ({c['prev']} → {c['count']}).",
            f"{c['name_en']} complaints {'increased' if up else 'decreased'} by {abs(round(c['change'] * 100))}% "
            f"city-wide ({c['prev']} → {c['count']}) compared to last month.",
            c["change"], category=c["code"])
    cat_by_id = {c.id: c for c in cats}
    for (bid, cid), n in cell.items():
        p = cell_prev.get((bid, cid), 0)
        if n < MIN_INSIGHT or n - p < 3 or (p and n / p < SPIKE_RATIO):
            continue
        c, b = cat_by_id[cid], brgys[bid]
        ch = _pct_change(n, p)
        add("spike", "red" if n >= 2 * max(p, 1) and n >= 8 else "amber",
            f"{c.name_fil or c.name}: tumaas ng {_fmt_change(ch)} sa Brgy. {b.name} ({p} → {n}) kumpara sa {prev_label}.",
            f"{c.name} complaints increased by {round(ch * 100)}% in Barangay {b.name} ({p} → {n}) compared to last month.",
            ch, bid, c.code)
    for r in o["rankings"]:
        if r["total"] >= 15 and r["top"] and r["top"][0]["count"] >= 5 and (r["top"][0]["share"] or 0) >= .25:
            top = r["top"][0]
            add("concentration", "amber",
                f"{round(top['share'] * 100)}% ng reklamo sa {r['name']} ay mula sa Brgy. {top['barangay']} "
                f"({top['count']} sa {r['total']}). Isang lugar ang dapat tutukan.",
                f"{round(top['share'] * 100)}% of {r['name']} complaints came from Barangay {top['barangay']} "
                f"({top['count']} of {r['total']}): one area to focus on.",
                top["share"], top["barangay_id"], r["code"])
    # persistent: same barangay in the top 3 for an issue in each of the last 3 months
    for c in cats:
        s = series[c.id]
        if sum(s[-3:]) < 15:
            continue
        tops = []
        for k in range(3):
            m0 = add_months(o["start"], -k)
            m1 = add_months(m0, 1)
            cnt = Counter(_problems(m0, m1).filter(category=c).values_list("barangay_id", flat=True))
            tops.append({b for b, _ in cnt.most_common(3)})
        for bid in set.intersection(*tops):
            add("persistent", "red",
                f"Brgy. {brgys[bid].name} ay nasa top 3 ng {c.name_fil or c.name} sa loob ng 3 sunod-sunod na buwan. "
                f"Paulit-ulit ito: kailangan ng pangmatagalang solusyon, hindi lang tapal.",
                f"Barangay {brgys[bid].name} has been in the top 3 for {c.name} for 3 months in a row: "
                f"a recurring problem that needs a lasting fix, not another patch.",
                None, bid, c.code)
    for r in [r for r in o["resources"] if r["status"] == "short" and r["gap"] >= 5][:3]:
        if True:
            add("capacity", "red" if r["overdue"] >= 20 else "amber",
                f"{r['code']}: kulang ang kapasidad ng ~{round(r['gap'])} kaso/buwan ({r['overdue']} overdue ngayon).",
                f"{r['code']}: capacity short by ~{round(r['gap'])} cases/month ({r['overdue']} overdue now).",
                r["gap"])
    rank = {"red": 0, "amber": 1, "info": 2}
    found.sort(key=lambda i: (rank[i["level"]], -abs(i["value"] or 0)))
    return found[:12]
