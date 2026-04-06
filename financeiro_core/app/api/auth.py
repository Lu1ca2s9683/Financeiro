import jwt
import datetime
from ninja import Router, Schema
from ninja.errors import HttpError
from typing import List, Optional
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.hashers import check_password

router = Router()

SECRET_KEY = settings.SECRET_KEY

# --- Schemas ---

class LoginSchema(Schema):
    username: str
    password: str

class TokenSchema(Schema):
    token: str

class SwitchLojaSchema(Schema):
    loja_id: int

class LojaOut(Schema):
    id: int
    nome: str
    role: str

class GrupoOut(Schema):
    id: int
    nome: str
    role: str
    lojas: List[LojaOut]

class UserOut(Schema):
    id: int
    nome: str
    email: str

class AuthMeOut(Schema):
    user: UserOut
    grupos: List[GrupoOut]
    active_loja: Optional[LojaOut] = None

class ActiveLojaOut(Schema):
    active_loja: LojaOut

# --- Helpers ---

def create_token(user_id: int, active_loja_id: Optional[int] = None):
    payload = {
        "user_id": user_id,
        "active_loja_id": active_loja_id,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

def decode_token(token: str):
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HttpError(401, "Token expirado")
    except jwt.InvalidTokenError:
        raise HttpError(401, "Token inválido")

def get_user_from_request(request):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HttpError(401, "Token ausente")

    token = auth_header.split(" ")[1]
    payload = decode_token(token)

    try:
        user = User.objects.using('vendas').get(id=payload["user_id"])
    except User.DoesNotExist:
        raise HttpError(401, "Usuário não encontrado")

    return user, payload.get("active_loja_id")

# --- Endpoints ---

@router.post("/login", response=TokenSchema)
def login(request, payload: LoginSchema):
    try:
        # Consulta o usuário estritamente no banco de dados secundário (Orion/Vendas)
        user = User.objects.using('vendas').get(username=payload.username)
    except User.DoesNotExist:
        raise HttpError(401, "Credenciais inválidas")

    # Verifica o hash da senha
    if not check_password(payload.password, user.password):
        raise HttpError(401, "Credenciais inválidas")

    # O Orion deve ter os grupos e lojas vinculadas na base, mas neste momento de transição
    # não está explícito no prompt como recuperar `active_loja_id` real da base do Orion.
    # Por segurança, vamos iniciar com active_loja_id=None ou tentar extrair de grupos/permissões se existissem.
    # No futuro, precisaremos de um JOIN nas tabelas do Orion se necessário.
    active_loja_id = None

    # Gera o JWT com base no user_id do Orion
    token = create_token(user.id, active_loja_id)
    return {"token": token}

# --- Lógica de Grupos Fictícia Temporária ---
# Substituir por consulta real no Orion quando modelos de GrupoLojas/Lojas estiverem mapeados.
def get_dummy_grupos():
    return [
        {
            "id": 1,
            "nome": "Acesso Geral",
            "role": "GESTOR",
            "lojas": [
                { "id": 1, "nome": "Matriz", "role": "GESTOR" }
            ]
        }
    ]

@router.get("/me", response=AuthMeOut)
def me(request):
    user, active_loja_id = get_user_from_request(request)

    grupos_ficticios = get_dummy_grupos()

    active_loja = None
    if active_loja_id:
        for grupo in grupos_ficticios:
            for loja in grupo["lojas"]:
                if loja["id"] == active_loja_id:
                    active_loja = loja
                    break

    # Fallback to first store if none is strictly matched
    if not active_loja and grupos_ficticios and grupos_ficticios[0]["lojas"]:
        active_loja = grupos_ficticios[0]["lojas"][0]

    return {
        "user": {
            "id": user.id,
            "nome": user.first_name or user.username,
            "email": user.email
        },
        "grupos": grupos_ficticios,
        "active_loja": active_loja
    }

@router.post("/switch-loja", response=ActiveLojaOut)
def switch_loja(request, payload: SwitchLojaSchema):
    user, _ = get_user_from_request(request)

    grupos_ficticios = get_dummy_grupos()

    # Valida se o usuário tem acesso à loja
    target_loja = None
    for grupo in grupos_ficticios:
        for loja in grupo["lojas"]:
            if loja["id"] == payload.loja_id:
                target_loja = loja
                break

    if not target_loja:
        raise HttpError(403, "Acesso negado à loja solicitada")

    # Retorna a loja e injeta um header para o front
    new_token = create_token(user.id, target_loja["id"])
    response = request.create_response({"active_loja": target_loja})
    response["X-New-Token"] = new_token
    return response
