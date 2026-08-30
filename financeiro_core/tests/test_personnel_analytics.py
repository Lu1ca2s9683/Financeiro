import xml.etree.ElementTree as ET
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

from django.http import HttpResponse
from django.test import TestCase

from financeiro_core.app.services.dre_service import DREService
from financeiro_core.models import CategoriaDespesa, ContaPagar, RateioDespesa
from financeiro_core.reports.dre_pdf import DREPDFGenerator
from financeiro_core.reports.dre_xml import DREXMLGenerator


class PersonnelAnalyticsTest(TestCase):
    def setUp(self):
        self.pessoal = CategoriaDespesa.objects.create(
            nome="Salários", grupo_contabil="PESSOAL"
        )
        self.vendas = MagicMock()
        self.vendas.get_faturamento_por_loja.return_value = []
        self.service = DREService(vendas_client=self.vendas)

    def _expense(self, value, **overrides):
        fields = {
            "descricao": "Folha",
            "loja_id_externo": 1,
            "categoria": self.pessoal,
            "valor_bruto": Decimal(value),
            "data_competencia": date(2026, 8, 1),
            "data_transacao": date(2026, 8, 20),
        }
        fields.update(overrides)
        return ContaPagar.objects.create(**fields)

    def _dre(self):
        return self.service.gerar(1, 8, 2026, "Loja 1", "teste")

    def test_direct_personnel_expense_is_counted_once_and_attributed(self):
        self._expense(
            "3500.00",
            descricao="Pix Lucas",
            vendedor_id_externo=10,
            vendedor_nome_snapshot="Lucas",
        )

        dre = self._dre()
        pessoal = dre["pessoal_por_vendedor"]

        self.assertEqual(dre["resumo"]["despesas_pessoal"], Decimal("3500.00"))
        self.assertEqual(pessoal["total_pessoal"], Decimal("3500.00"))
        self.assertEqual(pessoal["total_individualizado"], Decimal("3500.00"))
        self.assertEqual(pessoal["total_nao_individualizado"], Decimal("0.00"))
        self.assertEqual(
            pessoal["vendedores"],
            [
                {
                    "vendedor_id_externo": 10,
                    "vendedor_nome": "Lucas",
                    "valor": Decimal("3500.00"),
                }
            ],
        )
        lancamento = next(
            item
            for grupo in dre["grupos_detalhados"]
            for categoria in grupo["categorias"]
            for item in categoria["lancamentos"]
        )
        self.assertEqual(lancamento["vendedor_id_externo"], 10)
        self.assertEqual(lancamento["vendedor_nome"], "Lucas")

    def test_payroll_batch_conserves_personnel_without_double_counting(self):
        despesa = self._expense("14500.00")
        allocations = [
            (10, "Lucas", "3500.00"),
            (11, "Maria", "2800.00"),
            (12, "Joao", "3100.00"),
            (13, "Ana", "2600.00"),
            (None, None, "2500.00"),
        ]
        for seller_id, name, value in allocations:
            RateioDespesa.objects.create(
                despesa=despesa,
                descricao=name or "Encargos",
                valor=Decimal(value),
                categoria=self.pessoal,
                vendedor_id_externo=seller_id,
                vendedor_nome_snapshot=name,
            )

        dre = self._dre()
        pessoal = dre["pessoal_por_vendedor"]

        self.assertEqual(dre["resumo"]["despesas_pessoal"], Decimal("14500.00"))
        self.assertEqual(pessoal["total_pessoal"], Decimal("14500.00"))
        self.assertEqual(pessoal["total_individualizado"], Decimal("12000.00"))
        self.assertEqual(
            pessoal["total_nao_individualizado"], Decimal("2500.00")
        )
        self.assertEqual(
            sum(
                (item["valor"] for item in pessoal["vendedores"]),
                Decimal("0.00"),
            )
            + pessoal["total_nao_individualizado"],
            dre["resumo"]["despesas_pessoal"],
        )

    def test_historical_snapshot_is_used_without_current_seller_lookup(self):
        self._expense(
            "1000.00",
            vendedor_id_externo=10,
            vendedor_nome_snapshot="Lucas",
        )
        self.vendas.get_vendedores_ativos_por_loja.side_effect = AssertionError(
            "DRE must not query sellers"
        )

        dre = self._dre()

        self.assertEqual(
            dre["pessoal_por_vendedor"]["vendedores"][0]["vendedor_nome"],
            "Lucas",
        )
        self.vendas.get_vendedores_ativos_por_loja.assert_not_called()

    def test_pdf_and_xml_consume_personnel_contract_and_legacy_is_safe(self):
        self._expense(
            "3500.00",
            vendedor_id_externo=10,
            vendedor_nome_snapshot="Lucas",
        )
        enriched = self._dre()

        xml_response = HttpResponse(content_type="application/xml")
        DREXMLGenerator(enriched).gerar(xml_response)
        root = ET.fromstring(xml_response.content)
        self.assertEqual(
            root.findtext("./pessoal_por_vendedor/total_pessoal"), "3500.00"
        )
        self.assertEqual(
            root.findtext(
                "./pessoal_por_vendedor/vendedores/vendedor/vendedor_nome"
            ),
            "Lucas",
        )

        pdf_response = HttpResponse(content_type="application/pdf")
        DREPDFGenerator(enriched).gerar(pdf_response)
        self.assertTrue(pdf_response.content.startswith(b"%PDF"))

        legacy = dict(enriched)
        legacy.pop("pessoal_por_vendedor")
        legacy_xml = HttpResponse(content_type="application/xml")
        DREXMLGenerator(legacy).gerar(legacy_xml)
        self.assertIsNone(
            ET.fromstring(legacy_xml.content).find("pessoal_por_vendedor")
        )
        legacy_pdf = HttpResponse(content_type="application/pdf")
        DREPDFGenerator(legacy).gerar(legacy_pdf)
        self.assertTrue(legacy_pdf.content.startswith(b"%PDF"))
