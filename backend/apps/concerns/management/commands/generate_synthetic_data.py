"""
Workflow-consistent synthetic data for demos, dashboards, GIS and ML.

    python manage.py generate_synthetic_data                 # ~1,800 concerns over the last 12 months
    python manage.py generate_synthetic_data --count 3000 --months 18 --seed 7
    python manage.py generate_synthetic_data --purge         # delete ALL synthetic records

How it works: every concern is simulated through the real lifecycle — intake → verify → route → office
acceptance → first response → inspection → work → supervisor validation → close — with times drawn from
office-specific speeds, ARTA working-day deadlines, P1–P4 priority caps and holidays. The simulation is then
cut at "now", so recent concerns are open at realistic stages and older ones are resolved, overdue,
extended, escalated, endorsed (DPWH) or rejected. Patterns built in: rainy-season drainage/flooding spikes,
holiday garbage and traffic spikes, recurring hotspots per barangay, flood-prone coastal barangays,
and slower turnaround for highly technical (road) work.

All records are flagged is_synthetic=True. Requires: seed_reference_data --lucena --demo-users.
"""
import contextlib
import math
import random
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.cases import deadlines
from apps.cases.models import Case, CaseNote, Department, Endorsement, EndorsementFollowUp, PriorityLevel
from apps.cases.services import suggested_route
from apps.concerns.models import Category, Concern, ConcernAttachment, StatusHistory, Subcategory
from apps.concerns.synthetic import corpus as C
from apps.concerns.synthetic import textgen
from apps.geo import geometry
from apps.geo.locate import find_purok
from apps.geo.models import Barangay, Purok
from apps.priority.services import compute_priority

S = Concern.Status
REF_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

# Base share of reports per category (%), and month multipliers (Jan..Dec)
CATEGORY_SHARE = {
    "road_damage": 16, "streetlight": 13, "drainage": 17, "solid_waste": 20,
    "public_safety": 9, "business_permit": 4, "traffic": 15, "other": 6,
}
RAINY = [0.8, 0.8, 0.8, 0.8, 0.9, 1.2, 1.5, 1.6, 1.5, 1.4, 1.1, 0.9]
SEASON = {
    "drainage": [0.6, 0.5, 0.4, 0.4, 0.6, 1.6, 2.2, 2.4, 2.0, 1.8, 1.2, 0.8],
    "road_damage": RAINY,
    "public_safety": [0.8, 0.8, 0.8, 0.9, 1.0, 1.3, 1.5, 1.5, 1.4, 1.4, 1.0, 0.9],
    "solid_waste": [1.6, 1.0, 0.9, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.1, 1.7],
    "traffic": [1.1, 1.0, 1.0, 0.9, 1.2, 1.3, 1.0, 1.2, 1.0, 1.0, 1.2, 1.8],
    "business_permit": [2.0, 1.8, 1.0, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8, 0.9, 1.0],
    "streetlight": [1.0, 1.0, 1.0, 1.0, 1.0, 1.1, 1.2, 1.2, 1.1, 1.1, 1.0, 1.1],
    "other": [1.0] * 12,
}
FLOOD_PRONE = {"Dalahican", "Barra", "Cotta", "Ransohan", "Talao-Talao", "Market View", "Ibabang Iyam", "Isabang"}
BUSY = {"Market View": 2.2, "Ibabang Dupay": 1.8, "Gulang-Gulang": 1.7, "Isabang": 1.6, "Dalahican": 1.5,
        "Ilayang Dupay": 1.4, "Mayao Crossing": 1.3, "Cotta": 1.3}
CHANNELS = [("web", 45), ("walk_in", 15), ("facebook", 15), ("barangay", 12), ("messenger", 8), ("hotline", 4), ("8888", 1)]
DUP_RATE = {"flooding": .35, "clogged_canal": .25, "hanging_wires": .3, "pothole": .2, "uncollected": .25,
            "light_out": .15, "congestion": .2, "open_manhole": .3, "fallen_tree": .3}
# Office speed: multiplier on the ARTA period (1.0 = finishes right at the deadline on median)
OFFICE_SPEED = {"CENRO": .55, "CTMO": .6, "CDRRMO": .5, "POSO": .7, "GSO": .85, "CVO": .8, "BPLO": 1.1,
                "CEO": 1.15, "CADMIN": .9}
# Chance a case stalls (waiting for materials/budget/no action) and stays open long past its target
STALL = {"CEO": .16, "BPLO": .10, "GSO": .08, "CADMIN": .08, "POSO": .05, "CVO": .06, "CENRO": .03, "CTMO": .04, "CDRRMO": .03}
ACCEPT_HOURS = {"CENRO": 2.5, "CTMO": 2, "CDRRMO": 1.5, "GSO": 4, "CEO": 6, "BPLO": 7, "POSO": 3, "CVO": 4, "CADMIN": 3}
TIMESTAMP_FIELDS = [
    (Concern, "created_at"), (Concern, "updated_at"), (StatusHistory, "created_at"), (Case, "assigned_at"),
    (CaseNote, "created_at"), (ConcernAttachment, "uploaded_at"), (Endorsement, "endorsed_at"),
    (EndorsementFollowUp, "at"),
]


@contextlib.contextmanager
def explicit_timestamps():
    """Let us write historical created_at values (auto_now/auto_now_add would overwrite them)."""
    saved = []
    for model, name in TIMESTAMP_FIELDS:
        f = model._meta.get_field(name)
        saved.append((f, f.auto_now, f.auto_now_add))
        f.auto_now = f.auto_now_add = False
    try:
        yield
    finally:
        for f, a, b in saved:
            f.auto_now, f.auto_now_add = a, b


