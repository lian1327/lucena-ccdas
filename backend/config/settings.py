"""
CCADSS settings — one file for development and production. Everything that differs comes from .env
(local) or the host's environment variables (Render). See DEPLOY.md for the full list.
"""
from datetime import timedelta
from pathlib import Path

from decouple import Csv, config

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config("SECRET_KEY")
DEBUG = config("DEBUG", default=False, cast=bool)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,127.0.0.1", cast=Csv())
RENDER_HOST = config("RENDER_EXTERNAL_HOSTNAME", default="")  # set automatically by Render
if RENDER_HOST:
    ALLOWED_HOSTS.append(RENDER_HOST)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # third-party
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_filters",
    "drf_spectacular",
    "storages",
    # local
    "apps.accounts",
    "apps.geo",
    "apps.concerns",
    "apps.cases",
    "apps.classification",
    "apps.priority",
    "apps.analytics",
    "apps.reports",
    "apps.notifications",
    "apps.classifier",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # serves /static/ (Django admin) without Nginx
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]

WSGI_APPLICATION = "config.wsgi.application"

# ---------------------------------------------------------------- database
# Production (Neon): DATABASE_URL=postgresql://user:pass@host/db?sslmode=require  (use the DIRECT, non-pooled URL)
# Local: the DB_* variables you already have.
DATABASE_URL = config("DATABASE_URL", default="")
if DATABASE_URL:
    import dj_database_url

    DATABASES = {"default": dj_database_url.parse(DATABASE_URL, conn_max_age=60, conn_health_checks=True,
                                                  ssl_require=DATABASE_URL.startswith("postgres") and not DEBUG)}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": config("DB_NAME"),
            "USER": config("DB_USER"),
            "PASSWORD": config("DB_PASSWORD"),
            "HOST": config("DB_HOST", default="localhost"),
            "PORT": config("DB_PORT", default="5432"),
        }
    }

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Manila"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------- files
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Photos (citizen reports, before/after proof) and trained models go to S3-compatible object storage in
# production (Backblaze B2 or Cloudflare R2), because free hosts wipe their disk on every restart.
# The bucket stays PRIVATE: every photo URL is signed and expires after an hour.
MEDIA_S3_BUCKET = config("MEDIA_S3_BUCKET", default="")
_static = {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage" if not DEBUG
           else "django.contrib.staticfiles.storage.StaticFilesStorage"}
if MEDIA_S3_BUCKET:
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": {
                "bucket_name": MEDIA_S3_BUCKET,
                # B2: https://s3.<region>.backblazeb2.com   R2: https://<account_id>.r2.cloudflarestorage.com
                "endpoint_url": config("MEDIA_S3_ENDPOINT"),
                "region_name": config("MEDIA_S3_REGION", default="auto"),  # B2: e.g. us-west-004 · R2: auto
                "access_key": config("MEDIA_S3_ACCESS_KEY_ID"),
                "secret_key": config("MEDIA_S3_SECRET_ACCESS_KEY"),
                "signature_version": "s3v4",
                "addressing_style": "path",
                "default_acl": None,
                "querystring_auth": True,                       # signed URLs
                "querystring_expire": 3600,                     # valid for 1 hour
                "file_overwrite": False,
            },
        },
        "staticfiles": _static,
    }
else:
    STORAGES = {"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"}, "staticfiles": _static}

DATA_UPLOAD_MAX_MEMORY_SIZE = 30 * 1024 * 1024  # 5 images × 5 MB + form
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------- API
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.ScopedRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {"public_submit": "10/hour", "public_track": "60/minute", "auth_login": "20/hour"},
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "CCADSS API",
    "DESCRIPTION": "LGU Citizen Concern Analytics and Decision Support System",
    "VERSION": "1.0.0",
    "COMPONENT_SPLIT_REQUEST": True,
    "SERVE_INCLUDE_SCHEMA": False,
    # Public API docs only while developing; in production the schema needs a staff login
    "SERVE_PERMISSIONS": ["rest_framework.permissions.AllowAny"] if DEBUG else ["rest_framework.permissions.IsAdminUser"],
    "ENUM_NAME_OVERRIDES": {
        "ConcernStatusEnum": "apps.concerns.models.Concern.Status",
        "ConcernChannelEnum": "apps.concerns.models.Concern.Channel",
        "EndorsementStatusEnum": "apps.cases.models.Endorsement.Status",
        "NotificationStatusEnum": "apps.notifications.models.Notification.Status",
        "NotificationChannelEnum": "apps.notifications.models.Notification.Channel",
    },
}

