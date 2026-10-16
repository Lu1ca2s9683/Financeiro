"""Regression: API cannot delete entities referenced by cash-movement history."""
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from ninja.testing import TestClient

from financeiro_core.app.api.endpoints import router
from financeiro_core.models import (
    CategoriaDespesa,
    ContaBancaria,
    ContaPagar,
    MovimentacaoCaixa,
)
from .helpers import create_test_token


class HistoricoFinanceiroProtegidoFase2BTest(TestCase):
    databases = {"default", "vendas"}

    def setUp(self):
        self.loja_id = 137
        self.user = User.objects.using("vendas").create(username="historic-protection")
        self.headers = {
            "Authorization": f"Bearer {create_test_token(self.user.pk, self.loja_id)}"
        }
        self.client = TestClient(router)
        self.categoria = CategoriaDespesa.objects.create(
            nome="Categoria historica", grupo_contabil="ADMINISTRATIVA"
        )
        self.conta = ContaBancaria.objects.create(
            nome="Caixa", loja_id_externo=self.loja_id,
            saldo_inicial=Decimal("100.00"), saldo_atual=Decimal("100.00"),
        )

    def registrar_movimento(self, **relacoes):
        return MovimentacaoCaixa.objects.create(
            conta=self.conta,
            tipo_movimentacao="ENTRADA",
            valor=Decimal("10.00"),
            descricao="Movimentacao financeira historica",
            loja_id_externo=self.loja_id,
            data_ocorrencia=timezone.now(),
            **relacoes,
        )

    def test_categoria_referenciada_nao_pode_ser_excluida_por_api(self):
        movimento = self.registrar_movimento(categoria=self.categoria)
        resposta = self.client.delete(
            f"/categorias/{self.categoria.pk}", headers=self.headers
        )
        self.assertEqual(resposta.status_code, 409, resposta.content)
        self.assertTrue(CategoriaDespesa.objects.filter(pk=self.categoria.pk).exists())
        self.assertEqual(MovimentacaoCaixa.objects.get(pk=movimento.pk).categoria_id, self.categoria.pk)

    def test_despesa_referenciada_nao_pode_ser_excluida_por_api(self):
        despesa = ContaPagar.objects.create(
            descricao="Despesa com historico financeiro",
            loja_id_externo=self.loja_id,
            categoria=self.categoria,
            valor_bruto=Decimal("10.00"),
            data_competencia=date(2026, 2, 1),
            data_transacao=date(2026, 2, 15),
        )
        movimento = self.registrar_movimento(despesa_vinculada=despesa)
        resposta = self.client.delete(f"/despesas/{despesa.pk}", headers=self.headers)
        self.assertEqual(resposta.status_code, 409, resposta.content)
        self.assertTrue(ContaPagar.objects.filter(pk=despesa.pk).exists())
        self.assertEqual(
            MovimentacaoCaixa.objects.get(pk=movimento.pk).despesa_vinculada_id,
            despesa.pk,
        )
