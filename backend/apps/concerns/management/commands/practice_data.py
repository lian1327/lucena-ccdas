"""
Practice cases for training, user acceptance testing (UAT) and the citizen usability sessions (Step 19).

    python manage.py practice_data            # create the practice set (skips if it already exists)
    python manage.py practice_data --reset    # delete the practice set and create it again (before every session)
    python manage.py practice_data --delete   # remove it

Each case is a real case driven through the same services the screens use, so alerts, deadlines, photo checks and
the tracking page behave exactly as they will in the pilot. Practice cases are marked is_practice, never send SMS
or email to the (fake) reporter, and use the demo staff accounts from seed_reference_data --demo-users.
Refuses to run when SITE_MODE=official (the City's live system) unless --force.
"""
import io
from datetime import timedelta

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.cases import services as cs
from apps.cases.models import Department
from apps.concerns.models import Category, Concern, ConcernAttachment
from apps.concerns.services import on_concern_submitted
from apps.concerns.trust import save_citizen_photos
from apps.geo.models import Barangay

NEEDED = ["pacd.desk", "ceo.desk", "ceo.head", "ceo.rdb.chief", "ceo.crew", "brgy.gg", "brgy.gg.kap"]
MOBILE = "09170000001"  # fake; practice cases never send SMS. Last 4 digits (0001) unlock the tracking-page actions.


def photo(label, seed, tone=(70, 110, 130)):
    """A 640×480 JPEG that says PRACTICE, so nobody mistakes it for a real site photo."""
    from PIL import Image, ImageDraw

    im = Image.new("RGB", (640, 480), tone)
    d = ImageDraw.Draw(im)
    for i in range(14):  # texture so each photo has its own perceptual hash
        x, y = (seed * 53 + i * 47) % 600, (seed * 31 + i * 29) % 440
        d.rectangle([x, y, x + 30 + (seed + i) % 40, y + 18], fill=((seed * 40 + i * 23) % 255, (i * 37) % 255, 160))
    d.rectangle([0, 200, 640, 280], fill=(255, 255, 255))
    d.text((24, 222), f"PRACTICE / PAGSASANAY  -  {label}", fill=(20, 20, 20))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=85)
    return buf.getvalue()


def upload(data, name):
    return SimpleUploadedFile(name, data, content_type="image/jpeg")


def centroid(barangay):
    g = barangay.boundary_geojson or {}
    coords = g.get("coordinates") or []
    ring = coords[0] if g.get("type") == "Polygon" else (coords[0][0] if coords else [])
    if not ring:
        return None
    return sum(p[1] for p in ring) / len(ring), sum(p[0] for p in ring) / len(ring)


