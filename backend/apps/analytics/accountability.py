"""
Accountability (Step 10): who acted on each case and what proof they submitted.

  office_proof(...)  ─ per office: share of fixes with verified before/after proof, red-flag photos,
                       overrides by validators, reports returned, citizen "not fixed", recurrences
  people(...)        ─ per person in an office: what they did (accepted, responded, inspected, submitted,
                       validated…) and the quality of their proof. Listed by name, not ranked:
                       it's for coaching and verification, not a leaderboard.
  ledger(...)        ─ one person's actions in time order, each with the case and the photos as evidence
  watchlist(...)     ─ recent items a supervisor should look at: overrides, disputed fixes, recurrences,
                       red-flag submissions still waiting for validation
"""
from collections import defaultdict

from django.db.models import Prefetch, Q

from apps.accounts.models import User
from apps.cases.evidence import RED, flag_list, is_verified_proof
from apps.cases.models import AccomplishmentReport, Case, Department
from apps.concerns.models import Concern, ConcernAttachment

STAFF_PHOTO_KINDS = ["before", "progress", "resolution"]


def _name(u):
    return (u.get_full_name() or u.username) if u else None


def _in(field, start, end):
    return {f"{field}__gte": start, f"{field}__lt": end}


# ------------------------------------------------------------------ offices
def office_proof(start, end, dept_ids=None):
    depts = Department.objects.filter(kind=Department.Kind.INTERNAL, is_active=True)
    if dept_ids is not None:
        depts = depts.filter(id__in=dept_ids)
    depts = list(depts.order_by("name"))
    ids = [d.id for d in depts]
    cases = list(Case.objects.filter(department_id__in=ids, level=Case.Level.CITY, concern__duplicate_of__isnull=True)
                 .filter(Q(**_in("validated_at", start, end)) | Q(**_in("concern__citizen_confirmed_at", start, end)))
                 .select_related("concern").only("department_id", "concern_id", "validated_at", "concern__citizen_confirmation",
                                                  "concern__citizen_confirmed_at"))
    resolved = [k for k in cases if k.validated_at and start <= k.validated_at < end]
    rids = [k.concern_id for k in resolved]
    atts = defaultdict(list)
    for a in ConcernAttachment.objects.filter(concern_id__in=rids, kind__in=["before", "resolution"]).only(
            "concern_id", "kind", "gps_source", "flags"):
        atts[a.concern_id].append(a)
    recurred = set(Concern.objects.filter(recurrence_of_id__in=rids).values_list("recurrence_of_id", flat=True))
    reports = list(AccomplishmentReport.objects.filter(case__department_id__in=ids, **_in("submitted_at", start, end))
                   .only("case__department_id", "status", "override_reason").select_related("case"))
    red_photo = defaultdict(int)
    photos = defaultdict(int)
    for a in ConcernAttachment.objects.filter(concern__case__department_id__in=ids, kind__in=STAFF_PHOTO_KINDS,
                                              **_in("uploaded_at", start, end)).only("flags", "concern__case__department_id") \
            .values("concern__case__department_id", "flags"):
        d = a["concern__case__department_id"]
        photos[d] += 1
        red_photo[d] += bool(set(a["flags"] or []) & RED)

    rows = []
    for d in depts:
        res = [k for k in resolved if k.department_id == d.id]
        ans = [k for k in cases if k.department_id == d.id and k.concern.citizen_confirmed_at
               and start <= k.concern.citizen_confirmed_at < end]
        rep = [r for r in reports if r.case.department_id == d.id]
        if not res and not rep and not ans:
            continue
        with_ba = [k for k in res if {a.kind for a in atts[k.concern_id]} >= {"before", "resolution"}]
        proof = [k for k in res if is_verified_proof(k, atts[k.concern_id])]
        rows.append({
            "department_id": d.id, "code": d.code, "name": d.name,
            "resolved": len(res),
            "before_after": len(with_ba),
            "verified_proof": len(proof),
            "proof_rate": round(len(proof) / len(res), 4) if res else None,
            "photos": photos[d.id],
            "red_flag_photos": red_photo[d.id],
            "reports": len(rep),
            "reports_returned": sum(1 for r in rep if r.status == "returned"),
            "overrides": sum(1 for r in rep if r.status == "approved" and r.override_reason),
            "citizen_answered": len(ans),
            "citizen_fixed": sum(1 for k in ans if k.concern.citizen_confirmation == "fixed"),
            "citizen_not_fixed": sum(1 for k in ans if k.concern.citizen_confirmation == "not_fixed"),
            "recurrences": sum(1 for k in res if k.concern_id in recurred),
        })
    rows.sort(key=lambda r: (r["proof_rate"] is None, r["proof_rate"] or 0))
    return rows


