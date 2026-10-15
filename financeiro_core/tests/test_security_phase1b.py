"""Regressao Fase 1B: GLOBAL e GESTOR_GRUPO, sem acesso residual."""
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

    def test_global_access_without_group_membership(self):
        self.user.is_superuser = True
        self.user.save(using='vendas')

        with connections['vendas'].cursor() as cursor:
            cursor.execute(
                'DELETE FROM vendas_grupolojas_super_usuarios_grupo '
                'WHERE user_id = %s',
                [self.user.pk],
            )

        response = self.fin.get('/contas/', headers=self.headers)
        self.assertEqual(response.status_code, 200)

        me = self.auth.get('/me', headers=self.headers)
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()['active_loja']['role'], 'GLOBAL')

    def test_inactive_store_revokes_existing_token(self):
        with connections['vendas'].cursor() as cursor:
            cursor.execute(
                'UPDATE vendas_loja SET ativa = 0 WHERE id = %s',
                [self.loja_id],
            )

        response = self.fin.get('/contas/', headers=self.headers)
        self.assertEqual(response.status_code, 401)
