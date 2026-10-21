"""Pin → purok: point-in-polygon, 30 m snapping, and the chosen barangay winning over a neighbour."""
from apps.geo import geometry
from apps.geo.locate import find_purok
from apps.geo.models import Purok

from .base import CCADSSTestCase

# A ~110 m square around (13.9400, 121.6200)
SQUARE = {"type": "Polygon", "coordinates": [[[121.6195, 13.9395], [121.6205, 13.9395], [121.6205, 13.9405],
                                               [121.6195, 13.9405], [121.6195, 13.9395]]]}
EAST = {"type": "Polygon", "coordinates": [[[121.6205, 13.9395], [121.6215, 13.9395], [121.6215, 13.9405],
                                             [121.6205, 13.9405], [121.6205, 13.9395]]]}


def purok(brgy, name, geom, zone=False):
    min_lat, max_lat, min_lng, max_lng = geometry.bbox(geom)
    return Purok.objects.create(barangay=brgy, name=name, is_zone=zone, boundary_geojson=geom,
                                min_lat=min_lat, max_lat=max_lat, min_lng=min_lng, max_lng=max_lng, area_ha=1.2,
                                center_lat=round((min_lat + max_lat) / 2, 6), center_lng=round((min_lng + max_lng) / 2, 6))


class GeometryTests(CCADSSTestCase):
    def test_contains(self):
        self.assertTrue(geometry.contains(SQUARE, 13.9400, 121.6200))
        self.assertFalse(geometry.contains(SQUARE, 13.9420, 121.6200))

    def test_distance_outside_is_positive(self):
        d = geometry.distance_m(SQUARE, 13.9400, 121.6207)  # ≈ 21 m east of the edge
        self.assertGreater(d, 10)
        self.assertLess(d, 35)


class LocateTests(CCADSSTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.p1 = purok(cls.brgy, "Prk. Mabuhay", SQUARE)
        cls.p2 = purok(cls.other_brgy, "Prk. Silangan", EAST)

    def test_point_inside(self):
        p, d = find_purok(13.9400, 121.6200)
        self.assertEqual((p, d), (self.p1, 0.0))

    def test_snaps_within_30m(self):
        p, d = find_purok(13.9400, 121.61935, barangay_id=self.brgy.pk)  # ≈ 16 m west of the edge
        self.assertEqual(p, self.p1)
        self.assertGreater(d, 0)

    def test_far_point_has_no_purok(self):
        self.assertEqual(find_purok(13.9500, 121.6300), (None, None))

    def test_chosen_barangay_wins_on_the_boundary(self):
        p, _ = find_purok(13.9400, 121.6206, barangay_id=self.brgy.pk)  # inside EAST, but citizen chose brgy
        self.assertEqual(p, self.p1)

    def test_report_is_tagged_from_the_pin(self):
        from decimal import Decimal

        c = self.make_concern(lat=Decimal("13.940000"), lng=Decimal("121.620000"))
        self.assertEqual((c.purok_id, c.purok_source), (self.p1.pk, "pin"))
