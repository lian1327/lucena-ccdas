"""
Proof-of-work layer for the synthetic data (Step 10). Runs automatically at the end of generate_synthetic_data,
or on its own over existing synthetic cases:

    python manage.py generate_proof_data            # (re)build before/after photos, reports, confirmations, recurrences
    python manage.py generate_proof_data --seed 7

For every synthetic case where work was reported done it adds:
  • a BEFORE photo (at inspection) and metadata on the AFTER photo: where/when taken, GPS source, perceptual hash
  • an accomplishment report: work done, crew (+ job-order workers), materials, time on site, reviewer
  • realistic problems, more often in slower offices: missing before photo, no GPS, photo taken far from the pin,
    an old photo, the same photo reused on two cases; validators approving anyway write an override reason
  • citizen answers to "Naayos ba talaga?" (mostly yes; "not fixed" reopens the case and it is re-done later)
  • recurrence links: the same problem reported again at the same spot within 30 days of the "fix"
Everything stays flagged is_synthetic via the parent concern and is removed by generate_synthetic_data --purge.
"""
import contextlib
import math
import random
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.cases import evidence
from apps.cases.models import AccomplishmentReport, Case, CaseNote
from apps.concerns.models import Concern, ConcernAttachment, StatusHistory
from apps.concerns.services import find_recurrence
from apps.concerns.synthetic import corpus as C

S = Concern.Status
# chance per completed case: (no before photo, no GPS, far from site, stale photo, reused photo)
QUALITY = {
    "CEO": (.10, .14, .06, .05, .03), "BPLO": (.07, .10, .04, .04, .02), "GSO": (.04, .05, .03, .03, .02),
    "CADMIN": (.03, .04, .02, .02, .01), "POSO": (.03, .04, .02, .02, .01), "CVO": (.03, .04, .02, .02, .01),
    "CENRO": (.02, .03, .02, .02, .01), "CTMO": (.02, .03, .02, .02, .01), "CDRRMO": (.02, .03, .01, .01, .0),
    "_brgy": (.12, .18, .05, .06, .02),
}
FAMILY = {"road_damage": "road", "drainage": "drain", "solid_waste": "waste", "streetlight": "light"}
MATERIALS = {
    "road": [("Cold mix asphalt", 2, 8, "sako"), ("Graba", 1, 3, "m³"), ("Semento", 2, 10, "sako")],
    "drain": [("Sako (para sa basura)", 5, 20, "pcs"), ("Grating / rehas", 1, 2, "pcs")],
    "waste": [("Garbage bags", 10, 40, "pcs"), ("Biyahe ng truck", 1, 3, "trip")],
    "light": [("LED lamp 100W", 1, 2, "pcs"), ("Photocell", 1, 1, "pcs"), ("Kable #12", 5, 30, "m")],
    "other": [("Barricade tape", 1, 2, "roll"), ("Signage", 1, 2, "pcs")],
}
EQUIPMENT = {"road": "Plate compactor, dump truck", "drain": "Pala, kalaykay, declogging pump", "waste": "Garbage compactor truck",
             "light": "Boom truck, safety harness", "other": "Service vehicle"}
OVERRIDES = [
    "Personal kong ininspeksyon ang lugar; mahina ang GPS sa lugar dahil sa mga gusali.",
    "Na-verify sa site visit kasama ang kagawad; naka-off ang location ng cellphone ng crew.",
    "Tumawag ako sa nag-report at kinumpirma niyang naayos na; lumang cellphone ang gamit ng crew.",
    "Kinunan ng ibang anggulo; kasama ko ang crew noong araw na iyon.",
]
NOT_FIXED = {"road": ["May butas pa rin sa gitna ng kalsada.", "Tinapalan pero lumubog ulit."],
             "drain": ["Bumara ulit pagkaraan ng isang araw.", "Baha pa rin kapag umuulan."],
             "light": ["Patay pa rin ang ilaw sa gabi.", "Isang gabi lang umilaw."],
             "waste": ["Hindi pa nakuha ang basura sa dulo ng kalye.", "Kalahati lang ang hinakot."],
             "other": ["Kalahati lang ang inayos.", "Walang dumating sa lugar namin."]}
FIXED_FEEDBACK = ["Salamat po!", "Mabilis ang aksyon, salamat.", "", "", "Ayos na po, maraming salamat."]


@contextlib.contextmanager
def historical(*fields):
    saved = []
    for model, name in fields:
        f = model._meta.get_field(name)
        saved.append((f, f.auto_now, f.auto_now_add))
        f.auto_now = f.auto_now_add = False
    try:
        yield
    finally:
        for f, a, b in saved:
            f.auto_now, f.auto_now_add = a, b


