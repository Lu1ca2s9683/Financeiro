from django.test import TestCase
from django.contrib.auth.models import User
from financeiro_core.models import ContaPagar, CategoriaDespesa, FechamentoMensal, Fornecedor
from decimal import Decimal
from datetime import date
from ninja.testing import TestClient
from financeiro_core.app.api.endpoints import router
import jwt
import datetime

# Same key as security.py
SECRET_KEY = "django-insecure-chave-dev-local"

def create_token(user_id, active_loja_id):
    payload = {
        "user_id": user_id,
        "active_loja_id": active_loja_id,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

class DespesasApiTest(TestCase):
    def setUp(self):
        self.client = TestClient(router)
        self.user = User.objects.create_user(username='testuser', password='password')
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
        # Must send auth header
        response = self.client.get(f"/despesas/{self.despesa_aberta.id}", headers=self.auth_headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['id'], self.despesa_aberta.id)
        self.assertEqual(float(data['valor_bruto']), 100.0)

    def test_update_status_open_month(self):
        response = self.client.patch(f"/despesas/{self.despesa_aberta.id}/status", json={"status": "PAGO"}, headers=self.auth_headers)
        self.assertEqual(response.status_code, 200)
        self.despesa_aberta.refresh_from_db()
        self.assertEqual(self.despesa_aberta.status, "PAGO")

    def test_update_status_closed_month(self):
        response = self.client.patch(f"/despesas/{self.despesa_fechada.id}/status", json={"status": "CANCELADO"}, headers=self.auth_headers)
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
        response = self.client.put(f"/despesas/{self.despesa_aberta.id}", json=payload, headers=self.auth_headers)
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
            "fornecedor_id": self.fornecedor.id
        }
        response = self.client.put(f"/despesas/{self.despesa_fechada.id}", json=payload, headers=self.auth_headers)
        self.assertEqual(response.status_code, 400)

    def test_move_despesa_to_closed_month(self):
        payload = {
            "descricao": "Movendo para fechado",
            "loja_id": self.loja_id,
            "categoria_id": self.categoria.id,
            "valor": 100.00,
            "data_competencia": f"{self.ano_fechado}-{self.mes_fechado:02d}-15",
            "data_vencimento": f"{self.ano_aberto}-{self.mes_aberto:02d}-20",
             "fornecedor_id": self.fornecedor.id
        }
        response = self.client.put(f"/despesas/{self.despesa_aberta.id}", json=payload, headers=self.auth_headers)
        self.assertEqual(response.status_code, 400)

    def test_access_wrong_store(self):
        # Tries to access store 1 with token for store 2
        token_loja_2 = create_token(self.user.id, 2)
        headers_2 = {"Authorization": f"Bearer {token_loja_2}"}

        # Endpoint expects access to store 1 (implicitly via object ownership or explicit param)
        # obter_resumo_dashboard asks for store 1
        response = self.client.get(f"/dashboard/resumo/{self.loja_id}/{self.mes_aberto}/{self.ano_aberto}", headers=headers_2)
        self.assertEqual(response.status_code, 403)

    def test_dashboard_summary(self):
        # 1. Despesa atrasada
        ContaPagar.objects.create(
            descricao="Atrasada",
            loja_id_externo=self.loja_id,
            categoria=self.categoria,
            valor_bruto=Decimal('50.00'),
            data_competencia=date(self.ano_aberto, self.mes_aberto, 1),
            data_vencimento=date(self.ano_aberto, self.mes_aberto, 5),
            status='ATRASADO'
        )

        # 2. Despesa vencendo hoje
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

        response = self.client.get(f"/dashboard/resumo/{self.loja_id}/{self.mes_aberto}/{self.ano_aberto}", headers=self.auth_headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertGreaterEqual(data['despesas_atrasadas'], 1)
        self.assertGreaterEqual(data['despesas_vencendo_semana'], 1)
