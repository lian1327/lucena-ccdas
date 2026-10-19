from rest_framework import generics, permissions
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import CCADSSTokenObtainPairSerializer, MeSerializer


class CCADSSTokenObtainPairView(TokenObtainPairView):
    serializer_class = CCADSSTokenObtainPairSerializer
    throttle_scope = "auth_login"


class MeView(generics.RetrieveAPIView):
    serializer_class = MeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user
