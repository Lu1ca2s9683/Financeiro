from typing import Optional, List
from ninja.security import HttpBearer
from django.conf import settings
import jwt
from ninja.errors import HttpError

SECRET_KEY = "django-insecure-chave-dev-local" # TODO: Load from settings

class AuthBearer(HttpBearer):
    def authenticate(self, request, token):
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            request.user_id = payload["user_id"]
            request.active_loja_id = payload.get("active_loja_id")

            # Here we could validate user existence, but for now we trust the token
            # since it's signed by us (or the trusted external system)
            return payload
        except jwt.ExpiredSignatureError:
            return None # 401
        except jwt.InvalidTokenError:
            return None # 401

def get_current_user_id(request):
    return getattr(request, "user_id", None)

def get_current_active_loja_id(request):
    return getattr(request, "active_loja_id", None)

def check_permission(request, loja_id_requested: int):
    active = get_current_active_loja_id(request)
    if not active:
        raise HttpError(401, "Usuário sem loja ativa")

    if active != loja_id_requested:
        raise HttpError(403, f"Acesso negado: Você está logado na loja {active}, mas tentou acessar a loja {loja_id_requested}.")
