"""Module 3: text normalisation, the classifier pipeline, and the 'AI never has the final word' rule."""
import csv
import random
from pathlib import Path

from django.conf import settings

from apps.classifier import pipeline
from apps.classifier.services import apply_ai
from apps.classifier.text import normalize
from apps.concerns.models import Subcategory
from apps.concerns.synthetic import textgen

from .base import CCADSSTestCase


class NormalizeTests(CCADSSTestCase):
    def test_texting_style_is_normalised(self):
        self.assertEqual(normalize("Bahaaa d2 sa brgy, pls ayusin ASAP!!! 09171234567"),
                         "baha dito sa barangay please ayusin agad")

    def test_links_and_numbers_removed(self):
        self.assertEqual(normalize("tingnan https://fb.com/x 123 lubak"), "tingnan lubak")


class PipelineTests(CCADSSTestCase):
    def test_without_a_model_reports_are_still_accepted(self):
        c = self.make_concern(category=None, lat=None, lng=None)
        self.assertIsNone(apply_ai(c))
        self.assertIsNone(c.category_id)

    def test_trained_pipeline_generalises_to_hand_written_reports(self):
        """Train on generated reports, test on the separately written challenge set (not seen in training)."""
        rng = random.Random(7)
        texts, labels = [], []
        for sub in Subcategory.objects.select_related("category"):
            for _ in range(25):
                texts.append(textgen.compose(sub.code, sub.category.code, "tapat ng palengke", rng))
                labels.append(sub.category.code)
        model = pipeline.build("logistic_regression").fit(texts, labels)
        path = Path(settings.BASE_DIR) / "ml" / "challenge_set.csv"
        rows = list(csv.DictReader(path.open(encoding="utf-8")))
        acc = sum(model.predict([r["text"]])[0] == r["category"] for r in rows) / len(rows)
        self.assertGreater(acc, 0.75, f"challenge-set accuracy {acc:.3f}")
