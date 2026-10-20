"""
Run the active model over existing reports and store its suggestion (ai_* fields) without changing their category.

    python manage.py classify_reports --since 2026-04-20     # e.g. simulate "the model was live since April"

Demo procedure for an honest live-accuracy figure on synthetic data:
    python manage.py train_classifier --before 2026-04-20 --activate    # model only knows older reports
    python manage.py classify_reports --since 2026-04-20                # it "sees" newer reports first
    python manage.py train_classifier                                   # then the full model for deployment
"""
from datetime import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.dateparse import parse_date

from apps.classifier import pipeline
from apps.concerns.models import Concern


class Command(BaseCommand):
    help = "Store the active model's suggestion on existing reports (for live-accuracy monitoring)."

    def add_arguments(self, p):
        p.add_argument("--since", required=True)

    def handle(self, *a, **o):
        since = timezone.make_aware(datetime.combine(parse_date(o["since"]), datetime.min.time()))
        mv, art = pipeline.active_artifact()
        if not art:
            self.stderr.write("No active model. Run train_classifier first.")
            return
        qs = Concern.objects.filter(created_at__gte=since).exclude(description="").only("id", "description")
        items = list(qs)
        cat_ids = {c.code: c.id for c in __import__("apps.concerns.models", fromlist=["Category"]).Category.objects.all()}
        sub_ids = {s.code: s.id for s in __import__("apps.concerns.models", fromlist=["Subcategory"]).Subcategory.objects.all()}
        for i in range(0, len(items), 500):
            chunk = items[i:i + 500]
            for c in chunk:
                r = pipeline.classify(c.description)
                c.ai_category_id = cat_ids.get(r["category"])
                c.ai_subcategory_id = sub_ids.get(r["subcategory"]) if r["subcategory"] else None
                c.ai_confidence, c.ai_top, c.ai_model_id = r["confidence"], r["top"], mv.id
            Concern.objects.bulk_update(chunk, ["ai_category", "ai_subcategory", "ai_confidence", "ai_top", "ai_model"])
        self.stdout.write(self.style.SUCCESS(f"Stored suggestions from v{mv.version} on {len(items)} reports since {o['since']}."))
