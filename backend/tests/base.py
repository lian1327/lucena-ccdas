"""
Shared fixtures for the CCADSS test suite.

Run everything:            python manage.py test tests -v 2
One module:                python manage.py test tests.test_notifications
Reference data comes from the real seed command, so the tests exercise the same offices, categories,
ARTA classes and priority levels the system ships with.
"""
import io
import shutil
import tempfile
from contextlib import contextmanager
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings

from apps.accounts.models import User
from apps.concerns.models import Category, Concern
from apps.concerns.services import on_concern_submitted
from apps.geo.models import Barangay

TMP_MEDIA = tempfile.mkdtemp(prefix="ccadss-test-media-")
TMP_MODELS = tempfile.mkdtemp(prefix="ccadss-test-models-")

# A point in Lucena City proper used as "the site" in most tests
SITE = (Decimal("13.941200"), Decimal("121.617300"))

TEST_SETTINGS = dict(
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
    MEDIA_ROOT=TMP_MEDIA,
    ML_MODEL_DIR=TMP_MODELS,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    CCADSS_SMS_PROVIDER="console",
    CCADSS_SMS_QUIET_HOURS="0",
    CCADSS_NOTIFY_SEND_INLINE="1",
    CCADSS_NOTIFY_EMAIL="1",
    CCADSS_PUBLIC_SITE_URL="https://ccadss.example.ph",
    CCADSS_SMS_SIGNATURE="LGU Lucena",
    REST_FRAMEWORK={
        "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework_simplejwt.authentication.JWTAuthentication"],
        "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
        "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
        "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
        "PAGE_SIZE": 20,
        "DEFAULT_THROTTLE_CLASSES": [],  # throttling has its own test; keep the rest deterministic
        "DEFAULT_THROTTLE_RATES": {"public_submit": "1000/hour", "public_track": "1000/minute", "auth_login": "1000/hour"},
    },
)


def jpeg(seed=0, size=(64, 48), name=None):
    """A small real JPEG. Different seeds give visually different images (different perceptual hashes)."""
    from PIL import Image, ImageDraw

    im = Image.new("RGB", size, (200, 200, 200))
    d = ImageDraw.Draw(im)
    for i in range(6):
        x = (seed * 37 + i * 11) % size[0]
        y = (seed * 17 + i * 7) % size[1]
        d.rectangle([x, y, x + 12 + seed % 9, y + 9], fill=((seed * 50 + i * 30) % 255, 40 * i % 255, 90))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=90)
    return SimpleUploadedFile(name or f"photo{seed}.jpg", buf.getvalue(), content_type="image/jpeg")


def near_site(dlat=0.0, dlng=0.0, accuracy=10):
    """Browser-style evidence metadata for a photo taken at the site (offsets in degrees)."""
    return {"device_lat": float(SITE[0]) + dlat, "device_lng": float(SITE[1]) + dlng, "device_accuracy": accuracy}


@override_settings(**TEST_SETTINGS)
class CCADSSTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_reference_data", "--lucena", "--demo-users", stdout=io.StringIO())
        cls.brgy = Barangay.objects.get(name="Ibabang Iyam")
        cls.other_brgy = Barangay.objects.get(name="Gulang-Gulang")
        cls.road = Category.objects.get(code="road_damage")
        cls.light = Category.objects.get(code="streetlight")
        cls.u = {u.username: u for u in User.objects.all()}

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP_MEDIA, ignore_errors=True)

    def user(self, username):
        return self.u[username]

    def make_concern(self, *, category="road", lat=SITE[0], lng=SITE[1], barangay=None, contact="09171234567",
                     email="", anonymous=False, submit=True, **kw):
        c = Concern.objects.create(
            title=kw.pop("title", "Malaking lubak"),
            description=kw.pop("description", "Malaking lubak sa gitna ng kalsada, delikado sa motor."),
            category=self.road if category == "road" else category,
            barangay=barangay or self.brgy,
            location_description=kw.pop("location_description", "tapat ng chapel"),
            latitude=lat, longitude=lng,
            reporter_name="" if anonymous else kw.pop("reporter_name", "Juan Dela Cruz"),
            reporter_contact="" if anonymous else contact,
            reporter_email="" if anonymous else email,
            is_anonymous=anonymous, consent_given=True, **kw,
        )
        if submit:
            on_concern_submitted(c)
            c.refresh_from_db()
        return c

    @contextmanager
    def committed(self):
        """Run on_commit callbacks (notifications are sent after the transaction commits)."""
        with self.captureOnCommitCallbacks(execute=True):
            yield

    # ---- workflow shortcuts (the same service calls the API views make) ----
    def route_to_city(self, c):
        from apps.cases import services as cs

        pacd = self.user("pacd.desk")
        cs.verify(c, pacd, category=c.category, severity=2)
        return cs.route(c, pacd, level="city")

    def accept(self, c, desk="ceo.desk"):
        from apps.cases import services as cs

        case = c.case
        answers = {q: "oo" for q in (case.department.screening_checklist or [])}
        return cs.accept(c, self.user(desk), priority_level=case.priority_level, screening=answers)

    def work_until_resolved(self, c, *, crew="ceo.crew", validator="ceo.rdb.chief", after_meta=None, override=""):
        from apps.cases import services as cs

        self.route_to_city(c)
        self.accept(c)
        cs.assign_person(c, self.user("ceo.desk"), person=self.user(crew))
        cs.inspect(c, self.user(crew), findings="Lubak na 1m x 1m", photos=[jpeg(1)], photo_meta=[near_site()])
        cs.complete_work(c, self.user(crew), remarks="Tinapalan ng aspalto", photos=[jpeg(2)],
                         photo_meta=[after_meta or near_site(0.0001)])
        cs.validate(c, self.user(validator), approve=True, override_reason=override)
        c.refresh_from_db()
        return c
