"""
Office performance KPIs (Module 6).

FAIRNESS PRINCIPLE: offices do different work (3-day garbage pickup vs 20-day road repair), so no office is
judged by raw speed against another. Every rate below measures an office against ITS OWN commitments:
the ARTA-based target date, the priority-level response target, and the 1-working-day acceptance rule.

Definitions (period = [start, end)):
  received          cases routed to the office during the period
  resolved          cases validated (fix confirmed) during the period
  on_time_rate      resolved in period whose validation ≤ target date (incl. one lawful ARTA extension)
  acceptance_rate   of cases routed in period whose acceptance is decided (accepted, or deadline passed):
                    share accepted within 1 working day
  response_rate     same idea for first field action within the priority target (P1: 4 hours)
  p1_make_safe_rate P1 cases whose make-safe happened within 4 hours
  median_days       median calendar days from routing to validation (context only; not scored)
  backlog           open cases right now; overdue = past target date; aging_30 = open > 30 days
  extension_rate    share of cases routed in period that used the one ARTA extension
  escalation_rate   share of cases routed in period that escalated at least once
  reopen_rate       resolved in period that had been reopened (resolved → in progress) at least once
  returned          cases this office sent back to PACD (wrong office) — informational, not penalized

GRADE: attention = index < 75, or ≥3 missed targets, or on-time < 70%, or P1 make-safe < 70% · good = index ≥ 85 and ≤1 missed target · else watch

PERFORMANCE INDEX (0–100), published weights:
  40% on-time · 20% response · 15% acceptance · 15% backlog health (1 − overdue/open) · 10% no-reopen
Shown only when the office resolved ≥ MIN_SAMPLE cases in the period; otherwise "insufficient data".
"""
import statistics
from collections import Counter, defaultdict
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from apps.cases.models import Case, CaseNote, Department
from apps.concerns.models import Concern, StatusHistory

S = Concern.Status
OPEN = Concern.OPEN_STATUSES
MIN_SAMPLE = 5
WEIGHTS = {"on_time": .40, "response": .20, "acceptance": .15, "backlog": .15, "quality": .10}
TARGETS = {"on_time": .85, "response": .85, "acceptance": .90, "overdue_share": .20, "reopen": .05,
           "proof": .80, "not_fixed": .10, "recurrence": .10}


def _rate(num, den):
    return round(num / den, 4) if den else None


def _cases(dept_ids=None):
    qs = Case.objects.select_related("concern__category", "concern__subcategory", "concern__barangay",
                                     "priority_level", "department", "division") \
        .filter(level=Case.Level.CITY, department__kind=Department.Kind.INTERNAL,
                concern__duplicate_of__isnull=True)
    if dept_ids is not None:
        qs = qs.filter(department_id__in=dept_ids)
    return qs


def _reopened_ids(concern_ids):
    return set(StatusHistory.objects.filter(
        concern_id__in=concern_ids, from_status__in=[S.RESOLVED, S.CLOSED], to_status=S.IN_PROGRESS,
    ).values_list("concern_id", flat=True))


def quality_lookup(concern_ids):
    """
    Batched proof-of-work facts for a set of concerns (one query each):
      reopened   ─ reopened after being marked fixed (by staff or because the citizen said "not fixed")
      recurred   ─ same problem reported again at the same spot within 30 days of the fix
      proof      ─ has before + after photos, located, with no red flag (apps.cases.evidence)
      overrides  ─ approved even though the photo checks raised a red flag
    """
    from apps.cases.evidence import is_verified_proof
    from apps.cases.models import AccomplishmentReport
    from apps.concerns.models import ConcernAttachment

    ids = list(set(concern_ids))
    atts = defaultdict(list)
    for a in ConcernAttachment.objects.filter(concern_id__in=ids, kind__in=["before", "resolution"]) \
            .only("concern_id", "kind", "gps_source", "flags"):
        atts[a.concern_id].append(a)
    return {
        "reopened": _reopened_ids(ids),
        "recurred": set(Concern.objects.filter(recurrence_of_id__in=ids).values_list("recurrence_of_id", flat=True)),
        "proof": {cid for cid in ids if is_verified_proof(None, atts.get(cid, []))},
        "overrides": set(AccomplishmentReport.objects.filter(case__concern_id__in=ids, status="approved")
                         .exclude(override_reason="").values_list("case__concern_id", flat=True)),
    }


