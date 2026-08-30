from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from financeiro_core.domain.services import (
    CalculadoraFinanceira,
    FaturamentoItemDTO,
    TaxaAplicavelDTO,
)
from financeiro_core.infrastructure.vendas_client import VendasClientSQL


class _RepositorioTaxasConfigurado:
    def __init__(self, taxas=None):
        self.taxas = taxas or {}
        self.chamadas = []

    def buscar_taxa(self, loja_id, tipo, bandeira, parcelas):
        chave = (tipo, bandeira, parcelas)
        self.chamadas.append((loja_id, *chave))
        return self.taxas.get(chave)


class SalesPaymentAdapterContractTest(SimpleTestCase):
    @staticmethod
    def _consultar(rows):
        cursor = MagicMock()
        cursor.fetchall.return_value = rows

        with patch(
            "financeiro_core.infrastructure.vendas_client.connections"
        ) as connections:
            context_cursor = (
                connections.__getitem__.return_value.cursor.return_value.__enter__
            )
            context_cursor.return_value = cursor
            itens = VendasClientSQL().get_faturamento_por_loja(9, 1, 2026)

        query, params = cursor.execute.call_args.args
        return itens, query, params

    def test_sales_form_and_subtype_map_to_truthful_financeiro_types(self):
        rows = [
            ("DINHEIRO", None, Decimal("10.00")),
            ("PIX_CONTA", None, Decimal("20.00")),
            ("CARTAO", "DEBITO", Decimal("30.00")),
            ("CARTAO", "CREDITO", Decimal("40.00")),
            ("CARTAO", "PIX_MAQUINA", Decimal("50.00")),
            ("CARTAO", None, Decimal("60.00")),
            ("VOUCHER", None, Decimal("70.00")),
            ("OUTRO", None, Decimal("80.00")),
        ]

        itens, _, _ = self._consultar(rows)

        self.assertEqual(
            [item.tipo_pagamento for item in itens],
            [
                "DINHEIRO",
                "PIX_CONTA",
                "DEBITO",
                "CREDITO_NAO_IDENTIFICADO",
                "PIX_MAQUINA",
                "CARTAO_NAO_IDENTIFICADO",
                "VOUCHER",
                "OUTRO",
            ],
        )
        self.assertTrue(all(item.bandeira == "GERAL" for item in itens))
        self.assertTrue(all(item.parcelas == 1 for item in itens))
        self.assertNotIn(
            itens[3].tipo_pagamento,
            {"CREDITO_AVISTA", "CREDITO_PARCELADO"},
        )

    def test_sql_keeps_payment_slots_filters_and_subtype_separate(self):
        _, query, params = self._consultar([])

        self.assertEqual(params, [9, 1, 2026])
        self.assertIn("v.loja_id = %s", query)
        self.assertIn("EXTRACT(MONTH FROM c.data) = %s", query)
        self.assertIn("EXTRACT(YEAR FROM c.data) = %s", query)
        self.assertIn("v.ignorar_faturamento = FALSE", query)
        self.assertIn("e.id IS NULL", query)
        self.assertIn("v.forma_pagamento as forma", query)
        self.assertIn("v.subtipo_pagamento_1 as subtipo", query)
        self.assertIn("v.valor_pagamento_1 as valor", query)
        self.assertIn("v.forma_pagamento_2 as forma", query)
        self.assertIn("v.subtipo_pagamento_2 as subtipo", query)
        self.assertIn("v.valor_pagamento_2 as valor", query)
        self.assertIn("UNION ALL", query)
        self.assertIn("GROUP BY forma, subtipo", query)
        self.assertNotIn("COALESCE(v.subtipo_pagamento", query)


