#!/usr/bin/env python3
"""Fase 1B: bloqueio a perfis nao gestores e revogacao por requisicao.
Execute no diretorio raiz do projeto. --check nao altera arquivos.
"""
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# O script reside em scripts/ na copia usada pelo Codespaces.
FILES = {
    'financeiro_core/app/api/auth.py': None,
    'financeiro_core/app/api/security.py': None,
    'financeiro_core/tests/helpers.py': None,
    'financeiro_core/tests/test_auth.py': None,
    'financeiro-frontend/src/services/api.ts': None,
    'financeiro-frontend/src/app/login/page.tsx': None,
}


def replace_once(content, before, after, file):
    n = content.count(before)
    if n != 1:
        raise RuntimeError(f'{file}: trecho esperado encontrado {n} vezes (esperado: 1). Nao alterar.')
    return content.replace(before, after, 1)


def update_auth(s):
    path='auth.py'
    start=s.index('def fetch_user_lojas(')
    end=s.index('\ndef mount_grupos(',start)
    original=s[start:end]
    if 'SELECT id, nome FROM vendas_loja' not in original or 'vendas_grupolojas_super_usuarios_grupo' not in original:
        raise RuntimeError('auth.py: bloco de permissoes mudou; inspecionar manualmente')
    new='''def fetch_user_lojas(user_id: int, is_superuser: bool) -> List[dict]:
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

        cursor.execute(''' + "'''" + '''
            SELECT DISTINCT l.id, l.nome
            FROM vendas_loja l
            JOIN vendas_grupolojas_super_usuarios_grupo gsu
              ON gsu.grupolojas_id = l.grupo_id
            WHERE gsu.user_id = %s AND l.ativa = true
            ORDER BY l.id
        ''' + "'''" + ''', [user_id])
        return [
            {'id': row[0], 'nome': row[1], 'role': 'GESTOR_GRUPO'}
            for row in cursor.fetchall()
        ]
'''
    s=s[:start]+new+s[end:]

    s=replace_once(s,
'''    active_loja_id = None
    if lojas:
        active_loja_id = lojas[0]["id"]
''',
'''    if not lojas:
        raise HttpError(403, "Usuario sem permissao para acessar o Financeiro")
    active_loja_id = lojas[0]["id"]
''',path)

    s=replace_once(s,
'''    payload = decode_token(token)

    try:
        user = User.objects.using('vendas').get(id=payload["user_id"])''',
'''    payload = decode_token(token)
    if type(payload.get("user_id")) is not int:
        raise HttpError(401, "Token invalido")

    try:
        user = User.objects.using('vendas').get(id=payload["user_id"])''',path)

    s=replace_once(s,
'''    return user, payload.get("active_loja_id")''',
'''    active_loja_id = payload.get("active_loja_id")
    if type(active_loja_id) is not int:
        raise HttpError(403, "Loja ativa invalida")
    lojas = fetch_user_lojas(user.id, user.is_superuser)
    if not any(loja["id"] == active_loja_id for loja in lojas):
        raise HttpError(403, "Acesso financeiro revogado ou loja indisponivel")
    request.financeiro_lojas = lojas
    return user, active_loja_id''',path)

    s=replace_once(s,
'''    lojas = fetch_user_lojas(user.id, user.is_superuser)
    grupos = mount_grupos(lojas)''',
'''    lojas = request.financeiro_lojas
    grupos = mount_grupos(lojas)''',path)

    s=replace_once(s,
'''    # Fallback para a primeira loja, se houver
    if not active_loja and lojas:
        active_loja = lojas[0]
''',
'''    # Token de loja revogada nunca migra silenciosamente para outra loja.
''',path)

    s=replace_once(s,
'''    lojas = fetch_user_lojas(user.id, user.is_superuser)

    # Valida se o usuário tem acesso à loja''',
'''    lojas = request.financeiro_lojas

    # Valida se o usuário tem acesso à loja''',path)
    return s


