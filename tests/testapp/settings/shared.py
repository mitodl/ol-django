"""
Django settings for testapp project.

Generated by 'django-admin startproject' using Django 2.2.15.

For more information on this file, see
https://docs.djangoproject.com/en/2.2/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/2.2/ref/settings/
"""

import os

import dj_database_url

from mitol.common.envs import get_string, import_settings_modules, init_app_settings

init_app_settings(namespace="MITOL", site_name="MIT Open Learning Common Library")
import_settings_modules(
    "mitol.common.settings.base",
    "mitol.common.settings.webpack",
    "mitol.mail.settings.email",
    "mitol.authentication.settings.touchstone",
    "mitol.authentication.settings.djoser_settings",
    "mitol.payment_gateway.settings.cybersource",
    "mitol.google_sheets.settings.google_sheets",
    "mitol.google_sheets_refunds.settings.google_sheets_refunds",
    "mitol.google_sheets_deferrals.settings.google_sheets_deferrals",
    "mitol.hubspot_api.settings.hubspot_api",
)

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/2.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "TESTAPP_SECRET"

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ["*"]


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # third party
    "oauth2_provider",
    "rest_framework",
    # reusable apps
    "mitol.authentication.apps.AuthenticationApp",
    "mitol.common.apps.CommonApp",
    "mitol.digitalcredentials.apps.DigitalCredentialsApp",
    "mitol.google_sheets.apps.GoogleSheetsApp",
    "mitol.google_sheets_refunds.apps.GoogleSheetsRefundsApp",
    "mitol.google_sheets_deferrals.apps.GoogleSheetsDeferralsApp",
    "mitol.hubspot_api.apps.HubspotApiApp",
    "mitol.mail.apps.MailApp",
    "mitol.oauth_toolkit_extensions.apps.OAuthToolkitExtensionsApp",
    "mitol.openedx.apps.OpenedxApp",
    "mitol.payment_gateway.apps.PaymentGatewayApp",
    "mitol.geoip.apps.GeoIPApp",
    "mitol.posthog.apps.Posthog",
    # test app, integrates the reusable apps
    "testapp",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "testapp.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR + "/testapp/templates/"],
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

WSGI_APPLICATION = "testapp.wsgi.application"

REST_FRAMEWORK = {"TEST_REQUEST_DEFAULT_FORMAT": "json"}


# Database
# https://docs.djangoproject.com/en/2.2/ref/settings/#databases

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

DEFAULT_DATABASE_CONFIG = dj_database_url.parse(
    get_string(
        name="DATABASE_URL",
        default="postgres://postgres:postgres@localhost:5432/postgres",
        description="The connection url to the Postgres database",
        required=True,
    )
)

DATABASES = {"default": DEFAULT_DATABASE_CONFIG}

AUTHENTICATION_BACKENDS = (
    "django.contrib.auth.backends.ModelBackend",
    "social_core.backends.saml.SAMLAuth",
)


# Password validation
# https://docs.djangoproject.com/en/2.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
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
# https://docs.djangoproject.com/en/2.2/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/2.2/howto/static-files/

STATIC_URL = "/static/"


SITE_NAME = "Test app"
SITE_BASE_URL = "http://127.0.0.1:8000/"


# required for migrations
OAUTH2_PROVIDER_ACCESS_TOKEN_MODEL = "oauth2_provider.AccessToken"
OAUTH2_PROVIDER_APPLICATION_MODEL = "oauth2_provider.Application"
OAUTH2_PROVIDER_REFRESH_TOKEN_MODEL = "oauth2_provider.RefreshToken"

OAUTH2_PROVIDER = {
    "SCOPES": {
        "read": "Read access",
        "write": "Write access",
        "only_logout": "Only access to logout",
    },
    "DEFAULT_SCOPES": ["read", "write"],
    "SCOPES_BACKEND_CLASS": "mitol.oauth_toolkit_extensions.backends.ApplicationAccessOrSettingsScopes",
}

REST_FRAMEWORK = {"TEST_REQUEST_DEFAULT_FORMAT": "json"}

MITOL_DIGITAL_CREDENTIALS_AUTH_TYPE = "test"
MITOL_DIGITAL_CREDENTIALS_DEEP_LINK_URL = "testscheme://localhost"

MITOL_PAYMENT_GATEWAY_CYBERSOURCE_ACCESS_KEY = "abc123"
MITOL_PAYMENT_GATEWAY_CYBERSOURCE_PROFILE_ID = "abc123"
MITOL_PAYMENT_GATEWAY_CYBERSOURCE_SECURITY_KEY = "Test1234"
MITOL_PAYMENT_GATEWAY_CYBERSOURCE_SECURE_ACCEPTANCE_URL = "https://google.com"
MITOL_PAYMENT_GATEWAY_CYBERSOURCE_MERCHANT_ID = "test"
MITOL_PAYMENT_GATEWAY_CYBERSOURCE_MERCHANT_SECRET = "test1234"
MITOL_PAYMENT_GATEWAY_CYBERSOURCE_MERCHANT_SECRET_KEY_ID = "test1234"

MITOL_HUBSPOT_API_ID_PREFIX = "app"
MITOL_HUBSPOT_API_PRIVATE_TOKEN = "testtoken"