def compute(cases, start, end, now=None, q=None):
    """KPI dict for an iterable of Case objects (one office, one division, or the whole city)."""
    now = now or timezone.now()
    cases = list(cases)
    routed = [k for k in cases if k.routed_at and start <= k.routed_at < end]
    resolved = [k for k in cases if k.validated_at and start <= k.validated_at < end]
    open_now = [k for k in cases if k.concern.status in OPEN]

    on_time = [k for k in resolved if k.due_at and k.validated_at <= k.due_at]
    acc_decided = [k for k in routed if k.accepted_at or (k.acceptance_due_at and k.acceptance_due_at < now)]
    acc_ok = [k for k in acc_decided if k.accepted_at and k.acceptance_due_at and k.accepted_at <= k.acceptance_due_at]
    resp_decided = [k for k in routed if k.response_due_at and (k.responded_at or k.response_due_at < now)]
    resp_ok = [k for k in resp_decided if k.responded_at and k.responded_at <= k.response_due_at]
    p1 = [k for k in resp_decided if k.priority_level and k.priority_level.code == "P1"]
    p1_ok = [k for k in p1 if k.responded_at and k.responded_at <= k.response_due_at]
    overdue = [k for k in open_now if k.due_at and k.due_at < now]
    aging30 = [k for k in open_now if k.routed_at and now - k.routed_at > timedelta(days=30)]
    q = q if q is not None else quality_lookup([k.concern_id for k in resolved])
    rids = {k.concern_id for k in resolved}
    reopened = q["reopened"] & rids
    recurred = q["recurred"] & rids
    answered = [k for k in cases if k.concern.citizen_confirmed_at and start <= k.concern.citizen_confirmed_at < end]
    not_fixed = [k for k in answered if k.concern.citizen_confirmation == "not_fixed"]
    days = [(k.validated_at - k.routed_at).total_seconds() / 86400 for k in resolved if k.routed_at]

    out = {
        "received": len(routed),
        "resolved": len(resolved),
        "on_time": len(on_time),
        "on_time_rate": _rate(len(on_time), len(resolved)),
        "acceptance_rate": _rate(len(acc_ok), len(acc_decided)),
        "response_rate": _rate(len(resp_ok), len(resp_decided)),
        "p1_cases": len(p1),
        "p1_make_safe_rate": _rate(len(p1_ok), len(p1)),
        "median_days": round(statistics.median(days), 1) if days else None,
        "p90_days": round(statistics.quantiles(days, n=10)[-1], 1) if len(days) >= 10 else None,
        "backlog": len(open_now),
        "overdue": len(overdue),
        "aging_30": len(aging30),
        "extension_rate": _rate(sum(1 for k in routed if k.extended_at), len(routed)),
        "escalation_rate": _rate(sum(1 for k in routed if k.escalation_level), len(routed)),
        "reopen_rate": _rate(sum(1 for k in resolved if k.concern_id in reopened), len(resolved)),
        "returned": sum(1 for k in routed if k.return_count),
        # proof of work (Step 10)
        "proof_rate": _rate(len(q["proof"] & rids), len(resolved)),
        "overrides": len(q["overrides"] & rids),
        "recurrence_rate": _rate(len(recurred), len(resolved)),
        "citizen_answered": len(answered),
        "citizen_not_fixed": len(not_fixed),
        "not_fixed_rate": _rate(len(not_fixed), len(answered)),
        "quality_rate": _rate(len(reopened | recurred), len(resolved)),
    }
    out.update(_index(out))
    return out


