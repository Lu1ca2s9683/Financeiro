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

# Adiciona a URL do frontend em produção se estiver definida
# (Recomendado adicionar FRONTEND_URL nas variáveis de ambiente do Render)
if 'FRONTEND_URL' in os.environ:
    CORS_ALLOWED_ORIGINS.append(os.environ['FRONTEND_URL'])

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

# Configuração Padrão (Local - Desenvolvimento)
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

# --- CONFIGURAÇÃO RENDER (Produção) ---

if 'DATABASE_URL' in os.environ:
    # 1. Configura o Banco do Financeiro (Onde salvamos despesas e fechamentos)
    # Pega automaticamente da variável DATABASE_URL do serviço
    DATABASES['default'] = dj_database_url.config(conn_max_age=600, ssl_require=True)
    
    # 2. Configura o Banco de Vendas (Externo/Real)
    if 'VENDAS_DATABASE_URL' in os.environ:
        # Se você adicionou a variável no Passo 2, ele entra aqui!
        # Conecta diretamente no banco de produção das lojas.
        DATABASES['vendas_db'] = dj_database_url.parse(
            os.environ['VENDAS_DATABASE_URL'],
            conn_max_age=600,
            ssl_require=True
        )
    else:
        # Se esqueceu de colocar a variável, ele usa o default como fallback
        # (Isso evita que o sistema caia, mas os dados de vendas estarão vazios se não houver backup)
        DATABASES['vendas_db'] = DATABASES['default']

# Segurança extra: Se estamos no Render mas nem o banco principal foi achado
elif 'RENDER' in os.environ:
    raise ValueError("ERRO CRÍTICO: DATABASE_URL não encontrada no Render.")

# Router para impedir que o Financeiro tente criar tabelas no banco de Vendas
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