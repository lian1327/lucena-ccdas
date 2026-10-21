"""
Notification settings. Each can be set in settings.py (CCADSS_<NAME>) or as an environment variable (<NAME>).

    SMS_PROVIDER        console | semaphore | disabled     (default console: printed to the log, nothing sent)
    SEMAPHORE_API_KEY   from semaphore.co → Account → API
    SMS_SENDER_NAME     registered sender name (blank = the account's default)
    SMS_SIGNATURE       appended to every SMS, default "LGU Lucena"
    PUBLIC_SITE_URL     base of tracking links, e.g. https://concerns.lucenacity.gov.ph
    SMS_QUIET_HOURS     "21-7": SMS created in this window wait until 7:00 (Asia/Manila)
    NOTIFY_SEND_INLINE  1 = send right after the request commits; 0 = only the worker sends
    NOTIFY_EMAIL        1 = also email reporters who gave an address
    NOTIFY_REMINDER_DAYS days after "resolved" to ask "Naayos ba talaga?" (0 = off)
"""
import os

from django.conf import settings

DEFAULTS = {
    "SMS_PROVIDER": "console",
    "SEMAPHORE_API_KEY": "",
    "SMS_SENDER_NAME": "",
    "SMS_SIGNATURE": "LGU Lucena",
    "PUBLIC_SITE_URL": "http://localhost:5173",
    "SMS_QUIET_HOURS": "21-7",
    "NOTIFY_SEND_INLINE": "1",
    "NOTIFY_EMAIL": "1",
    "NOTIFY_REMINDER_DAYS": "3",
}


def get(name):
    v = getattr(settings, f"CCADSS_{name}", None)
    if v is None:
        v = os.environ.get(name, DEFAULTS[name])
    return v


def flag(name):
    return str(get(name)).strip().lower() in ("1", "true", "yes", "on")


def quiet_hours():
    """(start_hour, end_hour) or None."""
    raw = str(get("SMS_QUIET_HOURS") or "").strip()
    if not raw or raw == "0":
        return None
    a, b = raw.split("-")
    return int(a), int(b)


def site_url():
    return str(get("PUBLIC_SITE_URL")).rstrip("/")
