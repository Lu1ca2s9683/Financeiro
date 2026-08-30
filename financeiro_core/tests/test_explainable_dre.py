import xml.etree.ElementTree as ET
from decimal import Decimal
from unittest.mock import MagicMock

from django.http import HttpResponse
from django.test import SimpleTestCase, TestCase

from financeiro_core.app.services.dre_service import DREService
from financeiro_core.domain.services import (
    CalculadoraFinanceira,
    FaturamentoItemDTO,
    TaxaAplicavelDTO,
)
from financeiro_core.reports.dre_pdf import DREPDFGenerator
from financeiro_core.reports.dre_xml import DREXMLGenerator


EXPLAINABLE_ITEMS = [
    FaturamentoItemDTO("DINHEIRO", "GERAL", 1, Decimal("100.00")),
    FaturamentoItemDTO("PIX_CONTA", "GERAL", 1, Decimal("50.00")),
    FaturamentoItemDTO("PIX_MAQUINA", "GERAL", 1, Decimal("25.00")),
    FaturamentoItemDTO("PIX", "GERAL", 1, Decimal("10.00")),
    FaturamentoItemDTO("DEBITO", "GERAL", 1, Decimal("200.00")),
    FaturamentoItemDTO("CREDITO_AVISTA", "GERAL", 1, Decimal("40.00")),
    FaturamentoItemDTO("CREDITO_PARCELADO", "GERAL", 3, Decimal("60.00")),
    FaturamentoItemDTO(
        "CREDITO_NAO_IDENTIFICADO", "GERAL", 1, Decimal("300.00")
    ),
    FaturamentoItemDTO(
        "CARTAO_NAO_IDENTIFICADO", "GERAL", 1, Decimal("20.00")
    ),
    FaturamentoItemDTO("VOUCHER", "GERAL", 1, Decimal("15.00")),
    FaturamentoItemDTO("OUTRO", "GERAL", 1, Decimal("5.00")),
]


class _RepositorioTaxas:
    def __init__(self, taxas=None):
        self.taxas = taxas or {}
        self.chamadas = []

    def buscar_taxa(self, loja_id, tipo, bandeira, parcelas):
        chave = (tipo, bandeira, parcelas)
        self.chamadas.append((loja_id, *chave))
        return self.taxas.get(chave)


class ExplainablePaymentDomainTest(SimpleTestCase):
    def test_detailed_payment_totals_conserve_every_aggregate(self):
        resultado = CalculadoraFinanceira.calcular_liquido_vendas(
            EXPLAINABLE_ITEMS,
            _RepositorioTaxas(),
            loja_id=7,
        )

        self.assertEqual(resultado["total_bruto"], Decimal("825.00"))
        self.assertEqual(resultado["total_dinheiro"], Decimal("100.00"))
        self.assertEqual(resultado["total_pix"], Decimal("85.00"))
        self.assertEqual(resultado["total_cartao"], Decimal("620.00"))
        self.assertEqual(resultado["total_outros"], Decimal("20.00"))

        self.assertEqual(resultado["total_pix_conta"], Decimal("50.00"))
        self.assertEqual(resultado["total_pix_maquina"], Decimal("25.00"))
        self.assertEqual(resultado["total_pix_nao_detalhado"], Decimal("10.00"))
        self.assertEqual(resultado["total_debito"], Decimal("200.00"))
        self.assertEqual(resultado["total_credito_avista"], Decimal("40.00"))
        self.assertEqual(resultado["total_credito_parcelado"], Decimal("60.00"))
        self.assertEqual(
            resultado["total_credito_nao_identificado"], Decimal("300.00")
        )
        self.assertEqual(
            resultado["total_cartao_nao_identificado"], Decimal("20.00")
        )
        self.assertEqual(resultado["total_voucher"], Decimal("15.00"))
        self.assertEqual(
            resultado["total_outros_nao_identificados"], Decimal("5.00")
        )

        self.assertEqual(
            resultado["total_pix"],
            resultado["total_pix_conta"]
            + resultado["total_pix_maquina"]
            + resultado["total_pix_nao_detalhado"],
        )
        self.assertEqual(
            resultado["total_cartao"],
            resultado["total_debito"]
            + resultado["total_credito_avista"]
            + resultado["total_credito_parcelado"]
            + resultado["total_credito_nao_identificado"]
            + resultado["total_cartao_nao_identificado"],
        )
        self.assertEqual(
            resultado["total_outros"],
            resultado["total_voucher"]
            + resultado["total_outros_nao_identificados"],
        )

    def test_fee_coverage_tracks_only_eligible_known_modalities(self):
        taxa = TaxaAplicavelDTO(Decimal("1.00"), Decimal("0.00"))
        repo = _RepositorioTaxas(
            {
                ("DEBITO", "VISA", 1): taxa,
                ("PIX", "VISA", 1): taxa,
            }
        )
        itens = [
            FaturamentoItemDTO("DEBITO", "VISA", 1, Decimal("100.00")),
            FaturamentoItemDTO("DEBITO", "MASTER", 1, Decimal("50.00")),
            FaturamentoItemDTO("PIX_MAQUINA", "VISA", 1, Decimal("25.00")),
            FaturamentoItemDTO("PIX_MAQUINA", "MASTER", 1, Decimal("10.00")),
            FaturamentoItemDTO("PIX_CONTA", "GERAL", 1, Decimal("30.00")),
            FaturamentoItemDTO(
                "CREDITO_NAO_IDENTIFICADO", "GERAL", 1, Decimal("40.00")
            ),
            FaturamentoItemDTO(
                "CARTAO_NAO_IDENTIFICADO", "GERAL", 1, Decimal("20.00")
            ),
        ]

        resultado = CalculadoraFinanceira.calcular_liquido_vendas(
            itens,
            repo,
            loja_id=7,
        )

        self.assertEqual(
            resultado["valor_pagamentos_elegiveis_taxa"], Decimal("185.00")
        )
        self.assertEqual(
            resultado["valor_pagamentos_com_taxa_configurada"], Decimal("125.00")
        )
        self.assertEqual(
            resultado["valor_pagamentos_sem_taxa_configurada"], Decimal("60.00")
        )
        self.assertEqual(resultado["total_taxas"], Decimal("1.25"))
        self.assertEqual(
            repo.chamadas,
            [
                (7, "DEBITO", "VISA", 1),
                (7, "DEBITO", "MASTER", 1),
                (7, "PIX", "VISA", 1),
                (7, "PIX", "MASTER", 1),
            ],
        )


