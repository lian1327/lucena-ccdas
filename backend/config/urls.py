from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apps.classifier.views import PublicClassifyView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/auth/", include("apps.accounts.urls")),
    path("api/v1/public/", include("apps.concerns.urls_public")),
    path("api/v1/staff/map/", include("apps.geo.urls_staff")),
    path("api/v1/staff/analytics/", include("apps.analytics.urls")),
    path("api/v1/staff/ml/", include("apps.classifier.urls")),
    path("api/v1/public/classify/", PublicClassifyView.as_view(), name="public-classify"),
    path("api/v1/staff/", include("apps.notifications.urls")),
    path("api/v1/staff/", include("apps.cases.urls_staff")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
