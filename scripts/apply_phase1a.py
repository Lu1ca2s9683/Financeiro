#!/usr/bin/env python3
"""Fase 1A: hardening inicial do Financeiro, em checkout local ou Codespaces.

Use somente em branch, com working tree limpa.
Valida todas as âncoras ANTES de gravar qualquer arquivo.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import sys
import tempfile


def replace_once(content: str, old: str, new: str, filename: str) -> str:
    matches = content.count(old)
    if matches != 1:
        raise RuntimeError(f"{filename}: esperado 1 trecho, encontrados {matches}. Nenhum arquivo foi alterado.")
    return content.replace(old, new, 1)


def settings_changes(content: str) -> str:
    name = "config/settings.py"
    content = replace_once(
        content,
        "SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-chave-dev-local-minimo-32-bytes')",
        '''# Nunca utilizar chave fixa ou previsível fora do ambiente de testes dedicado.
SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    if os.environ.get('DJANGO_SETTINGS_MODULE') == 'config.settings_test':
        SECRET_KEY = 'test-only-placeholder-overridden-by-settings-test'
    else:
        from django.core.exceptions import ImproperlyConfigured
        raise ImproperlyConfigured('SECRET_KEY precisa estar configurada no ambiente.')''',
        name,
    )
    content = replace_once(
        content,
        "DEBUG = 'RENDER' not in os.environ",
        "DEBUG = os.environ.get('DEBUG', 'false').strip().lower() in {'true', '1', 'yes', 'on'}",
        name,
    )
    content = replace_once(
        content,
        '''ALLOWED_HOSTS = ['localhost', '127.0.0.1']

RENDER_EXTERNAL_HOSTNAME = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)
else:
    ALLOWED_HOSTS.append('*')''',
        '''ALLOWED_HOSTS = ['localhost', '127.0.0.1']
ALLOWED_HOSTS.extend(
    host.strip()
    for host in os.environ.get('APP_ALLOWED_HOSTS', '').split(',')
    if host.strip()
)
RENDER_EXTERNAL_HOSTNAME = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)
# Deliberadamente sem wildcard '*': cadastrar todos os domínios utilizados.''',
        name,
    )

    # Substitui os dois passwords hardcoded SEM copiar seus valores para o patch.
    match = re.findall(r"(?m)^[ \t]*'PASSWORD':[ \t]*'[^'\r\n]*',[ \t]*$", content)
    if len(match) != 2:
        raise RuntimeError(f"{name}: esperado 2 campos PASSWORD literais, encontrados {len(match)}")
    content = content.replace(match[0], "        'PASSWORD': os.environ.get('DB_PASSWORD', ''),", 1)
    content = content.replace(match[1], "        'PASSWORD': os.environ.get('VENDAS_DB_PASSWORD', ''),", 1)
    content = replace_once(
        content,
        "# --- SENHAS E I18N ---",
        '''# Cabeçalhos HTTPS entregues pelo proxy reverso confiável do Render.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

# --- SENHAS E I18N ---''',
        name,
    )
    return content


def auth_changes(content: str) -> str:
    name = "financeiro_core/app/api/auth.py"
    content = replace_once(
        content,
        "return jwt.decode(token, SECRET_KEY, algorithms=[\"HS256\"])",
        "return jwt.decode(token, SECRET_KEY, algorithms=[\"HS256\"], options={\"require\": [\"exp\", \"user_id\"]})",
        name,
    )
    content = replace_once(
        content,
        '''    except User.DoesNotExist:
        raise HttpError(401, "Usuário não encontrado")

    return user, payload.get("active_loja_id")''',
        '''    except User.DoesNotExist:
        raise HttpError(401, "Usuário não encontrado")
    if not user.is_active:
        raise HttpError(401, "Usuário desativado")

    return user, payload.get("active_loja_id")''',
        name,
    )
    content = replace_once(
        content,
        '''    except User.DoesNotExist:
        raise HttpError(401, "Credenciais inválidas")

    # Verifica o hash da senha''',
        '''    except User.DoesNotExist:
        raise HttpError(401, "Credenciais inválidas")
    if not user.is_active:
        raise HttpError(401, "Credenciais inválidas")

    # Verifica o hash da senha''',
        name,
    )
    # Elimina logs de usuário/token nas trocas de loja.
    for needle in (
        '    print(f"DEBUG: Trocando para a loja ID {payload.loja_id}")\n',
        '    print("DEBUG: Permissão confirmada")\n',
        '    print("DEBUG: Novo token gerado")\n',
    ):
        content = replace_once(content, needle, '', name)
    return content


def security_changes(content: str) -> str:
    name = "financeiro_core/app/api/security.py"
    old = '''class AuthBearer(HttpBearer):
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
            return None'''
    new = '''class AuthBearer(HttpBearer):
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
            return None'''
    return replace_once(content, old, new, name)


def endpoints_changes(content: str) -> str:
    name = "financeiro_core/app/api/endpoints.py"
    old = '''def listar_perfis_taxas(request, loja_id: Optional[int] = None):
    """Lista perfis de taxas, opcionalmente filtrando por loja."""
    if loja_id:
        check_permission(request, loja_id)

    qs = PerfilTaxaCartao.objects.filter(ativo=True).prefetch_related('taxas')
    if loja_id:
        qs = qs.filter(loja_id_externo=loja_id)
    return qs'''
    new = '''def listar_perfis_taxas(request, loja_id: Optional[int] = None):
    """Lista taxas exclusivamente da loja ativa; filtro explícito não amplia escopo."""
    active_loja_id = getattr(request, 'active_loja_id', None)
    if active_loja_id is None:
        raise HttpError(403, "Nenhuma loja ativa no contexto")
    if loja_id is not None:
        check_permission(request, loja_id)
    else:
        loja_id = active_loja_id

    return PerfilTaxaCartao.objects.filter(
        ativo=True,
        loja_id_externo=loja_id,
    ).prefetch_related('taxas')'''
    return replace_once(content, old, new, name)


CHANGES = {
    'config/settings.py': settings_changes,
    'financeiro_core/app/api/auth.py': auth_changes,
    'financeiro_core/app/api/security.py': security_changes,
    'financeiro_core/app/api/endpoints.py': endpoints_changes,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.cwd(), help='Raiz do clone Financeiro')
    parser.add_argument('--check', action='store_true', help='Validar sem gravar arquivos')
    args = parser.parse_args()
    root = args.root.resolve()
    updated: dict[Path, str] = {}
    for filename, transformer in CHANGES.items():
        path = root / filename
        if not path.is_file():
            raise RuntimeError(f"Arquivo ausente: {path}")
        original = path.read_text(encoding='utf-8')
        modified = transformer(original)
        compile(modified, str(path), 'exec')
        updated[path] = modified
    print(f"Validação concluída: {len(updated)} arquivos; todos os trechos esperados foram encontrados.")
    if args.check:
        return 0
    for path, content in updated.items():
        fd, tmpname = tempfile.mkstemp(prefix='.phase1a-', dir=str(path.parent), text=True)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as handle:
                handle.write(content)
            os.replace(tmpname, path)
        finally:
            if os.path.exists(tmpname):
                os.unlink(tmpname)
    print('Arquivos atualizados. Revise: git diff --check && git diff --stat')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except RuntimeError as error:
        print(f'ERRO: {error}', file=sys.stderr)
        raise SystemExit(1)
