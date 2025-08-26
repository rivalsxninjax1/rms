# rms_backend/settings.py
import os
from pathlib import Path
from datetime import timedelta
from urllib.parse import urlparse
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# ---------------- Core ----------------
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-not-for-prod")
DEBUG = os.getenv("DJANGO_DEBUG", "1") == "1"

def _split_list(var: str, default: str = ""):
    raw = os.getenv(var, default)
    return [x.strip() for x in raw.split(",") if x.strip()]

ALLOWED_HOSTS = _split_list("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"

TIME_ZONE = os.getenv("TIME_ZONE", "Asia/Kathmandu")
USE_TZ = True
LANGUAGE_CODE = "en-us"
USE_I18N = True

# ---------------- Apps ----------------
INSTALLED_APPS = [
    # Django
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # 3rd-party
    "rest_framework",
    "django_filters",
    "drf_spectacular",
    "corsheaders",
    "whitenoise.runserver_nostatic",  # for runserver; Whitenoise middleware serves static in prod

    # Local apps
    "accounts",
    "core",
    "inventory",
    "menu",
    "orders.apps.OrdersConfig",       # ensure signals (merge on login) load
    "reservations",
    "reports",
    "billing",
    "payments",
    "coupons",
     "loyality",
    "storefront",
]


# ---------------- Celery ----------------
# Broker & backend: Redis by default; set via env if you prefer RabbitMQ, etc.
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://127.0.0.1:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)

CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
# Keep Celery aligned with your Django timezone
CELERY_TIMEZONE = locals().get("TIME_ZONE", "UTC")

# Beat schedule: runs every 5 minutes
CELERY_BEAT_SCHEDULE = {
    "mark-no-show-reservations-every-5-minutes": {
        "task": "reservations.tasks_portal.mark_no_show_reservations",
        "schedule": 300.0,  # seconds
    },
}



# ---------------- Middleware ----------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # static in prod
    
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "orders.middleware.EnsureCartInitializedMiddleware",  # custom cart init for anonymous users
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# Optional canonical host in prod (prevents www/non-www cookie split)
CANONICAL_HOST = os.getenv("CANONICAL_HOST", "").strip()
if CANONICAL_HOST and not DEBUG:
    # Insert after SecurityMiddleware (index 1)
    MIDDLEWARE.insert(1, "core.middleware.CanonicalHostMiddleware")

ROOT_URLCONF = "rms_backend.urls"
WSGI_APPLICATION = "rms_backend.wsgi.application"
ASGI_APPLICATION = "rms_backend.asgi.application"

# ---------------- Templates ----------------
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {
        "context_processors": [
            "django.template.context_processors.debug",
            "django.template.context_processors.request",
            "django.contrib.auth.context_processors.auth",
            "django.contrib.messages.context_processors.messages",
            "storefront.context.site_context",
        ],
    },
}]

# ---------------- Database ----------------
DATABASE_URL = os.getenv("DATABASE_URL", "")
if DATABASE_URL:
    u = urlparse(DATABASE_URL)
    engine = "django.db.backends.postgresql"
    if u.scheme.startswith("mysql"):
        engine = "django.db.backends.mysql"
    DATABASES = {
        "default": {
            "ENGINE": engine,
            "NAME": u.path.lstrip("/"),
            "USER": u.username,
            "PASSWORD": u.password,
            "HOST": u.hostname,
            "PORT": str(u.port or ""),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# ---------------- Sessions (stable across requests) ----------------
SESSION_ENGINE = "django.contrib.sessions.backends.db"  # DB-backed sessions
SESSION_COOKIE_AGE = int(os.getenv("SESSION_COOKIE_AGE", str(60 * 60 * 24 * 14)))  # 14 days
SESSION_SAVE_EVERY_REQUEST = False

# Cookie security depends on DEBUG
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
CSRF_COOKIE_SAMESITE = os.getenv("CSRF_COOKIE_SAMESITE", "Lax")

# Optional cookie domain for subdomains (e.g., ".example.com")
SESSION_COOKIE_DOMAIN = os.getenv("SESSION_COOKIE_DOMAIN") or None
CSRF_COOKIE_DOMAIN = os.getenv("CSRF_COOKIE_DOMAIN") or None

# ---------------- DRF + JWT ----------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_FILTER_BACKENDS": ["django_filters.rest_framework.DjangoFilterBackend"],
    "DEFAULT_PARSER_CLASSES": (
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.FormParser",
        "rest_framework.parsers.MultiPartParser",
    ),
}
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}
SPECTACULAR_SETTINGS = {
    "TITLE": "RMS API",
    "DESCRIPTION": "Restaurant/E-commerce API",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# ---------------- Static / Media ----------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"] if (BASE_DIR / "static").exists() else []
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
WHITENOISE_USE_FINDERS = True

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ---------------- CORS / CSRF ----------------
CORS_ALLOW_ALL_ORIGINS = True if DEBUG else False

def _split_space(name: str, default=""):
    return [x for x in os.getenv(name, default).split() if x]

# Example for local
SITE_URL = os.getenv("SITE_URL", "http://127.0.0.1:8000")
DOMAIN = os.getenv("DOMAIN", SITE_URL)

# CSRF_TRUSTED_ORIGINS must include scheme in Django 4+
_csrf = set()
for v in _split_list("DJANGO_CSRF_TRUSTED_ORIGINS", ""):
    _csrf.add(v.rstrip("/"))
if SITE_URL:
    _csrf.add(SITE_URL)
parsed_dom = urlparse(DOMAIN if "://" in DOMAIN else f"http://{DOMAIN}")
if parsed_dom.netloc:
    _csrf.add(f"http://{parsed_dom.netloc}")
    _csrf.add(f"https://{parsed_dom.netloc}")
CSRF_TRUSTED_ORIGINS = sorted(_csrf)

# ---------------- Stripe ----------------
STRIPE_PUBLIC_KEY = os.getenv("STRIPE_PUBLIC_KEY", "")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_CURRENCY = os.getenv("STRIPE_CURRENCY", "usd").lower()

# ---------------- Auth redirects ----------------
LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/my-orders/"
LOGOUT_REDIRECT_URL = "/"

# ---------------- Aggregators (optional) ----------------
UBEREATS_ORDER_URL = os.getenv("UBEREATS_ORDER_URL", "")
DOORDASH_ORDER_URL = os.getenv("DOORDASH_ORDER_URL", "")
