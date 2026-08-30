from datetime import date
from decimal import Decimal

from django.test import TestCase

from financeiro_core.app.services.dre_repositories import DjangoRepositorioDespesas
from financeiro_core.models import CategoriaDespesa, ContaPagar


class CashBasisRepositoryTest(TestCase):
    def setUp(self):
        self.categoria = CategoriaDespesa.objects.create(
            nome="Administrativa", grupo_contabil="ADMINISTRATIVA"
        )

    def _despesa(self, competencia, transacao, valor):
        return ContaPagar.objects.create(
            descricao="Despesa entre exercícios",
            loja_id_externo=3,
            categoria=self.categoria,
            valor_bruto=Decimal(valor),
            data_competencia=competencia,
            data_transacao=transacao,
        )

    def test_december_competence_paid_in_january_belongs_to_january(self):
        self._despesa(date(2025, 12, 1), date(2026, 1, 2), "75.00")

        repo = DjangoRepositorioDespesas()

        self.assertEqual(
            repo.agrupar_despesas_por_grupo_contabil(3, 1, 2026),
            {"ADMINISTRATIVA": Decimal("75.00")},
        )
        self.assertEqual(repo.agrupar_despesas_por_grupo_contabil(3, 12, 2025), {})

    def test_january_competence_paid_in_december_belongs_to_december(self):
        self._despesa(date(2026, 1, 1), date(2025, 12, 20), "80.00")

        repo = DjangoRepositorioDespesas()

        self.assertEqual(
            repo.agrupar_despesas_por_grupo_contabil(3, 12, 2025),
            {"ADMINISTRATIVA": Decimal("80.00")},
        )
        self.assertEqual(repo.agrupar_despesas_por_grupo_contabil(3, 1, 2026), {})

    def test_other_store_is_not_included(self):
        ContaPagar.objects.create(
            descricao="Outra loja",
            loja_id_externo=4,
            categoria=self.categoria,
            valor_bruto=Decimal("90.00"),
            data_competencia=date(2026, 1, 1),
            data_transacao=date(2026, 1, 2),
        )

        self.assertEqual(
            DjangoRepositorioDespesas().agrupar_despesas_por_grupo_contabil(
                3, 1, 2026
            ),
            {},
        )