class ExplainableDREContractTest(TestCase):
    def test_line_11_describes_all_payment_method_fees(self):
        vendas_client = MagicMock()
        vendas_client.get_faturamento_por_loja.return_value = EXPLAINABLE_ITEMS
        dre = DREService(
            vendas_client=vendas_client,
            repositorio_taxas=_RepositorioTaxas(),
        ).gerar(7, 1, 2026, "Loja 7", "teste")

        linha_11 = next(
            linha for linha in dre["linhas"] if linha["codigo"] == "11"
        )
        self.assertEqual(
            linha_11["descricao"],
            "(-) Taxas de Meios de Pagamento",
        )
        self.assertNotEqual(linha_11["descricao"], "(-) Taxas de Cartão")

    def test_dre_adds_explanation_without_new_sales_query_or_formula_change(self):
        vendas_client = MagicMock()
        vendas_client.get_faturamento_por_loja.return_value = EXPLAINABLE_ITEMS
        dre = DREService(
            vendas_client=vendas_client,
            repositorio_taxas=_RepositorioTaxas(),
        ).gerar(7, 1, 2026, "Loja 7", "teste")

        vendas_client.get_faturamento_por_loja.assert_called_once_with(7, 1, 2026)
        resumo = dre["resumo"]
        composicao = dre["composicao_recebimentos"]
        qualidade = dre["qualidade_recebimentos"]

        self.assertEqual(resumo["receita_bruta"], Decimal("825.00"))
        self.assertEqual(composicao["dinheiro"]["total"], Decimal("100.00"))
        self.assertEqual(composicao["pix"]["total"], Decimal("85.00"))
        self.assertEqual(composicao["pix"]["conta"], Decimal("50.00"))
        self.assertEqual(composicao["pix"]["maquina"], Decimal("25.00"))
        self.assertEqual(composicao["cartao"]["total"], Decimal("620.00"))
        self.assertEqual(
            composicao["cartao"]["credito_nao_identificado"],
            Decimal("300.00"),
        )
        self.assertEqual(composicao["outros"]["voucher"], Decimal("15.00"))
        self.assertTrue(qualidade["receita_conservada"])
        self.assertEqual(qualidade["diferenca_conservacao"], Decimal("0.00"))
        self.assertEqual(
            qualidade["valor_credito_sem_detalhe"], Decimal("300.00")
        )
        self.assertEqual(
            qualidade["valor_cartao_sem_subtipo"], Decimal("20.00")
        )
        self.assertEqual(
            qualidade["valor_pagamentos_elegiveis_taxa"], Decimal("335.00")
        )
        self.assertEqual(
            qualidade["valor_pagamentos_sem_taxa_configurada"],
            Decimal("335.00"),
        )
        self.assertTrue(qualidade["possui_credito_sem_detalhe"])
        self.assertTrue(qualidade["possui_cartao_sem_subtipo"])
        self.assertTrue(qualidade["possui_pagamentos_elegiveis_sem_taxa"])

        self.assertEqual(
            resumo["receita_liquida"],
            resumo["receita_bruta"] - resumo["impostos"],
        )
        self.assertEqual(
            resumo["lucro_liquido"],
            resumo["resultado_operacional"]
            - resumo["despesas_financeiras_total"],
        )


