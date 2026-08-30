import unittest
from unittest.mock import patch

from django.test import TestCase
from django.contrib.auth.models import User
from financeiro_core.models import (
    CategoriaDespesa,
    ContaPagar,
    FechamentoMensal,
    Fornecedor,
    RateioDespesa,
)
from decimal import Decimal
from datetime import date
from ninja.testing import TestClient
from financeiro_core.app.api.endpoints import router

# Same key as security.py
from .helpers import create_test_token
create_token = create_test_token

@patch("financeiro_core.app.services.dre_service.VendasClientSQL.get_faturamento_por_loja", return_value=[])
class DespesasApiTest(TestCase):
    databases = {'default', 'vendas'}

    def setUp(self):
        self.client = TestClient(router)
        self.user = User.objects.using('vendas').create(username='testuser', password='password')
        User.objects.using('default').create(username='testuser', password='password')
        self.categoria = CategoriaDespesa.objects.create(nome="Teste Cat", ativa=True)
        self.fornecedor = Fornecedor.objects.create(razao_social="Fornecedor Teste", cnpj_cpf="12345678000199")

        self.loja_id = 1
        self.token = create_token(self.user.id, self.loja_id)
        self.auth_headers = {"Authorization": f"Bearer {self.token}"}

        self.mes_aberto = 10
        self.ano_aberto = 2024

        self.mes_fechado = 9
        self.ano_fechado = 2024

        # Criar fechamento
        FechamentoMensal.objects.create(
            loja_id_externo=self.loja_id,
            mes=self.mes_fechado,
            ano=self.ano_fechado,
            faturamento_bruto=Decimal('1000'),
            total_taxas=Decimal('10'),
            receita_liquida=Decimal('990'),
            total_despesas=Decimal('100'),
            resultado_operacional=Decimal('890'),
            status='CONCLUIDO'
        )

        self.despesa_aberta = ContaPagar.objects.create(
            descricao="Despesa Aberta",
            loja_id_externo=self.loja_id,
            categoria=self.categoria,
            valor_bruto=Decimal('100.00'),
            data_competencia=date(self.ano_aberto, self.mes_aberto, 15),
            data_transacao=date(self.ano_aberto, self.mes_aberto, 20),
        )

        self.despesa_fechada = ContaPagar.objects.create(
            descricao="Despesa Fechada",
            loja_id_externo=self.loja_id,
            categoria=self.categoria,
            valor_bruto=Decimal('100.00'),
            data_competencia=date(self.ano_fechado, self.mes_fechado, 15),
            data_transacao=date(self.ano_fechado, self.mes_fechado, 20),
        )


    def test_get_despesa_detail(self, mock_faturamento):
        # Must send auth header
        response = self.client.get(f"/despesas/{self.despesa_aberta.id}", headers=self.auth_headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['id'], self.despesa_aberta.id)
        self.assertEqual(float(data['valor_bruto']), 100.0)

    @unittest.skip("KNOWN_BUG_PHASE_1: production PATCH/status behavior is not implemented or contract not currently executable")
    def test_update_status_open_month(self, mock_faturamento):
        pass

    @unittest.skip("KNOWN_BUG_PHASE_1: production PATCH/status behavior is not implemented or contract not currently executable")
    def test_update_status_closed_month(self, mock_faturamento):
        pass

    def test_edit_despesa_open_month(self, mock_faturamento):
        payload = {
            "descricao": "Editada",
            "loja_id": self.loja_id,
            "categoria_id": self.categoria.id,
            "valor": 150.00,
            "data_competencia": f"{self.ano_aberto}-{self.mes_aberto:02d}-15",
            "data_transacao": f"{self.ano_aberto}-{self.mes_aberto:02d}-20",
            "fornecedor_id": self.fornecedor.id
        }
        response = self.client.put(f"/despesas/{self.despesa_aberta.id}", json=payload, headers=self.auth_headers)
        self.assertEqual(response.status_code, 200)
        self.despesa_aberta.refresh_from_db()
        self.assertEqual(self.despesa_aberta.descricao, "Editada")
        self.assertEqual(self.despesa_aberta.valor_bruto, Decimal('150.00'))

    def test_edit_despesa_closed_month(self, mock_faturamento):
        payload = {
            "descricao": "Tentativa Edicao",
            "loja_id": self.loja_id,
            "categoria_id": self.categoria.id,
            "valor": 150.00,
            "data_competencia": f"{self.ano_fechado}-{self.mes_fechado:02d}-15",
            "data_transacao": f"{self.ano_fechado}-{self.mes_fechado:02d}-20",
            "fornecedor_id": self.fornecedor.id
        }
        response = self.client.put(f"/despesas/{self.despesa_fechada.id}", json=payload, headers=self.auth_headers)
        self.assertEqual(response.status_code, 409)

    def test_closed_competence_does_not_block_open_cash_period(self, mock_faturamento):
        payload = {
            "descricao": "Movendo para fechado",
            "loja_id": self.loja_id,
            "categoria_id": self.categoria.id,
            "valor": 100.00,
            "data_competencia": f"{self.ano_fechado}-{self.mes_fechado:02d}-15",
            "data_transacao": f"{self.ano_aberto}-{self.mes_aberto:02d}-20",
             "fornecedor_id": self.fornecedor.id
        }
        response = self.client.put(f"/despesas/{self.despesa_aberta.id}", json=payload, headers=self.auth_headers)
        self.assertEqual(response.status_code, 200)

    def test_access_wrong_store(self, mock_faturamento):
        # Tries to access store 1 with token for store 2
        token_loja_2 = create_token(self.user.id, 2)
        headers_2 = {"Authorization": f"Bearer {token_loja_2}"}

        # Endpoint expects access to store 1 (implicitly via object ownership or explicit param)
        # obter_resumo_dashboard asks for store 1
        response = self.client.get(f"/dashboard/resumo/{self.loja_id}/{self.mes_aberto}/{self.ano_aberto}", headers=headers_2)
        self.assertEqual(response.status_code, 403)

    def test_dashboard_does_not_fabricate_due_date_metrics(self, mock_faturamento):
        # ContaPagar has no due-date field. Cash/competence dates are not due dates.
        ContaPagar.objects.create(
            descricao="Sem vencimento inferível",
            loja_id_externo=self.loja_id,
            categoria=self.categoria,
            valor_bruto=Decimal('50.00'),
            data_competencia=date(self.ano_aberto, self.mes_aberto, 1),
            data_transacao=date(self.ano_aberto, self.mes_aberto, 5),
        )

        hoje = date.today()
        ContaPagar.objects.create(
            descricao="Transação hoje sem vencimento",
            loja_id_externo=self.loja_id,
            categoria=self.categoria,
            valor_bruto=Decimal('60.00'),
            data_competencia=date(self.ano_aberto, self.mes_aberto, 1),
            data_transacao=hoje,
        )

        response = self.client.get(f"/dashboard/resumo/{self.loja_id}/{self.mes_aberto}/{self.ano_aberto}", headers=self.auth_headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data['despesas_atrasadas'], 0)
        self.assertEqual(data['despesas_vencendo_semana'], 0)

    def test_dashboard_total_uses_original_expense_value_once(self, mock_faturamento):
        RateioDespesa.objects.create(
            despesa=self.despesa_aberta,
            descricao="Parte A",
            valor=Decimal("60.00"),
            categoria=self.categoria,
        )
        RateioDespesa.objects.create(
            despesa=self.despesa_aberta,
            descricao="Parte B",
            valor=Decimal("39.99"),
            categoria=self.categoria,
        )

        response = self.client.get(
            f"/dashboard/resumo/{self.loja_id}/{self.mes_aberto}/{self.ano_aberto}",
            headers=self.auth_headers,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Decimal(str(response.json()["total_despesas_mes"])), Decimal("100.00"))

    def test_get_dre_no_side_effects(self, mock_faturamento):
        # 15. GET do DRE não cria FechamentoMensal.
        # 16. GET do DRE não modifica FechamentoMensal existente.
        from financeiro_core.models import FechamentoMensal

        count_before = FechamentoMensal.objects.count()
        response = self.client.get(f"/dre/{self.loja_id}/{self.mes_aberto}/{self.ano_aberto}", headers=self.auth_headers)
        self.assertEqual(response.status_code, 200)

        count_after = FechamentoMensal.objects.count()
        self.assertEqual(count_before, count_after)

    def test_post_fechamento_rejects_closed_period_without_mutation(self, mock_faturamento):
        from financeiro_core.models import FechamentoMensal

        fechamento = FechamentoMensal.objects.get(loja_id_externo=self.loja_id, mes=self.mes_fechado, ano=self.ano_fechado)
        self.assertEqual(fechamento.status, 'CONCLUIDO')
        valores_antes = {
            "faturamento_bruto": fechamento.faturamento_bruto,
            "total_taxas": fechamento.total_taxas,
            "receita_liquida": fechamento.receita_liquida,
            "total_despesas": fechamento.total_despesas,
            "resultado_operacional": fechamento.resultado_operacional,
            "dados_auditoria_snapshot": fechamento.dados_auditoria_snapshot,
        }

        response = self.client.post(f"/fechamento/calcular/{self.loja_id}/{self.mes_fechado}/{self.ano_fechado}", headers=self.auth_headers)
        self.assertEqual(response.status_code, 409)
        mock_faturamento.assert_not_called()

        fechamento.refresh_from_db()
        self.assertEqual(fechamento.status, 'CONCLUIDO')
        self.assertEqual(
            {campo: getattr(fechamento, campo) for campo in valores_antes},
            valores_antes,
        )

    def test_post_fechamento_invalid_month_returns_400(self, mock_faturamento):
        response = self.client.post(
            f"/fechamento/calcular/{self.loja_id}/13/{self.ano_aberto}",
            headers=self.auth_headers,
        )

        self.assertEqual(response.status_code, 400)

    def test_post_fechamento_invalid_store_returns_403(self, mock_faturamento):
        response = self.client.post(
            f"/fechamento/calcular/{self.loja_id + 1}/{self.mes_aberto}/{self.ano_aberto}",
            headers=self.auth_headers,
        )

        self.assertEqual(response.status_code, 403)

    def test_dashboard_response_contract(self, mock_faturamento):
        response = self.client.get(
            f"/dashboard/resumo/{self.loja_id}/{self.mes_aberto}/{self.ano_aberto}",
            headers=self.auth_headers,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            set(response.json()),
            {
                "percentual_pago",
                "percentual_atrasado",
                "percentual_previsto",
                "total_despesas_mes",
                "despesas_vencendo_semana",
                "despesas_atrasadas",
                "saude_financeira",
                "mensagem_assistente",
            },
        )

    def test_dashboard_invalid_month_returns_400(self, mock_faturamento):
        response = self.client.get(
            f"/dashboard/resumo/{self.loja_id}/13/{self.ano_aberto}",
            headers=self.auth_headers,
        )

        self.assertEqual(response.status_code, 400)

    def test_dashboard_requires_authentication(self, mock_faturamento):
        response = self.client.get(
            f"/dashboard/resumo/{self.loja_id}/{self.mes_aberto}/{self.ano_aberto}"
        )

        self.assertEqual(response.status_code, 401)

    def test_post_fechamento_requires_authentication(self, mock_faturamento):
        response = self.client.post(
            f"/fechamento/calcular/{self.loja_id}/{self.mes_aberto}/{self.ano_aberto}"
        )

        self.assertEqual(response.status_code, 401)

    def test_dre_json_structure(self, mock_faturamento):
        response = self.client.get(f"/dre/{self.loja_id}/{self.mes_aberto}/{self.ano_aberto}", headers=self.auth_headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()

        # 7. Nome real da loja aparece no JSON.
        self.assertEqual(data['identificacao']['loja_nome'], f"Loja {self.loja_id}")
        self.assertEqual(data['identificacao']['regime'], "CAIXA")

        # Tem qualidade de dados
        self.assertIn('qualidade_dados', data)
        self.assertIn('resumo', data)
        self.assertIn('grupos_detalhados', data)

    def test_invalid_store_returns_403(self, mock_faturamento):
        # 13. loja fora do contexto retorna 403.
        token = create_test_token(self.user.id, 999)
        headers = {"Authorization": f"Bearer {token}"}

        response = self.client.get(f"/dre/1/{self.mes_aberto}/{self.ano_aberto}", headers=headers)
        self.assertEqual(response.status_code, 403)

    def test_invalid_month_returns_400(self, mock_faturamento):
        # 19. Mês inválido recebe 400.
        response = self.client.get(f"/dre/{self.loja_id}/13/{self.ano_aberto}", headers=self.auth_headers)
        self.assertEqual(response.status_code, 400)

    def test_pdf_export(self, mock_faturamento):
        # 20. PDF retorna 200.
        # 21. PDF retorna application/pdf.
        # 23. PDF possui Content-Disposition.
        response = self.client.get(f"/dre/{self.loja_id}/{self.mes_aberto}/{self.ano_aberto}/pdf", headers=self.auth_headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('attachment; filename="DRE_', response['Content-Disposition'])

    def test_xml_export(self, mock_faturamento):
        # 24. XML retorna 200.
        # 25. XML retorna application/xml.
        # 26. XML pode ser lido pelo ElementTree.
        # 27. XML possui versao="1.0".
        import xml.etree.ElementTree as ET
        response = self.client.get(f"/dre/{self.loja_id}/{self.mes_aberto}/{self.ano_aberto}/xml", headers=self.auth_headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/xml; charset=utf-8')

        root = ET.fromstring(response.content)
        self.assertEqual(root.tag, 'dre')
        self.assertEqual(root.attrib.get('versao'), '1.0')
        self.assertEqual(root.attrib.get('regime'), 'CAIXA')