def offset(lat, lng, meters, rng):
    ang = rng.uniform(0, 2 * math.pi)
    dlat = meters * math.cos(ang) / 111_320
    dlng = meters * math.sin(ang) / (111_320 * max(math.cos(math.radians(lat)), .01))
    return lat + dlat, lng + dlng


class Command(BaseCommand):
    help = "Add before/after evidence, accomplishment reports, citizen confirmations and recurrences to synthetic cases."

    def add_arguments(self, p):
        p.add_argument("--seed", type=int, default=2026)

    def handle(self, *a, **o):
        from apps.notifications.services import muted

        with muted():  # synthetic history must never text real numbers or fill the outbox
            return self._handle(*a, **o)

    def _handle(self, *a, **o):
        self.rng = random.Random(o["seed"] + 10)
        self.now = timezone.now()
        self._images()
        cases = list(Case.objects.filter(concern__is_synthetic=True, concern__duplicate_of__isnull=True,
                                         work_completed_at__isnull=False)
                     .select_related("concern__category", "concern__subcategory", "department", "work_completed_by",
                                     "inspected_by", "validated_by", "assigned_to", "division")
                     .order_by("work_completed_at"))
        self.stdout.write(f"  proof of work for {len(cases)} completed cases…")
        AccomplishmentReport.objects.filter(case__concern__is_synthetic=True).delete()
        ConcernAttachment.objects.filter(concern__is_synthetic=True, kind="before").delete()
        Concern.objects.filter(is_synthetic=True).update(citizen_confirmation="", citizen_confirmed_at=None,
                                                         citizen_feedback="", recurrence_of=None)
        self.crews = {}
        for u in User.objects.filter(is_active=True, department__isnull=False).exclude(role__in=["office_desk", "mayor", "city_admin"]):
            self.crews.setdefault(u.department_id, []).append(u)
        stats = {"reports": 0, "red": 0, "overrides": 0, "confirmed": 0, "not_fixed": 0, "recurrences": 0}
        recent_after = {}  # dept -> list of after phashes (for deliberate reuse)
        with historical((AccomplishmentReport, "submitted_at"), (ConcernAttachment, "uploaded_at"),
                        (StatusHistory, "created_at"), (CaseNote, "created_at")), transaction.atomic():
            for i, case in enumerate(cases):
                self._case(case, stats, recent_after)
                if (i + 1) % 400 == 0:
                    self.stdout.write(f"    … {i + 1}/{len(cases)}")
            stats["recurrences"] = self._recurrences()
        self.stdout.write(self.style.SUCCESS(
            f"Proof data: {stats['reports']} accomplishment reports, {stats['red']} with red-flag photos "
            f"({stats['overrides']} approved with an override reason), {stats['confirmed']} citizen confirmations "
            f"({stats['not_fixed']} 'not fixed' → reopened), {stats['recurrences']} recurrences."))

    # ---------------------------------------------------------------- images
    def _images(self):
        from PIL import Image, ImageDraw

        import io

        from django.core.files.base import ContentFile
        from django.core.files.storage import default_storage

        self.img = {}
        for fam in ("road", "drain", "waste", "light", "other"):
            for phase in ("before", "after"):
                names = []
                for v in range(3):
                    name = f"synthetic/proof/{fam}_{phase}_{v}.jpg"
                    if not default_storage.exists(name):  # local media/ or Cloudflare R2 in production
                        im = Image.new("RGB", (640, 480), (120 + 20 * v, 150, 185) if fam == "light" and phase == "after" else (170 - 10 * v, 175, 180))
                        d = ImageDraw.Draw(im)
                        d.rectangle([0, 300, 640, 480], fill=(95 + 8 * v, 95, 100))  # ground/road
                        if fam == "road":
                            if phase == "before":
                                d.ellipse([230, 340, 410, 420], fill=(40, 35, 30))
                            else:
                                d.rectangle([220, 335, 420, 425], fill=(55, 55, 60))
                        elif fam == "drain":
                            d.rectangle([60, 360, 580, 400], fill=(70, 60, 50) if phase == "before" else (60, 90, 120))
                            if phase == "before":
                                for k in range(12):
                                    d.ellipse([80 + 40 * k, 350, 110 + 40 * k, 380], fill=(150, 120, 60))
                        elif fam == "waste":
                            if phase == "before":
                                for k in range(9):
                                    d.ellipse([200 + 25 * k % 220, 290 + 12 * k % 60, 260 + 25 * k % 220, 350 + 12 * k % 60],
                                              fill=(60 + 15 * k, 70, 40))
                        elif fam == "light":
                            d.rectangle([310, 80, 322, 300], fill=(60, 60, 60))
                            d.ellipse([290, 60, 345, 100], fill=(255, 240, 150) if phase == "after" else (50, 50, 50))
                        else:
                            d.rectangle([250, 220, 390, 300], fill=(200, 60, 40) if phase == "before" else (80, 150, 90))
                        d.text((16, 16), f"SYNTHETIC {phase.upper()} · {fam}", fill=(255, 255, 255))
                        buf = io.BytesIO()
                        im.save(buf, "JPEG", quality=70)
                        default_storage.save(name, ContentFile(buf.getvalue()))
                    names.append(name)
                self.img[(fam, phase)] = names

    # ---------------------------------------------------------------- per case
    def _hash(self):
        return f"{self.rng.getrandbits(64):016x}"

    def _photo(self, case, kind, at, who, q, report=None, phash=None):
        rng, c = self.rng, case.concern
        no_gps, far, stale = rng.random() < q[1], rng.random() < q[2], rng.random() < q[3]
        att = ConcernAttachment(concern=c, kind=kind, uploaded_by=who, uploaded_at=at, report=report,
                                phash=phash or self._hash())
        fam = FAMILY.get(c.category.code, "other")
        att.file = rng.choice(self.img[(fam, "before" if kind == "before" else "after")])
        if not no_gps:
            base = (float(c.latitude), float(c.longitude)) if c.latitude is not None else \
                (float(c.barangay.center_lat), float(c.barangay.center_lng)) if c.barangay.center_lat else None
            if base:
                lat, lng = offset(*base, rng.uniform(400, 1800) if far else abs(rng.gauss(0, 25)) + 3, rng)
                att.latitude, att.longitude = evidence.to_decimal(lat), evidence.to_decimal(lng)
                if rng.random() < .65:
                    att.gps_source = "exif"
                else:
                    att.gps_source, att.gps_accuracy_m = "device", round(rng.uniform(5, 40), 1)
        if att.gps_source == "exif" or rng.random() < .5:
            att.time_source = "exif"
            att.taken_at = at - (timedelta(days=rng.uniform(4, 15)) if stale else timedelta(minutes=rng.uniform(2, 50)))
        evidence.check(att, case, scan_reuse=False)
        return att

    def _case(self, case, stats, recent_after):
        rng = self.rng
        c = case.concern
        dept = case.department
        q = QUALITY.get(dept.code if dept and case.level == "city" else "_brgy", QUALITY["_brgy"])
        if case.level == "external":
            return
        doer = case.work_completed_by or case.assigned_to
        fam = FAMILY.get(c.category.code, "other")
        t_done = case.work_completed_at
        t_start = max(case.inspected_at or t_done - timedelta(hours=6), t_done - timedelta(hours=rng.uniform(1, 7)))

        assign_note = case.notes.filter(body__startswith="Itinalaga").first()
        if assign_note and assign_note.author_id:  # the chief who assigned the crew, not PACD who routed
            Case.objects.filter(pk=case.pk).update(assigned_by=assign_note.author_id)
        notes = list(case.notes.filter(body__startswith="Returned to field").order_by("created_at"))
        reports = []
        # a returned first attempt (the generator's 7% "sent back once")
        if notes:
            rr = AccomplishmentReport(case=case, submitted_by=doer, submitted_at=notes[0].created_at - timedelta(hours=rng.uniform(1, 10)),
                                      work_done=case.completion_remarks or "Natapos ang trabaho.",
                                      started_at=t_start - timedelta(days=1), finished_at=notes[0].created_at - timedelta(hours=1),
                                      status="returned", reviewed_by=case.validated_by, reviewed_at=notes[0].created_at,
                                      review_remarks="May natitira pang trabaho.")
            rr.save()
            reports.append(rr)
        r = AccomplishmentReport(
            case=case, submitted_by=doer, submitted_at=t_done, work_done=case.completion_remarks or "Natapos ang trabaho.",
            started_at=t_start, finished_at=t_done,
            other_workers=", ".join(f"{rng.choice(C.FIRST_NAMES)} {rng.choice(C.LAST_NAMES)} (JO)" for _ in range(rng.randint(0, 3))),
            materials=[{"item": it, "qty": rng.randint(lo, hi), "unit": unit}
                       for it, lo, hi, unit in rng.sample(MATERIALS[fam], k=min(len(MATERIALS[fam]), rng.randint(1, 2)))],
            equipment=EQUIPMENT[fam],
            status="approved" if case.validated_at else "submitted",
            reviewed_by=case.validated_by, reviewed_at=case.validated_at,
        )
        r.save()
        reports.append(r)
        pool = [u for u in self.crews.get(case.department_id, []) if case.division_id is None or u.division_id in (None, case.division_id)]
        crew = {doer} if doer else set()
        crew |= set(rng.sample(pool, k=min(len(pool), rng.randint(0, 1))))
        for rep in reports:
            rep.crew.set([u for u in crew if u])

        atts = []
        if rng.random() >= q[0]:
            t_before = case.inspected_at or t_start
            atts.append(self._photo(case, "before", t_before, case.inspected_by or doer, q, report=r))
        # update the generator's after photo(s), or add one
        after = list(c.attachments.filter(kind="resolution"))
        reuse = None
        if rng.random() < q[4] and recent_after.get(case.department_id):
            reuse = rng.choice(recent_after[case.department_id][-30:])
        for k, old in enumerate(after or [None]):
            a = self._photo(case, "resolution", t_done, doer, q, report=r, phash=reuse if k == 0 else None)
            if reuse and k == 0:
                a.flags = sorted(set(a.flags) | {"reused"})
                a.caption = "Kapareho ng litrato sa ibang kaso"
            if old:
                old.delete()
            atts.append(a)
        if after and not reuse:
            recent_after.setdefault(case.department_id, []).append(atts[-1].phash)
        ConcernAttachment.objects.bulk_create(atts)
        stats["reports"] += 1
        reds = evidence.red_flags(atts)
        if reds:
            stats["red"] += 1
            if r.status == "approved":
                r.override_reason = rng.choice(OVERRIDES)
                r.save(update_fields=["override_reason"])
                CaseNote.objects.create(case=case, author=case.validated_by, created_at=case.validated_at,
                                        body=f"Approved despite photo flags ({', '.join(reds)}): {r.override_reason}")
                stats["overrides"] += 1

        # citizen confirmation
        if c.resolved_at and c.status in (S.RESOLVED, S.CLOSED) and c.reporter_contact and rng.random() < .38:
            t_ans = c.resolved_at + timedelta(hours=rng.uniform(3, 96))
            if t_ans <= self.now:
                bad = rng.random() < (.30 if reds else .05 if case.level == "barangay" else .035)
                self._confirm(case, r, t_ans, not bad, stats)

    def _confirm(self, case, report, t_ans, fixed, stats):
        rng, c = self.rng, case.concern
        c.citizen_confirmed_at = t_ans
        stats["confirmed"] += 1
        if fixed:
            c.citizen_confirmation = "fixed"
            c.citizen_feedback = rng.choice(FIXED_FEEDBACK)
            c.save(update_fields=["citizen_confirmation", "citizen_confirmed_at", "citizen_feedback"])
            return
        stats["not_fixed"] += 1
        c.citizen_confirmation = "not_fixed"
        c.citizen_feedback = rng.choice(NOT_FIXED[FAMILY.get(c.category.code, "other")])
        msg = f"Ayon sa nag-report, HINDI pa naayos: {c.citizen_feedback} Binuksan muli ang kaso."
        hist = [StatusHistory(concern=c, from_status=c.status, to_status=S.IN_PROGRESS, remarks=msg, created_at=t_ans)]
        CaseNote.objects.create(case=case, author=None, created_at=t_ans, body=f"Citizen disputed the fix. {msg}")
        redo = t_ans + timedelta(days=rng.uniform(1, 6))
        crew = list(report.crew.all())
        if redo <= self.now:
            r2 = AccomplishmentReport.objects.create(
                case=case, submitted_by=report.submitted_by, submitted_at=redo, work_done="Binalikan at tinapos ang natitirang trabaho.",
                started_at=redo - timedelta(hours=3), finished_at=redo, materials=report.materials, equipment=report.equipment,
                status="approved", reviewed_by=case.validated_by, reviewed_at=redo + timedelta(hours=4))
            r2.crew.set(crew)
            q = QUALITY.get(case.department.code if case.department and case.level == "city" else "_brgy", QUALITY["_brgy"])
            a = self._photo(case, "resolution", redo, report.submitted_by, (0, q[1] / 2, 0, 0, 0), report=r2)
            a.save()
            case.work_completed_at = redo
            case.validated_at = case.resolved_at = redo + timedelta(hours=4)
            c.resolved_at = case.validated_at
            hist.append(StatusHistory(concern=c, from_status=S.IN_PROGRESS, to_status=S.RESOLVED, created_at=case.validated_at,
                                      remarks="Binalikan ng crew at naayos na ang natitira.", changed_by=case.validated_by))
            c.status = S.RESOLVED
        else:
            case.work_completed_at = case.validated_at = case.resolved_at = None
            case.work_completed_by = case.validated_by = None
            c.status, c.resolved_at = S.IN_PROGRESS, None
        case.save()
        c.save(update_fields=["citizen_confirmation", "citizen_confirmed_at", "citizen_feedback", "status", "resolved_at"])
        StatusHistory.objects.bulk_create(hist)

    # ---------------------------------------------------------------- recurrences
    def _recurrences(self):
        n = 0
        for c in Concern.objects.filter(is_synthetic=True, duplicate_of__isnull=True, latitude__isnull=False) \
                .exclude(status=S.REJECTED).order_by("created_at"):
            prev = find_recurrence(c, now=c.created_at)
            if prev:
                Concern.objects.filter(pk=c.pk).update(recurrence_of=prev)
                n += 1
        return n
