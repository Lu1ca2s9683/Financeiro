import inspect
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from ninja.testing import TestClient

from financeiro_core.app.api.endpoints import (
    TransferenciaIn,
    calcular_fechamento,
    registrar_transferencia,
    router,
)
from financeiro_core.models import ContaBancaria, MovimentacaoCaixa

from .helpers import create_test_token


class Phase1EndpointSourceContractTest(SimpleTestCase):
    def test_fechamento_has_one_schema_one_route_and_explicit_signature(self):
        source_path = Path(settings.BASE_DIR) / "financeiro_core" / "app" / "api" / "endpoints.py"
        source = source_path.read_text(encoding="utf-8")

        self.assertEqual(source.count("class FechamentoOut"), 1)
        self.assertEqual(
            source.count('@router.post("/fechamento/calcular/{loja_id}/{mes}/{ano}"'),
            1,
        )
        self.assertEqual(
            list(inspect.signature(calcular_fechamento).parameters),
            ["request", "loja_id", "mes", "ano"],
        )


class ContasTransferenciaApiTest(TestCase):
    databases = {"default", "vendas"}

    def setUp(self):
        self.client = TestClient(router)
        self.user = User.objects.using("vendas").create(username="phase1-user")
        self.loja_id = 10
        self.headers = {
            "Authorization": f"Bearer {create_test_token(self.user.id, self.loja_id)}"
        }
        self.origem = ContaBancaria.objects.create(
            nome="Caixa",
            tipo="CAIXA_FISICO",
            loja_id_externo=self.loja_id,
            saldo_inicial=Decimal("100.00"),
            saldo_atual=Decimal("100.00"),
        )
        self.destino = ContaBancaria.objects.create(
            nome="Banco",
            tipo="CONTA_CORRENTE",
            banco_codigo="001",
            agencia="1234",
            conta="5678-9",
            loja_id_externo=self.loja_id,
            saldo_inicial=Decimal("25.00"),
            saldo_atual=Decimal("25.00"),
        )
        self.inativa = ContaBancaria.objects.create(
            nome="Inativa",
            loja_id_externo=self.loja_id,
            ativo=False,
        )
        self.outra_loja = ContaBancaria.objects.create(
            nome="Outra loja",
            loja_id_externo=self.loja_id + 1,
        )

    def _transfer_payload(self, **overrides):
        payload = {
            "conta_origem_id": self.origem.id,
            "conta_destino_id": self.destino.id,
            "valor": "30.50",
            "data": "2026-08-29",
            "descricao": "Sangria para o banco",
        }
        payload.update(overrides)
        return payload

    def test_get_contas_returns_only_active_accounts_from_active_store(self):
        response = self.client.get("/contas/", headers=self.headers)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual([item["id"] for item in data], [self.origem.id, self.destino.id])
        self.assertEqual(
            set(data[0]),
            {
                "id",
                "nome",
                "tipo",
                "banco_codigo",
                "agencia",
                "conta",
                "saldo_inicial",
                "saldo_atual",
                "ativo",
            },
        )
        self.assertEqual(Decimal(str(data[0]["saldo_inicial"])), Decimal("100.00"))
        self.assertEqual(Decimal(str(data[0]["saldo_atual"])), Decimal("100.00"))

    def test_get_contas_requires_authentication(self):
        response = self.client.get("/contas/")

        self.assertEqual(response.status_code, 401)

    def test_transfer_success_creates_both_movements_with_request_date(self):
        response = self.client.post(
            "/contas/transferencia",
            json=self._transfer_payload(),
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 200)
        movements = list(MovimentacaoCaixa.objects.order_by("id"))
        self.assertEqual(len(movements), 2)
        self.assertEqual(
            [movement.tipo_movimentacao for movement in movements],
            ["TRANSFERENCIA_SAIDA", "TRANSFERENCIA_ENTRADA"],
        )
        self.assertTrue(all(movement.data_ocorrencia.date() == date(2026, 8, 29) for movement in movements))

        self.origem.refresh_from_db()
        self.destino.refresh_from_db()
        self.assertEqual(self.origem.saldo_atual, Decimal("69.50"))
        self.assertEqual(self.destino.saldo_atual, Decimal("55.50"))

    def test_transfer_rejects_same_source_and_destination(self):
        response = self.client.post(
            "/contas/transferencia",
            json=self._transfer_payload(conta_destino_id=self.origem.id),
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(MovimentacaoCaixa.objects.exists())

    def test_transfer_requires_authentication(self):
        response = self.client.post(
            "/contas/transferencia",
            json=self._transfer_payload(),
        )

        self.assertEqual(response.status_code, 401)
        self.assertFalse(MovimentacaoCaixa.objects.exists())

    def test_transfer_rejects_non_positive_value(self):
        response = self.client.post(
            "/contas/transferencia",
            json=self._transfer_payload(valor="0.00"),
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(MovimentacaoCaixa.objects.exists())

    def test_transfer_rejects_account_from_another_store(self):
        response = self.client.post(
            "/contas/transferencia",
            json=self._transfer_payload(conta_destino_id=self.outra_loja.id),
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(MovimentacaoCaixa.objects.exists())

    def test_transfer_rolls_back_first_side_when_second_creation_fails(self):
        real_create = MovimentacaoCaixa.objects.create
        call_count = 0

        def create_then_fail(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise RuntimeError("simulated destination failure")
            return real_create(**kwargs)

        request = SimpleNamespace(
            auth=None,
            active_loja_id=self.loja_id,
            user_id=self.user.id,
        )
        payload = TransferenciaIn(**self._transfer_payload(data=date(2026, 8, 29)))

        with patch.object(MovimentacaoCaixa.objects, "create", side_effect=create_then_fail):
            with self.assertRaisesRegex(RuntimeError, "simulated destination failure"):
                registrar_transferencia(request, payload)

        self.assertFalse(MovimentacaoCaixa.objects.exists())
        self.origem.refresh_from_db()
        self.destino.refresh_from_db()
        self.assertEqual(self.origem.saldo_atual, Decimal("100.00"))
        self.assertEqual(self.destino.saldo_atual, Decimal("25.00"))
