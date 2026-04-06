from typing import Optional, List
from ninja.security import HttpBearer
from django.conf import settings
import jwt
from ninja.errors import HttpError
from django.contrib.auth.models import User

SECRET_KEY = settings.SECRET_KEY

class AuthBearer(HttpBearer):
    def authenticate(self, request, token):
        print("DEBUG: Token recebido")
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            print(f"DEBUG: Payload decodificado: {payload}")

            # Fetch user strictly from the secondary DB to validate
            user = User.objects.using('vendas').get(id=payload["user_id"])

            request.user_id = payload["user_id"]
            request.active_loja_id = payload.get("active_loja_id")
            request.user = user  # Attach user object to the request

            return user
        except jwt.ExpiredSignatureError as e:
            print(f"DEBUG: Erro ao validar usuário: {e}")
            return None
        except jwt.InvalidTokenError as e:
            print(f"DEBUG: Erro ao validar usuário: {e}")
            return None
        except User.DoesNotExist as e:
            print(f"DEBUG: Erro ao validar usuário: User {payload.get('user_id')} não encontrado no banco vendas. Erro: {e}")
            return None
        except Exception as e:
            print(f"DEBUG: Erro ao validar usuário: {e}")
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