# ------------------------------------------------------------------ people
ACTIONS = [
    ("accepted", "Tinanggap"), ("responded", "Unang aksyon"), ("inspected", "Inspeksyon"),
    ("submitted", "Nag-sumite ng report"), ("crew", "Kasama sa crew"), ("validated", "Nag-validate"),
    ("returned", "Nagbalik sa crew"), ("overrides", "Inaprubahan kahit may red flag"),
]


def _staff_in_scope(dept_id, division_id=None):
    qs = User.objects.filter(department_id=dept_id, is_active=True).exclude(role=User.Role.CITIZEN)
    if division_id:
        qs = qs.filter(division_id=division_id)
    return list(qs.select_related("division").order_by("last_name", "first_name"))


def people(dept, start, end, division_id=None):
    users = _staff_in_scope(dept.id, division_id)
    uid = {u.id for u in users}
    cnt = {u.id: defaultdict(int) for u in users}
    cases = Case.objects.filter(department=dept)
    for field, key in (("accepted", "accepted"), ("responded", "responded"), ("inspected", "inspected")):
        for v in cases.filter(**_in(f"{field}_at", start, end), **{f"{field}_by_id__in": uid}).values_list(f"{field}_by_id", flat=True):
            cnt[v][key] += 1
    reports = list(AccomplishmentReport.objects.filter(case__department=dept, **_in("submitted_at", start, end))
                   .prefetch_related("crew").select_related("case__concern"))
    returned_own = defaultdict(int)
    for r in reports:
        if r.submitted_by_id in uid:
            cnt[r.submitted_by_id]["submitted"] += 1
            if r.status == "returned":
                returned_own[r.submitted_by_id] += 1
        for c in r.crew.all():
            if c.id in uid and c.id != r.submitted_by_id:
                cnt[c.id]["crew"] += 1
        if r.reviewed_by_id in uid and r.reviewed_at and start <= r.reviewed_at < end:
            cnt[r.reviewed_by_id]["validated" if r.status == "approved" else "returned"] += 1
            if r.status == "approved" and r.override_reason:
                cnt[r.reviewed_by_id]["overrides"] += 1
    photos = defaultdict(lambda: [0, 0, 0])  # total, red, located
    for a in ConcernAttachment.objects.filter(uploaded_by_id__in=uid, kind__in=STAFF_PHOTO_KINDS,
                                              **_in("uploaded_at", start, end)).values("uploaded_by_id", "flags", "gps_source"):
        p = photos[a["uploaded_by_id"]]
        p[0] += 1
        p[1] += bool(set(a["flags"] or []) & RED)
        p[2] += a["gps_source"] != "none"
    disputed = defaultdict(int)
    recur = defaultdict(int)
    submitters = {r.case.concern_id: r.submitted_by_id for r in reports if r.status == "approved"}
    if submitters:
        for cid in Concern.objects.filter(pk__in=submitters, citizen_confirmation="not_fixed").values_list("id", flat=True):
            disputed[submitters[cid]] += 1
        for cid in Concern.objects.filter(recurrence_of_id__in=submitters).values_list("recurrence_of_id", flat=True):
            recur[submitters[cid]] += 1
    open_now = defaultdict(int)
    for v in cases.filter(concern__status__in=Concern.OPEN_STATUSES, assigned_to_id__in=uid).values_list("assigned_to_id", flat=True):
        open_now[v] += 1
    out = []
    for u in users:
        c, p = cnt[u.id], photos[u.id]
        total = sum(c.values())
        out.append({
            "id": u.id, "name": _name(u), "role": u.role, "role_display": u.get_role_display(),
            "division": u.division.name if u.division else None,
            "actions": {k: c.get(k, 0) for k, _ in ACTIONS}, "total_actions": total,
            "open_assigned": open_now[u.id],
            "photos": p[0], "red_flag_photos": p[1],
            "located_rate": round(p[2] / p[0], 4) if p[0] else None,
            "reports_returned": returned_own[u.id],
            "citizen_not_fixed": disputed[u.id], "recurrences": recur[u.id],
        })
    return out