class Command(BaseCommand):
    help = "Create, reset or delete the practice cases used for training, UAT and usability sessions."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete and recreate the practice set.")
        parser.add_argument("--delete", action="store_true", help="Delete the practice set only.")
        parser.add_argument("--force", action="store_true", help="Allow on SITE_MODE=official (not recommended).")

    def handle(self, *args, reset=False, delete=False, force=False, **kw):
        if getattr(settings, "CCADSS_SITE_MODE", "prototype") == "official" and not force:
            raise CommandError("SITE_MODE is official (the City's live system). Run practice sessions on the "
                               "prototype or a test copy, or pass --force.")
        existing = Concern.objects.filter(is_practice=True)
        if reset or delete:
            n = self._delete(existing)
            self.stdout.write(f"Deleted {n} practice case(s).")
            if delete:
                return
        elif existing.exists():
            self.stdout.write("Practice cases already exist. Use --reset to recreate them.")
            self._print(existing)
            return
        self._check_accounts()
        with transaction.atomic():
            made = self._build()
        self.stdout.write(self.style.SUCCESS(f"Created {len(made)} practice cases."))
        self._print(Concern.objects.filter(is_practice=True))

    # ------------------------------------------------------------------ helpers
    def _delete(self, qs):
        n = 0
        for c in qs:
            for a in ConcernAttachment.objects.filter(concern=c):
                a.file.delete(save=False)
            c.delete()
            n += 1
        return n

    def _check_accounts(self):
        missing = [u for u in NEEDED if not User.objects.filter(username=u, is_active=True).exists()]
        if missing:
            raise CommandError(f"Missing demo accounts: {', '.join(missing)}. "
                               "Run: python manage.py seed_reference_data --lucena --demo-users")
        self.u = {u.username: u for u in User.objects.filter(username__in=NEEDED)}

    def _site(self, brgy, i):
        """Points about 300 m apart so practice cases never auto-merge with each other (except where intended)."""
        c = centroid(brgy) or (13.9412, 121.6173)
        return round(c[0] + 0.0027 * (i % 4), 6), round(c[1] + 0.0027 * (i // 4), 6)

    def _concern(self, n, *, title, description, category, brgy, at, channel=Concern.Channel.WEB, photo_bytes=None,
                 danger=False, landmark="Practice site"):
        c = Concern.objects.create(
            title=f"[Practice] {title}", description=description, category=category, barangay=brgy,
            location_description=landmark, latitude=at[0], longitude=at[1], channel=channel,
            reporter_name="Practice Reporter", reporter_contact=MOBILE, is_anonymous=False, consent_given=True,
            notify_sms=False, notify_email=False, danger_now=danger, is_practice=True,
        )
        if photo_bytes:
            save_citizen_photos(c, [upload(photo_bytes, f"practice-{n}.jpg")],
                                [{"device_lat": at[0], "device_lng": at[1], "device_accuracy": 10}])
        on_concern_submitted(c)
        c.refresh_from_db()
        return c

    @staticmethod
    def meta(at, d=0.0):
        return {"device_lat": at[0] + d, "device_lng": at[1], "device_accuracy": 8, "live": True}

    def _route_city(self, c, dept=None):
        cs.verify(c, self.u["pacd.desk"], category=c.category, severity=3)
        cs.route(c, self.u["pacd.desk"], level="city", department=dept)
        c.refresh_from_db()
        return c

    def _accept(self, c):
        case = c.case
        answers = {q: "oo" for q in (case.department.screening_checklist or [])}
        cs.accept(c, self.u["ceo.desk"], priority_level=case.priority_level, screening=answers)
        c.refresh_from_db()
        return c

    # ------------------------------------------------------------------ the set
    def _build(self):
        brgy = Barangay.objects.get(name="Ibabang Iyam")
        gg = Barangay.objects.get(name="Gulang-Gulang")
        road = Category.objects.get(code="road_damage")
        drain = Category.objects.get(code="drainage")
        light = Category.objects.get(code="streetlight")
        ceo = Department.objects.get(code="CEO")
        crew, chief = self.u["ceo.crew"], self.u["ceo.rdb.chief"]
        reused = photo("lubak sa kalsada", 1)
        made = []

        # 1 RESOLVED: before/after photos, waiting for the citizen's answer (SUS task 3, UAT C-04, H-02 example)
        at = self._site(brgy, 0)
        c = self._concern(1, title="Malaking lubak sa kalsada", category=road, brgy=brgy, at=at, photo_bytes=reused,
                          description="May malaking lubak sa gitna ng kalsada, delikado sa motor lalo na sa gabi.")
        self._route_city(c); self._accept(c)
        cs.assign_person(c, self.u["ceo.desk"], person=crew)
        cs.inspect(c, crew, findings="Lubak na mga 1 m x 1 m.", photos=[upload(photo("BEFORE", 2), "before.jpg")],
                   photo_meta=[self.meta(at)])
        cs.complete_work(c, crew, remarks="Tinapalan ng cold mix at pinatag.",
                         photos=[upload(photo("AFTER", 3, (90, 140, 90)), "after.jpg")], photo_meta=[self.meta(at, 0.00005)])
        cs.validate(c, chief, approve=True)
        made.append(("RESOLVED – citizen confirms the fix (SUS task 3, UAT C-04)", c))

        # 2 NEW web report waiting for PACD triage (UAT P-02)
        c = self._concern(2, title="Barado ang kanal", category=drain, brgy=brgy, at=self._site(brgy, 1),
                          photo_bytes=photo("kanal", 4),
                          description="Barado ang kanal sa tabi ng daan, umaapaw kapag umuulan at bumabaha sa bahay.")
        made.append(("NEW – PACD triage and AI suggestion (UAT P-02)", c))

        # 3 + 4 ROUTED to CEO waiting for acceptance, and a report of the same problem 120 m away for manual linking
        at4 = self._site(brgy, 2)
        c4 = self._concern(4, title="Sirang kalsada malapit sa paaralan", category=road, brgy=brgy, at=at4,
                           description="Sira at may butas ang kalsada malapit sa gate ng paaralan.")
        self._route_city(c4)
        made.append(("ROUTED – office desk accepts (UAT D-01, D-03)", c4))
        c3 = self._concern(3, title="Butas sa daan tapat ng school", category=road, brgy=brgy,
                           at=(round(at4[0] + 0.00108, 6), at4[1]), channel=Concern.Channel.FACEBOOK,
                           description="Malaking butas sa daan tapat ng school, maraming estudyante ang dumadaan.")
        made.append(("NEW – similar report 120 m away, link as duplicate (UAT P-03)", c3))

        # 5 MISROUTED: a streetlight concern sent to CEO by mistake (UAT D-02 return to PACD)
        c = self._concern(5, title="Patay ang ilaw sa poste", category=light, brgy=brgy, at=self._site(brgy, 3),
                          description="Tatlong gabi nang patay ang ilaw sa poste, madilim at delikado.")
        self._route_city(c, dept=ceo)
        made.append(("ROUTED TO WRONG OFFICE – return to PACD (UAT D-02)", c))

        # 6 ASSIGNED to the field crew (field view F-01 to F-06)
        at = self._site(brgy, 4)
        c = self._concern(6, title="Lubak sa kanto ng kapilya", category=road, brgy=brgy, at=at,
                          photo_bytes=photo("lubak kapilya", 5),
                          description="Lubak sa kanto ng kapilya, napupuno ng tubig kapag umuulan.")
        self._route_city(c); self._accept(c)
        cs.assign_person(c, self.u["ceo.desk"], person=crew)
        made.append(("ASSIGNED to ceo.crew – field view (UAT F-01 to F-06)", c))

        # 7 WORK DONE, waiting for the chief's validation (UAT H-02, H-03)
        at = self._site(brgy, 5)
        c = self._concern(7, title="Nakalubog na manhole", category=drain, brgy=brgy, at=at,
                          description="Nakalubog ang takip ng manhole, puwedeng mahulog ang gulong ng sasakyan.")
        self._route_city(c); self._accept(c)
        cs.assign_person(c, self.u["ceo.desk"], person=crew)
        cs.inspect(c, crew, findings="Lubog ang takip ng manhole.", photos=[upload(photo("BEFORE manhole", 6), "b.jpg")],
                   photo_meta=[self.meta(at)])
        cs.complete_work(c, crew, remarks="Inangat at sinemento ang takip.",
                         photos=[upload(photo("AFTER manhole", 7, (90, 140, 90)), "a.jpg")], photo_meta=[self.meta(at)])
        made.append(("WORK DONE – chief validates or returns (UAT H-02, H-03)", c))

        # 8 NATIONAL ROAD: to be endorsed to DPWH (UAT P-05)
        c = self._concern(8, title="Lubak sa national highway", category=road, brgy=brgy, at=self._site(brgy, 6),
                          landmark="Maharlika Highway (practice)",
                          description="Malalaking lubak sa national highway malapit sa terminal.")
        made.append(("NEW – national road, endorse to DPWH (UAT P-05)", c))

        # 9 REUSED PHOTO: same photo as case 1 (screening signal, UAT P-06)
        c = self._concern(9, title="Lubak sa likod ng palengke", category=road, brgy=brgy, at=self._site(brgy, 7),
                          photo_bytes=reused, description="May lubak sa likod ng palengke.")
        made.append(("NEW – reused photo flag, PACD screening (UAT P-06)", c))

        # 10 ACCEPTED, unassigned: possible false report to close as unfounded (UAT H-06)
        c = self._concern(10, title="Sirang tulay daw", category=road, brgy=brgy, at=self._site(brgy, 8),
                          description="Sira raw ang tulay, hindi na madaanan.")
        self._route_city(c); self._accept(c)
        made.append(("ACCEPTED – close as unfounded after site check (UAT H-05, H-06)", c))

        # 11 BARANGAY-LEVEL case in Gulang-Gulang (UAT B-01, B-02)
        c = self._concern(11, title="Baradong kanal sa purok", category=drain, brgy=gg, at=self._site(gg, 0),
                          description="Barado ang maliit na kanal sa purok, mabaho at may lamok.")
        cs.verify(c, self.u["pacd.desk"], category=drain, severity=2)
        cs.route(c, self.u["pacd.desk"], level="barangay")
        made.append(("BARANGAY LEVEL – Gulang-Gulang (UAT B-01, B-02)", c))

        self._labels = {c.pk: label for label, c in made}
        return made

    def _print(self, qs):
        labels = getattr(self, "_labels", {})
        self.stdout.write("")
        self.stdout.write(f"{'Reference':<18} {'Status':<13} Use")
        for c in qs.order_by("pk"):
            self.stdout.write(f"{c.reference_no:<18} {c.status:<13} {labels.get(c.pk, c.title)}")
        self.stdout.write("")
        self.stdout.write(f"Reporter mobile on every practice case: {MOBILE} (last 4 digits: {MOBILE[-4:]}).")
        self.stdout.write("Write the RESOLVED reference on the usability observer sheet as 'REF-DEMO'.")
