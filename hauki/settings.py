"""
Django settings for hauki project.
"""

import logging
import os
import subprocess

import environ
import sentry_sdk
from django.conf.global_settings import LANGUAGES as GLOBAL_LANGUAGES
from django.core.exceptions import ImproperlyConfigured
from sentry_sdk.integrations.django import DjangoIntegration

CONFIG_FILE_NAME = "config_dev.env"

# This will get default settings, as Django has not yet initialized
# logging when importing this file
logger = logging.getLogger(__name__)


def get_git_revision_hash() -> str:
    """
    Retrieve the git hash for the underlying git repository or die trying

    We need a way to retrieve git revision hash for sentry reports
    I assume that if we have a git repository available we will
    have git-the-comamand as well
    """
    try:
        # We are not interested in gits complaints
        git_hash = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL, encoding="utf8"
        )
    # ie. "git" was not found
    # should we return a more generic meta hash here?
    # like "undefined"?
    except FileNotFoundError:
        git_hash = "git_not_available"
    except subprocess.CalledProcessError:
        # Ditto
        git_hash = "no_repository"
    return git_hash.rstrip()


root = environ.Path(__file__) - 2  # two levels back in hierarchy
env = environ.Env(
    DEBUG=(bool, False),
    DJANGO_LOG_LEVEL=(str, "INFO"),
    CONN_MAX_AGE=(int, 0),
    SYSTEM_DATA_SOURCE_ID=(str, "hauki"),
    LANGUAGES=(list, ["fi", "sv", "en"]),
    DATABASE_URL=(str, "postgres:///hauki"),
    TEST_DATABASE_URL=(str, ""),
    TOKEN_AUTH_ACCEPTED_AUDIENCE=(str, ""),
    TOKEN_AUTH_SHARED_SECRET=(str, ""),
    SECRET_KEY=(str, ""),
    ALLOWED_HOSTS=(list, []),
    ADMINS=(list, []),
    SECURE_PROXY_SSL_HEADER=(tuple, None),
    MEDIA_ROOT=(environ.Path(), root("media")),
    STATIC_ROOT=(environ.Path(), root("static")),
    MEDIA_URL=(str, "/media/"),
    STATIC_URL=(str, "/static/"),
    TRUST_X_FORWARDED_HOST=(bool, False),
    SENTRY_DSN=(str, ""),
    SENTRY_ENVIRONMENT=(str, "development"),
    COOKIE_PREFIX=(str, "hauki"),
    INTERNAL_IPS=(list, []),
    INSTANCE_NAME=(str, "Hauki"),
    EXTRA_INSTALLED_APPS=(list, []),
    ENABLE_DJANGO_EXTENSIONS=(bool, False),
    MAIL_MAILGUN_KEY=(str, ""),
    MAIL_MAILGUN_DOMAIN=(str, ""),
    MAIL_MAILGUN_API=(str, ""),
    RESOURCE_DEFAULT_TIMEZONE=(str, None),
)

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = root()

# Django environ has a nasty habit of complanining at level
# WARN about env file not being preset. Here we pre-empt it.
env_file_path = os.path.join(BASE_DIR, CONFIG_FILE_NAME)
if os.path.exists(env_file_path):
    # Logging configuration is not available at this point
    print(f"Reading config from {env_file_path}")
    environ.Env.read_env(env_file_path)

DEBUG = env("DEBUG")
TEMPLATE_DEBUG = False

ALLOWED_HOSTS = env("ALLOWED_HOSTS")
ADMINS = env("ADMINS")
INTERNAL_IPS = env("INTERNAL_IPS", default=(["127.0.0.1"] if DEBUG else []))
DATABASES = {"default": env.db()}

DATABASES["default"]["CONN_MAX_AGE"] = env("CONN_MAX_AGE")

if env("TEST_DATABASE_URL"):
    DATABASES["default"]["TEST"] = env.db("TEST_DATABASE_URL")

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

AUTH_USER_MODEL = "users.User"

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/v1/"
LOGOUT_REDIRECT_URL = "/v1/"

RESOURCE_DEFAULT_TIMEZONE = env("RESOURCE_DEFAULT_TIMEZONE")

DJANGO_ORGHIERARCHY_DATASOURCE_MODEL = "hours.DataSource"

SYSTEM_DATA_SOURCE_ID = env("SYSTEM_DATA_SOURCE_ID")

SITE_ID = 1

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "timestamped_named": {
            "format": "%(asctime)s %(name)s %(levelname)s: %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "timestamped_named",
        },
        # Just for reference, not used
        "blackhole": {
            "class": "logging.NullHandler",
        },
    },
    "loggers": {
        "": {
            "handlers": ["console"],
            "level": os.getenv("DJANGO_LOG_LEVEL", "INFO"),
        },
        "django": {
            "handlers": ["console"],
            "level": os.getenv("DJANGO_LOG_LEVEL", "INFO"),
        },
    },
}
# Application definition

INSTALLED_APPS = [
    "helusers.apps.HelusersConfig",
    "modeltranslation",
    "helusers.apps.HelusersAdminConfig",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.humanize",
    "simple_history",
    # disable Django’s development server static file handling
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework.authtoken",
    "django_filters",
    "django_orghierarchy",
    "timezone_field",
    "mptt",
    # Apps within this repository
    "users",
    "hours",
    # OpenAPI
    "drf_spectacular",
] + env("EXTRA_INSTALLED_APPS")

if env("SENTRY_DSN"):
    sentry_sdk.init(
        dsn=env("SENTRY_DSN"),
        environment=env("SENTRY_ENVIRONMENT"),
        release=get_git_revision_hash(),
        integrations=[DjangoIntegration()],
    )