CORS_ALLOWED_ORIGINS = config("CORS_ALLOWED_ORIGINS", default="http://localhost:5173", cast=Csv())
CSRF_TRUSTED_ORIGINS = config("CSRF_TRUSTED_ORIGINS", default="http://localhost:5173", cast=Csv())

# ---------------------------------------------------------------- CCADSS engines
PRIORITY_SCORING = {
    "WEIGHTS": {"severity": 0.35, "affected": 0.25, "duplicates": 0.20, "delay": 0.20},
    "AFFECTED_CAP": 1000,
    "DUPLICATE_CAP": 10,
}
DUPLICATE_DETECTION = {"RADIUS_M": 100, "WINDOW_DAYS": 14}
SERVICE_AREA_BOUNDS = {"lat": (13.85, 14.05), "lng": (121.53, 121.70)}  # rough Lucena box

# ---------------------------------------------------------------- site mode (Step 16)
# official  = the City's portal (only with the City's written authorization)
# prototype = research prototype: no GOVPH/seal, banner says reports do not reach City Hall
CCADSS_SITE_MODE = config("SITE_MODE", default="prototype")
CCADSS_ORG_NAME = config("ORG_NAME", default="Dalubhasaan ng Lungsod ng Lucena")
CCADSS_CONTACT_EMAIL = config("CONTACT_EMAIL", default="")
# Show generated sample data on the public landing page (always labelled "halimbawang datos")
CCADSS_PUBLIC_SAMPLE_DATA = config("PUBLIC_SAMPLE_DATA", default=True, cast=bool)
CCADSS_CRON_TOKEN = config("CRON_TOKEN", default="")
ADMIN_URL = config("ADMIN_URL", default="admin/")

# ---------------------------------------------------------------- notifications (Step 15)
CCADSS_SMS_PROVIDER = config("SMS_PROVIDER", default="console")
CCADSS_SEMAPHORE_API_KEY = config("SEMAPHORE_API_KEY", default="")
CCADSS_SMS_SENDER_NAME = config("SMS_SENDER_NAME", default="")
CCADSS_SMS_SIGNATURE = config("SMS_SIGNATURE", default="LGU Lucena")
CCADSS_PUBLIC_SITE_URL = config("PUBLIC_SITE_URL", default="http://localhost:5173")
CCADSS_SMS_QUIET_HOURS = config("SMS_QUIET_HOURS", default="21-7")
CCADSS_NOTIFY_SEND_INLINE = config("NOTIFY_SEND_INLINE", default="1")
CCADSS_NOTIFY_EMAIL = config("NOTIFY_EMAIL", default="1")
CCADSS_NOTIFY_REMINDER_DAYS = config("NOTIFY_REMINDER_DAYS", default="3")

EMAIL_BACKEND = config("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = config("EMAIL_HOST", default="")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=True, cast=bool)
EMAIL_TIMEOUT = 10
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="CCADSS Lucena <itsolutions@dll.edu.ph>")

CELERY_BROKER_URL = config("CELERY_BROKER_URL", default="redis://localhost:6379/0")
CELERY_TIMEZONE = TIME_ZONE

# ---------------------------------------------------------------- production security
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SECURE_REDIRECT_EXEMPT = [r"^api/v1/health/$"]  # the host's health check calls plain HTTP
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = config("HSTS_SECONDS", default=3600, cast=int)  # raise to 31536000 once stable
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
    X_FRAME_OPTIONS = "DENY"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"plain": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "plain"}},
    "root": {"handlers": ["console"], "level": "INFO" if not DEBUG else "WARNING"},
    "loggers": {"django.request": {"handlers": ["console"], "level": "WARNING", "propagate": False}},
}
