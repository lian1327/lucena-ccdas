"""Role-based access: each role sees and does only what its job needs (Module 2 / RA 10173)."""
from rest_framework.test import APIClient

from apps.cases.scoping import permissions_for, scoped_concerns
from apps.concerns.models import Concern

from .base import CCADSSTestCase

URL = "/api/v1/staff/concerns/"


class ScopeTests(CCADSSTestCase):
    def setUp(self):
        self.mine = self.make_concern()                                   # Ibabang Iyam, road → CEO
        self.other = self.make_concern(barangay=self.other_brgy, category=self.light, lat=None, lng=None)
        self.about_officials = self.make_concern(involves_barangay_officials=True, category=self.light,
                                                 lat=None, lng=None)

    def ids(self, username):
        return set(scoped_concerns(self.user(username)).values_list("pk", flat=True))

    def test_pacd_and_executives_see_everything(self):
        for u in ("pacd.desk", "cityadmin", "mayor"):
            self.assertTrue({self.mine.pk, self.other.pk}.issubset(self.ids(u)), u)

    def test_office_sees_only_its_own_categories(self):
        ceo = self.ids("ceo.desk")
        self.assertIn(self.mine.pk, ceo)
        self.assertNotIn(self.other.pk, ceo)

    def test_field_staff_sees_nothing_until_accepted(self):
        self.route_to_city(self.mine)
        self.assertNotIn(self.mine.pk, self.ids("ceo.crew"))
        self.accept(self.mine)
        from apps.cases import services as cs

        cs.assign_person(self.mine, self.user("ceo.desk"), person=self.user("ceo.crew"))
        self.assertIn(self.mine.pk, self.ids("ceo.crew"))

    def test_mayor_is_read_only(self):
        p = permissions_for(self.user("mayor"), self.mine)
        self.assertFalse(p["can_act"])
        self.assertFalse(p["route"])

    def test_field_staff_cannot_route(self):
        self.assertFalse(permissions_for(self.user("ceo.crew"), self.mine)["route"])


class ApiAccessTests(CCADSSTestCase):
    def setUp(self):
        self.c = self.make_concern()
        self.api = APIClient()

    def test_anonymous_cannot_use_staff_api(self):
        self.assertEqual(self.api.get(URL).status_code, 401)

    def test_citizen_account_is_forbidden(self):
        from apps.accounts.models import User

        citizen = User.objects.create_user("juan", password="x", role=User.Role.CITIZEN)
        self.api.force_authenticate(citizen)
        self.assertEqual(self.api.get(URL).status_code, 403)

    def test_out_of_scope_case_is_404(self):
        self.api.force_authenticate(self.user("gso.desk"))
        self.assertEqual(self.api.get(f"{URL}{self.c.pk}/").status_code, 404)

    def test_mayor_cannot_route_through_api(self):
        self.api.force_authenticate(self.user("mayor"))
        r = self.api.post(f"{URL}{self.c.pk}/route/", {"level": "city"}, format="json")
        self.assertIn(r.status_code, (400, 403))
        self.c.refresh_from_db()
        self.assertEqual(self.c.status, Concern.Status.SUBMITTED)

    def test_pacd_routes_through_api(self):
        self.api.force_authenticate(self.user("pacd.desk"))
        r = self.api.post(f"{URL}{self.c.pk}/verify/", {"category": "road_damage", "severity": 2}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        r = self.api.post(f"{URL}{self.c.pk}/route/", {"level": "city"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["status"], "assigned")

    def test_login_returns_tokens(self):
        u = self.user("pacd.desk")
        u.set_password("Test#12345")
        u.save()
        r = self.api.post("/api/v1/auth/token/", {"username": "pacd.desk", "password": "Test#12345"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertIn("access", r.json())
        bad = self.api.post("/api/v1/auth/token/", {"username": "pacd.desk", "password": "wrong"}, format="json")
        self.assertEqual(bad.status_code, 401)
