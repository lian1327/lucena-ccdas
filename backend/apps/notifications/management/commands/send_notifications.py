import time

from django.core.management.base import BaseCommand

from apps.notifications import services


class Command(BaseCommand):
    help = ("Send queued SMS/email (after quiet hours), retry failures, queue 'Naayos ba talaga?' reminders and "
            "sync delivery status. Schedule every 5 minutes (Windows Task Scheduler / cron), or run with --loop.")

    def add_arguments(self, p):
        p.add_argument("--loop", action="store_true", help="Keep running (development).")
        p.add_argument("--every", type=int, default=60, help="Seconds between runs with --loop.")
        p.add_argument("--purge-days", type=int, default=0, help="Also blank recipients older than N days (RA 10173).")

    def handle(self, *a, **o):
        while True:
            r = services.queue_reminders()
            s = services.send_due()
            f = services.retry_due()
            y = services.sync_statuses()
            msg = f"reminders queued {r} · sent {s} · retried {f} · status synced {y}"
            if o["purge_days"]:
                msg += f" · purged {services.purge(o['purge_days'])}"
            self.stdout.write(msg)
            if not o["loop"]:
                return
            time.sleep(o["every"])
