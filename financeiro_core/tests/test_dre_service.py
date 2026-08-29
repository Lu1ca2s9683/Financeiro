from django.test import TestCase
from unittest.mock import MagicMock
from decimal import Decimal
from financeiro_core.app.services.dre_service import DREService
from financeiro_core.domain.services import FaturamentoItemDTO

class DREServiceTest(TestCase):
    databases = {'default', 'vendas'}

    def setUp(self):
        self.mock_vendas_client = MagicMock()
        self.service = DREService(vendas_client=self.mock_vendas_client)

    def test_gerar_dre_sem_faturamento(self):
        self.mock_vendas_client.get_faturamento_por_loja.return_value = []

        dre_data = self.service.gerar(loja_id=1, mes=10, ano=2024, loja_nome="Loja Teste", gerado_por="testuser")

        self.assertEqual(dre_data["resumo"]["receita_bruta"], Decimal('0.00'))

    def test_gerar_dre_com_faturamento(self):
        self.mock_vendas_client.get_faturamento_por_loja.return_value = [
            FaturamentoItemDTO(tipo_pagamento="PIX", bandeira="GERAL", parcelas=1, valor_bruto=Decimal("1000.00"))
        ]

        dre_data = self.service.gerar(loja_id=1, mes=10, ano=2024, loja_nome="Loja Teste", gerado_por="testuser")

        self.assertEqual(dre_data["resumo"]["receita_bruta"], Decimal('1000.00'))
