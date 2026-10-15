import jwt
import datetime
from ninja import Router, Schema
from ninja.errors import HttpError
from typing import List, Optional
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.hashers import check_password
from django.db import connections
from django.http import HttpResponse

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

class SwitchLojaOut(Schema):
    active_loja: LojaOut
    token: str

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
        return jwt.decode(token, SECRET_KEY, algorithms=["HS256"], options={"require": ["exp", "user_id"]})
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
    if type(payload.get("user_id")) is not int:
        raise HttpError(401, "Token invalido")

    try:
        user = User.objects.using('vendas').get(id=payload["user_id"])
    except User.DoesNotExist:
        raise HttpError(401, "Usuário não encontrado")
    if not user.is_active:
        raise HttpError(401, "Usuário desativado")

    active_loja_id = payload.get("active_loja_id")
    if type(active_loja_id) is not int:
        raise HttpError(403, "Loja ativa invalida")
    lojas = fetch_user_lojas(user.id, user.is_superuser)
    if not any(loja["id"] == active_loja_id for loja in lojas):
        raise HttpError(403, "Acesso financeiro revogado ou loja indisponivel")
    request.financeiro_lojas = lojas
    return user, active_loja_id

# --- Endpoints ---

@router.post("/login", response=TokenSchema)
def login(request, payload: LoginSchema):
    try:
        # Consulta o usuário estritamente no banco de dados secundário (Orion/Vendas)
        user = User.objects.using('vendas').get(username=payload.username)
    except User.DoesNotExist:
        raise HttpError(401, "Credenciais inválidas")
    if not user.is_active:
        raise HttpError(401, "Credenciais inválidas")

    # Verifica o hash da senha
    if not check_password(payload.password, user.password):
        raise HttpError(401, "Credenciais inválidas")

    # Busca as lojas do usuário para definir a loja ativa inicial
    lojas = fetch_user_lojas(user.id, user.is_superuser)

    if not lojas:
        raise HttpError(403, "Usuario sem permissao para acessar o Financeiro")
    active_loja_id = lojas[0]["id"]

    # Gera o JWT com base no user_id do Orion e com a loja ativa inicial
    token = create_token(user.id, active_loja_id)
    return {"token": token}

# --- Lógica de Permissões via Raw SQL ---

def fetch_user_lojas(user_id: int, is_superuser: bool) -> List[dict]:
    """Devolve SOMENTE lojas com autorizacao financeira atual.

    GLOBAL: superusuario ativo do ERP; GESTOR_GRUPO: vinculo na M2M
    vendas_grupolojas_super_usuarios_grupo. Perfis USUARIO, CONFERENTE
    e GESTOR de loja NAO sao elegiveis. Sem cache: revogacao imediata.
    """
    with connections['vendas'].cursor() as cursor:
        if is_superuser:
            cursor.execute("SELECT id, nome FROM vendas_loja WHERE ativa = true ORDER BY id")
            return [
                {'id': row[0], 'nome': row[1], 'role': 'GLOBAL'}
                for row in cursor.fetchall()
            ]

        cursor.execute('''
            SELECT DISTINCT l.id, l.nome
            FROM vendas_loja l
            JOIN vendas_grupolojas_super_usuarios_grupo gsu
              ON gsu.grupolojas_id = l.grupo_id
            WHERE gsu.user_id = %s AND l.ativa = true
            ORDER BY l.id
        ''', [user_id])
        return [
            {'id': row[0], 'nome': row[1], 'role': 'GESTOR_GRUPO'}
            for row in cursor.fetchall()
        ]

def mount_grupos(lojas: List[dict]) -> List[dict]:
    """Cria um grupo aglutinador para as lojas encontradas."""
    if not lojas:
        return []
    return [
        {
            "id": 1,
            "nome": "Minhas Lojas",
            "role": "MEMBER",
            "lojas": lojas
        }
    ]

@router.get("/me", response=AuthMeOut)
def me(request):
    user, active_loja_id = get_user_from_request(request)

    lojas = request.financeiro_lojas
    grupos = mount_grupos(lojas)

    active_loja = None
    if active_loja_id:
        for loja in lojas:
            if loja["id"] == active_loja_id:
                active_loja = loja
                break

    # Token de loja revogada nunca migra silenciosamente para outra loja.

    return {
        "user": {
            "id": user.id,
            "nome": user.first_name or user.username,
            "email": user.email
        },
        "grupos": grupos,
        "active_loja": active_loja
    }

@router.post("/switch-loja", response=SwitchLojaOut)
def switch_loja(request, payload: SwitchLojaSchema):
    user, _ = get_user_from_request(request)

    lojas = request.financeiro_lojas

    # Valida se o usuário tem acesso à loja
    target_loja = None
    for loja in lojas:
        if loja["id"] == payload.loja_id:
            target_loja = loja
            break

    if not target_loja:
        raise HttpError(403, "Acesso negado à loja solicitada")


    # Retorna a loja e o novo token no corpo
    new_token = create_token(user.id, target_loja["id"])

    return {"active_loja": target_loja, "token": new_token}
