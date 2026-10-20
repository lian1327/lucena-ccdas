from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny, BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User

from . import pipeline
from .models import ModelVersion
from .services import live_stats

R = User.Role


class SuggestionSerializer(serializers.Serializer):
    category = serializers.CharField()
    category_name = serializers.CharField()
    confidence = serializers.FloatField()
    subcategory = serializers.CharField(allow_null=True)
    subcategory_name = serializers.CharField(allow_null=True)
    subcategory_confidence = serializers.FloatField(allow_null=True)


class ClassifyResultSerializer(SuggestionSerializer):
    top = SuggestionSerializer(many=True)
    model_version = serializers.IntegerField()
    auto = serializers.BooleanField()


class ClassifyRequestSerializer(serializers.Serializer):
    text = serializers.CharField(max_length=3000)


class PublicClassifyView(APIView):
    """Live suggestion while the citizen types ("Mukhang ito ay…"). Nothing is stored."""

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_scope = "public_track"

    @extend_schema(request=ClassifyRequestSerializer, responses=ClassifyResultSerializer, operation_id="public_classify")
    def post(self, request):
        ser = ClassifyRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        text = ser.validated_data["text"]
        if len(text.split()) < 3:
            return Response(status=status.HTTP_204_NO_CONTENT)
        res = pipeline.classify(text)
        return Response(res) if res else Response(status=status.HTTP_204_NO_CONTENT)


class CanSeeModel(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and (u.is_superuser or u.role in (R.CITY_ADMIN, R.MAYOR, R.PACD)))


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and (u.is_superuser or u.role == R.CITY_ADMIN))


class ModelVersionSerializer(serializers.ModelSerializer):
    trained_by = serializers.CharField(source="trained_by.get_full_name", default=None)

    class Meta:
        model = ModelVersion
        fields = ["id", "version", "created_at", "trained_by", "algorithm", "n_train", "n_test", "data_sources",
                  "metrics", "challenge_metrics", "is_active", "notes"]


class LivePointSerializer(serializers.Serializer):
    month = serializers.CharField()
    n = serializers.IntegerField()
    agreement = serializers.FloatField()


class LiveCatSerializer(serializers.Serializer):
    code = serializers.CharField()
    n = serializers.IntegerField()
    agreement = serializers.FloatField()


class ConfusionSerializer(serializers.Serializer):
    actual = serializers.CharField()
    predicted = serializers.CharField()
    count = serializers.IntegerField()


class LiveSerializer(serializers.Serializer):
    n = serializers.IntegerField()
    agreement = serializers.FloatField(allow_null=True)
    sub_agreement = serializers.FloatField(allow_null=True)
    auto_eligible = serializers.IntegerField()
    auto_agreement = serializers.FloatField(allow_null=True)
    by_month = LivePointSerializer(many=True)
    by_category = LiveCatSerializer(many=True)
    top_confusions = ConfusionSerializer(many=True)


class MLOverviewSerializer(serializers.Serializer):
    active = ModelVersionSerializer(allow_null=True)
    versions = ModelVersionSerializer(many=True)
    live = LiveSerializer()
    auto_threshold = serializers.FloatField()


class MLOverviewView(APIView):
    """Active model, its evaluation, earlier versions, and live agreement with PACD."""

    permission_classes = [CanSeeModel]

    @extend_schema(responses=MLOverviewSerializer, operation_id="ml_overview")
    def get(self, request):
        versions = list(ModelVersion.objects.all()[:10])
        active = next((v for v in versions if v.is_active), None) or ModelVersion.objects.filter(is_active=True).first()
        return Response({
            "active": ModelVersionSerializer(active).data if active else None,
            "versions": ModelVersionSerializer(versions, many=True).data,
            "live": live_stats(), "auto_threshold": pipeline.AUTO_THRESHOLD,
        })


class TrainRequestSerializer(serializers.Serializer):
    real_only = serializers.BooleanField(default=False)
    notes = serializers.CharField(required=False, allow_blank=True, max_length=500)


class MLTrainView(APIView):
    """Retrain on all staff-verified reports (≈ 30–60 s). Activated only if not worse than the current model."""

    permission_classes = [IsAdmin]

    @extend_schema(request=TrainRequestSerializer, responses=ModelVersionSerializer, operation_id="ml_train")
    def post(self, request):
        from django.conf import settings
        from pathlib import Path

        ser = TrainRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        challenge = Path(settings.BASE_DIR) / "ml" / "challenge_set.csv"
        try:
            res = pipeline.train(real_only=ser.validated_data["real_only"], challenge_csv=challenge if challenge.exists() else None,
                                 log=lambda *_: None)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        mv = pipeline.save_version(res, user=request.user, notes=ser.validated_data.get("notes", ""))
        return Response(ModelVersionSerializer(mv).data, status=status.HTTP_201_CREATED)


class MLActivateView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(request=None, responses=ModelVersionSerializer, operation_id="ml_activate")
    def post(self, request, pk):
        mv = ModelVersion.objects.get(pk=pk)
        ModelVersion.objects.filter(is_active=True).update(is_active=False)
        mv.is_active = True
        mv.save(update_fields=["is_active"])
        return Response(ModelVersionSerializer(mv).data)
