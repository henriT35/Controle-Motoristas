from pathlib import Path
import os
from urllib.parse import urlparse
from celery.schedules import crontab

try:
    import environ
except ImportError:
    environ = None

BASE_DIR = Path(__file__).resolve().parent.parent

# Local execution reads .env.local automatically. Production/container
# environments can still provide normal environment variables.
if environ:
    for env_file in (BASE_DIR / ".env.local", BASE_DIR / ".env"):
        if env_file.exists():
            environ.Env.read_env(env_file, overwrite=False, encoding="utf-8-sig")

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-only-change-me")
DEBUG = os.getenv("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = [h.strip() for h in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()]
CSRF_TRUSTED_ORIGINS = [o.strip() for o in os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()]
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

INSTALLED_APPS = [
    "django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes",
    "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles",
    "apps.core", "apps.users", "apps.drivers", "apps.clients", "apps.operations",
    "apps.ssw", "apps.proofs", "apps.dashboard", "apps.reports", "apps.notifications", "apps.audit", "apps.bugs", "apps.messaging",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.core.middleware.ScreenPerformanceMiddleware",
    "apps.core.middleware.ContentSecurityPolicyMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
        "apps.core.context.global_context",
    ]},
}]
WSGI_APPLICATION = "config.wsgi.application"

# Two supported local modes:
# - sqlite (default for zero-setup execution without Docker)
# - postgres (the project target; configure DATABASE_URL in .env.local)
DB_MODE = os.getenv("DATABASE_MODE", "sqlite").strip().lower()
if DB_MODE == "postgres":
    database_url = os.getenv("DATABASE_URL", "").strip()
    if database_url:
        url = urlparse(database_url)
        db_name = url.path.lstrip("/")
        db_user = url.username
        db_password = url.password
        db_host = url.hostname
        db_port = url.port or 5432
    else:
        db_name = os.getenv("DB_NAME", "painel_motoristas")
        db_user = os.getenv("DB_USER", "painel")
        db_password = os.getenv("DB_PASSWORD", "painel")
        db_host = os.getenv("DB_HOST", "localhost")
        db_port = int(os.getenv("DB_PORT", "5432"))
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": db_name,
        "USER": db_user,
        "PASSWORD": db_password,
        "HOST": db_host,
        "PORT": db_port,
        "CONN_MAX_AGE": 60,
    }}
else:
    sqlite_path = os.getenv("SQLITE_PATH", str(BASE_DIR / "local_data" / "painel_motoristas.sqlite3"))
    Path(sqlite_path).parent.mkdir(parents=True, exist_ok=True)
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": sqlite_path,
    }}

LANGUAGE_CODE = "pt-br"
TIME_ZONE = os.getenv("TZ", "America/Belem")
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
SERVE_PROTECTED_MEDIA = os.getenv("SERVE_PROTECTED_MEDIA", "0") == "1"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/dashboard/"
LOGOUT_REDIRECT_URL = "/login/"

CELERY_BROKER_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = CELERY_BROKER_URL
CELERY_TIMEZONE = TIME_ZONE
# In the zero-setup local mode, tasks may run synchronously until Redis/worker
# are intentionally enabled later.
CELERY_TASK_ALWAYS_EAGER = os.getenv("CELERY_TASK_ALWAYS_EAGER", "1" if DB_MODE == "sqlite" else "0") == "1"
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_TASK_ROUTES = {
    # O robô Playwright roda em um worker dedicado na VPS. O restante das
    # tarefas continua na fila default.
    "apps.ssw.tasks.run_robot_import": {"queue": "ssw"},
}
# Beat consulta as rotinas a cada minuto; cada rotina decide sua própria cadência/janela.
CELERY_BEAT_SCHEDULE = {
    "ssw-routine-scheduler": {
        "task": "apps.ssw.tasks.smart_scheduler",
        "schedule": crontab(minute="*"),
    },
    # Fecha obrigações EXACT do dia anterior e materializa ROM13 sem culpa
    # automática. Ouro expira neutro. Rodada diária é suficiente e idempotente.
    "driver-evaluation-housekeeping": {
        "task": "apps.drivers.tasks.evaluation_housekeeping",
        "schedule": crontab(hour=0, minute=5),
    },
}

SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True


AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
SESSION_COOKIE_SECURE = os.getenv("DJANGO_SECURE_COOKIES", "0" if DEBUG else "1") == "1"
CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE
SECURE_SSL_REDIRECT = os.getenv("DJANGO_SECURE_SSL_REDIRECT", "0") == "1"
SECURE_REFERRER_POLICY = "same-origin"

