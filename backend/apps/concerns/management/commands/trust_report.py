"""
For the study (Step 17): how often reports turned out unfounded, and whether flagged reports were unfounded
more often than the rest — the real-world accuracy of the screening signals.

    python manage.py trust_report                 # all real (non-synthetic) reports
    python manage.py trust_report --since 2027-06-01
"""
from datetime import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.concerns import trust


class Command(BaseCommand):
    help = "Unfounded-report rate and how well each screening flag predicted it."

    def add_arguments(self, p):
        p.add_argument("--since", help="YYYY-MM-DD")

    def handle(self, *a, **o):
        since = timezone.make_aware(datetime.fromisoformat(o["since"])) if o.get("since") else None
        r = trust.report_card(since)
        rate = f"{r['unfounded_rate']:.1%}" if r["unfounded_rate"] is not None else "—"
        self.stdout.write(f"Decided reports: {r['decided']} · unfounded: {r['unfounded']} ({rate})")
        self.stdout.write(f"{'flag':18} {'reports':>8} {'unfounded':>10} {'rate':>7}")
        for code, v in r["by_flag"].items():
            rr = f"{v['unfounded_rate']:.1%}" if v["unfounded_rate"] is not None else "—"
            self.stdout.write(f"{code:18} {v['reports']:>8} {v['unfounded']:>10} {rr:>7}")
