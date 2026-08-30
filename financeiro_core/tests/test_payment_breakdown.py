from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from financeiro_core.domain.services import (
    CalculadoraFinanceira,
    FaturamentoItemDTO,
    TaxaAplicavelDTO,
)
from financeiro_core.infrastructure.vendas_client import VendasClientSQL


class _RepositorioTaxas:
    def __init__(self, taxa=None):
        self.taxa = taxa

    def buscar_taxa(self, loja_id, tipo, bandeira, parcelas):
        return self.taxa


class PaymentBreakdownTest(SimpleTestCase):
    def test_known_payment_methods_reconcile_to_gross_revenue(self):
        itens = [
            FaturamentoItemDTO("DINHEIRO", "GERAL", 1, Decimal("100.00")),
            FaturamentoItemDTO("PIX", "GERAL", 1, Decimal("200.00")),
            FaturamentoItemDTO("DEBITO", "VISA", 1, Decimal("300.00")),
            FaturamentoItemDTO("CREDITO_AVISTA", "MASTER", 1, Decimal("400.00")),
        ]

        resultado = CalculadoraFinanceira.calcular_liquido_vendas(
            itens, _RepositorioTaxas(), loja_id=7
        )

        self.assertEqual(resultado["total_bruto"], Decimal("1000.00"))
        self.assertEqual(resultado["total_dinheiro"], Decimal("100.00"))
        self.assertEqual(resultado["total_pix"], Decimal("200.00"))
        self.assertEqual(resultado["total_cartao"], Decimal("700.00"))
        self.assertEqual(resultado["total_outros"], Decimal("0.00"))
        self.assertEqual(
            resultado["total_bruto"],
            resultado["total_dinheiro"]
            + resultado["total_cartao"]
            + resultado["total_pix"]
            + resultado["total_outros"],
        )

    def test_unidentified_card_is_card_but_truly_unknown_payment_is_other(self):
        itens = [
            FaturamentoItemDTO(
                "CARTAO_NAO_IDENTIFICADO", "GERAL", 1, Decimal("50.00")
            ),
            FaturamentoItemDTO("OUTRO", "GERAL", 1, Decimal("25.00")),
        ]

        resultado = CalculadoraFinanceira.calcular_liquido_vendas(
            itens, _RepositorioTaxas(), loja_id=7
        )

        self.assertEqual(resultado["total_cartao"], Decimal("50.00"))
        self.assertEqual(resultado["total_outros"], Decimal("25.00"))
        self.assertEqual(resultado["total_bruto"], Decimal("75.00"))

    def test_fee_rounding_is_half_up_per_aggregate_item(self):
        itens = [
            FaturamentoItemDTO("DEBITO", "VISA", 1, Decimal("100.50")),
            FaturamentoItemDTO("DEBITO", "VISA", 1, Decimal("0.50")),
        ]
        repo = _RepositorioTaxas(
            TaxaAplicavelDTO(percentual=Decimal("1.00"), valor_fixo=Decimal("0.10"))
        )

        resultado = CalculadoraFinanceira.calcular_liquido_vendas(
            itens, repo, loja_id=7
        )

        # 100.50 * 1% + 0.10 = 1.105 -> 1.11; 0.50 * 1% + 0.10 -> 0.11.
        self.assertEqual(resultado["total_taxas"], Decimal("1.22"))

    def test_cent_and_ten_cents_are_conserved_exactly(self):
        itens = [
            FaturamentoItemDTO("DINHEIRO", "GERAL", 1, Decimal("0.01")),
            FaturamentoItemDTO("PIX", "GERAL", 1, Decimal("0.10")),
        ]

        resultado = CalculadoraFinanceira.calcular_liquido_vendas(
            itens, _RepositorioTaxas(), loja_id=7
        )

        self.assertEqual(resultado["total_bruto"], Decimal("0.11"))
        self.assertEqual(resultado["total_dinheiro"], Decimal("0.01"))
        self.assertEqual(resultado["total_pix"], Decimal("0.10"))

    def test_fixed_fee_is_applied_once_per_existing_aggregate_dto_contract(self):
        repo = _RepositorioTaxas(
            TaxaAplicavelDTO(percentual=Decimal("0.00"), valor_fixo=Decimal("0.30"))
        )
        agregado_unico = [
            FaturamentoItemDTO("DEBITO", "VISA", 1, Decimal("200.00"))
        ]
        dois_agregados = [
            FaturamentoItemDTO("DEBITO", "VISA", 1, Decimal("100.00")),
            FaturamentoItemDTO("DEBITO", "MASTER", 1, Decimal("100.00")),
        ]

        taxa_unica = CalculadoraFinanceira.calcular_liquido_vendas(
            agregado_unico, repo, loja_id=7
        )["total_taxas"]
        taxas_separadas = CalculadoraFinanceira.calcular_liquido_vendas(
            dois_agregados, repo, loja_id=7
        )["total_taxas"]

        self.assertEqual(taxa_unica, Decimal("0.30"))
        self.assertEqual(taxas_separadas, Decimal("0.60"))


class VendasClientSQLTest(SimpleTestCase):
    @patch("financeiro_core.infrastructure.vendas_client.connections")
    def test_query_preserves_filters_both_payment_slots_and_cash_period(self, connections):
        cursor = MagicMock()
        connections.__getitem__.return_value.cursor.return_value.__enter__.return_value = cursor
        cursor.fetchall.return_value = [
            ("DINHEIRO", None, Decimal("100.00")),
            ("PIX_CONTA", None, Decimal("200.00")),
            ("CARTAO", None, Decimal("300.00")),
            (None, None, Decimal("40.00")),
        ]

        itens = VendasClientSQL().get_faturamento_por_loja(9, 1, 2026)

        query, params = cursor.execute.call_args.args
        self.assertEqual(params, [9, 1, 2026])
        self.assertIn("v.loja_id = %s", query)
        self.assertIn("EXTRACT(MONTH FROM c.data) = %s", query)
        self.assertIn("EXTRACT(YEAR FROM c.data) = %s", query)
        self.assertIn("v.ignorar_faturamento = FALSE", query)
        self.assertIn("e.id IS NULL", query)
        self.assertIn("v.valor_pagamento_1", query)
        self.assertIn("v.valor_pagamento_2", query)
        self.assertIn("UNION ALL", query)
        self.assertEqual(
            [item.tipo_pagamento for item in itens],
            ["DINHEIRO", "PIX_CONTA", "CARTAO_NAO_IDENTIFICADO", "OUTRO"],
        )
        self.assertTrue(all(item.parcelas == 1 for item in itens))