def update_security(s):
    path='security.py'
    s=replace_once(s,
'from django.contrib.auth.models import User\n',
'from django.contrib.auth.models import User\nfrom . import auth as financeiro_auth\n',path)
    s=replace_once(s,
'''            user = User.objects.using('vendas').get(id=user_id)
            if not user.is_active:
                return None

            request.user_id = user_id''',
'''            user = User.objects.using('vendas').get(id=user_id)
            if not user.is_active or type(loja_id) is not int:
                return None

            # O JWT sozinho nao comprova vinculo ATUAL com a loja.
            # Checagem a cada request: o vinculo revogado deixa de funcionar.
            lojas = financeiro_auth.fetch_user_lojas(user_id, user.is_superuser)
            loja = next((item for item in lojas if item['id'] == loja_id), None)
            if loja is None:
                return None

            request.financeiro_role = loja['role']
            request.user_id = user_id''',path)
    return s


def update_helper(s):
    path='helpers.py'
    s=replace_once(s,
'''from django.conf import settings
''',
'''from django.conf import settings
from django.db import connections


def seed_financial_access_test_store(user_id, active_loja_id):
    """Fixture de vinculo REAL em tabelas SQLite de teste, nunca em producao.

    O test router so migra auth/contenttypes no alias vendas. O esquema minimo
    dessas duas tabelas espelha as consultas do ERP no contrato financeiro.
    """
    if active_loja_id is None or connections['vendas'].vendor != 'sqlite':
        return
    with connections['vendas'].cursor() as cursor:
        cursor.execute(''' + "'''" + '''
            CREATE TABLE IF NOT EXISTS vendas_loja (
                id INTEGER PRIMARY KEY, nome TEXT NOT NULL,
                ativa BOOLEAN NOT NULL DEFAULT 1, grupo_id INTEGER NOT NULL
            )
        ''' + "'''" + ''')
        cursor.execute(''' + "'''" + '''
            CREATE TABLE IF NOT EXISTS vendas_grupolojas_super_usuarios_grupo (
                user_id INTEGER NOT NULL, grupolojas_id INTEGER NOT NULL,
                UNIQUE (user_id, grupolojas_id)
            )
        ''' + "'''" + ''')
        cursor.execute(
            "INSERT OR IGNORE INTO vendas_loja (id, nome, ativa, grupo_id) VALUES (%s, %s, 1, %s)",
            [active_loja_id, f"Loja teste {active_loja_id}", active_loja_id],
        )
        cursor.execute(
            "INSERT OR IGNORE INTO vendas_grupolojas_super_usuarios_grupo (user_id, grupolojas_id) "
            "VALUES (%s, %s)", [user_id, active_loja_id],
        )
''',path)
    s=replace_once(s,
'''def create_test_token(user_id, active_loja_id):
    payload = {''',
'''def create_test_token(user_id, active_loja_id):
    seed_financial_access_test_store(user_id, active_loja_id)
    payload = {''',path)
    return s


def update_auth_tests(s):
    path='test_auth.py'
    s=replace_once(s,
'''    @patch("financeiro_core.app.api.auth.fetch_user_lojas", return_value=[])
    def test_login_uses_isolated_sales_user_without_external_sql(self, mock_fetch_user_lojas):''',
'''    @patch("financeiro_core.app.api.auth.fetch_user_lojas", return_value=[
        {"id": 1, "nome": "Loja autorizada", "role": "GESTOR_GRUPO"}
    ])
    def test_login_uses_isolated_sales_user_without_external_sql(self, mock_fetch_user_lojas):''',path)
    s=replace_once(s,
'''        self.assertIsNone(payload["active_loja_id"])''',
'''        self.assertEqual(payload["active_loja_id"], 1)''',path)
    return s


