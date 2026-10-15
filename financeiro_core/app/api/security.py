from typing import Optional, List
from ninja.security import HttpBearer
from django.conf import settings
import jwt
from ninja.errors import HttpError
from django.contrib.auth.models import User

SECRET_KEY = settings.SECRET_KEY

class AuthBearer(HttpBearer):
    def authenticate(self, request, token):
        try:
            payload = jwt.decode(
                token,
                SECRET_KEY,
                algorithms=["HS256"],
                options={"require": ["exp", "user_id"]},
            )
            user_id = payload["user_id"]
            loja_id = payload.get("active_loja_id")
            if type(user_id) is not int or (loja_id is not None and type(loja_id) is not int):
                return None

            user = User.objects.using('vendas').get(id=user_id)
            if not user.is_active:
                return None

            request.user_id = user_id
            request.active_loja_id = loja_id
            request.user = user
            return user
        except (jwt.InvalidTokenError, User.DoesNotExist, KeyError, TypeError, ValueError):
            # Não registrar tokens ou payloads JWT nos logs.
            return None

def get_current_user_id(request):
    return getattr(request, "user_id", None)

def get_current_active_loja_id(request):
    return getattr(request, "active_loja_id", None)

def check_permission(request, loja_id_requested: int):
    active = get_current_active_loja_id(request)
    if not active:
        raise HttpError(400, "Nenhuma loja ativa no contexto")

    if active != loja_id_requested:
        raise HttpError(403, f"Acesso negado: Você está logado na loja {active}, mas tentou acessar a loja {loja_id_requested}.")
