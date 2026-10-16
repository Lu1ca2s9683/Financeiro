"""Fase 2A - saldo atomico de MovimentacaoCaixa.

Execute a partir da raiz do repositorio:
    python scripts/apply_phase2a.py --check
    python scripts/apply_phase2a.py

Este utilitario valida os trechos exatos antes de editar qualquer arquivo.
Nao modifica o banco de dados nem recalcula saldos existentes.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

BASE = Path(__file__).resolve().parent.parent
MODEL = BASE / "financeiro_core/app/models/entidades.py"
TEST = BASE / "financeiro_core/tests/test_balance_atomic_phase2a.py"

OLD_IMPORT = "from django.db import models\nfrom django.contrib.auth.models import User\nfrom decimal import Decimal\n"
NEW_IMPORT = """from django.db import models, router, transaction
from django.db.models import F
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from decimal import Decimal, InvalidOperation
"""

OLD_SAVE = """    def save(self, *args, **kwargs):
        # Controle para não duplicar valores se for um update (simples)
        is_new = self.pk is None

        super().save(*args, **kwargs)

        # O gatilho atualiza o saldo apenas na inserção inicial para evitar corrupção em edições complexas
        if is_new:
            if self.tipo_movimentacao in ['ENTRADA', 'TRANSFERENCIA_ENTRADA']:
                self.conta.saldo_atual += self.valor
            elif self.tipo_movimentacao in ['SAIDA', 'TRANSFERENCIA_SAIDA']:
                self.conta.saldo_atual -= self.valor

            self.conta.save(update_fields=['saldo_atual'])
"""

NEW_SAVE = """    def save(self, *args, **kwargs):
        # Fase 2A: a insercao e o ajuste de saldo formam uma transacao unica.
        # Atualizacoes/estornos de movimentos existentes serao tratadas na 2B.
        if self.pk is not None:
            return super().save(*args, **kwargs)

        entradas = {'ENTRADA', 'TRANSFERENCIA_ENTRADA'}
        saidas = {'SAIDA', 'TRANSFERENCIA_SAIDA'}
        if self.tipo_movimentacao not in entradas | saidas:
            raise ValidationError({'tipo_movimentacao': 'Tipo de movimentacao invalido.'})

        try:
            valor = Decimal(str(self.valor))
        except (InvalidOperation, TypeError, ValueError):
            raise ValidationError({'valor': 'Valor monetario invalido.'}) from None

        # O campo possui decimal_places=2: nao aceitar frações perdidas
        # na gravacao do movimento que divergeriam do saldo ajustado.
        if not valor.is_finite() or valor <= 0 or valor.as_tuple().exponent < -2:
            raise ValidationError({'valor': 'Informe um valor positivo com ate duas casas decimais.'})

        delta = valor if self.tipo_movimentacao in entradas else -valor
        using = kwargs.get('using') or router.db_for_write(type(self), instance=self)
        previous_state = (self.pk, self._state.adding, self._state.db)
        save_kwargs = {**kwargs, 'using': using}

        try:
            with transaction.atomic(using=using):
                super().save(*args, **save_kwargs)
                # F() executa o incremento diretamente no banco, sem
                # sobrescrever incrementos feitos por outra transacao.
                updated = (
                    ContaBancaria.objects.using(using)
                    .filter(pk=self.conta_id, loja_id_externo=self.loja_id_externo)
                    .update(saldo_atual=F('saldo_atual') + delta)
                )
                if updated != 1:
                    raise ValidationError(
                        'Conta bancaria inexistente ou pertencente a outra loja.'
                    )
        except Exception:
            # Um INSERT pode definir pk antes de um UPDATE falhar; apos
            # rollback, restaurar tambem o estado Python da instancia.
            self.pk, self._state.adding, self._state.db = previous_state
            raise
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true', help='Validar sem alterar arquivos')
    args = parser.parse_args()
    if not MODEL.exists():
        print(f'ERRO: execute na raiz do repo. Ausente: {MODEL}', file=sys.stderr)
        return 2
    original = MODEL.read_text(encoding='utf-8')
    for title, needle in [('imports', OLD_IMPORT), ('save antigo', OLD_SAVE)]:
        count = original.count(needle)
        if count != 1:
            print(f'ERRO: {title}: esperada uma correspondencia, encontradas {count}. Sem alteracoes.', file=sys.stderr)
            return 2
    if TEST.exists():
        print(f'ERRO: teste ja existe: {TEST}. Sem alteracoes.', file=sys.stderr)
        return 2
    revised = original.replace(OLD_IMPORT, NEW_IMPORT, 1).replace(OLD_SAVE, NEW_SAVE, 1)
    try:
        compile(revised, str(MODEL), 'exec')
    except SyntaxError as err:
        print(f'ERRO: codigo gerado invalido: {err}', file=sys.stderr)
        return 2
    print('Validacao OK: modelo e novo teste; nenhuma migration necessaria.')
    if args.check:
        return 0
    MODEL.write_text(revised, encoding='utf-8')
    TEST.write_text(TEST_TEXT, encoding='utf-8')
    print('Atualizado:', MODEL.relative_to(BASE))
    print('Criado:', TEST.relative_to(BASE))
    return 0


TEST_TEXT = '''"""Fase 2A: escritas atomicas em conta bancaria (SQLite em testes)."""
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
'''


if __name__ == '__main__':
    raise SystemExit(main())
