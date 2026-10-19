from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import User


class CCADSSTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Adds role/scope claims so the frontend can route without an extra request."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["username"] = user.username
        token["full_name"] = user.get_full_name() or user.username
        token["role"] = user.role
        token["barangay_id"] = user.barangay_id
        token["department_id"] = user.department_id
        return token


class MeSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    role_display = serializers.CharField(source="get_role_display", read_only=True)
    barangay = serializers.CharField(source="barangay.name", default=None, read_only=True)
    department = serializers.CharField(source="department.name", default=None, read_only=True)

    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name", "full_name",
                  "role", "role_display", "barangay", "department"]
        read_only_fields = fields

    def get_full_name(self, obj) -> str:
        return obj.get_full_name() or obj.username
