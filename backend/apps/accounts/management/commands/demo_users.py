"""
Demo accounts on a public server.

    python manage.py demo_users --list      who exists and whether they still use the published password
    python manage.py demo_users --rotate    give every demo account a new random password (printed once)
    python manage.py demo_users --delete    remove them (do this before a real City pilot)

The demo password is printed in the project documents, so a server reachable from the internet must
never keep it. Accounts that own records are deactivated instead of deleted, to keep the audit trail.
"""
import secrets
import string

from django.core.management.base import BaseCommand, CommandError
from django.db.models.deletion import ProtectedError

from apps.accounts.models import User
from apps.concerns.management.commands.seed_reference_data import DEMO_PASSWORD, DEMO_USERS


def _password():
    alphabet = string.ascii_letters + string.digits
    return "-".join("".join(secrets.choice(alphabet) for _ in range(5)) for _ in range(4))


class Command(BaseCommand):
    help = "List, rotate passwords of, or delete the seeded demo accounts."

    def add_arguments(self, p):
        g = p.add_mutually_exclusive_group(required=True)
        g.add_argument("--list", action="store_true")
        g.add_argument("--rotate", action="store_true")
        g.add_argument("--delete", action="store_true")

    def handle(self, *a, **o):
        names = [u[0] for u in DEMO_USERS]
        users = list(User.objects.filter(username__in=names).order_by("username"))
        if not users:
            raise CommandError("No demo accounts found.")
        if o["list"]:
            for u in users:
                weak = u.check_password(DEMO_PASSWORD)
                self.stdout.write(f"{u.username:22} {u.get_role_display():40} "
                                  f"{'PUBLISHED PASSWORD' if weak else 'ok'}{'' if u.is_active else ' (inactive)'}")
            return
        if o["rotate"]:
            self.stdout.write(self.style.WARNING("New passwords (shown once; store them in a password manager):"))
            for u in users:
                pw = _password()
                u.set_password(pw)
                u.save(update_fields=["password"])
                self.stdout.write(f"  {u.username:22} {pw}")
            return
        removed = deactivated = 0
        for u in users:
            try:
                u.delete()
                removed += 1
            except ProtectedError:
                u.is_active = False
                u.set_unusable_password()
                u.save(update_fields=["is_active", "password"])
                deactivated += 1
        self.stdout.write(self.style.SUCCESS(f"Deleted {removed}, deactivated {deactivated} (they own records)."))
