from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

from django.test import TestCase

from financeiro_core.app.services.dre_service import DREService
from financeiro_core.models import CategoriaDespesa, ContaPagar, RateioDespesa


class RateioIntegrityTest(TestCase):
    def setUp(self):
        self.categoria_principal = CategoriaDespesa.objects.create(
            nome="Administrativa", grupo_contabil="ADMINISTRATIVA"
        )
        self.categoria_a = CategoriaDespesa.objects.create(
            nome="Custos", grupo_contabil="CUSTOS"
        )
        self.categoria_b = CategoriaDespesa.objects.create(
            nome="Pessoal", grupo_contabil="PESSOAL"
        )
        vendas = MagicMock()
        vendas.get_faturamento_por_loja.return_value = []
        self.service = DREService(vendas_client=vendas)

    def _criar_despesa(self, segundo_valor):
        despesa = ContaPagar.objects.create(
            descricao=f"Rateio {segundo_valor}",
            loja_id_externo=1,
            categoria=self.categoria_principal,
            valor_bruto=Decimal("100.00"),
            data_competencia=date(2026, 1, 5),
            data_transacao=date(2026, 1, 10),
        )
        RateioDespesa.objects.create(
            despesa=despesa,
            descricao="Parte A",
            valor=Decimal("60.00"),
            categoria=self.categoria_a,
        )
        segundo = RateioDespesa.objects.create(
            despesa=despesa,
            descricao="Parte B",
            valor=Decimal(segundo_valor),
            categoria=self.categoria_b,
        )
        return despesa, segundo

    def _gerar(self):
        return self.service.gerar(1, 1, 2026, "Loja 1", "teste")

    @staticmethod
    def _total_classificado(dre):
        return sum(
            (grupo["total"] for grupo in dre["grupos_detalhados"]),
            Decimal("0.00"),
        )

    def test_exact_rateio_is_used_without_adjustment(self):
        self._criar_despesa("40.00")

        dre = self._gerar()

        self.assertEqual(self._total_classificado(dre), Decimal("100.00"))
        self.assertEqual(
            dre["qualidade_dados"]["quantidade_rateios_com_ajuste_tolerado"], 0
        )
        self.assertEqual(
            dre["qualidade_dados"]["valor_absoluto_ajustes_rateio"],
            Decimal("0.00"),
        )

    def test_one_cent_short_is_normalized_only_in_dre_and_audited(self):
        _, segundo = self._criar_despesa("39.99")

        dre = self._gerar()

        segundo.refresh_from_db()
        self.assertEqual(segundo.valor, Decimal("39.99"))
        self.assertEqual(self._total_classificado(dre), Decimal("100.00"))
        qualidade = dre["qualidade_dados"]
        self.assertEqual(qualidade["quantidade_rateios_com_ajuste_tolerado"], 1)
        self.assertEqual(
            qualidade["valor_absoluto_ajustes_rateio"], Decimal("0.01")
        )
        lancamentos = [
            item
            for grupo in dre["grupos_detalhados"]
            for categoria in grupo["categorias"]
            for item in categoria["lancamentos"]
        ]
        self.assertEqual(
            sum((item["valor"] for item in lancamentos), Decimal("0.00")),
            Decimal("100.00"),
        )
        self.assertIn(Decimal("0.01"), [item["ajuste_conservacao"] for item in lancamentos])

    def test_one_cent_over_is_normalized_only_in_dre_and_audited(self):
        _, segundo = self._criar_despesa("40.01")

        dre = self._gerar()

        segundo.refresh_from_db()
        self.assertEqual(segundo.valor, Decimal("40.01"))
        self.assertEqual(self._total_classificado(dre), Decimal("100.00"))
        self.assertEqual(
            dre["qualidade_dados"]["valor_absoluto_ajustes_rateio"],
            Decimal("0.01"),
        )

    def test_invalid_rateio_falls_back_to_original_expense_exactly_once(self):
        self._criar_despesa("39.98")

        dre = self._gerar()

        self.assertEqual(self._total_classificado(dre), Decimal("100.00"))
        self.assertEqual(dre["resumo"]["despesas_administrativas"], Decimal("100.00"))
        self.assertEqual(dre["resumo"]["custos_produtos"], Decimal("0.00"))
        self.assertTrue(dre["qualidade_dados"]["possui_rateios_invalidos"])
        self.assertEqual(
            dre["qualidade_dados"]["valor_despesas_com_rateio_invalido"],
            Decimal("100.00"),
        )

    def test_all_classifications_conserve_all_considered_expenses(self):
        for segundo_valor in ("40.00", "39.99", "40.01", "39.98"):
            self._criar_despesa(segundo_valor)

        dre = self._gerar()

        qualidade = dre["qualidade_dados"]
        self.assertEqual(qualidade["valor_total_despesas_consideradas"], Decimal("400.00"))
        self.assertEqual(qualidade["valor_total_despesas_classificadas"], Decimal("400.00"))
        self.assertEqual(qualidade["diferenca_conservacao_despesas"], Decimal("0.00"))
        self.assertEqual(self._total_classificado(dre), Decimal("400.00"))
