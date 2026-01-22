"""
Django settings for config project.
"""

from pathlib import Path
import os
import dj_database_url

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# --- SEGURANÇA ---
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-chave-dev-local')

# DEBUG será False se estiver no Render
DEBUG = 'RENDER' not in os.environ

# --- CONFIGURAÇÃO DE HOSTS ---
ALLOWED_HOSTS = ['localhost', '127.0.0.1']

RENDER_EXTERNAL_HOSTNAME = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)
else:
    # Fallback para permitir tudo se a variável não estiver definida (cuidado em produção)
    ALLOWED_HOSTS.append('*')

if RENDER_EXTERNAL_HOSTNAME:
    CSRF_TRUSTED_ORIGINS = [f'https://{RENDER_EXTERNAL_HOSTNAME}']

# --- APLICAÇÃO ---
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',
    'ninja',
    'financeiro_core',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# --- BANCO DE DADOS ---

# Configuração Padrão (Local)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'financeiro_db',
        'USER': 'postgres',
        'PASSWORD': '96835967@Luck',
        'HOST': 'localhost',
        'PORT': '5432',
    },
    'vendas_db': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'loja_producao_backup',
        'USER': 'postgres',
        'PASSWORD': '96835967@Luck',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

# --- CONFIGURAÇÃO RENDER (Lógica Inteligente) ---

# Se a variável DATABASE_URL existe, significa que estamos no ambiente de nuvem
if 'DATABASE_URL' in os.environ:
    # 1. Configura o Banco Principal (Financeiro) usando a URL padrão do Render
    DATABASES['default'] = dj_database_url.config(conn_max_age=600, ssl_require=True)
    
    # 2. Configura o Banco Secundário (Vendas)
    if 'VENDAS_DATABASE_URL' in os.environ:
        # CONEXÃO REAL: Se definimos a URL externa, conecta no banco de produção das vendas
        DATABASES['vendas_db'] = dj_database_url.parse(
            os.environ['VENDAS_DATABASE_URL'],
            conn_max_age=600,
            ssl_require=False
        )
    else:
        # FALLBACK: Se não existir a variável, usa o mesmo banco do financeiro
        # (Útil se você restaurou o backup dentro do banco financeiro_db no Render)
        DATABASES['vendas_db'] = DATABASES['default']

# Segurança: Se estamos no Render mas a DATABASE_URL não apareceu, avisamos
elif 'RENDER' in os.environ:
    raise ValueError("ERRO CRÍTICO: A variável de ambiente DATABASE_URL não foi definida no Render! Adicione-a na aba Environment.")

DATABASE_ROUTERS = ['config.db_routers.VendasRouter']

# --- SENHAS E I18N ---
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True

# --- ARQUIVOS ESTÁTICOS ---
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

if not DEBUG:
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'