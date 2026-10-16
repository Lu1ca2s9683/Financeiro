"""Fase 2A: escritas atomicas em conta bancaria (SQLite em testes)."""
from datetime import datetime
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from financeiro_core.models import ContaBancaria, MovimentacaoCaixa


class SaldoAtomicoFase2ATest(TestCase):
    def setUp(self):
        self.loja_id = 101
        self.conta = ContaBancaria.objects.create(
            nome='Caixa principal', loja_id_externo=self.loja_id,
            saldo_inicial=Decimal('100.00'), saldo_atual=Decimal('100.00'),
        )

    def movimento(self, conta, tipo, valor, loja_id=None):
        return MovimentacaoCaixa.objects.create(
            conta=conta,
            tipo_movimentacao=tipo,
            valor=valor,
            descricao='Teste de consistencia',
            data_ocorrencia=timezone.make_aware(datetime(2026, 8, 29, 12)),
            loja_id_externo=self.loja_id if loja_id is None else loja_id,
        )

    def test_referencia_de_conta_desatualizada_nao_sobrescreve_saldo(self):
        referencia_a = ContaBancaria.objects.get(pk=self.conta.pk)
        referencia_b = ContaBancaria.objects.get(pk=self.conta.pk)
        self.movimento(referencia_a, 'ENTRADA', Decimal('17.50'))
        # A referencia_b ainda tem saldo 100.00 em memoria.
        self.assertEqual(referencia_b.saldo_atual, Decimal('100.00'))
        self.movimento(referencia_b, 'SAIDA', Decimal('3.20'))
        self.conta.refresh_from_db()
        self.assertEqual(self.conta.saldo_atual, Decimal('114.30'))
        self.assertEqual(MovimentacaoCaixa.objects.count(), 2)

    def test_entradas_e_saidas_de_transferencia_preservam_total(self):
        destino = ContaBancaria.objects.create(
            nome='Banco destino', loja_id_externo=self.loja_id,
            saldo_inicial=Decimal('40.00'), saldo_atual=Decimal('40.00'),
        )
        self.movimento(self.conta, 'TRANSFERENCIA_SAIDA', Decimal('12.35'))
        self.movimento(destino, 'TRANSFERENCIA_ENTRADA', Decimal('12.35'))
        self.conta.refresh_from_db()
        destino.refresh_from_db()
        self.assertEqual(self.conta.saldo_atual, Decimal('87.65'))
        self.assertEqual(destino.saldo_atual, Decimal('52.35'))
        self.assertEqual(self.conta.saldo_atual + destino.saldo_atual, Decimal('140.00'))

    def test_movimento_de_outra_loja_reverte_insert_e_saldo(self):
        instance = MovimentacaoCaixa(
            conta=self.conta,
            tipo_movimentacao='ENTRADA',
            valor=Decimal('10.00'),
            descricao='Loja errada',
            data_ocorrencia=timezone.now(),
            loja_id_externo=self.loja_id + 1,
        )
        with self.assertRaises(ValidationError):
            instance.save()
        self.assertIsNone(instance.pk)
        self.assertTrue(instance._state.adding)
        self.assertFalse(MovimentacaoCaixa.objects.exists())
        self.conta.refresh_from_db()
        self.assertEqual(self.conta.saldo_atual, Decimal('100.00'))

    def test_valores_nao_monetarios_sao_rejeitados_sem_gravacao(self):
        for valor in (Decimal('0'), Decimal('-1'), Decimal('1.001')):
            with self.subTest(valor=valor), self.assertRaises(ValidationError):
                self.movimento(self.conta, 'ENTRADA', valor)
        self.assertFalse(MovimentacaoCaixa.objects.exists())
        self.conta.refresh_from_db()
        self.assertEqual(self.conta.saldo_atual, Decimal('100.00'))

    def test_tipo_desconhecido_e_rejeitado_sem_movimentacao(self):
        with self.assertRaises(ValidationError):
            self.movimento(self.conta, 'TIPO_INVALIDO', Decimal('3.00'))
        self.assertFalse(MovimentacaoCaixa.objects.exists())
        self.conta.refresh_from_db()
        self.assertEqual(self.conta.saldo_atual, Decimal('100.00'))
