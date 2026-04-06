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

# --- Lógica de Permissões via Raw SQL ---

def fetch_user_lojas(user_id: int, is_superuser: bool) -> List[dict]:
    """Busca as lojas e permissões do usuário direto no banco secundário usando SQL bruto."""
    lojas_dict = {}

    with connections['vendas'].cursor() as cursor:
        if is_superuser:
            cursor.execute("SELECT id, nome FROM vendas_loja WHERE ativa = true")
            for row in cursor.fetchall():
                lojas_dict[row[0]] = {"id": row[0], "nome": row[1], "role": "GLOBAL"}
        else:
            # Regra Nova: Superusuário de Grupo
            cursor.execute('''
                SELECT l.id, l.nome
                FROM vendas_loja l
                INNER JOIN vendas_grupolojas_super_usuarios_grupo gsu ON l.grupo_id = gsu.grupolojas_id
                WHERE gsu.user_id = %s AND l.ativa = true
            ''', [user_id])
            for row in cursor.fetchall():
                if row[0] not in lojas_dict:
                    lojas_dict[row[0]] = {"id": row[0], "nome": row[1], "role": "GESTOR_GRUPO"}

            # Regra 2: Gestor
            cursor.execute('''
                SELECT l.id, l.nome
                FROM vendas_loja l
                INNER JOIN vendas_loja_gestores lg ON l.id = lg.loja_id
                WHERE lg.user_id = %s AND l.ativa = true
            ''', [user_id])
            for row in cursor.fetchall():
                if row[0] not in lojas_dict: # Prioridade maior ou mantém se não existir
                    lojas_dict[row[0]] = {"id": row[0], "nome": row[1], "role": "GESTOR"}

            # Regra 3a: Usuário Base (vendas_userprofile)
            cursor.execute('''
                SELECT l.id, l.nome
                FROM vendas_loja l
                INNER JOIN vendas_userprofile up ON l.id = up.loja_id
                WHERE up.user_id = %s AND l.ativa = true
            ''', [user_id])
            for row in cursor.fetchall():
                if row[0] not in lojas_dict:
                    lojas_dict[row[0]] = {"id": row[0], "nome": row[1], "role": "USUARIO"}

            # Regra 3b: Conferente (vendas_userprofile_lojas_conferencia)
            cursor.execute('''
                SELECT l.id, l.nome
                FROM vendas_loja l
                INNER JOIN vendas_userprofile_lojas_conferencia uplc ON l.id = uplc.loja_id
                INNER JOIN vendas_userprofile up ON uplc.userprofile_id = up.id
                WHERE up.user_id = %s AND l.ativa = true
            ''', [user_id])
            for row in cursor.fetchall():
                if row[0] not in lojas_dict:
                    lojas_dict[row[0]] = {"id": row[0], "nome": row[1], "role": "CONFERENTE"}

    return list(lojas_dict.values())

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

    lojas = fetch_user_lojas(user.id, user.is_superuser)
    grupos = mount_grupos(lojas)

    active_loja = None
    if active_loja_id:
        for loja in lojas:
            if loja["id"] == active_loja_id:
                active_loja = loja
                break

    # Fallback para a primeira loja, se houver
    if not active_loja and lojas:
        active_loja = lojas[0]

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
    print(f"DEBUG: Trocando para a loja ID {payload.loja_id}")
    user, _ = get_user_from_request(request)

    lojas = fetch_user_lojas(user.id, user.is_superuser)

    # Valida se o usuário tem acesso à loja
    target_loja = None
    for loja in lojas:
        if loja["id"] == payload.loja_id:
            target_loja = loja
            break

    if not target_loja:
        raise HttpError(403, "Acesso negado à loja solicitada")

    print("DEBUG: Permissão confirmada")

    # Retorna a loja e o novo token no corpo
    new_token = create_token(user.id, target_loja["id"])
    print("DEBUG: Novo token gerado")

    return {"active_loja": target_loja, "token": new_token}
