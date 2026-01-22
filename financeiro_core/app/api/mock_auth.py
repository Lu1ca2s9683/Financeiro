import jwt
import datetime
from ninja import Router, Schema
from ninja.errors import HttpError
from typing import List, Optional

router = Router()

SECRET_KEY = "django-insecure-chave-dev-local"  # Mesmo do settings.py para simplificar

# --- Mock Data ---
USERS = {
    "usuario": {
        "id": 10,
        "password": "senha",
        "nome": "João",
        "email": "joao@email.com",
        "grupos": [
            {
                "id": 1,
                "nome": "Grupo SP",
                "role": "SUPER_GRUPO",
                "lojas": [
                    { "id": 1, "nome": "Loja Centro", "role": "GESTOR" },
                    { "id": 2, "nome": "Loja Norte", "role": "LEITURA" }
                ]
            }
        ]
    },
    "leitura": {
        "id": 11,
        "password": "senha",
        "nome": "Maria",
        "email": "maria@email.com",
        "grupos": [
            {
                "id": 1,
                "nome": "Grupo SP",
                "role": "LEITURA",
                "lojas": [
                    { "id": 2, "nome": "Loja Norte", "role": "LEITURA" }
                ]
            }
        ]
    }
}

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

    user = None
    for u in USERS.values():
        if u["id"] == payload["user_id"]:
            user = u
            break

    if not user:
        raise HttpError(401, "Usuário não encontrado")

    return user, payload.get("active_loja_id")

# --- Endpoints ---

@router.post("/login", response=TokenSchema)
def login(request, payload: LoginSchema):
    user = USERS.get(payload.username)
    if not user or user["password"] != payload.password:
        raise HttpError(401, "Credenciais inválidas")

    # Default active store: first one found
    active_loja_id = None
    if user["grupos"] and user["grupos"][0]["lojas"]:
        active_loja_id = user["grupos"][0]["lojas"][0]["id"]

    token = create_token(user["id"], active_loja_id)
    return {"token": token}

@router.get("/me", response=AuthMeOut)
def me(request):
    user, active_loja_id = get_user_from_request(request)

    active_loja = None
    if active_loja_id:
        for grupo in user["grupos"]:
            for loja in grupo["lojas"]:
                if loja["id"] == active_loja_id:
                    active_loja = loja
                    break

    return {
        "user": {
            "id": user["id"],
            "nome": user["nome"],
            "email": user["email"]
        },
        "grupos": user["grupos"],
        "active_loja": active_loja
    }

@router.post("/switch-loja", response=ActiveLojaOut)
def switch_loja(request, payload: SwitchLojaSchema):
    user, _ = get_user_from_request(request)

    # Valida se o usuário tem acesso à loja
    target_loja = None
    for grupo in user["grupos"]:
        for loja in grupo["lojas"]:
            if loja["id"] == payload.loja_id:
                target_loja = loja
                break

    if not target_loja:
        raise HttpError(403, "Acesso negado à loja solicitada")

    # Gera novo token com a loja ativa atualizada (Simulando sessão stateful via token stateless)
    # Na vida real, isso poderia ser uma sessão no backend, mas aqui retornamos o objeto loja
    # e o frontend deve usar o novo token se retornássemos um, mas o contrato diz que retorna "active_loja".
    # O contrato não retorna um novo token. Isso implica que o backend de vendas gerencia sessão ou
    # o token JWT não muda e o backend Financeiro deve confiar no "switch".
    # POREM, para o Financeiro funcionar sem sessão no backend, o ideal é o token conter a loja.
    # Mas se o contrato externo não retorna token novo, então o estado está lá no Sales.
    # Como este é um MOCK do Sales, vamos assumir que o Sales sabe quem é a loja ativa.
    # Mas o Financeiro Backend é stateless.
    # SOLUÇÃO: Vamos quebrar um pouco o contrato MOCK e retornar um header ou cookie,
    # OU vamos assumir que o frontend deve mandar o `loja_id` em toda request (header `X-Active-Loja`?).
    # O prompt diz: "active_loja_id... Extrair: user_id, roles, active_loja_id" do token/middleware.

    # Se o switch-loja não retorna token, o token antigo continua valendo.
    # Se o token antigo tem `active_loja_id` antigo, como atualizamos?
    # Resposta: O contrato diz que retorna `active_loja`. O frontend deve atualizar seu contexto.
    # O Backend Financeiro precisa saber qual a loja ativa.
    # Vamos adicionar um header customizado `X-Mock-New-Token` na resposta para o frontend pegar,
    # OU vamos simplificar e pedir pro frontend mandar `loja_id` ativo no header sempre.
    # O prompt diz: "Contexto Global... Loja ativa... Ser usado por TODAS as páginas".
    # E "Autorização Backend... Extrair active_loja_id".

    # Vamos fazer o endpoint mock retornar o novo token em um header ou corpo para facilitar nossa vida,
    # ou assumir que o frontend manda o ID.
    # O contrato oficial diz apenas body response: { active_loja: ... }.
    # Vou manter o contrato no body.
    # E vou fazer um "HACK" no mock: O switch-loja vai retornar um token novo num header `Authorization` de resposta
    # se possível, ou vamos apenas confiar que o frontend manda o ID da loja na query/header para o financeiro.

    # MELHOR: O Middleware de Auth do Financeiro vai ler o Header `X-Active-Loja-ID` se o token não tiver,
    # ou vamos apenas atualizar o token.

    # Vou injetar um novo token no response body para facilitar o desenvolvimento,
    # mesmo que fuja um pouco do contrato estrito de "Response",
    # vou adicionar o campo `token` opcional no schema de retorno para facilitar.

    new_token = create_token(user["id"], target_loja["id"])

    # Hack para o frontend atualizar o token
    response = request.create_response({"active_loja": target_loja})
    response["X-New-Token"] = new_token
    return response
