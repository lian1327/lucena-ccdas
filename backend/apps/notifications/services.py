"""
Citizen notifications (SMS + email) and staff alerts.

Flow:  status change → StatusHistory row → signal → (after commit) queue() renders the message per channel
       → send() now, or later by `manage.py send_notifications` (quiet hours, retries, reminders, status sync).
Nothing is sent while muted() is active (synthetic data, imports, tests).
"""
import threading
from contextlib import contextmanager
from datetime import datetime, time, timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.concerns.models import Concern

from . import conf
from .messages import render_email, render_sms
from .models import Notification, StaffAlert
from .providers import FINAL_FAIL, get_provider
from .sms import normalize_ph_mobile, segments

E = Notification.Event
S = Concern.Status
MAX_ATTEMPTS = 3
_state = threading.local()


@contextmanager
def muted():
    prev = getattr(_state, "muted", False)
    _state.muted = True
    try:
        yield
    finally:
        _state.muted = prev


def is_muted():
    return getattr(_state, "muted", False)


# ---------------------------------------------------------------- which update is worth a message

def event_for(history):
    """Map a public timeline entry to a citizen event, or None (internal steps and repeats send nothing)."""
    if not history.is_public:
        return None
    if not history.from_status:
        return E.RECEIVED
    if history.from_status == history.to_status:
        return None
    t = history.to_status
    if t == S.ASSIGNED:
        return E.ASSIGNED
    if t == S.IN_PROGRESS:
        return E.REOPENED if history.from_status in Concern.DONE_STATUSES else E.IN_PROGRESS
    if t == S.RESOLVED:
        return E.RESOLVED
    if t == S.CLOSED:
        return None if history.from_status == S.RESOLVED else E.CLOSED  # resolved → closed is not news
    if t == S.REJECTED:
        return E.REJECTED
    return None


def on_history(history):
    if is_muted():
        return
    event = event_for(history)
    if event:
        pk = history.pk
        transaction.on_commit(lambda: _queue_history(pk, event))


def _queue_history(history_pk, event):
    from apps.concerns.models import StatusHistory

    h = StatusHistory.objects.select_related("concern").filter(pk=history_pk).first()
    if h:
        queue(h.concern, event, history=h)


def citizen_event(concern, event, extra=None, cascade=True):
    """Explicit events that are not a status change (deadline extension). Also tells linked reporters."""
    if is_muted():
        return
    ids = [concern.pk] + (list(concern.duplicates.values_list("pk", flat=True)) if cascade else [])
    key = f"{event}:{timezone.now():%Y%m%d%H%M}"

    def run():
        for c in Concern.objects.filter(pk__in=ids):
            queue(c, event, extra=extra, dedupe=key)

    transaction.on_commit(run)


# ---------------------------------------------------------------- queue & send

def next_allowed(now=None):
    """Earliest send time outside quiet hours (Asia/Manila)."""
    now = now or timezone.now()
    q = conf.quiet_hours()
    if not q:
        return now
    start, end = q
    local = timezone.localtime(now)
    h = local.hour
    in_quiet = (h >= start or h < end) if start > end else (start <= h < end)
    if not in_quiet:
        return now
    day = local.date() if h < end else local.date() + timedelta(days=1)
    return timezone.make_aware(datetime.combine(day, time(end, 0)), timezone.get_current_timezone())


def channels_for(concern):
    if concern.is_synthetic:  # generated test data never texts anyone
        return []
    out = []
    number = normalize_ph_mobile(concern.reporter_contact)
    if number and concern.notify_sms and not concern.is_anonymous:
        out.append((Notification.Channel.SMS, number))
    if concern.reporter_email and concern.notify_email and conf.flag("NOTIFY_EMAIL") and not concern.is_anonymous:
        out.append((Notification.Channel.EMAIL, concern.reporter_email))
    return out


def queue(concern, event, history=None, extra=None, dedupe=None):
    """Create one Notification per available channel; send right away unless inline sending is off."""
    created = []
    key = dedupe or (f"h{history.pk}" if history else event)
    now = timezone.now()
    for channel, to in channels_for(concern):
        if channel == Notification.Channel.SMS:
            subject, body = "", render_sms(concern, event, history, extra)
            when = next_allowed(now)
        else:
            subject, body = render_email(concern, event, history, extra)
            when = now
        try:
            with transaction.atomic():
                n = Notification.objects.create(
                    concern=concern, history=history, channel=channel, event=event, dedupe_key=key,
                    recipient=to, subject=subject, body=body,
                    segments=segments(body) if channel == Notification.Channel.SMS else 0,
                    scheduled_for=when,
                )
        except IntegrityError:
            continue  # already queued for this update
        created.append(n)
    if conf.flag("NOTIFY_SEND_INLINE"):
        for n in created:
            if n.scheduled_for <= now:
                send(n)
    return created


