"""
SMS providers. Each returns a Result; none raise for an ordinary delivery failure.
Semaphore (https://api.semaphore.co/docs): POST /api/v4/messages with apikey, number, message, sendername.
Messages that start with the word "TEST" are silently dropped by Semaphore, so render() never starts with it.
"""
import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

from . import conf

log = logging.getLogger("ccadss.sms")

SEMAPHORE_URL = "https://api.semaphore.co/api/v4"
FINAL_OK = {"sent"}
FINAL_FAIL = {"failed", "refunded"}


@dataclass
class Result:
    ok: bool
    provider: str
    message_id: str = ""
    status: str = ""
    network: str = ""
    error: str = ""
    raw: dict = field(default_factory=dict)


class ConsoleProvider:
    """Development: prints the SMS to the server log. Nothing leaves the machine and no credits are used."""

    name = "console"

    def send(self, number, text):
        log.info("SMS (console) → %s: %s", number, text)
        print(f"[SMS console] → {number}: {text}")
        return Result(ok=True, provider=self.name, status="Sent")

    def fetch(self, message_id):
        return None

    def balance(self):
        return None


class DisabledProvider(ConsoleProvider):
    name = "disabled"

    def send(self, number, text):
        return Result(ok=False, provider=self.name, error="SMS sending is disabled (SMS_PROVIDER=disabled).")


class SemaphoreProvider:
    name = "semaphore"

    def __init__(self, api_key, sender_name="", timeout=8):
        self.api_key = api_key
        self.sender_name = sender_name
        self.timeout = timeout

    def _call(self, method, path, params):
        params = {**params, "apikey": self.api_key}
        data = None
        url = f"{SEMAPHORE_URL}{path}"
        if method == "GET":
            url += "?" + urllib.parse.urlencode(params)
        else:
            data = urllib.parse.urlencode(params).encode()
        req = urllib.request.Request(url, data=data, method=method,
                                     headers={"Accept": "application/json", "User-Agent": "CCADSS/1.0"})
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode() or "null")

    def send(self, number, text):
        if not self.api_key:
            return Result(ok=False, provider=self.name, error="SEMAPHORE_API_KEY is not set.")
        params = {"number": number, "message": text}
        if self.sender_name:
            params["sendername"] = self.sender_name
        try:
            payload = self._call("POST", "/messages", params)
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")[:500]
            return Result(ok=False, provider=self.name, error=f"HTTP {e.code}: {body}")
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            return Result(ok=False, provider=self.name, error=f"Network error: {e}")
        except ValueError:
            return Result(ok=False, provider=self.name, error="Provider returned a non-JSON reply.")
        # Success is a list with one object per recipient; errors come back as a dict of field → messages.
        if isinstance(payload, list) and payload and isinstance(payload[0], dict) and payload[0].get("message_id"):
            m = payload[0]
            status = str(m.get("status", ""))
            return Result(ok=status.lower() not in FINAL_FAIL, provider=self.name,
                          message_id=str(m.get("message_id")), status=status, network=str(m.get("network") or ""),
                          raw=m, error="" if status.lower() not in FINAL_FAIL else f"Provider status {status}")
        return Result(ok=False, provider=self.name, error=f"Rejected: {json.dumps(payload)[:500]}")

    def fetch(self, message_id):
        """Current status of one message, or None if it could not be read."""
        try:
            payload = self._call("GET", f"/messages/{message_id}", {})
        except Exception:  # noqa: BLE001 — status sync is best-effort
            return None
        m = payload[0] if isinstance(payload, list) and payload else payload
        if not isinstance(m, dict):
            return None
        return Result(ok=True, provider=self.name, message_id=str(message_id), status=str(m.get("status", "")),
                      network=str(m.get("network") or ""), raw=m)

    def balance(self):
        try:
            payload = self._call("GET", "/account", {})
        except Exception:  # noqa: BLE001
            return None
        return payload.get("credit_balance") if isinstance(payload, dict) else None


def get_provider():
    name = str(conf.get("SMS_PROVIDER")).strip().lower()
    if name == "semaphore":
        return SemaphoreProvider(str(conf.get("SEMAPHORE_API_KEY")), str(conf.get("SMS_SENDER_NAME") or ""))
    if name == "disabled":
        return DisabledProvider()
    return ConsoleProvider()