def _index(m):
    if m["resolved"] < MIN_SAMPLE:
        return {"index": None, "grade": "insufficient", "flags": [f"Kulang ang datos (<{MIN_SAMPLE} naresolba)"]}
    backlog_health = 1 - (m["overdue"] / m["backlog"]) if m["backlog"] else 1.0
    parts = {
        "on_time": m["on_time_rate"] or 0,
        "response": m["response_rate"] if m["response_rate"] is not None else 1,
        "acceptance": m["acceptance_rate"] if m["acceptance_rate"] is not None else 1,
        "backlog": backlog_health,
        "quality": 1 - (m["quality_rate"] or 0),  # not reopened and the problem didn't come back
    }
    score = round(100 * sum(WEIGHTS[k] * v for k, v in parts.items()), 1)
    flags = []

    def below(v, target):  # compare on the displayed (whole-percent) value so flags never contradict the label
        return v is not None and round(v * 100) < round(target * 100)

    if below(m["on_time_rate"] or 0, TARGETS["on_time"]):
        flags.append(f"On-time {pct(m['on_time_rate'])} (target {pct(TARGETS['on_time'])})")
    if below(m["response_rate"], TARGETS["response"]):
        flags.append(f"Unang aksyon {pct(m['response_rate'])} (target {pct(TARGETS['response'])})")
    if m["p1_cases"] and below(m["p1_make_safe_rate"], .9):
        flags.append(f"P1 make-safe ≤4h: {pct(m['p1_make_safe_rate'])}")
    if below(m["acceptance_rate"], TARGETS["acceptance"]):
        flags.append(f"Pagtanggap ≤1 WD: {pct(m['acceptance_rate'])}")
    # Backlog flags are relative to the office's volume, so a small office with 3 stale cases isn't
    # treated like a large one with 80.
    if m["backlog"] >= 5 and m["overdue"] / m["backlog"] > TARGETS["overdue_share"] \
            and m["overdue"] >= max(5, .05 * m["received"]):
        flags.append(f"{m['overdue']} sa {m['backlog']} bukas ay overdue")
    if m["aging_30"] >= max(5, .10 * m["received"]):
        flags.append(f"{m['aging_30']} kasong bukas nang >30 araw")
    if round((m["reopen_rate"] or 0) * 100) > round(TARGETS["reopen"] * 100):
        flags.append(f"Reopened {pct(m['reopen_rate'])}")
    if below(m["proof_rate"], TARGETS["proof"]):
        flags.append(f"May patunay (before/after + lokasyon) {pct(m['proof_rate'])} (target {pct(TARGETS['proof'])})")
    if m["citizen_answered"] >= MIN_SAMPLE and round((m["not_fixed_rate"] or 0) * 100) > round(TARGETS["not_fixed"] * 100):
        flags.append(f"{m['citizen_not_fixed']} sa {m['citizen_answered']} nag-report: hindi pa naayos")
    if round((m["recurrence_rate"] or 0) * 100) > round(TARGETS["recurrence"] * 100):
        flags.append(f"Bumalik ang problema sa {pct(m['recurrence_rate'])} ng naayos (≤30 araw)")
    # Grade from both the score and how many commitments are being missed
    severe = (m["on_time_rate"] or 0) < .70 or (m["p1_cases"] >= 3 and (m["p1_make_safe_rate"] or 0) < .70)
    if score < 75 or len(flags) >= 3 or severe:
        grade = "attention"
    elif score >= 85 and len(flags) <= 1:
        grade = "good"
    else:
        grade = "watch"
    return {"index": score, "grade": grade, "flags": flags, "components": {k: round(v, 3) for k, v in parts.items()}}


def pct(v):
    return "—" if v is None else f"{round(v * 100)}%"


# ---------------- public API ----------------

