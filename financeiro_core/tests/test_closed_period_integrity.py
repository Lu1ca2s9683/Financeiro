from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from ninja.testing import TestClient

from financeiro_core.app.api.endpoints import router
from financeiro_core.models import (
    CategoriaDespesa,
    ContaPagar,
    FechamentoMensal,
    RateioDespesa,
)

from .helpers import create_test_token


class ClosedPeriodIntegrityTest(TestCase):
    databases = {"default", "vendas"}

    def setUp(self):
        self.client = TestClient(router)
        self.loja_id = 12
        user = User.objects.using("vendas").create(username="closed-period")
        User.objects.using("default").create(username="closed-period")
        self.headers = {
            "Authorization": f"Bearer {create_test_token(user.id, self.loja_id)}"
        }
        self.categoria = CategoriaDespesa.objects.create(
            nome="Administrativa", grupo_contabil="ADMINISTRATIVA"
        )
        self.outra_categoria = CategoriaDespesa.objects.create(
            nome="Custos", grupo_contabil="CUSTOS"
        )
        self.fechamento = FechamentoMensal.objects.create(
            loja_id_externo=self.loja_id,
            mes=1,
            ano=2026,
            faturamento_bruto=Decimal("1000.00"),
            total_taxas=Decimal("10.00"),
            receita_liquida=Decimal("900.00"),
            total_despesas=Decimal("100.00"),
            resultado_operacional=Decimal("800.00"),
            status="CONCLUIDO",
            dados_auditoria_snapshot={"frozen": True},
        )

    def _payload(self, transacao, **overrides):
        payload = {
            "descricao": "Despesa",
            "loja_id": self.loja_id,
            "categoria_id": self.categoria.id,
            "valor": "100.00",
            "data_competencia": "2026-02-01",
            "data_transacao": transacao,
            "rateios": [],
        }
        payload.update(overrides)
        return payload

    def _despesa(self, transacao):
        return ContaPagar.objects.create(
            descricao="Persistida",
            loja_id_externo=self.loja_id,
            categoria=self.categoria,
            valor_bruto=Decimal("100.00"),
            data_competencia=date(2026, 2, 1),
            data_transacao=transacao,
        )

    def test_create_in_closed_cash_period_is_rejected(self):
        response = self.client.post(
            "/despesas/", json=self._payload("2026-01-15"), headers=self.headers
        )

        self.assertEqual(response.status_code, 409)
        self.assertFalse(ContaPagar.objects.exists())

    def test_other_store_closed_period_does_not_block_create(self):
        FechamentoMensal.objects.filter(pk=self.fechamento.pk).update(loja_id_externo=99)

        response = self.client.post(
            "/despesas/", json=self._payload("2026-01-15"), headers=self.headers
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(ContaPagar.objects.get().loja_id_externo, self.loja_id)

    def test_edit_currently_in_closed_cash_period_is_rejected(self):
        despesa = self._despesa(date(2026, 1, 15))

        response = self.client.put(
            f"/despesas/{despesa.id}",
            json=self._payload("2026-02-15", descricao="Alterada"),
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 409)
        despesa.refresh_from_db()
        self.assertEqual(despesa.descricao, "Persistida")

    def test_move_from_open_into_closed_cash_period_is_rejected(self):
        despesa = self._despesa(date(2026, 2, 15))

        response = self.client.put(
            f"/despesas/{despesa.id}",
            json=self._payload("2026-01-15", descricao="Movida"),
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 409)
        despesa.refresh_from_db()
        self.assertEqual(despesa.data_transacao, date(2026, 2, 15))

    def test_delete_in_closed_cash_period_is_rejected(self):
        despesa = self._despesa(date(2026, 1, 15))

        response = self.client.delete(f"/despesas/{despesa.id}", headers=self.headers)

        self.assertEqual(response.status_code, 409)
        self.assertTrue(ContaPagar.objects.filter(pk=despesa.pk).exists())

    def test_rateios_cannot_be_replaced_in_closed_cash_period(self):
        despesa = self._despesa(date(2026, 1, 15))
        rateio = RateioDespesa.objects.create(
            despesa=despesa,
            descricao="Original",
            valor=Decimal("100.00"),
            categoria=self.categoria,
        )
        payload = self._payload(
            "2026-01-15",
            rateios=[
                {
                    "descricao": "Novo",
                    "valor": "100.00",
                    "categoria_id": self.outra_categoria.id,
                }
            ],
        )

        response = self.client.put(
            f"/despesas/{despesa.id}", json=payload, headers=self.headers
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(list(despesa.splits.values_list("id", flat=True)), [rateio.id])

    @patch("financeiro_core.app.services.dre_service.VendasClientSQL.get_faturamento_por_loja")
    def test_recalculation_of_closed_period_is_rejected_without_query_or_mutation(
        self, get_sales
    ):
        before = {
            "faturamento_bruto": self.fechamento.faturamento_bruto,
            "total_taxas": self.fechamento.total_taxas,
            "receita_liquida": self.fechamento.receita_liquida,
            "total_despesas": self.fechamento.total_despesas,
            "resultado_operacional": self.fechamento.resultado_operacional,
            "dados_auditoria_snapshot": self.fechamento.dados_auditoria_snapshot,
        }

        response = self.client.post(
            "/fechamento/calcular/12/1/2026", headers=self.headers
        )

        self.assertEqual(response.status_code, 409)
        get_sales.assert_not_called()
        self.fechamento.refresh_from_db()
        after = {field: getattr(self.fechamento, field) for field in before}
        self.assertEqual(after, before)