class ExplainableDREPresentationTest(SimpleTestCase):
    @staticmethod
    def _fixture():
        return {
            "identificacao": {
                "loja_id": 7,
                "loja_nome": "Loja 7",
                "mes": 1,
                "ano": 2026,
                "periodo_descricao": "Janeiro de 2026",
                "gerado_em": "2026-01-31T12:00:00",
                "gerado_por": "teste",
            },
            "resumo": {
                "receita_bruta": Decimal("825.00"),
                "receita_liquida": Decimal("825.00"),
                "lucro_bruto": Decimal("825.00"),
                "resultado_operacional": Decimal("825.00"),
                "lucro_liquido": Decimal("825.00"),
                "margem_bruta_percentual": Decimal("100.00"),
                "margem_operacional_percentual": Decimal("100.00"),
                "margem_liquida_percentual": Decimal("100.00"),
            },
            "linhas": [],
            "grupos_detalhados": [],
            "qualidade_dados": {},
            "composicao_recebimentos": {
                "dinheiro": {"total": Decimal("100.00")},
                "pix": {
                    "total": Decimal("85.00"),
                    "conta": Decimal("50.00"),
                    "maquina": Decimal("25.00"),
                    "nao_detalhado": Decimal("10.00"),
                },
                "cartao": {
                    "total": Decimal("620.00"),
                    "debito": Decimal("200.00"),
                    "credito_avista": Decimal("40.00"),
                    "credito_parcelado": Decimal("60.00"),
                    "credito_nao_identificado": Decimal("300.00"),
                    "nao_identificado": Decimal("20.00"),
                },
                "outros": {
                    "total": Decimal("20.00"),
                    "voucher": Decimal("15.00"),
                    "nao_identificado": Decimal("5.00"),
                },
            },
            "qualidade_recebimentos": {
                "receita_conservada": True,
                "diferenca_conservacao": Decimal("0.00"),
                "valor_credito_sem_detalhe": Decimal("300.00"),
                "valor_cartao_sem_subtipo": Decimal("20.00"),
                "valor_pagamentos_elegiveis_taxa": Decimal("335.00"),
                "valor_pagamentos_com_taxa_configurada": Decimal("0.00"),
                "valor_pagamentos_sem_taxa_configurada": Decimal("335.00"),
                "possui_credito_sem_detalhe": True,
                "possui_cartao_sem_subtipo": True,
                "possui_pagamentos_elegiveis_sem_taxa": True,
            },
        }

    def test_pdf_accepts_enriched_and_legacy_contracts(self):
        enriched = self._fixture()
        legacy = dict(enriched)
        legacy.pop("composicao_recebimentos")
        legacy.pop("qualidade_recebimentos")

        for contrato in (enriched, legacy):
            with self.subTest(enriched="composicao_recebimentos" in contrato):
                response = HttpResponse(content_type="application/pdf")
                DREPDFGenerator(contrato).gerar(response)
                self.assertTrue(response.content.startswith(b"%PDF"))
                self.assertGreater(len(response.content), 1000)

    def test_xml_serializes_enriched_contract_and_omits_unknown_legacy_detail(self):
        enriched_response = HttpResponse(content_type="application/xml")
        DREXMLGenerator(self._fixture()).gerar(enriched_response)
        root = ET.fromstring(enriched_response.content)

        self.assertEqual(
            root.findtext("./composicao_recebimentos/pix/conta"), "50.00"
        )
        self.assertEqual(
            root.findtext(
                "./composicao_recebimentos/cartao/credito_nao_identificado"
            ),
            "300.00",
        )
        self.assertEqual(
            root.findtext(
                "./qualidade_recebimentos/valor_pagamentos_sem_taxa_configurada"
            ),
            "335.00",
        )
        self.assertEqual(
            root.findtext("./qualidade_recebimentos/receita_conservada"),
            "true",
        )

        legacy = self._fixture()
        legacy.pop("composicao_recebimentos")
        legacy.pop("qualidade_recebimentos")
        legacy_response = HttpResponse(content_type="application/xml")
        DREXMLGenerator(legacy).gerar(legacy_response)
        legacy_root = ET.fromstring(legacy_response.content)
        self.assertIsNone(legacy_root.find("composicao_recebimentos"))
        self.assertIsNone(legacy_root.find("qualidade_recebimentos"))
