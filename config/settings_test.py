from .settings import *  # noqa: F403,F401

DEBUG = True
CORS_ALLOW_ALL_ORIGINS = True

# Fully isolated databases: automated tests never require PostgreSQL/Render.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    },
    "vendas": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    },
}

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

SECRET_KEY = "django-insecure-test-key-for-test-environment-only"

# The Sales test DB receives only the Django auth/contenttypes schema needed
# to exercise the authentication boundary. Financeiro migrations stay on default.
DATABASE_ROUTERS = ["config.test_routers.TestRouter"]