MIDDLEWARE = [
    # CorsMiddleware should be placed as high as possible and above WhiteNoiseMiddleware
    # in particular
    "corsheaders.middleware.CorsMiddleware",
    # Ditto for securitymiddleware
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "simple_history.middleware.HistoryRequestMiddleware",
]

# django-extensions is a set of developer friendly tools
if env("ENABLE_DJANGO_EXTENSIONS"):
    INSTALLED_APPS.append("django_extensions")


ROOT_URLCONF = "hauki.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "hauki.wsgi.application"

# Password validation
# https://docs.djangoproject.com/en/3.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation."
        "UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/3.0/topics/i18n/

# Map language codes to the (code, name) tuples used by Django
# We want to keep the ordering in LANGUAGES configuration variable,
# thus some gyrations
language_map = {x: y for x, y in GLOBAL_LANGUAGES}
try:
    LANGUAGES = tuple((lang, language_map[lang]) for lang in env("LANGUAGES"))
except KeyError as e:
    raise ImproperlyConfigured(f'unknown language code "{e.args[0]}"')
LANGUAGE_CODE = env("LANGUAGES")[0]

TIME_ZONE = "Europe/Helsinki"

USE_I18N = True

USE_L10N = True

USE_TZ = True

LOCALE_PATHS = [root("locale")]

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.0/howto/static-files/

STATIC_URL = env("STATIC_URL")
MEDIA_URL = env("MEDIA_URL")
STATIC_ROOT = env("STATIC_ROOT")
MEDIA_ROOT = env("MEDIA_ROOT")

# Whether to trust X-Forwarded-Host headers for all purposes
# where Django would need to make use of its own hostname
# fe. generating absolute URLs pointing to itself
# Most often used in reverse proxy setups
# https://docs.djangoproject.com/en/3.0/ref/settings/#use-x-forwarded-host
USE_X_FORWARDED_HOST = env("TRUST_X_FORWARDED_HOST")

# Specifies a header that is trusted to indicate that the request was using
# https while traversing over the Internet at large. This is used when
# a proxy terminates the TLS connection and forwards the request over
# a secure network. Specified using a tuple.
# https://docs.djangoproject.com/en/3.0/ref/settings/#secure-proxy-ssl-header
SECURE_PROXY_SSL_HEADER = env("SECURE_PROXY_SSL_HEADER")

CORS_ORIGIN_ALLOW_ALL = True
CSRF_COOKIE_NAME = "%s-csrftoken" % env("COOKIE_PREFIX")
SESSION_COOKIE_NAME = "%s-sessionid" % env("COOKIE_PREFIX")

# DRF Settings
# https://www.django-rest-framework.org/api-guide/settings/

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "hours.renderers.BrowsableAPIRendererWithoutForms",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "rest_framework.filters.OrderingFilter",
        "django_filters.rest_framework.DjangoFilterBackend",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "hours.authentication.HaukiSignedAuthentication",
        "hours.authentication.HaukiTokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ],
    "DEFAULT_METADATA_CLASS": "hours.metadata.TranslatedChoiceNamesMetadata",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

# shown in the browsable API
INSTANCE_NAME = env("INSTANCE_NAME")

#
# Anymail
#

if env("MAIL_MAILGUN_KEY"):
    ANYMAIL = {
        "MAILGUN_API_KEY": env("MAIL_MAILGUN_KEY"),
        "MAILGUN_SENDER_DOMAIN": env("MAIL_MAILGUN_DOMAIN"),
        "MAILGUN_API_URL": env("MAIL_MAILGUN_API"),
    }
    EMAIL_BACKEND = "anymail.backends.mailgun.EmailBackend"
elif not env("MAIL_MAILGUN_KEY") and DEBUG is True:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

#
# Django spectacular (OpenAPI) settings
#
SPECTACULAR_SETTINGS = {
    "TITLE": "Hauki API",
    "DESCRIPTION": """
API for the City of Helsinki opening hours database

# Introduction

To do.

# Authentication methods

<SecurityDefinitions />
""",
    "VERSION": "0.0.1",
    "EXTERNAL_DOCS": {
        "description": "Hauki API in GitHub",
        "url": "https://github.com/City-of-Helsinki/hauki",
    },
}

# local_settings.py can be used to override environment-specific settings
# like database and email that differ between development and production.
local_settings_path = os.path.join(BASE_DIR, "local_settings.py")
if os.path.exists(local_settings_path):
    with open(local_settings_path) as fp:
        code = compile(fp.read(), local_settings_path, "exec")
    # Here, we execute local code on the server. Luckily, local_settings.py and BASE_DIR
    # are hard-coded above, so this cannot be used to execute any other files.
    exec(code, globals(), locals())  # nosec


# Django SECRET_KEY setting, used for password reset links and such
SECRET_KEY = env("SECRET_KEY")
if not DEBUG and not SECRET_KEY:
    raise Exception("In production, SECRET_KEY must be provided in the environment.")
# If a secret key was not supplied elsewhere, generate a random one and print
# a warning (logging is not configured yet?). This means that any functionality
# expecting SECRET_KEY to stay same will break upon restart. Should not be a
# problem for development.
if not SECRET_KEY:
    logger.warn(
        "SECRET_KEY was not defined in configuration."
        " Generating a temporary key for dev."
    )
    import random

    system_random = random.SystemRandom()
    SECRET_KEY = "".join(
        [
            system_random.choice("abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)")
            for i in range(64)
        ]
    )
