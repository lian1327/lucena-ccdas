from django.urls import path
from rest_framework_simplejwt.views import TokenBlacklistView, TokenRefreshView

from .views import CCADSSTokenObtainPairView, MeView

urlpatterns = [
    path("token/", CCADSSTokenObtainPairView.as_view(), name="token_obtain"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("logout/", TokenBlacklistView.as_view(), name="token_blacklist"),
    path("me/", MeView.as_view(), name="me"),
]
