from django.test import TestCase
from django.contrib.auth.models import User
from financeiro_core.models import ContaPagar, CategoriaDespesa, FechamentoMensal, Fornecedor
from decimal import Decimal
from datetime import date
from ninja.testing import TestClient
from financeiro_core.app.api.endpoints import router
import json

class DespesasApiTest(TestCase):
    def setUp(self):
        self.client = TestClient(router)
        self.user = User.objects.create_user(username='testuser', password='password')
        self.categoria = CategoriaDespesa.objects.create(nome="Teste Cat", ativa=True)
        self.fornecedor = Fornecedor.objects.create(razao_social="Fornecedor Teste", cnpj_cpf="12345678000199")

        self.loja_id = 1
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
            data_vencimento=date(self.ano_aberto, self.mes_aberto, 20),
            status='PREVISTO'
        )

        self.despesa_fechada = ContaPagar.objects.create(
            descricao="Despesa Fechada",
            loja_id_externo=self.loja_id,
            categoria=self.categoria,
            valor_bruto=Decimal('100.00'),
            data_competencia=date(self.ano_fechado, self.mes_fechado, 15),
            data_vencimento=date(self.ano_fechado, self.mes_fechado, 20),
            status='PAGO'
        )

    def test_get_despesa_detail(self):
        response = self.client.get(f"/despesas/{self.despesa_aberta.id}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['id'], self.despesa_aberta.id)
        # Comparar como float ou string
        self.assertEqual(float(data['valor_bruto']), 100.0)

    def test_update_status_open_month(self):
        response = self.client.patch(f"/despesas/{self.despesa_aberta.id}/status", json={"status": "PAGO"})
        self.assertEqual(response.status_code, 200)
        self.despesa_aberta.refresh_from_db()
        self.assertEqual(self.despesa_aberta.status, "PAGO")

    def test_update_status_closed_month(self):
        response = self.client.patch(f"/despesas/{self.despesa_fechada.id}/status", json={"status": "CANCELADO"})
        if response.status_code == 422:
            print("Status validation error:", response.json())
        self.assertEqual(response.status_code, 400)
        self.despesa_fechada.refresh_from_db()
        self.assertNotEqual(self.despesa_fechada.status, "CANCELADO")

    def test_edit_despesa_open_month(self):
        payload = {
            "descricao": "Editada",
            "loja_id": self.loja_id,
            "categoria_id": self.categoria.id,
            "valor": 150.00,
            "data_competencia": f"{self.ano_aberto}-{self.mes_aberto:02d}-15",
            "data_vencimento": f"{self.ano_aberto}-{self.mes_aberto:02d}-20",
            "fornecedor_id": self.fornecedor.id
        }
        response = self.client.put(f"/despesas/{self.despesa_aberta.id}", json=payload)
        self.assertEqual(response.status_code, 200)
        self.despesa_aberta.refresh_from_db()
        self.assertEqual(self.despesa_aberta.descricao, "Editada")
        self.assertEqual(self.despesa_aberta.valor_bruto, Decimal('150.00'))

    def test_edit_despesa_closed_month(self):
        payload = {
            "descricao": "Tentativa Edicao",
            "loja_id": self.loja_id,
            "categoria_id": self.categoria.id,
            "valor": 150.00,
            "data_competencia": f"{self.ano_fechado}-{self.mes_fechado:02d}-15",
            "data_vencimento": f"{self.ano_fechado}-{self.mes_fechado:02d}-20",
            # Adicionando fornecedor_id pra garantir
            "fornecedor_id": self.fornecedor.id
        }
        response = self.client.put(f"/despesas/{self.despesa_fechada.id}", json=payload)
        if response.status_code != 400:
             print("EDIT CLOSED ERROR:", response.json())
        self.assertEqual(response.status_code, 400)

    def test_move_despesa_to_closed_month(self):
        payload = {
            "descricao": "Movendo para fechado",
            "loja_id": self.loja_id,
            "categoria_id": self.categoria.id,
            "valor": 100.00,
            "data_competencia": f"{self.ano_fechado}-{self.mes_fechado:02d}-15", # Mês fechado
            "data_vencimento": f"{self.ano_aberto}-{self.mes_aberto:02d}-20",
             "fornecedor_id": self.fornecedor.id
        }
        response = self.client.put(f"/despesas/{self.despesa_aberta.id}", json=payload)
        if response.status_code != 400:
             print("MOVE CLOSED ERROR:", response.json())
        self.assertEqual(response.status_code, 400)

    def test_dashboard_summary(self):
        # Cria mais algumas despesas para testar os contadores
        # 1. Despesa atrasada
        ContaPagar.objects.create(
            descricao="Atrasada",
            loja_id_externo=self.loja_id,
            categoria=self.categoria,
            valor_bruto=Decimal('50.00'),
            data_competencia=date(self.ano_aberto, self.mes_aberto, 1),
            data_vencimento=date(self.ano_aberto, self.mes_aberto, 5), # Já passou (considerando hoje > dia 5)
            status='ATRASADO'
        )

        # 2. Despesa vencendo hoje (deve contar como vencendo na semana)
        hoje = date.today()
        ContaPagar.objects.create(
            descricao="Vence Hoje",
            loja_id_externo=self.loja_id,
            categoria=self.categoria,
            valor_bruto=Decimal('60.00'),
            data_competencia=date(self.ano_aberto, self.mes_aberto, 1),
            data_vencimento=hoje,
            status='PREVISTO'
        )

        response = self.client.get(f"/dashboard/resumo/{self.loja_id}/{self.mes_aberto}/{self.ano_aberto}")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn("percentual_pago", data)
        self.assertIn("mensagem_assistente", data)
        # Verifica se contou a despesa atrasada
        self.assertGreaterEqual(data['despesas_atrasadas'], 1)
        # Verifica se contou a despesa vencendo hoje
        self.assertGreaterEqual(data['despesas_vencendo_semana'], 1)
