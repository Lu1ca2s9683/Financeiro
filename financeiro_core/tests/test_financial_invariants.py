from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import TestCase
from ninja.testing import TestClient

from financeiro_core.app.api.endpoints import router
from financeiro_core.app.services.dre_service import DREService
from financeiro_core.domain.services import FaturamentoItemDTO, TaxaAplicavelDTO
from financeiro_core.models import CategoriaDespesa, ContaPagar

from .helpers import create_test_token


SALES_ITEMS = [
    FaturamentoItemDTO("DINHEIRO", "GERAL", 1, Decimal("100.00")),
    FaturamentoItemDTO("PIX", "GERAL", 1, Decimal("200.00")),
    FaturamentoItemDTO("DEBITO", "VISA", 1, Decimal("300.00")),
    FaturamentoItemDTO("CREDITO_AVISTA", "MASTER", 1, Decimal("400.00")),
]


class _CardOnlyFeeRepository:
    def buscar_taxa(self, loja_id, tipo, bandeira, parcelas):
        if tipo in {"DEBITO", "CREDITO_AVISTA"}:
            return TaxaAplicavelDTO(Decimal("1.00"), Decimal("0.00"))
        return None


class DRECascadeInvariantTest(TestCase):
    def setUp(self):
        valores = {
            "IMPOSTOS": "100.00",
            "CUSTOS": "100.00",
            "PESSOAL": "50.00",
            "ADMINISTRATIVA": "25.00",
            "MARKETING": "25.00",
            "FINANCEIRA": "30.00",
        }
        for grupo, valor in valores.items():
            categoria = CategoriaDespesa.objects.create(nome=grupo, grupo_contabil=grupo)
            ContaPagar.objects.create(
                descricao=grupo,
                loja_id_externo=8,
                categoria=categoria,
                valor_bruto=Decimal(valor),
                data_competencia=date(2025, 12, 1),
                data_transacao=date(2026, 1, 10),
            )

    def test_exact_cascade_and_card_fee_single_subtraction(self):
        vendas = MagicMock()
        vendas.get_faturamento_por_loja.return_value = SALES_ITEMS
        dre = DREService(
            vendas_client=vendas, repositorio_taxas=_CardOnlyFeeRepository()
        ).gerar(8, 1, 2026, "Loja 8", "teste")
        resumo = dre["resumo"]

        vendas.get_faturamento_por_loja.assert_called_once_with(8, 1, 2026)
        self.assertEqual(resumo["receita_bruta"], Decimal("1000.00"))
        self.assertEqual(resumo["total_dinheiro"], Decimal("100.00"))
        self.assertEqual(resumo["total_pix"], Decimal("200.00"))
        self.assertEqual(resumo["total_cartao"], Decimal("700.00"))
        self.assertEqual(resumo["total_outros"], Decimal("0.00"))
        self.assertEqual(
            resumo["receita_bruta"],
            resumo["total_dinheiro"]
            + resumo["total_cartao"]
            + resumo["total_pix"]
            + resumo["total_outros"],
        )
        self.assertEqual(
            resumo["receita_liquida"],
            resumo["receita_bruta"] - resumo["impostos"],
        )
        self.assertEqual(
            resumo["lucro_bruto"],
            resumo["receita_liquida"] - resumo["custos_produtos"],
        )
        self.assertEqual(
            resumo["despesas_operacionais"],
            resumo["despesas_pessoal"]
            + resumo["despesas_administrativas"]
            + resumo["despesas_marketing"],
        )
        self.assertEqual(
            resumo["resultado_operacional"],
            resumo["lucro_bruto"] - resumo["despesas_operacionais"],
        )
        self.assertEqual(resumo["taxas_cartao"], Decimal("7.00"))
        self.assertEqual(
            resumo["despesas_financeiras_total"],
            resumo["taxas_cartao"] + resumo["outras_despesas_financeiras"],
        )
        self.assertEqual(
            resumo["lucro_liquido"],
            resumo["resultado_operacional"]
            - resumo["despesas_financeiras_total"],
        )
        self.assertEqual(resumo["receita_liquida"], Decimal("900.00"))
        self.assertEqual(resumo["lucro_liquido"], Decimal("663.00"))


class DREAndClosingConsistencyTest(TestCase):
    databases = {"default", "vendas"}

    def setUp(self):
        self.client = TestClient(router)
        self.loja_id = 21
        user = User.objects.using("vendas").create(username="dre-closing")
        User.objects.using("default").create(username="dre-closing")
        self.headers = {
            "Authorization": f"Bearer {create_test_token(user.id, self.loja_id)}"
        }
        categoria = CategoriaDespesa.objects.create(
            nome="Administrativa", grupo_contabil="ADMINISTRATIVA"
        )
        ContaPagar.objects.create(
            descricao="Aluguel",
            loja_id_externo=self.loja_id,
            categoria=categoria,
            valor_bruto=Decimal("80.00"),
            data_competencia=date(2026, 1, 1),
            data_transacao=date(2026, 1, 10),
        )

    @patch(
        "financeiro_core.app.services.dre_repositories.DjangoRepositorioTaxas.buscar_taxa",
        return_value=None,
    )
    @patch(
        "financeiro_core.app.services.dre_service.VendasClientSQL.get_faturamento_por_loja",
        return_value=SALES_ITEMS,
    )
    def test_get_dre_and_post_closing_agree_from_one_sales_query_each(
        self, get_sales, _get_fee
    ):
        dre_response = self.client.get(
            f"/dre/{self.loja_id}/1/2026", headers=self.headers
        )
        closing_response = self.client.post(
            f"/fechamento/calcular/{self.loja_id}/1/2026", headers=self.headers
        )

        self.assertEqual(dre_response.status_code, 200)
        self.assertEqual(closing_response.status_code, 200)
        self.assertEqual(get_sales.call_count, 2)
        dre = dre_response.json()["resumo"]
        closing = closing_response.json()
        self.assertEqual(
            set(closing),
            {
                "loja_id",
                "mes",
                "ano",
                "faturamento_bruto",
                "total_dinheiro",
                "total_cartao",
                "total_pix",
                "total_outros",
                "impostos",
                "receita_liquida",
                "custos_produtos",
                "lucro_bruto",
                "despesas_operacionais",
                "resultado_operacional",
                "despesas_financeiras",
                "lucro_liquido",
                "status",
            },
        )
        mapping = {
            "faturamento_bruto": "receita_bruta",
            "total_dinheiro": "total_dinheiro",
            "total_cartao": "total_cartao",
            "total_pix": "total_pix",
            "total_outros": "total_outros",
            "impostos": "impostos",
            "receita_liquida": "receita_liquida",
            "custos_produtos": "custos_produtos",
            "lucro_bruto": "lucro_bruto",
            "despesas_operacionais": "despesas_operacionais",
            "resultado_operacional": "resultado_operacional",
            "despesas_financeiras": "despesas_financeiras_total",
            "lucro_liquido": "lucro_liquido",
        }
        for closing_key, dre_key in mapping.items():
            self.assertEqual(
                Decimal(str(closing[closing_key])),
                Decimal(str(dre[dre_key])),
                closing_key,
            )
