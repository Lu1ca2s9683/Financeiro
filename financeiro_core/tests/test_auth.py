import datetime
from types import SimpleNamespace
from unittest.mock import patch

import jwt
from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase
from ninja.testing import TestClient

from financeiro_core.app.api.auth import router as auth_router
from financeiro_core.app.api.security import AuthBearer
from .helpers import create_test_token


class AuthBoundaryTest(TestCase):
    databases = {"default", "vendas"}

    def setUp(self):
        self.password = "password"
        self.user = User.objects.db_manager("vendas").create_user(
            username="testauthuser",
            password=self.password,
            first_name="Test",
            email="testauth@example.com",
        )
        self.loja_id = 1
        self.token = create_test_token(self.user.id, self.loja_id)

    def test_auth_bearer_valid_token_uses_isolated_sales_db(self):
        request = SimpleNamespace()

        result = AuthBearer().authenticate(request, self.token)

        self.assertEqual(result.id, self.user.id)
        self.assertEqual(request.user_id, self.user.id)
        self.assertEqual(request.active_loja_id, self.loja_id)
        self.assertEqual(request.user.id, self.user.id)

    def test_auth_bearer_rejects_nonexistent_sales_user(self):
        request = SimpleNamespace()
        invalid_token = create_test_token(999999, self.loja_id)

        result = AuthBearer().authenticate(request, invalid_token)

        self.assertIsNone(result)

    def test_auth_bearer_rejects_invalid_signature(self):
        request = SimpleNamespace()
        invalid_token = jwt.encode(
            {"user_id": self.user.id, "active_loja_id": self.loja_id},
            "wrong-secret",
            algorithm="HS256",
        )

        result = AuthBearer().authenticate(request, invalid_token)

        self.assertIsNone(result)

    @patch("financeiro_core.app.api.auth.fetch_user_lojas", return_value=[])
    def test_login_uses_isolated_sales_user_without_external_sql(self, mock_fetch_user_lojas):
        client = TestClient(auth_router)

        response = client.post(
            "/login",
            json={"username": self.user.username, "password": self.password},
        )

        self.assertEqual(response.status_code, 200)
        token = response.json()["token"]
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        self.assertEqual(payload["user_id"], self.user.id)
        self.assertIsNone(payload["active_loja_id"])
        mock_fetch_user_lojas.assert_called_once_with(self.user.id, self.user.is_superuser)

    @patch("financeiro_core.app.api.auth.fetch_user_lojas")
    def test_auth_me_accepts_valid_financeiro_token(self, mock_fetch_user_lojas):
        mock_fetch_user_lojas.return_value = [
            {"id": self.loja_id, "nome": "Loja principal", "role": "GESTOR"}
        ]
        client = TestClient(auth_router)

        response = client.get(
            "/me",
            headers={"Authorization": f"Bearer {self.token}"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["user"]["id"], self.user.id)
        self.assertEqual(response.json()["active_loja"]["id"], self.loja_id)

    @patch("financeiro_core.app.api.auth.fetch_user_lojas", return_value=[])
    def test_auth_me_rejects_nonexistent_sales_user(self, mock_fetch_user_lojas):
        client = TestClient(auth_router)
        token = create_test_token(999999, self.loja_id)

        response = client.get(
            "/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 401)
        mock_fetch_user_lojas.assert_not_called()

    def test_auth_me_rejects_expired_token(self):
        client = TestClient(auth_router)
        token = jwt.encode(
            {
                "user_id": self.user.id,
                "active_loja_id": self.loja_id,
                "exp": datetime.datetime.utcnow() - datetime.timedelta(minutes=1),
            },
            settings.SECRET_KEY,
            algorithm="HS256",
        )

        response = client.get(
            "/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 401)

    def test_auth_me_rejects_invalid_token(self):
        client = TestClient(auth_router)

        response = client.get(
            "/me",
            headers={"Authorization": "Bearer not-a-jwt"},
        )

        self.assertEqual(response.status_code, 401)

    @patch("financeiro_core.app.api.auth.fetch_user_lojas")
    def test_switch_loja_token_immediately_updates_auth_me_store(self, mock_fetch_user_lojas):
        mock_fetch_user_lojas.return_value = [
            {"id": self.loja_id, "nome": "Loja principal", "role": "GESTOR"},
            {"id": 2, "nome": "Loja destino", "role": "GESTOR"},
        ]
        client = TestClient(auth_router)

        switch_response = client.post(
            "/switch-loja",
            json={"loja_id": 2},
            headers={"Authorization": f"Bearer {self.token}"},
        )

        self.assertEqual(switch_response.status_code, 200)
        new_token = switch_response.json()["token"]
        self.assertNotEqual(new_token, self.token)

        me_response = client.get(
            "/me",
            headers={"Authorization": f"Bearer {new_token}"},
        )

        self.assertEqual(me_response.status_code, 200)
        self.assertEqual(me_response.json()["active_loja"]["id"], 2)
