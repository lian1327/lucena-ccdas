"""
System endpoints (no models):
  GET  /api/v1/health/          host health check (DB reachable)
  GET  /api/v1/public/site/     site mode + identity, read by the frontend at start-up
  POST /api/v1/internal/cron/   scheduled jobs, called every 30 min by GitHub Actions (X-Cron-Token header)
"""
import hmac
import logging
import time

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.utils import timezone
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

log = logging.getLogger("ccadss.cron")


class _Open(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []


class HealthView(_Open):
    @extend_schema(operation_id="health", responses=inline_serializer("Health", {"ok": serializers.BooleanField()}))
    def get(self, request):
        try:
            with connection.cursor() as c:
                c.execute("SELECT 1")
            return Response({"ok": True})
        except Exception:  # noqa: BLE001
            return Response({"ok": False}, status=status.HTTP_503_SERVICE_UNAVAILABLE)


class SiteInfoSerializer(serializers.Serializer):
    mode = serializers.ChoiceField(choices=["official", "prototype"])
    org_name = serializers.CharField()
    contact_email = serializers.CharField(allow_blank=True)
    sample_data = serializers.BooleanField(help_text="Public numbers include generated sample data (label them).")


def site_info():
    from apps.concerns.models import Concern

    sample = cache.get("site_has_sample")
    if sample is None:
        sample = bool(getattr(settings, "CCADSS_PUBLIC_SAMPLE_DATA", True)) and Concern.objects.filter(is_synthetic=True).exists()
        cache.set("site_has_sample", sample, 600)
    mode = str(getattr(settings, "CCADSS_SITE_MODE", "prototype")).lower()
    return {
        "mode": mode if mode in ("official", "prototype") else "prototype",
        "org_name": getattr(settings, "CCADSS_ORG_NAME", "") or "Dalubhasaan ng Lungsod ng Lucena",
        "contact_email": getattr(settings, "CCADSS_CONTACT_EMAIL", ""),
        "sample_data": sample,
    }


class SiteInfoView(_Open):
    @extend_schema(operation_id="public_site", responses=SiteInfoSerializer)
    def get(self, request):
        return Response(site_info())


def run_jobs():
    """Everything a scheduler would run. Each job is isolated so one failure doesn't stop the rest."""
    from apps.cases.services import escalate_overdue
    from apps.notifications import services as ns
    from apps.priority.services import recompute_open_concerns

    jobs = {
        "escalated": escalate_overdue,
        "reminders": ns.queue_reminders,
        "sent": ns.send_due,
        "retried": ns.retry_due,
        "status_synced": ns.sync_statuses,
    }
    if timezone.localtime().hour == 2 or not cache.get("priority_recomputed"):  # once a day is enough
        jobs["priorities"] = recompute_open_concerns
        cache.set("priority_recomputed", True, 60 * 60 * 20)
    out = {}
    for name, fn in jobs.items():
        t = time.monotonic()
        try:
            out[name] = fn()
        except Exception as e:  # noqa: BLE001
            log.exception("cron job %s failed", name)
            out[name] = f"error: {type(e).__name__}"
        out[f"{name}_ms"] = round((time.monotonic() - t) * 1000)
    return out


class CronView(_Open):
    @extend_schema(operation_id="internal_cron", request=None, responses={200: None})
    def post(self, request):
        token = getattr(settings, "CCADSS_CRON_TOKEN", "")
        given = request.headers.get("X-Cron-Token", "")
        if not token or not hmac.compare_digest(token, given):
            return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)
        result = run_jobs()
        log.info("cron %s", result)
        return Response(result)