# Integração Painel Motoristas ↔ Robô SSW
SSW_ROBOT_ENABLED = os.getenv("SSW_ROBOT_ENABLED", "0") == "1"
SSW_ROBOT_DIR = os.getenv("SSW_ROBOT_DIR", str(BASE_DIR / "robot_ssw"))
SSW_ROBOT_COMMAND = os.getenv("SSW_ROBOT_COMMAND", "")
SSW_ROBOT_DISPATCH_MODE = os.getenv("SSW_ROBOT_DISPATCH_MODE", "local_process")
SSW_ROBOT_TIMEOUT_SECONDS = int(os.getenv("SSW_ROBOT_TIMEOUT_SECONDS", "900"))
SSW_ROBOT_DISPATCH_TIMEOUT_SECONDS = int(os.getenv("SSW_ROBOT_DISPATCH_TIMEOUT_SECONDS", "90"))
SSW_ROBOT_HEARTBEAT_LOST_SECONDS = int(os.getenv("SSW_ROBOT_HEARTBEAT_LOST_SECONDS", "45"))
SSW_IMPORT_TIMEOUT_SECONDS = int(os.getenv("SSW_IMPORT_TIMEOUT_SECONDS", "3600"))
SSW_ROBOT_HEARTBEAT_SECONDS = int(os.getenv("SSW_ROBOT_HEARTBEAT_SECONDS", "10"))
SSW_ROBOT_ORPHAN_GRACE_SECONDS = int(os.getenv("SSW_ROBOT_ORPHAN_GRACE_SECONDS", "120"))
SSW_ROBOT_UNIT = os.getenv("SSW_ROBOT_UNIT", "BEL")
SSW_ROBOT_OPTION = os.getenv("SSW_ROBOT_OPTION", "036")
SSW_ROBOT_EXCEL = os.getenv("SSW_ROBOT_EXCEL", "S")
SSW_ROBOT_REPORT_TYPE = os.getenv("SSW_ROBOT_REPORT_TYPE", "ROMANEIOS_036")

# Mapa operacional geográfico — thresholds centralizados, sem valores mágicos no frontend.
GEO_DOMINANT_CITY_THRESHOLD = float(os.getenv("GEO_DOMINANT_CITY_THRESHOLD", "0.80"))
GEO_ALERT_MIN_SAMPLE = int(os.getenv("GEO_ALERT_MIN_SAMPLE", "10"))
GEO_OUTLIER_DOMINANCE_THRESHOLD = float(os.getenv("GEO_OUTLIER_DOMINANCE_THRESHOLD", "0.70"))
GEO_OUTLIER_MIN_SHARE = float(os.getenv("GEO_OUTLIER_MIN_SHARE", "0.02"))
GEO_HOME_STATE = os.getenv("GEO_HOME_STATE", "").strip().upper()
GEO_HOME_CITY = os.getenv("GEO_HOME_CITY", "").strip()

# Cache operacional. Na VPS/PostgreSQL usa Redis compartilhado entre web/workers;
# no Windows/SQLite usa LocMem sem dependência externa. A invalidação de fatos
# operacionais é centralizada em apps.core.cache/signals.
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "300"))
if DB_MODE == "postgres" and os.getenv("REDIS_URL", "").strip():
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": os.getenv("REDIS_CACHE_URL", os.getenv("REDIS_URL", "redis://localhost:6379/1")),
            "TIMEOUT": CACHE_TTL_SECONDS,
            "OPTIONS": {"socket_connect_timeout": 2, "socket_timeout": 2},
        }
    }
else:
    # No Windows o painel usa processos separados (Waitress, scheduler e comandos
    # de manutenção). LocMem é isolado por processo e fazia cada tela reconstruir
    # os mesmos agregados. FileBasedCache mantém o modo zero-dependência, mas
    # compartilha o cache entre esses processos e sobrevive a restart do Waitress.
    LOCAL_CACHE_DIR = BASE_DIR / "local_data" / "cache"
    LOCAL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
            "LOCATION": str(LOCAL_CACHE_DIR),
            "TIMEOUT": CACHE_TTL_SECONDS,
            "OPTIONS": {"MAX_ENTRIES": 5000, "CULL_FREQUENCY": 3},
        }
    }

SSW_IMPORT_ENGINE = os.getenv("SSW_IMPORT_ENGINE", "v2")
# Diagnóstico de SQL nas telas críticas. Local/SQLite fica ativo por padrão para
# localizar N+1 e scans caros; VPS pode ativar temporariamente via ambiente.
PERF_SQL_LOG = os.getenv("PERF_SQL_LOG", "1" if DB_MODE == "sqlite" else "0") == "1"

# Logging com rotação para evitar crescimento indefinido no modo local.
LOG_DIR = BASE_DIR / "local_data" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"compact": {"format": "{asctime} {levelname} {name}: {message}", "style": "{"}},
    "handlers": {
        "app_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_DIR / "painel.log",
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 5,
            "formatter": "compact",
            "level": "INFO",
        },
    },
    "loggers": {
        "apps": {"handlers": ["app_file"], "level": "INFO", "propagate": False},
        "apps.performance": {"handlers": ["app_file"], "level": "INFO", "propagate": False},
        "apps.cache": {"handlers": ["app_file"], "level": "INFO", "propagate": False},
    },
}

# URL pública/LAN usada nos links enviados aos motoristas. Em homologação pode
# ficar vazia e o Host da requisição será usado. Em produção prefira HTTPS.
PANEL_PUBLIC_BASE_URL = os.getenv("PANEL_PUBLIC_BASE_URL", "").strip().rstrip("/")

# Bridge WhatsApp em serviço Docker separado. Em modo local permanece False e
# PID/heartbeat são verificados no mesmo sistema operacional. Na VPS, o
# heartbeat compartilhado em local_data é a fonte de vida do container Node.
WHATSAPP_BRIDGE_EXTERNAL_SERVICE = os.getenv("WHATSAPP_BRIDGE_EXTERNAL_SERVICE", "0") == "1"
WHATSAPP_BRIDGE_TRUSTED_INTERNAL = os.getenv("WHATSAPP_BRIDGE_TRUSTED_INTERNAL", "0") == "1"