TESTS='''"""Regressao Fase 1B: GLOBAL e GESTOR_GRUPO, sem acesso residual."""
from django.contrib.auth.models import User
from django.db import connections
from django.test import TestCase
from ninja.testing import TestClient
from financeiro_core.app.api.auth import router as auth_router, fetch_user_lojas
from financeiro_core.app.api.endpoints import router as financeiro_router
from .helpers import create_test_token


class FinancialRBACPhase1BTest(TestCase):
    databases = {'default', 'vendas'}

    def setUp(self):
        self.user = User.objects.db_manager('vendas').create_user(
            username='rbac-group-user', password='strong-password', is_active=True
        )
        self.loja_id = 31
        self.token = create_test_token(self.user.pk, self.loja_id)
        self.headers = {'Authorization': f'Bearer {self.token}'}
        self.fin = TestClient(financeiro_router)
        self.auth = TestClient(auth_router)

    def test_group_manager_may_read_own_store(self):
        r = self.fin.get('/contas/', headers=self.headers)
        self.assertEqual(r.status_code, 200)

    def test_revoked_group_membership_blocks_old_token(self):
        with connections['vendas'].cursor() as cursor:
            cursor.execute(
                'DELETE FROM vendas_grupolojas_super_usuarios_grupo '
                'WHERE user_id = %s AND grupolojas_id = %s',
                [self.user.pk, self.loja_id],
            )
        self.assertEqual(self.fin.get('/contas/', headers=self.headers).status_code, 401)
        self.assertEqual(self.auth.get('/me', headers=self.headers).status_code, 403)

    def test_other_store_not_authorized(self):
        self.assertEqual(
            self.fin.get(f'/dashboard/resumo/{self.loja_id + 1}/1/2026', headers=self.headers).status_code,
            403,
        )

    def test_non_manager_without_group_membership_denied(self):
        user = User.objects.db_manager('vendas').create_user(
            username='rbac-common-user', password='strong-password'
        )
        self.assertEqual(
            self.auth.post('/login', json={'username': user.username, 'password': 'strong-password'}).status_code,
            403,
        )
        # Mesmo com token assinado e ID da loja, nao herda o acesso.
        forged = create_test_token(user.pk, self.loja_id)
        with connections['vendas'].cursor() as cursor:
            cursor.execute(
                'DELETE FROM vendas_grupolojas_super_usuarios_grupo WHERE user_id = %s',
                [user.pk],
            )
        self.assertEqual(
            self.fin.get('/contas/', headers={'Authorization': f'Bearer {forged}'}).status_code,
            401,
        )

    def test_group_manager_login_only_lists_group_stores(self):
        response = self.auth.post(
            '/login', json={'username': self.user.username, 'password': 'strong-password'}
        )
        self.assertEqual(response.status_code, 200)
        me = self.auth.get('/me', headers={'Authorization': f'Bearer {response.json()["token"]}'})
        self.assertEqual(me.status_code, 200)
        self.assertEqual([item['role'] for item in me.json()['grupos'][0]['lojas']], ['GESTOR_GRUPO'])
'''



def update_frontend_api(s):
    return replace_once(
        s,
        "throw new Error('FORBIDDEN_DEVICE');",
        "throw new Error('FINANCEIRO_ACCESS_DENIED');",
        'api.ts',
    )


def update_login_page(s):
    return replace_once(
        s,
        "if (err.message === 'FORBIDDEN_DEVICE') {\n        setError('Acesso não autorizado neste dispositivo. Este dispositivo ainda não foi liberado pelo administrador global. Após a liberação, tente novamente.');",
        "if (err.message === 'FINANCEIRO_ACCESS_DENIED') {\n        setError('Acesso ao Financeiro permitido somente para gestores de grupo e administradores globais autorizados.');",
        'login/page.tsx',
    )

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--check',action='store_true',help='Valida alvos sem gravar')
    args=parser.parse_args()
    if not (ROOT/'manage.py').is_file():
        raise SystemExit(f'Esperado repositorio na pasta {ROOT}. Coloque o script em scripts/.')
    updaters={
        'financeiro_core/app/api/auth.py':update_auth,
        'financeiro_core/app/api/security.py':update_security,
        'financeiro_core/tests/helpers.py':update_helper,
        'financeiro_core/tests/test_auth.py':update_auth_tests,
        'financeiro-frontend/src/services/api.ts':update_frontend_api,
        'financeiro-frontend/src/app/login/page.tsx':update_login_page,
    }
    updated={}
    for name,fn in updaters.items():
        path=ROOT/name
        old=path.read_text(encoding='utf-8')
        new=fn(old)
        if old==new:raise RuntimeError(f'{name}: nenhuma alteracao')
        if path.suffix == '.py':
            compile(new,str(path),'exec')
        updated[path]=new
    new_test=ROOT/'financeiro_core/tests/test_security_phase1b.py'
    if new_test.exists():raise RuntimeError(f'{new_test} ja existe')
    compile(TESTS,str(new_test),'exec')
    print(f'Validacao OK: {len(updated)} arquivos e 1 novo modulo de testes.')
    if args.check:return
    for path,content in updated.items():
        path.write_text(content,encoding='utf-8')
        print(f'Atualizado: {path.relative_to(ROOT)}')
    new_test.write_text(TESTS,encoding='utf-8')
    print(f'Criado: {new_test.relative_to(ROOT)}')

if __name__=='__main__':main()
