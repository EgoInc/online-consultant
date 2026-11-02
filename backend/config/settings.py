import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "local-development-only")
DEBUG = os.getenv("DJANGO_DEBUG", "true").lower() == "true"
ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,backend,testserver").split(",")
INSTALLED_APPS = [
    "django.contrib.contenttypes", "django.contrib.staticfiles", "rest_framework",
    "drf_spectacular", "drf_spectacular_sidecar", "corsheaders", "api",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "DIRS": [], "APP_DIRS": True, "OPTIONS": {"context_processors": []}}]
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"
APPEND_SLASH = False

if os.getenv("POSTGRES_HOST"):
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.postgresql",
        "HOST": os.environ["POSTGRES_HOST"],
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
        "NAME": os.getenv("POSTGRES_DB", "consultant"),
        "USER": os.getenv("POSTGRES_USER", "consultant"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", "consultant_dev"),
    }}
else:
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "UNAUTHENTICATED_USER": None,
    "EXCEPTION_HANDLER": "api.exceptions.exception_handler",
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
}
CORS_ALLOWED_ORIGINS = [origin.strip() for origin in os.getenv(
    "CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
).split(",") if origin.strip()]
CATALOG_PROVIDER = os.getenv("CATALOG_PROVIDER", "mock")
DIALOG_PROVIDER = os.getenv("DIALOG_PROVIDER", "mock")
SPECTACULAR_SETTINGS = {
    "TITLE": "Онлайн-консультант — API",
    "VERSION": "1.0.0",
    "DESCRIPTION": "API онлайн-консультанта. Для сообщений покупателя откройте раздел «Чат»: POST /api/v1/stores/{store_id}/dialog/messages возвращает ответ ассистента, состояние требований и товары. Раздел «Поиск товаров» предоставляет отдельный поиск по каталогу. По умолчанию работают сценарные моки; алгоритмы ВКР подключаются в catalog/engine.py.",
    "TAGS": [
        {"name": "Чат", "description": "Сообщения покупателя, ответ ассистента, требования и найденные товары. Для демо используйте store_id=demo-store или demo-lighting."},
        {"name": "Поиск товаров", "description": "Поиск товаров магазина с характеристиками; без реплики ассистента."},
        {"name": "Магазины", "description": "Подключение источника каталога и статус его подготовки."},
        {"name": "Сервис", "description": "Проверка доступности API и выбранных провайдеров."},
    ],
    "SERVE_INCLUDE_SCHEMA": False,
    "ENUM_NAME_OVERRIDES": {
        "ProviderModeEnum": ["mock", "real"],
        "MockScenarioEnum": ["default", "clarification", "results", "empty", "conflict", "error", "slow"],
    },
    "SWAGGER_UI_DIST": "SIDECAR",
    "SWAGGER_UI_FAVICON_HREF": "SIDECAR",
}
LANGUAGE_CODE = "ru-ru"
TIME_ZONE = "Europe/Moscow"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
