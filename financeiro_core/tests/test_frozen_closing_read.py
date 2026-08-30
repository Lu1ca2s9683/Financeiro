from copy import deepcopy
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from ninja.testing import TestClient

from financeiro_core.app.api.endpoints import router
from financeiro_core.models import FechamentoMensal

from .helpers import create_test_token


class FrozenClosingReadApiTest(TestCase):
    databases = {"default", "vendas"}

    def setUp(self):
        self.client = TestClient(router)
        self.loja_id = 31
        self.user = User.objects.using("vendas").create(username="frozen-read")
        User.objects.using("default").create(username="frozen-read")
        self.headers = {
            "Authorization": f"Bearer {create_test_token(self.user.id, self.loja_id)}"
        }
        self.snapshot = {
            "identificacao": {
                "loja_id": self.loja_id,
                "mes": 1,
                "ano": 2026,
                "regime": "CAIXA",
            },
            "resumo": {
                "receita_bruta": "1000.00",
                "total_dinheiro": "100.00",
                "total_cartao": "700.00",
                "total_pix": "200.00",
                "total_outros": "0.00",
                "impostos": "100.00",
                "receita_liquida": "900.00",
                "custos_produtos": "100.00",
                "lucro_bruto": "800.00",
                "despesas_operacionais": "100.00",
                "resultado_operacional": "700.00",
                "despesas_financeiras_total": "37.00",
                "lucro_liquido": "663.00",
            },
        }
        self.fechamento = FechamentoMensal.objects.create(
            loja_id_externo=self.loja_id,
            mes=1,
            ano=2026,
            faturamento_bruto=Decimal("1000.00"),
            total_taxas=Decimal("7.00"),
            receita_liquida=Decimal("900.00"),
            total_despesas=Decimal("100.00"),
            resultado_operacional=Decimal("700.00"),
            status="CONCLUIDO",
            dados_auditoria_snapshot=deepcopy(self.snapshot),
        )

    @property
    def url(self):
        return f"/fechamento/{self.loja_id}/1/2026"

    def test_requires_authentication(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 401)

    def test_rejects_another_active_store(self):
        other_headers = {
            "Authorization": f"Bearer {create_test_token(self.user.id, self.loja_id + 1)}"
        }

        response = self.client.get(self.url, headers=other_headers)

        self.assertEqual(response.status_code, 403)

    def test_rejects_invalid_month(self):
        response = self.client.get(
            f"/fechamento/{self.loja_id}/13/2026", headers=self.headers
        )

        self.assertEqual(response.status_code, 400)

    def test_missing_persisted_closing_returns_404(self):
        response = self.client.get(
            f"/fechamento/{self.loja_id}/2/2026", headers=self.headers
        )

        self.assertEqual(response.status_code, 404)

    @patch("financeiro_core.app.services.dre_service.DREService.gerar")
    @patch(
        "financeiro_core.app.services.dre_service.VendasClientSQL.get_faturamento_por_loja"
    )
    def test_concluded_read_uses_only_frozen_state_without_mutation_or_calculation(
        self, get_sales, gerar_dre
    ):
        before = {
            field: deepcopy(getattr(self.fechamento, field))
            for field in (
                "faturamento_bruto",
                "total_taxas",
                "receita_liquida",
                "total_despesas",
                "resultado_operacional",
                "status",
                "dados_auditoria_snapshot",
            )
        }

        response = self.client.get(self.url, headers=self.headers)

        self.assertEqual(response.status_code, 200)
        get_sales.assert_not_called()
        gerar_dre.assert_not_called()
        data = response.json()
        self.assertEqual(data["status"], "CONCLUIDO")
        expected = {
            "faturamento_bruto": "1000.00",
            "total_dinheiro": "100.00",
            "total_cartao": "700.00",
            "total_pix": "200.00",
            "total_outros": "0.00",
            "impostos": "100.00",
            "receita_liquida": "900.00",
            "custos_produtos": "100.00",
            "lucro_bruto": "800.00",
            "despesas_operacionais": "100.00",
            "resultado_operacional": "700.00",
            "despesas_financeiras": "37.00",
            "lucro_liquido": "663.00",
        }
        for field, value in expected.items():
            self.assertEqual(Decimal(str(data[field])), Decimal(value), field)

        self.fechamento.refresh_from_db()
        after = {field: getattr(self.fechamento, field) for field in before}
        self.assertEqual(after, before)

    def test_phase2_snapshot_returns_exact_frozen_payment_breakdown(self):
        response = self.client.get(self.url, headers=self.headers)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(Decimal(str(data["total_dinheiro"])), Decimal("100.00"))
        self.assertEqual(Decimal(str(data["total_cartao"])), Decimal("700.00"))
        self.assertEqual(Decimal(str(data["total_pix"])), Decimal("200.00"))
        self.assertEqual(Decimal(str(data["total_outros"])), Decimal("0.00"))

    def test_legacy_snapshot_returns_null_for_unavailable_payment_breakdown(self):
        legacy_snapshot = deepcopy(self.snapshot)
        for field in (
            "total_dinheiro",
            "total_cartao",
            "total_pix",
            "total_outros",
        ):
            legacy_snapshot["resumo"].pop(field)
        self.fechamento.dados_auditoria_snapshot = legacy_snapshot
        self.fechamento.save(update_fields=["dados_auditoria_snapshot"])

        response = self.client.get(self.url, headers=self.headers)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsNone(data["total_dinheiro"])
        self.assertIsNone(data["total_cartao"])
        self.assertIsNone(data["total_pix"])
        self.assertIsNone(data["total_outros"])
        self.assertEqual(Decimal(str(data["faturamento_bruto"])), Decimal("1000.00"))
        self.assertEqual(Decimal(str(data["impostos"])), Decimal("100.00"))

    def test_missing_legacy_snapshot_value_is_null_instead_of_fabricated(self):
        self.fechamento.dados_auditoria_snapshot = None
        self.fechamento.save(update_fields=["dados_auditoria_snapshot"])

        response = self.client.get(self.url, headers=self.headers)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(Decimal(str(data["faturamento_bruto"])), Decimal("1000.00"))
        self.assertEqual(Decimal(str(data["receita_liquida"])), Decimal("900.00"))
        self.assertEqual(
            Decimal(str(data["despesas_operacionais"])), Decimal("100.00")
        )
        self.assertEqual(
            Decimal(str(data["resultado_operacional"])), Decimal("700.00")
        )
        self.assertIsNone(data["impostos"])
        self.assertIsNone(data["custos_produtos"])
        self.assertIsNone(data["lucro_bruto"])
        self.assertIsNone(data["despesas_financeiras"])
        self.assertIsNone(data["lucro_liquido"])
