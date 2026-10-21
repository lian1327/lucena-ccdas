from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.permissions import STAFF_ROLES, HasRole
from apps.concerns.models import Concern

from . import conf, services
from .models import Notification, StaffAlert
from .providers import get_provider
from .serializers import (
    NotificationPageSerializer,
    NotificationSerializer,
    NotificationStatsSerializer,
    StaffAlertListSerializer,
    StaffAlertSerializer,
)

R = User.Role
LOG_ROLES = (R.CITY_ADMIN, R.MAYOR, R.PACD)


class AlertListView(APIView):
    """The signed-in staff member's bell: latest 30 alerts plus unread counts."""

    permission_classes = [HasRole(*STAFF_ROLES)]

    @extend_schema(operation_id="staff_alerts_list", responses=StaffAlertListSerializer,
                   parameters=[OpenApiParameter("unread", bool, required=False)])
    def get(self, request):
        qs = StaffAlert.objects.filter(user=request.user).select_related("concern")
        counts = qs.filter(read_at__isnull=True).aggregate(n=Count("id"), u=Count("id", filter=Q(is_urgent=True)))
        if request.query_params.get("unread") in ("1", "true"):
            qs = qs.filter(read_at__isnull=True)
        return Response({"unread": counts["n"], "urgent_unread": counts["u"],
                         "results": StaffAlertSerializer(qs[:30], many=True).data})


class AlertReadView(APIView):
    permission_classes = [HasRole(*STAFF_ROLES)]

    @extend_schema(operation_id="staff_alerts_read", request=None, responses=StaffAlertSerializer)
    def post(self, request, pk):
        a = get_object_or_404(StaffAlert, pk=pk, user=request.user)
        if not a.read_at:
            a.read_at = timezone.now()
            a.save(update_fields=["read_at"])
        return Response(StaffAlertSerializer(a).data)


class AlertReadAllView(APIView):
    permission_classes = [HasRole(*STAFF_ROLES)]

    @extend_schema(operation_id="staff_alerts_read_all", request=None, responses={200: None})
    def post(self, request):
        n = StaffAlert.objects.filter(user=request.user, read_at__isnull=True).update(read_at=timezone.now())
        return Response({"marked": n})


class NotificationLogView(APIView):
    """Citizen SMS/email log (recipients masked). PACD, City Administrator and Mayor's Office."""

    permission_classes = [HasRole(*LOG_ROLES)]

    @extend_schema(
        operation_id="staff_notifications_list", responses=NotificationPageSerializer,
        parameters=[OpenApiParameter(n, str, required=False) for n in ("status", "channel", "event", "q", "page")],
    )
    def get(self, request):
        qs = Notification.objects.select_related("concern")
        p = request.query_params
        for f in ("status", "channel", "event"):
            if p.get(f):
                qs = qs.filter(**{f: p[f]})
        if p.get("q"):
            qs = qs.filter(concern__reference_no__icontains=p["q"].strip())
        page = max(1, int(p.get("page") or 1))
        size = 25
        return Response({"count": qs.count(),
                         "results": NotificationSerializer(qs[(page - 1) * size: page * size], many=True).data})


class NotificationStatsView(APIView):
    permission_classes = [HasRole(*LOG_ROLES)]

    @extend_schema(operation_id="staff_notifications_stats", responses=NotificationStatsSerializer)
    def get(self, request):
        now = timezone.localtime()
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month = Notification.objects.filter(created_at__gte=start)
        sms = month.filter(channel=Notification.Channel.SMS)
        agg = sms.aggregate(n=Count("id"), credits=Sum("segments", filter=~Q(status=Notification.Status.SKIPPED)),
                            delivered=Count("id", filter=Q(status=Notification.Status.DELIVERED)),
                            final=Count("id", filter=Q(status__in=[Notification.Status.DELIVERED, Notification.Status.FAILED])))
        reports = Concern.objects.filter(created_at__gte=start, is_synthetic=False)
        reachable = reports.filter(~Q(reporter_contact="") | ~Q(reporter_email=""), is_anonymous=False).count()
        provider = get_provider()
        return Response({
            "provider": provider.name,
            "sender_name": str(conf.get("SMS_SENDER_NAME") or ""),
            "credit_balance": provider.balance(),
            "month_sms": agg["n"],
            "month_credits": agg["credits"] or 0,
            "month_email": month.filter(channel=Notification.Channel.EMAIL).count(),
            "delivered_rate": round(100 * agg["delivered"] / agg["final"], 1) if agg["final"] else None,
            "failed": Notification.objects.filter(status=Notification.Status.FAILED).count(),
            "queued": Notification.objects.filter(status=Notification.Status.QUEUED).count(),
            "opted_out": Concern.objects.filter(notify_sms=False).exclude(reporter_contact="").count(),
            "reach_rate": round(100 * reachable / reports.count(), 1) if reports.exists() else None,
        })


class NotificationRetryView(APIView):
    permission_classes = [HasRole(R.CITY_ADMIN, R.PACD)]

    @extend_schema(operation_id="staff_notifications_retry", request=None, responses=NotificationSerializer)
    def post(self, request, pk):
        n = get_object_or_404(Notification, pk=pk)
        if n.status != Notification.Status.FAILED or not n.recipient:
            return Response({"detail": "Only failed messages with a recipient can be retried."},
                            status=status.HTTP_400_BAD_REQUEST)
        services.send(n)
        return Response(NotificationSerializer(n).data)