class SalesPaymentFeeSafetyTest(SimpleTestCase):
    TAXA = TaxaAplicavelDTO(
        percentual=Decimal("2.00"),
        valor_fixo=Decimal("0.10"),
    )

    @staticmethod
    def _calcular(tipo, repo, bandeira="GERAL", parcelas=1):
        return CalculadoraFinanceira.calcular_liquido_vendas(
            [FaturamentoItemDTO(tipo, bandeira, parcelas, Decimal("100.00"))],
            repo,
            loja_id=7,
        )

    def test_debito_uses_general_debit_rate_exactly_once(self):
        repo = _RepositorioTaxasConfigurado({("DEBITO", "GERAL", 1): self.TAXA})

        resultado = self._calcular("DEBITO", repo)

        self.assertEqual(resultado["total_taxas"], Decimal("2.10"))
        self.assertEqual(repo.chamadas, [(7, "DEBITO", "GERAL", 1)])

    def test_pix_maquina_uses_general_pix_rate_exactly_once(self):
        repo = _RepositorioTaxasConfigurado({("PIX", "GERAL", 1): self.TAXA})

        resultado = self._calcular("PIX_MAQUINA", repo)

        self.assertEqual(resultado["total_taxas"], Decimal("2.10"))
        self.assertEqual(repo.chamadas, [(7, "PIX", "GERAL", 1)])

    def test_pix_conta_never_looks_up_machine_rate(self):
        repo = _RepositorioTaxasConfigurado({("PIX", "GERAL", 1): self.TAXA})

        resultado = self._calcular("PIX_CONTA", repo)

        self.assertEqual(resultado["total_taxas"], Decimal("0.00"))
        self.assertEqual(repo.chamadas, [])

    def test_unidentified_credit_never_uses_known_credit_rates(self):
        repo = _RepositorioTaxasConfigurado(
            {
                ("CREDITO_AVISTA", "GERAL", 1): self.TAXA,
                ("CREDITO_PARCELADO", "GERAL", 1): self.TAXA,
            }
        )

        resultado = self._calcular("CREDITO_NAO_IDENTIFICADO", repo)

        self.assertEqual(resultado["total_taxas"], Decimal("0.00"))
        self.assertEqual(repo.chamadas, [])

    def test_unidentified_card_never_looks_up_card_rate(self):
        repo = _RepositorioTaxasConfigurado(
            {("CREDITO_AVISTA", "GERAL", 1): self.TAXA}
        )

        resultado = self._calcular("CARTAO_NAO_IDENTIFICADO", repo)

        self.assertEqual(resultado["total_taxas"], Decimal("0.00"))
        self.assertEqual(repo.chamadas, [])

    def test_other_non_fee_types_never_look_up_rates(self):
        for tipo in ("DINHEIRO", "VOUCHER", "OUTRO", "NAO_SUPORTADO"):
            with self.subTest(tipo=tipo):
                repo = _RepositorioTaxasConfigurado(
                    {("PIX", "GERAL", 1): self.TAXA}
                )

                resultado = self._calcular(tipo, repo)

                self.assertEqual(resultado["total_taxas"], Decimal("0.00"))
                self.assertEqual(repo.chamadas, [])

    def test_existing_explicit_fee_eligible_domain_types_are_preserved(self):
        casos = [
            ("CREDITO_AVISTA", 1, "CREDITO_AVISTA"),
            ("CREDITO_PARCELADO", 3, "CREDITO_PARCELADO"),
            ("DEBITO", 1, "DEBITO"),
            ("PIX", 1, "PIX"),
        ]

        for tipo_dto, parcelas, tipo_taxa in casos:
            with self.subTest(tipo=tipo_dto):
                repo = _RepositorioTaxasConfigurado(
                    {(tipo_taxa, "VISA", parcelas): self.TAXA}
                )
                resultado = self._calcular(
                    tipo_dto,
                    repo,
                    bandeira="VISA",
                    parcelas=parcelas,
                )

                self.assertEqual(resultado["total_taxas"], Decimal("2.10"))
                self.assertEqual(
                    repo.chamadas,
                    [(7, tipo_taxa, "VISA", parcelas)],
                )


class SalesPaymentBreakdownConservationTest(SimpleTestCase):
    def test_all_sales_modalities_are_conserved_exactly_once(self):
        itens = [
            FaturamentoItemDTO("DINHEIRO", "GERAL", 1, Decimal("100.00")),
            FaturamentoItemDTO("PIX_CONTA", "GERAL", 1, Decimal("50.00")),
            FaturamentoItemDTO("PIX_MAQUINA", "GERAL", 1, Decimal("25.00")),
            FaturamentoItemDTO("DEBITO", "GERAL", 1, Decimal("200.00")),
            FaturamentoItemDTO(
                "CREDITO_NAO_IDENTIFICADO", "GERAL", 1, Decimal("300.00")
            ),
            FaturamentoItemDTO(
                "CARTAO_NAO_IDENTIFICADO", "GERAL", 1, Decimal("20.00")
            ),
            FaturamentoItemDTO("VOUCHER", "GERAL", 1, Decimal("10.00")),
            FaturamentoItemDTO("OUTRO", "GERAL", 1, Decimal("5.00")),
        ]
        repo = _RepositorioTaxasConfigurado()

        resultado = CalculadoraFinanceira.calcular_liquido_vendas(
            itens,
            repo,
            loja_id=7,
        )

        self.assertEqual(resultado["total_dinheiro"], Decimal("100.00"))
        self.assertEqual(resultado["total_pix"], Decimal("75.00"))
        self.assertEqual(resultado["total_cartao"], Decimal("520.00"))
        self.assertEqual(resultado["total_outros"], Decimal("15.00"))
        self.assertEqual(resultado["total_bruto"], Decimal("710.00"))
        self.assertEqual(
            resultado["total_bruto"],
            resultado["total_dinheiro"]
            + resultado["total_pix"]
            + resultado["total_cartao"]
            + resultado["total_outros"],
        )
