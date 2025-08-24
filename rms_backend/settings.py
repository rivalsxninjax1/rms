# rms_backend/settings.py
import os
from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env from project root
load_dotenv(BASE_DIR / ".env")

# ---------------- Core ----------------
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-not-for-prod")
DEBUG = os.getenv("DJANGO_DEBUG", "1") == "1"

def _split_list(val: str, default=""):
    raw = os.getenv(val, default)
    return [x.strip() for x in raw.split(",") if x.strip()]

ALLOWED_HOSTS = _split_list("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost")

AUTH_USER_MODEL = "accounts.User"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

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

    # 3rd party
    "rest_framework",
    "django_filters",
    "drf_spectacular",
    "corsheaders",
    "whitenoise.runserver_nostatic",  # optional: ensure whitenoise in dev

    # Local apps
    "accounts",
    "core",
    "inventory",
    "menu",
    "orders",
    "reservations",
    "reports",
    "billing",
    "payments",
    "promotions",
    "storefront",
]

# ---------------- Middleware ----------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # static in prod

    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",

    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

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
            # your storefront context
            "storefront.context.site_context",
        ],
    },
}]

# ---------------- Database ----------------
if os.getenv("DATABASE_URL"):
    import urllib.parse as urlparse
    for scheme in ["postgres", "postgresql"]:
        if scheme not in urlparse.uses_netloc:
            urlparse.uses_netloc.append(scheme)
    url = urlparse.urlparse(os.environ["DATABASE_URL"])
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": url.path[1:],
            "USER": url.username,
            "PASSWORD": url.password,
            "HOST": url.hostname,
            "PORT": url.port or "",
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# ---------------- DRF + JWT ----------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend"
    ],
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

SITE_URL = os.getenv("SITE_URL", "http://localhost:8000").rstrip("/")
DOMAIN = os.getenv("DOMAIN", SITE_URL).rstrip("/")

_origins = _split_space("DJANGO_CSRF_TRUSTED_ORIGINS", "")
if SITE_URL:
    _origins.append(SITE_URL)
CSRF_TRUSTED_ORIGINS = list({o.rstrip("/") for o in _origins})

# ---------------- Stripe ----------------
STRIPE_PUBLIC_KEY = os.getenv("STRIPE_PUBLIC_KEY", "")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_CURRENCY = os.getenv("STRIPE_CURRENCY", "usd").lower()

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/my-orders/"
LOGOUT_REDIRECT_URL = "/"
