from django.core.management.base import BaseCommand, CommandError

from apps.notifications import conf
from apps.notifications.providers import get_provider
from apps.notifications.sms import normalize_ph_mobile, segments, to_gsm


class Command(BaseCommand):
    help = "Check the SMS setup: shows provider and balance, and with --to sends one real message."

    def add_arguments(self, p):
        p.add_argument("--to", help="Your own mobile number, e.g. 09171234567")

    def handle(self, *a, **o):
        p = get_provider()
        self.stdout.write(f"Provider: {p.name} · sender: {conf.get('SMS_SENDER_NAME') or '(account default)'}")
        self.stdout.write(f"Credit balance: {p.balance()}")
        if not o.get("to"):
            return
        number = normalize_ph_mobile(o["to"])
        if not number:
            raise CommandError("Not a Philippine mobile number.")
        # Semaphore ignores messages that begin with the word TEST, so this one doesn't.
        text = to_gsm(f"CCADSS: gumagana ang SMS notifications. -{conf.get('SMS_SIGNATURE')}")
        r = p.send(number, text)
        self.stdout.write(f"{'OK' if r.ok else 'FAILED'} · {segments(text)} part(s) · id={r.message_id} "
                          f"status={r.status} {r.error}")
