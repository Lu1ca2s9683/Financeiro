"""Testes de regressão da primeira etapa de hardening (Fase 1A)."""
import datetime

import jwt
from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase
from ninja.testing import TestClient

from financeiro_core.app.api.auth import router as auth_router
from financeiro_core.app.api.endpoints import router as financeiro_router
from financeiro_core.models import PerfilTaxaCartao
from financeiro_core.tests.helpers import create_test_token


class SecurityPhase1ATest(TestCase):
    databases = {'default', 'vendas'}

    def setUp(self):
        self.user = User.objects.db_manager('vendas').create_user(
            username='fase1-seguranca', password='strong-test-password', is_active=True
        )
        self.user.is_superuser = False
        self.auth_client = TestClient(auth_router)
        self.fin_client = TestClient(financeiro_router)

    def test_disabled_user_cannot_log_in(self):
        self.user.is_active = False
        self.user.save(using='vendas')
        response = self.auth_client.post('/login', json={
            'username': self.user.username, 'password': 'strong-test-password'
        })
        self.assertEqual(response.status_code, 401)

    def test_disabled_user_token_is_rejected(self):
        self.user.is_active = False
        self.user.save(using='vendas')
        response = self.fin_client.get('/contas/', headers={
            'Authorization': f'Bearer {create_test_token(self.user.id, 1)}'
        })
        self.assertEqual(response.status_code, 401)

    def test_token_without_expiration_is_rejected(self):
        token = jwt.encode(
            {'user_id': self.user.id, 'active_loja_id': 1},
            settings.SECRET_KEY,
            algorithm='HS256',
        )
        response = self.fin_client.get('/contas/', headers={'Authorization': f'Bearer {token}'})
        self.assertEqual(response.status_code, 401)

    def test_tax_profiles_without_explicit_store_are_isolated(self):
        PerfilTaxaCartao.objects.create(
            nome='Perfil da loja 10', loja_id_externo=10,
            data_inicio_vigencia=datetime.date(2026, 1, 1),
        )
        PerfilTaxaCartao.objects.create(
            nome='Perfil da loja 20', loja_id_externo=20,
            data_inicio_vigencia=datetime.date(2026, 1, 1),
        )
        headers = {'Authorization': f'Bearer {create_test_token(self.user.id, 10)}'}
        response = self.fin_client.get('/taxas/perfis/', headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual([x['nome'] for x in response.json()], ['Perfil da loja 10'])

    def test_tax_profiles_cannot_be_queried_for_another_store(self):
        headers = {'Authorization': f'Bearer {create_test_token(self.user.id, 10)}'}
        response = self.fin_client.get('/taxas/perfis/?loja_id=20', headers=headers)
        self.assertEqual(response.status_code, 403)