class Command(BaseCommand):
    help = "Generate workflow-consistent synthetic concerns (flagged is_synthetic)."

    def add_arguments(self, p):
        p.add_argument("--count", type=int, default=1800, help="Number of original (non-duplicate) concerns.")
        p.add_argument("--months", type=int, default=12)
        p.add_argument("--seed", type=int, default=2026)
        p.add_argument("--purge", action="store_true", help="Delete all synthetic records and exit.")
        p.add_argument("--keep", action="store_true", help="Don't purge previous synthetic data first.")
        p.add_argument("--improvement", type=float, default=.15,
                       help="DEMO ASSUMPTION for year-on-year views: offices were this much slower (and stalled more) "
                            "more than 12 months ago, e.g. before the system was adopted. 0 = no change between years.")

    # ------------------------------------------------------------------ setup
    def handle(self, *a, **o):
        if o["purge"]:
            n = Concern.objects.filter(is_synthetic=True).count()
            Concern.objects.filter(is_synthetic=True).delete()
            self.stdout.write(self.style.SUCCESS(f"Purged {n} synthetic concerns (with their cases, history, photos)."))
            return
        if not PriorityLevel.objects.exists() or not Barangay.objects.exists():
            raise CommandError("Run: python manage.py seed_reference_data --lucena --demo-users")

        self.rng = random.Random(o["seed"])
        self.improvement = max(0.0, o["improvement"])
        self.now = timezone.now()
        self.start = self.now - timedelta(days=round(o["months"] * 30.4))
        if not o["keep"]:
            Concern.objects.filter(is_synthetic=True).delete()

        self._load_reference()
        if not self.puroks:
            self.stdout.write(self.style.WARNING("  No purok polygons: run `python manage.py import_boundaries` first so pins land "
                                                 "inside real barangay/purok outlines."))
        self._ensure_barangay_geo()
        self._placeholder_photos()
        used_refs = set(Concern.objects.values_list("reference_no", flat=True))
        self.used_refs = used_refs

        stats = {"concerns": 0, "duplicates": 0}
        with explicit_timestamps(), transaction.atomic():
            for i in range(o["count"]):
                master = self._one_concern()
                stats["concerns"] += 1
                stats["duplicates"] += self._duplicates(master)
                if (i + 1) % 250 == 0:
                    self.stdout.write(f"  … {i + 1}/{o['count']}")
        from django.core.management import call_command
        call_command("generate_proof_data", seed=o["seed"], stdout=self.stdout)  # Step 10: before/after proof, reports
        self.stdout.write("  computing priority scores…")
        with transaction.atomic():
            for c in Concern.objects.filter(is_synthetic=True).select_related("category").iterator():
                compute_priority(c)

        qs = Concern.objects.filter(is_synthetic=True)
        self.stdout.write(self.style.SUCCESS(
            f"Created {stats['concerns']} concerns + {stats['duplicates']} linked duplicate reports "
            f"({qs.filter(status__in=Concern.OPEN_STATUSES).count()} open, "
            f"{qs.filter(status__in=Concern.DONE_STATUSES).count()} resolved/closed, "
            f"{qs.filter(status=S.REJECTED).count()} rejected)."
        ))

    def _load_reference(self):
        self.cats = {c.code: c for c in Category.objects.filter(is_active=True)}
        self.subs = {}
        for s in Subcategory.objects.filter(is_active=True).select_related("category", "default_department", "default_division"):
            self.subs.setdefault(s.category.code, []).append(s)
        self.brgys = list(Barangay.objects.all())
        # real purok polygons (import_boundaries) → points land inside the right barangay and purok
        self.puroks = {}
        for pk in Purok.objects.filter(is_zone=False):
            self.puroks.setdefault(pk.barangay_id, []).append(pk)
        self.levels = {p.code: p for p in PriorityLevel.objects.all()}
        self.ext = {d.code: d for d in Department.objects.filter(kind="external")}
        users = list(User.objects.filter(is_active=True).select_related("department", "division", "barangay"))
        self.by_role = {}
        for u in users:
            self.by_role.setdefault(u.role, []).append(u)

    def pick_user(self, role, dept=None, division=None, barangay=None):
        pool = self.by_role.get(role, [])
        if dept:
            pool = [u for u in pool if u.department_id == dept.id]
        if division:
            pool = [u for u in pool if u.division_id == division.id] or pool
        if barangay:
            pool = [u for u in pool if u.barangay_id == barangay.id]
        return self.rng.choice(pool) if pool else None

    def _ensure_barangay_geo(self):
        """
        Placeholder centers so maps work. NOT surveyed coordinates — replace with PSA/OSM centroids.
        Poblacion barangays cluster near the city center; coastal ones sit to the south.
        """
        rng = random.Random(99)
        center = (13.9373, 121.6170)
        coastal = FLOOD_PRONE - {"Isabang", "Ibabang Iyam", "Market View"}
        for b in self.brgys:
            if b.center_lat is None:
                if b.name.startswith("Barangay "):
                    lat, lng = center[0] + rng.uniform(-.008, .008), center[1] + rng.uniform(-.008, .008)
                elif b.name in coastal:
                    lat, lng = rng.uniform(13.895, 13.918), rng.uniform(121.60, 121.66)
                else:
                    ang, r = rng.uniform(0, 2 * math.pi), rng.uniform(.015, .045)
                    lat, lng = center[0] + r * math.sin(ang) * .9 + .01, center[1] + r * math.cos(ang)
                b.center_lat, b.center_lng = round(lat, 6), round(lng, 6)
            if not b.population:
                b.population = rng.randint(2500, 32000) if not b.name.startswith("Barangay ") else rng.randint(900, 4000)
            b.save(update_fields=["center_lat", "center_lng", "population"])
        # Recurring hotspots per barangay. Each belongs to a category and has a dominant problem (a canal that
        # floods, a corner with chronic illegal parking). Most of that category's reports in the barangay land
        # there, and most of those are the dominant problem.
        self.hotspots = {}
        cats = [(c, w) for c, w in CATEGORY_SHARE.items() if c in self.subs and c not in ("business_permit", "other")]
        for b in self.brgys:
            n = 4 if b.name in BUSY or b.name in FLOOD_PRONE else 2
            spots = []
            for i in range(n):
                if b.name in FLOOD_PRONE and i < 2:
                    cat, sub = "drainage", rng.choice(["flooding", "clogged_canal"])
                else:
                    cat = rng.choices([c for c, _ in cats], [w for _, w in cats])[0]
                    sub = rng.choice(self.subs[cat]).code
                lat, lng = self.point_in(b, rng)
                spots.append((lat, lng, f"{rng.choice(C.LANDMARKS)}, {rng.choice(C.STREETS)}", cat, sub))
            self.hotspots[b.id] = spots

    def _placeholder_photos(self):
        """A few small images reused by synthetic attachments (no thousands of files)."""
        from PIL import Image, ImageDraw

        folder = Path(settings.MEDIA_ROOT) / "synthetic"
        folder.mkdir(parents=True, exist_ok=True)
        self.photos = {"report": [], "resolution": [], "progress": []}
        palette = {"report": (150, 110, 80), "resolution": (80, 150, 95), "progress": (200, 160, 40)}
        for kind, color in palette.items():
            for i in range(3):
                name = f"synthetic/{kind}_{i}.jpg"
                path = Path(settings.MEDIA_ROOT) / name
                if not path.exists():
                    im = Image.new("RGB", (640, 480), tuple(max(0, v - 25 * i) for v in color))
                    d = ImageDraw.Draw(im)
                    d.rectangle([140, 300, 500, 380], fill=(110, 110, 115))
                    d.text((20, 20), f"SYNTHETIC {kind.upper()} PHOTO", fill=(255, 255, 255))
                    im.save(path, quality=70)
                self.photos[kind].append(name)

    # ------------------------------------------------------------------ helpers
    def wchoice(self, pairs):
        items, weights = zip(*pairs)
        return self.rng.choices(items, weights=weights, k=1)[0]

    def ref(self, when):
        while True:
            r = f"CCD-{when.year}-" + "".join(self.rng.choice(REF_ALPHABET) for _ in range(6))
            if r not in self.used_refs:
                self.used_refs.add(r)
                return r

    def office_time(self, t):
        """Staff actions happen on working days, 8am–5pm."""
        t = timezone.localtime(t)
        for _ in range(14):
            if t.weekday() >= 5:
                t = (t + timedelta(days=1)).replace(hour=8, minute=self.rng.randint(0, 50))
                continue
            if t.hour < 8:
                t = t.replace(hour=8, minute=self.rng.randint(0, 50))
            if t.hour >= 17:
                t = (t + timedelta(days=1)).replace(hour=8, minute=self.rng.randint(0, 50))
                continue
            break
        return t

    def working_day_end(self, t):
        """5pm on t's date, moved forward to the next working day if it falls on a weekend/holiday."""
        from apps.cases.models import Holiday
        t = timezone.localtime(t).replace(hour=17, minute=0, second=0, microsecond=0)
        hol = set(Holiday.objects.filter(date__gte=t.date(), date__lte=t.date() + timedelta(days=10)).values_list("date", flat=True))
        while t.weekday() >= 5 or t.date() in hol:
            t += timedelta(days=1)
        return t

    def hours(self, lo, hi):
        return timedelta(hours=self.rng.uniform(lo, hi))

    def lognorm(self, median, sigma=.6):
        return median * math.exp(self.rng.gauss(0, sigma))

    def random_created(self):
        """Pick a timestamp weighted by category seasonality (sampled per category later)."""
        span = (self.now - self.start).total_seconds()
        t = self.start + timedelta(seconds=self.rng.uniform(0, span))
        # citizens report mostly 6am–10pm
        t = timezone.localtime(t).replace(hour=self.wchoice([(h, 3 if 7 <= h <= 21 else 1) for h in range(6, 23)]),
                                          minute=self.rng.randint(0, 59))
        return min(t, self.now - timedelta(minutes=self.rng.randint(5, 600)))

    def pick_category(self, when):
        m = when.month - 1
        return self.wchoice([(c, CATEGORY_SHARE[c] * SEASON[c][m]) for c in CATEGORY_SHARE if c in self.cats])

    def pick_barangay(self, cat, sub=""):
        def w(b):
            base = BUSY.get(b.name, 1.0) * (0.45 if b.name.startswith("Barangay ") else 1.0)
            if b.name in FLOOD_PRONE:
                base *= {"flooding": 6.0, "clogged_canal": 3.0, "foul_canal": 2.5}.get(sub, 2.0 if cat == "drainage" else 1.0)
            if cat in ("traffic", "business_permit") and (b.name.startswith("Barangay ") or b.name == "Market View"):
                base *= 2.5
            return base
        return self.wchoice([(b, w(b)) for b in self.brgys])

    def point_in(self, b, rng=None):
        """A random point inside a residential purok of b (bigger puroks a bit more likely); old jitter if none."""
        rng = rng or self.rng
        pks = self.puroks.get(b.id)
        if not pks:
            return float(b.center_lat) + rng.uniform(-.007, .007), float(b.center_lng) + rng.uniform(-.007, .007)
        pk = rng.choices(pks, [math.sqrt(max(x.area_ha, .5)) for x in pks])[0]
        for _ in range(60):
            lat, lng = rng.uniform(pk.min_lat, pk.max_lat), rng.uniform(pk.min_lng, pk.max_lng)
            if geometry.contains(pk.boundary_geojson, lat, lng):
                return lat, lng
        return float(pk.center_lat), float(pk.center_lng)

    def location(self, b, cat, national=False):
        """Returns (lat, lng, landmark, hotspot_sub_or_None)."""
        if national:
            lat, lng = self.point_in(b)
            return lat, lng, f"{self.rng.choice(C.LANDMARKS)}, {self.rng.choice(C.NATIONAL_ROADS)}", None
        spots = [h for h in self.hotspots[b.id] if h[3] == cat]
        if spots and self.rng.random() < .6:
            lat, lng, lm, _, sub = self.rng.choice(spots)
            return lat + self.rng.uniform(-.00025, .00025), lng + self.rng.uniform(-.00025, .00025), lm, sub
        lat, lng = self.point_in(b)
        return lat, lng, f"{self.rng.choice(C.LANDMARKS)}, {self.rng.choice(C.STREETS)}", None

    def person(self):
        return f"{self.rng.choice(C.FIRST_NAMES)} {self.rng.choice(C.LAST_NAMES)}", \
            f"09{self.rng.randint(15, 99)}{self.rng.randint(1000000, 9999999)}"

    # ------------------------------------------------------------------ one concern
    def _one_concern(self):
        rng = self.rng
        t0 = self.random_created()
        cat_code = self.pick_category(t0)
        cat = self.cats[cat_code]
        sub = rng.choice(self.subs.get(cat_code, [None])) if self.subs.get(cat_code) else None
        b = self.pick_barangay(cat_code, sub.code if sub else "")
        national = cat_code == "road_damage" and sub and sub.code in ("pothole", "damaged_pavement", "damaged_bridge") \
            and rng.random() < .3
        lat, lng, lm, spot_sub = self.location(b, cat_code, national)
        if spot_sub and rng.random() < .7:  # the hotspot's recurring problem
            sub = next((x for x in self.subs[cat_code] if x.code == spot_sub), sub)
        texts = C.DESCRIPTIONS.get(sub.code if sub else "_other", C.DESCRIPTIONS["_other"])
        desc = textgen.compose(sub.code if sub else "_other", cat_code, lm, rng, legacy=texts)
        channel = self.wchoice(CHANNELS)
        anon = rng.random() < .12
        name, phone = self.person()
        danger = rng.random() < ({"open_manhole": .7, "hanging_wires": .6, "fallen_tree": .5, "unsafe_structure": .4,
                                   "damaged_bridge": .3, "flooding": .2}.get(sub.code if sub else "", .04))
        staff_encoded = channel != "web"
        encoder = self.pick_user("barangay", barangay=b) if channel == "barangay" else self.pick_user("pacd")
        if channel == "barangay" and not encoder:
            encoder = self.pick_user("pacd")
        pinned = channel == "web" and rng.random() < .65 or staff_encoded and rng.random() < .25

        c = Concern(
            reference_no=self.ref(t0),
            title=f"{(sub.name_fil if sub else cat.name_fil) or cat.name} – {lm}"[:150],
            description=desc, category=cat, subcategory=sub,
            category_source=Concern.CategorySource.STAFF if staff_encoded else Concern.CategorySource.CITIZEN,
            channel=channel,
            source_reference={"facebook": "facebook.com/LucenaCityGov/posts/…", "walk_in": f"Action Center logbook #{rng.randint(1, 900)}",
                              "barangay": f"Brgy. {b.name} logbook #{rng.randint(1, 400)}", "messenger": "Messenger: City PIO page",
                              "hotline": "Hotline call", "8888": "DILG 8888 endorsement"}.get(channel, ""),
            external_ticket_no=f"8888-{t0.year}-{rng.randint(1000000, 9999999)}" if channel == "8888" else "",
            external_feedback_due_at=t0 + timedelta(hours=72) if channel == "8888" else None,
            encoded_by=encoder if staff_encoded else None,
            severity=4 if danger else 2,
            affected_count=self.wchoice([(1, 15), (5, 25), (50, 45), (500, 15)]),
            danger_now=danger,
            involves_barangay_officials=rng.random() < .015,
            barangay=b,
            latitude=round(lat, 6) if pinned else None, longitude=round(lng, 6) if pinned else None,
            location_description=lm,
            reporter_name="" if anon else name, reporter_contact="" if anon else phone, is_anonymous=anon,
            consent_given=True, consent_at=t0, is_synthetic=True,
            created_at=t0, updated_at=t0,
        )
        if pinned:
            pk, _ = find_purok(c.latitude, c.longitude, b.id)
            c.purok, c.purok_source = (pk, "pin") if pk else (None, "")
        elif self.puroks.get(b.id) and rng.random() < .4:  # reporter picked their purok from the list
            c.purok, c.purok_source = rng.choice(self.puroks[b.id]), "reporter"
        c.save()
        if rng.random() < (.45 if channel == "web" else .2):
            ConcernAttachment.objects.create(concern=c, kind="report", file=rng.choice(self.photos["report"]),
                                             uploaded_at=t0)
        self._simulate(c, national)
        return c

    # ------------------------------------------------------------------ lifecycle
    def _simulate(self, c, national):
        rng, now = self.rng, self.now
        events = []  # (time, kind, payload)
        hist = []    # (time, from, to, remarks, public, user)
        pacd = self.pick_user("pacd") or self.pick_user("city_admin")
        status = S.SUBMITTED
        hist.append((c.created_at, "", S.SUBMITTED, "Concern received.", True, c.encoded_by))

        def push(t, to, remarks, public=True, user=None):
            nonlocal status
            if t > now:
                return False
            hist.append((t, status, to, remarks, public, user))
            status = to
            return True

        def entry(t, remarks, user=None, public=True):
            if t <= now:
                hist.append((t, status, status, remarks, public, user))

        # --- verification
        t_verify = self.office_time(c.created_at + self.hours(.3, 20))
        if t_verify > now:
            return self._finish(c, hist, status, None)
        verifier = c.encoded_by if c.channel == "barangay" else pacd
        severity = min(5, max(1, (4 if c.danger_now else 2) + rng.choice([-1, 0, 0, 1])))
        c.is_verified, c.verified_by, c.verified_at, c.severity = True, verifier, t_verify, severity
        c.category_source = Concern.CategorySource.STAFF
        c.acknowledged_at = t_verify
        push(t_verify, S.UNDER_REVIEW, "Sinuri na ng LGU ang iyong report.", user=verifier)

        if c.channel == "8888":
            t_fb = c.created_at + self.hours(20, 96)
            if t_fb <= now:
                c.external_feedback_sent_at = t_fb
                c.external_feedback = "Naipasa sa kinauukulang opisina; may nakatakdang aksyon at petsa ng pagtapos."

        # --- rejected (≈4%)
        if rng.random() < .04:
            push(self.office_time(t_verify + self.hours(1, 30)), S.REJECTED, rng.choice(C.REJECT_REASONS), user=pacd)
            return self._finish(c, hist, status, None)

        # --- DPWH endorsement (national roads)
        if national:
            return self._endorsed(c, hist, push, entry, t_verify, pacd, lambda: status)

        # --- barangay-level
        sub = c.subcategory.code if c.subcategory else ""
        brgy_user = self.pick_user("barangay", barangay=c.barangay)
        if brgy_user and ((sub in ("uncollected", "overflowing_bin") and rng.random() < .4)
                          or (sub == "clogged_canal" and rng.random() < .15)):
            return self._barangay_level(c, hist, push, t_verify, brgy_user, lambda: status)

        # --- city office
        dept, div = suggested_route(c)
        if not dept:
            return self._finish(c, hist, status, None)
        t_route = self.office_time(t_verify + self.hours(.3, 6))
        if t_route > now:
            return self._finish(c, hist, status, None)
        level = self._level(c)
        case = Case(concern=c, level="city", department=dept, division=div, assigned_by=pacd,
                    assigned_at=t_route, routed_at=t_route, priority_level=level,
                    acceptance_due_at=deadlines.acceptance_due(t_route))
        case.due_at = case.original_due_at = deadlines.resolution_due(c, t_route, level)
        case.response_due_at = deadlines.response_due(t_route, level)
        push(t_route, S.ASSIGNED, f"Naipasa na sa {dept.name}. Target na petsa: {timezone.localtime(case.due_at):%b %d, %Y}.", user=pacd)
        notes = []

        # wrong office occasionally: returned then re-routed (same office kept for simplicity of routing table)
        if rng.random() < .05:
            t_ret = self.office_time(t_route + self.hours(1, 10))
            if t_ret <= now:
                case.return_count, case.returned_at = 1, t_ret
                case.return_reason = f"{dept.code}: {rng.choice(C.RETURN_REASONS)}"
                notes.append((t_ret, self.pick_user("office_desk", dept) or pacd, f"Ibinalik sa PACD: {case.return_reason}"))
                t_route = self.office_time(t_ret + self.hours(1, 8))
                if t_route > now:  # sitting in PACD's queue
                    hist.append((t_ret, S.ASSIGNED, S.UNDER_REVIEW, f"Returned by {dept.code}: {case.return_reason}", False, None))
                    case.department = case.division = None
                    case.acceptance_due_at = None
                    return self._finish(c, hist, S.UNDER_REVIEW, case, notes=notes)
                case.routed_at = t_route
                case.acceptance_due_at = deadlines.acceptance_due(t_route)
                case.due_at = case.original_due_at = deadlines.resolution_due(c, t_route, level)
                case.response_due_at = deadlines.response_due(t_route, level)

        # --- office acceptance (screening)
        desk = self.pick_user("office_desk", dept) or self.pick_user("dept_head", dept)
        legacy = 1 + (self.improvement if c.created_at < now - timedelta(days=365) else 0)  # see --improvement
        accept_h = ACCEPT_HOURS.get(dept.code, 4) * (.1 if level.code == "P1" else 1) * legacy
        t_accept = t_route + timedelta(hours=self.lognorm(accept_h, .7))
        t_accept = t_accept if level.code == "P1" else self.office_time(t_accept)
        if t_accept > now:
            return self._finish(c, hist, status, case, notes=notes)
        case.accepted_at, case.accepted_by = t_accept, desk
        case.screening = {q: rng.random() < .92 for q in (dept.screening_checklist or [])}
        entry(t_accept, f"Tinanggap na ng {dept.name}. Antas: {level.name_fil or level.name}. "
                        f"Target na petsa: {timezone.localtime(case.due_at):%b %d, %Y}.", desk)
        if not case.division_id:
            case.division = (div or dept.divisions.filter(is_active=True).first())

        # --- assignment
        chief = self.pick_user("division_chief", dept, case.division) or self.pick_user("dept_head", dept)
        crew = self.pick_user("dept_staff", dept, case.division) or chief
        t_assign = t_accept + (self.hours(.1, 1) if level.code == "P1" else self.hours(.5, 10))
        t_assign = t_assign if level.code == "P1" else self.office_time(t_assign)
        if t_assign > now:
            return self._finish(c, hist, status, case, notes=notes)
        case.assigned_to = crew
        notes.append((t_assign, chief, f"Itinalaga kay {crew.get_full_name() if crew else 'crew'}."))

        # --- first response / inspection
        speed = OFFICE_SPEED.get(dept.code, 1.0) * legacy
        period = deadlines.resolution_days(c, level)
        resp_days = min(((case.response_due_at - t_route).total_seconds() / 86400) if case.response_due_at else 2,
                        period * .25)
        t_resp = t_assign + timedelta(days=resp_days * self.lognorm(.7 * speed, .6))
        if level.code == "P1":
            t_resp = t_assign + timedelta(hours=self.lognorm(1.6 * speed, .6))  # emergencies: any hour
        else:
            t_resp = self.office_time(t_resp)
        t_resp = max(t_resp, t_assign + timedelta(minutes=15))
        if t_resp > now:
            return self._finish(c, hist, status, case, notes=notes)
        case.responded_at, case.responded_by = t_resp, crew
        if level.code == "P1":
            case.response_remarks = rng.choice(C.MAKE_SAFE)
            push(t_resp, S.IN_PROGRESS, case.response_remarks, user=crew)
            ConcernAttachment.objects.create(concern=c, kind="progress", file=rng.choice(self.photos["progress"]),
                                             uploaded_by=crew, uploaded_at=t_resp)
            t_insp = self.office_time(t_resp + self.hours(2, 20))
        else:
            t_insp = t_resp
        if t_insp > now:
            return self._finish(c, hist, status, case, notes=notes)
        sched = (timezone.localtime(t_insp) + timedelta(days=rng.randint(1, 5))).date()
        case.inspected_at, case.inspected_by = t_insp, crew
        case.inspection_findings, case.action_plan, case.scheduled_for = rng.choice(C.INSPECTION), "Ayon sa standard procedure.", sched
        if status != S.IN_PROGRESS:
            push(t_insp, S.IN_PROGRESS, f"Na-inspeksyon na ang lugar. Nakaiskedyul ang trabaho sa {sched:%b %d, %Y}.", user=crew)

        # --- work completion (office speed × ARTA period, lognormal); some cases stall indefinitely
        period_days = deadlines.resolution_days(c, level)
        # total elapsed working days from routing to work done; validation adds a few hours after
        work_wd = max(.4, self.lognorm(period_days * speed * .62, .5))
        stall = STALL.get(dept.code, .05) * (1.5 if c.category.service_class == "highly_technical" else 1) * (2 * legacy - 1)
        if rng.random() < stall * (.3 if level.code == "P1" else 1):
            # stalled (materials, budget, no action): finishes months late, so recent stalls are still open
            work_wd = max(work_wd, self.lognorm(80, .5))
        t_done = self.now + timedelta(days=365) if work_wd >= 10_000 else \
            self.office_time(max(t_route + timedelta(days=work_wd * 7 / 5), t_insp + self.hours(2, 30)))
        # extension: filed before the deadline when the crew is going to be late
        if t_done > case.due_at and rng.random() < .4:
            t_ext = case.due_at - self.hours(4, 30)
            if t_route < t_ext <= now:
                limit = deadlines.max_extension_due(case)
                case.extended_at = t_ext
                case.extension_reason = rng.choice(C.EXTENSION_REASONS)
                case.due_at = min(limit, max(case.due_at + timedelta(days=1), t_done + timedelta(days=1)))
                case.due_at = self.working_day_end(case.due_at)
                entry(t_ext, f"Na-extend ang target na petsa sa {timezone.localtime(case.due_at):%b %d, %Y}. "
                             f"Dahilan: {case.extension_reason}", chief)
        if t_done > now:
            return self._finish(c, hist, status, case, notes=notes)
        case.work_completed_at, case.work_completed_by = t_done, crew
        case.completion_remarks = rng.choice(C.RESOLUTION.get(c.category.code, C.RESOLUTION["other"]))
        ConcernAttachment.objects.create(concern=c, kind="resolution", file=rng.choice(self.photos["resolution"]),
                                         uploaded_by=crew, uploaded_at=t_done)
        hist.append((t_done, status, status, "Natapos na ang trabaho; hinihintay ang beripikasyon ng supervisor.", False, crew))

        # --- validation (≈7% sent back once)
        t_val = self.office_time(t_done + self.hours(1, 14))
        if rng.random() < .07:
            notes.append((t_val, chief, "Returned to field: may natitira pang trabaho."))
            t_val = self.office_time(t_val + self.hours(8, 60))
        if t_val > now:
            return self._finish(c, hist, status, case, notes=notes)
        case.validated_at, case.validated_by = t_val, chief
        case.resolution_summary, case.resolved_at = case.completion_remarks, t_val
        c.resolved_at = t_val
        push(t_val, S.RESOLVED, case.completion_remarks + " Salamat sa pag-report!", user=chief)

        # --- close (PACD closes the loop)
        t_close = self.office_time(t_val + self.hours(4, 96))
        if rng.random() < .88 and t_close <= now:
            push(t_close, S.CLOSED, "Isinara na ang report. Salamat sa pakikipagtulungan!", user=pacd)
        return self._finish(c, hist, status, case, notes=notes)

    def _level(self, c):
        lv = self.levels
        if c.danger_now or c.severity >= 5:
            return lv["P1"]
        if c.severity >= 4 or c.affected_count >= 500:
            return lv["P2"]
        return lv["P3"] if self.rng.random() < .8 else lv["P4"]

    def _barangay_level(self, c, hist, push, t_verify, kagawad, status):
        rng = self.rng
        t_route = self.office_time(t_verify + self.hours(.3, 4))
        if t_route > self.now:
            return self._finish(c, hist, status(), None)
        level = self._level(c)
        case = Case(concern=c, level="barangay", assigned_by=kagawad, assigned_at=t_route, routed_at=t_route,
                    accepted_at=t_route, accepted_by=kagawad, priority_level=level)
        case.due_at = case.original_due_at = deadlines.resolution_due(c, t_route, level)
        case.response_due_at = deadlines.response_due(t_route, level)
        push(t_route, S.ASSIGNED, f"Naipasa na sa Barangay {c.barangay.name}.", user=kagawad)
        t_done = self.office_time(t_route + timedelta(days=self.lognorm(1.5, .6)))
        if t_done > self.now:
            return self._finish(c, hist, status(), case)
        case.responded_at = case.inspected_at = t_route + (t_done - t_route) / 3
        case.work_completed_at, case.work_completed_by = t_done, kagawad
        case.completion_remarks = rng.choice(C.RESOLUTION["solid_waste"] if c.category.code == "solid_waste" else C.RESOLUTION["drainage"])
        push(case.responded_at, S.IN_PROGRESS, "Inaaksyunan na ng barangay.", user=kagawad)
        ConcernAttachment.objects.create(concern=c, kind="resolution", file=rng.choice(self.photos["resolution"]),
                                         uploaded_by=kagawad, uploaded_at=t_done)
        kap = next((u for u in self.by_role.get("barangay", []) if u.barangay_id == c.barangay_id and u.id != kagawad.id), None)
        t_val = self.office_time(t_done + self.hours(1, 24))
        if not kap or t_val > self.now:
            return self._finish(c, hist, status(), case)
        case.validated_at, case.validated_by, case.resolved_at = t_val, kap, t_val
        case.resolution_summary = case.completion_remarks
        c.resolved_at = t_val
        push(t_val, S.RESOLVED, case.completion_remarks, user=kap)
        t_close = self.office_time(t_val + self.hours(4, 72))
        if t_close <= self.now:
            push(t_close, S.CLOSED, "Isinara na ng barangay.", user=kap)
        return self._finish(c, hist, status(), case)

    def _endorsed(self, c, hist, push, entry, t_verify, pacd, status):
        rng = self.rng
        dpwh = self.ext.get("DPWH")
        t_end = self.office_time(t_verify + self.hours(1, 30))
        if not dpwh or t_end > self.now:
            return self._finish(c, hist, status(), None)
        case = Case(concern=c, level="external", department=dpwh, assigned_by=pacd, assigned_at=t_end, routed_at=t_end)
        case.due_at = case.original_due_at = deadlines.resolution_due(c, t_end)
        letter = f"PACD-{t_end.year}-{rng.randint(100, 999)}"
        push(t_end, S.ASSIGNED, f"Ang lugar ay sakop ng {dpwh.name}. Inendorso na ito ng City Hall (Ref. {letter}) "
                                f"at patuloy naming susubaybayan.", user=pacd)
        follow_ups = []
        e_status, agency_resp = "endorsed", ""
        t = t_end
        sched_after = timedelta(days=self.lognorm(14, .6))
        done_after = sched_after + timedelta(days=self.lognorm(18, .6))
        declined = rng.random() < .08
        while True:
            t = self.office_time(t + timedelta(days=7))
            if t > self.now:
                break
            note = "Tinawagan ang District Engineering Office para sa update."
            if declined and e_status == "endorsed":
                e_status, agency_resp = "declined", "Hindi kasama sa kanilang maintenance program ngayong taon."
            elif e_status == "endorsed" and t - t_end >= sched_after:
                e_status, agency_resp = "scheduled", "Isasama sa pothole patching program."
                push(t, S.IN_PROGRESS, f"Ayon sa {dpwh.code}, nakaiskedyul na ang aksyon.", user=pacd)
            elif e_status == "scheduled" and t - t_end >= done_after:
                e_status, agency_resp = "completed", "Natapos na ang patching ayon sa DPWH."
            follow_ups.append((t, rng.choice(["call", "letter", "email", "visit"]), note))
            if e_status in ("completed", "declined") or len(follow_ups) > 12:
                break
        if e_status == "completed":
            t_val = self.office_time(t + self.hours(4, 72))
            if t_val <= self.now:
                case.validated_at, case.validated_by, case.resolved_at = t_val, pacd, t_val
                case.work_completed_at = t
                case.resolution_summary = f"Na-patch na ng {dpwh.code} ang kalsada (na-verify ng LGU sa lugar)."
                c.resolved_at = t_val
                ConcernAttachment.objects.create(concern=c, kind="resolution", file=rng.choice(self.photos["resolution"]),
                                                 uploaded_by=pacd, uploaded_at=t_val)
                push(t_val, S.RESOLVED, case.resolution_summary, user=pacd)
        self._finish(c, hist, status(), case)
        e = Endorsement.objects.create(case=case, agency=dpwh, endorsed_by=pacd, endorsed_at=t_end, letter_reference=letter,
                                       contact_person="District Engineering Office", status=e_status, agency_response=agency_resp,
                                       follow_up_count=len(follow_ups),
                                       next_follow_up_at=(follow_ups[-1][0] if follow_ups else t_end) + timedelta(days=7))
        EndorsementFollowUp.objects.bulk_create([EndorsementFollowUp(endorsement=e, at=ft, by=pacd, method=m, notes=n)
                                                 for ft, m, n in follow_ups])

    def _finish(self, c, hist, status, case, notes=()):
        c.status = status
        c.updated_at = max(h[0] for h in hist)
        c.save()
        StatusHistory.objects.bulk_create([
            StatusHistory(concern=c, created_at=t, from_status=f, to_status=to, remarks=r, is_public=pub, changed_by=u)
            for t, f, to, r, pub, u in hist
        ])
        if case:
            self._escalations(c, case)
            case.save()
            CaseNote.objects.bulk_create([CaseNote(case=case, author=u, body=b, created_at=t) for t, u, b in notes])
        c._hist = hist
        return c

    def _escalations(self, c, case):
        """Replay the hourly escalation job: each missed commitment bumps the level once."""
        now = self.now
        breaches = []
        if case.acceptance_due_at and (case.accepted_at or now) > case.acceptance_due_at:
            breaches.append((case.acceptance_due_at, f"Hindi agad tinanggap ng {case.department.code if case.department else 'opisina'}"))
        if case.response_due_at and (case.responded_at or now) > case.response_due_at:
            breaches.append((case.response_due_at, f"Walang unang aksyon para sa {case.priority_level.code if case.priority_level else ''}"))
        end = case.validated_at or case.work_completed_at or now
        if case.due_at and end > case.due_at and case.level != "external":
            breaches.append((case.due_at, "Lumampas sa target na petsa"))
        if not breaches:
            return
        breaches.sort()
        case.escalation_level = min(3, len(breaches) + (1 if case.due_at and end - case.due_at > timedelta(days=10) else 0))
        case.escalated_at = breaches[0][0] + timedelta(hours=1)
        case.escalation_reason = "; ".join(b for _, b in breaches) + "."
        case.next_escalation_at = deadlines.add_working_days(breaches[-1][0], 2)

    # ------------------------------------------------------------------ duplicates
    def _duplicates(self, master):
        rng = self.rng
        sub = master.subcategory.code if master.subcategory else ""
        if master.status == S.REJECTED or rng.random() > DUP_RATE.get(sub, .08):
            return 0
        n = min(5, 1 + int(rng.expovariate(1.2)))
        end = master.resolved_at or self.now
        made = 0
        master_hist = [h for h in master._hist if h[1] != h[2] or h[2] == S.SUBMITTED][1:]
        for _ in range(n):
            t = master.created_at + timedelta(hours=rng.uniform(2, 24 * 6))
            if t >= end or t > self.now:
                continue
            same_person = rng.random() < .1 and not master.is_anonymous
            name, phone = (master.reporter_name, master.reporter_contact) if same_person else self.person()
            anon = rng.random() < .12 and not same_person
            d = Concern(
                reference_no=self.ref(t), title=master.title,
                description=textgen.compose(sub or "_other", master.category.code, master.location_description, rng,
                                            legacy=C.DESCRIPTIONS.get(sub, C.DESCRIPTIONS["_other"])),
                category=master.category, subcategory=master.subcategory, category_source=master.category_source,
                channel=self.wchoice(CHANNELS[:5]), severity=master.severity, affected_count=master.affected_count,
                danger_now=master.danger_now, barangay=master.barangay,
                latitude=master.latitude, longitude=master.longitude, location_description=master.location_description,
                purok=master.purok, purok_source=master.purok_source,
                reporter_name="" if anon else name, reporter_contact="" if anon else phone, is_anonymous=anon,
                consent_given=True, consent_at=t, duplicate_of=master, is_synthetic=True,
                is_verified=master.is_verified, verified_at=master.verified_at, status=S.SUBMITTED,
                created_at=t, updated_at=t,
            )
            hist = [(t, "", S.SUBMITTED, "Concern received.", True, None)]
            status = S.SUBMITTED
            for ht, _, to, remarks, pub, u in master_hist:
                if ht < t or not pub:
                    continue
                hist.append((ht, status, to, f"Kasama sa report {master.reference_no}. {remarks}", True, u))
                status = to
            d.status, d.resolved_at, d.updated_at = status, master.resolved_at if status in Concern.DONE_STATUSES else None, hist[-1][0]
            d.save()
            StatusHistory.objects.bulk_create([
                StatusHistory(concern=d, created_at=ht, from_status=f, to_status=to, remarks=r, is_public=pub, changed_by=u)
                for ht, f, to, r, pub, u in hist
            ])
            made += 1
        return made