def ledger(user, start, end, limit=200):
    """Everything this person did in the period, newest first, with the evidence attached to each action."""
    items = []
    cases = Case.objects.select_related("concern__barangay", "concern__subcategory", "concern__category")

    def row(at, kind, label, case, detail="", flags=(), photos=(), ok=None):
        c = case.concern
        items.append({
            "at": at, "kind": kind, "label": label, "concern_id": c.id, "reference_no": c.reference_no,
            "title": c.title, "barangay": c.barangay.name, "detail": detail[:240], "ok": ok,
            "flags": flag_list(sorted(set(flags))), "photos": list(photos),
        })

    for k in cases.filter(accepted_by=user, **_in("accepted_at", start, end)):
        row(k.accepted_at, "accepted", "Tinanggap ang kaso", k,
            f"{k.priority_level.code if k.priority_level else ''}", ok=(k.accepted_at <= k.acceptance_due_at) if k.acceptance_due_at else None)
    for k in cases.filter(responded_by=user, **_in("responded_at", start, end)):
        row(k.responded_at, "responded", "Unang aksyon", k, k.response_remarks,
            ok=(k.responded_at <= k.response_due_at) if k.response_due_at else None)
    for k in cases.filter(inspected_by=user, **_in("inspected_at", start, end)):
        row(k.inspected_at, "inspected", "Inspeksyon", k, k.inspection_findings)

    reports = AccomplishmentReport.objects.filter(Q(submitted_by=user) | Q(crew=user) | Q(reviewed_by=user)).distinct() \
        .select_related("case__concern__barangay", "submitted_by", "reviewed_by") \
        .prefetch_related(Prefetch("photos", queryset=ConcernAttachment.objects.order_by("kind")), "crew")
    for r in reports:
        photos = [{"url": a.file.url, "kind": a.kind, "distance_m": a.distance_m, "gps_source": a.gps_source,
                   "flags": flag_list(a.flags or [])} for a in r.photos.all()]
        reds = [f for a in r.photos.all() for f in (a.flags or []) if f in RED]
        if start <= r.submitted_at < end and (r.submitted_by_id == user.id or user in r.crew.all()):
            who = "Nag-sumite" if r.submitted_by_id == user.id else f"Kasama sa crew ni {_name(r.submitted_by)}"
            status = {"approved": "inaprubahan", "returned": "ibinalik", "submitted": "naghihintay ng validation"}[r.status]
            row(r.submitted_at, "report", f"Accomplishment report ({who})", r.case,
                f"{r.work_done} · {status}" + (f" · {r.review_remarks}" if r.status == "returned" and r.review_remarks else ""),
                reds, photos, ok=False if r.status == "returned" else (None if r.status == "submitted" else True))
        if r.reviewed_by_id == user.id and r.reviewed_at and start <= r.reviewed_at < end:
            if r.status == "approved":
                row(r.reviewed_at, "validated", "Nag-validate (inaprubahan)" + (" kahit may red flag" if r.override_reason else ""),
                    r.case, r.override_reason or r.review_remarks, reds, photos, ok=not r.override_reason)
            else:
                row(r.reviewed_at, "returned", "Ibinalik sa crew", r.case, r.review_remarks, reds, photos)
    items.sort(key=lambda i: i["at"], reverse=True)
    return items[:limit]


def watchlist(start, end, dept_ids=None, limit=25):
    """What a supervisor should open next."""
    out = []
    base = AccomplishmentReport.objects.select_related("case__concern__barangay", "case__department", "submitted_by",
                                                       "reviewed_by").prefetch_related("photos")
    cases = Case.objects.select_related("concern__barangay", "department")
    if dept_ids is not None:
        base = base.filter(case__department_id__in=dept_ids)
        cases = cases.filter(department_id__in=dept_ids)

    def item(kind, label, case, at, who, detail, level):
        c = case.concern
        out.append({"kind": kind, "label": label, "level": level, "at": at, "who": who, "detail": detail[:240],
                    "concern_id": c.id, "reference_no": c.reference_no, "title": c.title, "barangay": c.barangay.name,
                    "office": case.department.code if case.department else None})

    for r in base.filter(status="submitted"):
        reds = sorted({f for a in r.photos.all() for f in (a.flags or []) if f in RED})
        if reds:
            item("pending_red", "Naghihintay ng validation, may red flag", r.case, r.submitted_at, _name(r.submitted_by),
                 ", ".join(f["label"] for f in flag_list(reds)), "red")
    for r in base.filter(status="approved", **_in("reviewed_at", start, end)).exclude(override_reason=""):
        item("override", "Inaprubahan kahit may red flag", r.case, r.reviewed_at, _name(r.reviewed_by), r.override_reason, "amber")
    for k in cases.filter(concern__citizen_confirmation="not_fixed", **_in("concern__citizen_confirmed_at", start, end)):
        item("disputed", "Sabi ng nag-report: hindi pa naayos", k, k.concern.citizen_confirmed_at, "Nag-report",
             k.concern.citizen_feedback, "red")
    for c in Concern.objects.filter(recurrence_of__case__in=cases, **_in("created_at", start, end)) \
            .select_related("recurrence_of__case__department", "recurrence_of__barangay"):
        k = c.recurrence_of.case
        item("recurrence", "Bumalik ang problema matapos ayusin", k, c.created_at, None,
             f"Bagong report {c.reference_no}, {(c.created_at - c.recurrence_of.resolved_at).days if c.recurrence_of.resolved_at else '?'} araw matapos maayos",
             "amber")
    out.sort(key=lambda i: (i["level"] != "red", -i["at"].timestamp()))
    return out[:limit]