def period_bounds(period, date_from=None, date_to=None, now=None):
    now = timezone.localtime(now or timezone.now())
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "this_month":
        start = today.replace(day=1)
        return start, now, "Ngayong buwan"
    if period == "last_month":
        end = today.replace(day=1)
        start = (end - timedelta(days=1)).replace(day=1)
        return start, end, start.strftime("%B %Y")
    if period == "quarter":
        q_month = 3 * ((today.month - 1) // 3) + 1
        start = today.replace(month=q_month, day=1)
        return start, now, f"Q{(today.month - 1) // 3 + 1} {today.year}"
    if period == "12m":
        return today - timedelta(days=365), now, "Huling 12 buwan"
    if period == "custom" and date_from:
        start = timezone.make_aware(timezone.datetime.combine(date_from, timezone.datetime.min.time()))
        end = timezone.make_aware(timezone.datetime.combine(date_to or now.date(), timezone.datetime.min.time())) + timedelta(days=1)
        return start, end, f"{date_from:%b %d, %Y} – {(end - timedelta(days=1)):%b %d, %Y}"
    return today - timedelta(days=90), now, "Huling 90 araw"


def scorecard(start, end, dept_ids=None):
    """One row per internal office + a city-wide row."""
    now = timezone.now()
    by_dept = defaultdict(list)
    all_cases = list(_cases(dept_ids))
    for k in all_cases:
        by_dept[k.department_id].append(k)
    depts = Department.objects.filter(kind=Department.Kind.INTERNAL, is_active=True)
    if dept_ids is not None:
        depts = depts.filter(id__in=dept_ids)
    q = quality_lookup([k.concern_id for k in all_cases if k.validated_at and start <= k.validated_at < end])
    rows = []
    for d in depts.order_by("name"):
        m = compute(by_dept.get(d.id, []), start, end, now, q)
        if m["received"] == 0 and m["resolved"] == 0 and m["backlog"] == 0:
            continue
        rows.append({"department_id": d.id, "code": d.code, "name": d.name, **m})
    rows.sort(key=lambda r: (r["index"] is None, -(r["index"] or 0)))
    for i, r in enumerate(rows, 1):
        r["rank"] = i if r["index"] is not None else None
    city = compute(all_cases, start, end, now, q)
    return rows, city


def monthly_trend(cases, months=12, now=None):
    """On-time rate, received and resolved per calendar month (oldest → newest)."""
    now = timezone.localtime(now or timezone.now())
    first = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    starts = []
    for _ in range(months):
        starts.append(first)
        first = (first - timedelta(days=1)).replace(day=1)
    starts.reverse()
    cases = list(cases)
    out = []
    for i, s in enumerate(starts):
        e = starts[i + 1] if i + 1 < len(starts) else now
        resolved = [k for k in cases if k.validated_at and s <= k.validated_at < e]
        on_time = sum(1 for k in resolved if k.due_at and k.validated_at <= k.due_at)
        out.append({
            "month": s.strftime("%Y-%m"), "label": s.strftime("%b %Y"),
            "received": sum(1 for k in cases if k.routed_at and s <= k.routed_at < e),
            "resolved": len(resolved),
            "on_time_rate": _rate(on_time, len(resolved)),
        })
    return out


def office_detail(dept, start, end):
    now = timezone.now()
    cases = list(_cases([dept.id]))
    q = quality_lookup([k.concern_id for k in cases if k.validated_at and start <= k.validated_at < end])
    m = compute(cases, start, end, now, q)
    divisions = []
    by_div = defaultdict(list)
    for k in cases:
        by_div[k.division_id].append(k)
    for div in dept.divisions.all():
        dm = compute(by_div.get(div.id, []), start, end, now, q)
        if dm["received"] or dm["resolved"] or dm["backlog"]:
            divisions.append({"id": div.id, "name": div.name, **{k: dm[k] for k in (
                "received", "resolved", "on_time_rate", "response_rate", "median_days", "backlog", "overdue", "aging_30",
                "proof_rate")}})
    open_now = [k for k in cases if k.concern.status in OPEN]
    buckets = [("0–7 araw", 0, 7), ("8–14", 8, 14), ("15–30", 15, 30), ("31–60", 31, 60), ("61–90", 61, 90), (">90", 91, 10**6)]
    aging = []
    for label, lo, hi in buckets:
        n = sum(1 for k in open_now if k.routed_at and lo <= (now - k.routed_at).days <= hi)
        aging.append({"bucket": label, "count": n})
    period_cases = [k for k in cases if k.routed_at and start <= k.routed_at < end]
    issues = Counter((k.concern.subcategory.name if k.concern.subcategory else k.concern.category.name) for k in period_cases)
    worst = sorted((k for k in open_now if k.due_at and k.due_at < now), key=lambda k: k.due_at)[:10]
    city_cases = list(_cases())
    staff_load = Counter((k.assigned_to.get_full_name() or k.assigned_to.username) for k in open_now if k.assigned_to)
    return {
        "department": {"id": dept.id, "code": dept.code, "name": dept.name},
        "kpis": m,
        "divisions": divisions,
        "aging": aging,
        "top_issues": [{"name": n, "count": c} for n, c in issues.most_common(8)],
        "trend": monthly_trend(cases),
        "city_trend": monthly_trend(city_cases),
        "oldest_overdue": [{
            "id": k.concern_id, "reference_no": k.concern.reference_no, "title": k.concern.title,
            "barangay": k.concern.barangay.name, "priority": k.priority_level.code if k.priority_level else None,
            "due_at": k.due_at, "days_overdue": (now - k.due_at).days, "escalation_level": k.escalation_level,
            "stage": k.stage,
        } for k in worst],
        "workload": [{"name": n, "open": c} for n, c in staff_load.most_common()],
    }