def send(n, provider=None):
    """Attempt delivery once. Never raises: failures are recorded on the row for the worker to retry."""
    if n.status not in (Notification.Status.QUEUED, Notification.Status.FAILED):
        return n
    n.attempts += 1
    n.last_attempt_at = timezone.now()
    if n.channel == Notification.Channel.SMS:
        p = provider or get_provider()
        r = p.send(n.recipient, n.body)
        n.provider = r.provider
        n.provider_message_id = r.message_id or n.provider_message_id
        n.provider_status = r.status
        n.network = r.network
        n.error = r.error
        if r.ok:
            n.status = Notification.Status.SENT
            n.sent_at = timezone.now()
        else:
            n.status = Notification.Status.FAILED
    else:
        n.provider = "email"
        try:
            send_mail(n.subject, n.body, getattr(settings, "DEFAULT_FROM_EMAIL", None), [n.recipient],
                      fail_silently=False)
            n.status = Notification.Status.SENT
            n.sent_at = timezone.now()
            n.error = ""
        except Exception as e:  # noqa: BLE001 — any SMTP problem is a failed attempt
            n.status = Notification.Status.FAILED
            n.error = f"{type(e).__name__}: {e}"[:1000]
    n.save()
    return n


def retry_due(now=None):
    """Failed rows get up to MAX_ATTEMPTS tries, waiting 5, then 10 minutes between them."""
    now = now or timezone.now()
    done = 0
    for n in Notification.objects.filter(status=Notification.Status.FAILED, attempts__lt=MAX_ATTEMPTS):
        wait = timedelta(minutes=5 * 2 ** max(0, n.attempts - 1))
        if n.last_attempt_at and n.last_attempt_at + wait > now:
            continue
        send(n)
        done += 1
    return done


def send_due(now=None):
    now = now or timezone.now()
    rows = Notification.objects.filter(status=Notification.Status.QUEUED, scheduled_for__lte=now).order_by("scheduled_for")
    provider = get_provider()
    n = 0
    for row in rows[:500]:
        send(row, provider if row.channel == Notification.Channel.SMS else None)
        n += 1
    return n


def queue_reminders(now=None):
    """'Naayos ba talaga?' once, N days after resolution, to reporters who haven't answered."""
    now = now or timezone.now()
    days = int(conf.get("NOTIFY_REMINDER_DAYS") or 0)
    if days <= 0:
        return 0
    from apps.cases.services import CONFIRM_WINDOW_DAYS

    qs = Concern.objects.filter(
        status=S.RESOLVED, citizen_confirmation="",
        resolved_at__lte=now - timedelta(days=days),
        resolved_at__gte=now - timedelta(days=CONFIRM_WINDOW_DAYS - 1),
    ).exclude(notifications__event=E.REMINDER)
    n = 0
    for c in qs:
        n += len(queue(c, E.REMINDER, dedupe="reminder"))
    return n


def sync_statuses(now=None):
    """Ask the provider what happened to recent SMS (Sent / Failed / Refunded)."""
    now = now or timezone.now()
    provider = get_provider()
    rows = Notification.objects.filter(
        channel=Notification.Channel.SMS, status=Notification.Status.SENT, provider=provider.name,
        sent_at__gte=now - timedelta(days=3),
    ).exclude(provider_message_id="")
    n = 0
    for row in rows[:200]:
        r = provider.fetch(row.provider_message_id)
        if not r:
            continue
        s = r.status.lower()
        row.provider_status = r.status
        row.network = r.network or row.network
        if s == "sent":
            row.status = Notification.Status.DELIVERED
        elif s in FINAL_FAIL:
            row.status = Notification.Status.FAILED
            row.error = f"Network rejected the message ({r.status})."
            row.attempts = MAX_ATTEMPTS  # a network rejection won't change on retry
        row.save(update_fields=["provider_status", "network", "status", "error", "attempts"])
        n += 1
    return n


def purge(days=365):
    """RA 10173 retention: keep the log, drop the phone number / email after `days`."""
    cutoff = timezone.now() - timedelta(days=days)
    return Notification.objects.filter(created_at__lt=cutoff).exclude(recipient="").update(recipient="")


# ---------------------------------------------------------------- staff alerts

def _staff(**filters):
    from apps.accounts.models import User

    return User.objects.filter(is_active=True, **filters)


def alert(users, kind, concern, title, body="", urgent=False, exclude=None):
    if is_muted() or (concern is not None and concern.is_synthetic):  # sample data never rings anyone's bell
        return 0
    rows, seen = [], set()
    for u in users:
        if not u or u.pk in seen or (exclude and u.pk == exclude.pk):
            continue
        seen.add(u.pk)
        rows.append(StaffAlert(user=u, kind=kind, concern=concern, title=title[:160], body=body[:300], is_urgent=urgent))
    StaffAlert.objects.bulk_create(rows)
    return len(rows)


def office_leads(case):
    """Who receives and validates for an office: desk + head, and the division chief if a division is set."""
    from apps.accounts.models import User

    if not case or not case.department_id:
        return []
    R = User.Role
    users = list(_staff(department_id=case.department_id, role__in=[R.OFFICE_DESK, R.DEPT_HEAD]))
    if case.division_id:
        users += list(_staff(division_id=case.division_id, role=R.DIVISION_CHIEF))
    return users


def pacd_staff():
    from apps.accounts.models import User

    return _staff(role=User.Role.PACD)


def escalation_targets(case):
    from apps.accounts.models import User

    R = User.Role
    if case.escalation_level == 1:
        return _staff(department_id=case.department_id, role=R.DEPT_HEAD) if case.department_id else []
    if case.escalation_level == 2:
        return _staff(role=R.CITY_ADMIN)
    return _staff(role=R.MAYOR)
