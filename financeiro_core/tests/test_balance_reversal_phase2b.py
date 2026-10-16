"""Fase 2B: nao editar/apagar movimentos; estornos auditaveis e atomicos."""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.utils import timezone
from ninja.testing import TestClient

from financeiro_core.app.api.endpoints import (
    EstornoMovimentacaoIn,
    estornar_movimentacao,
    router,
)
from financeiro_core.models import ContaBancaria, MovimentacaoCaixa, FechamentoMensal
from .helpers import create_test_token


class MovimentacaoImutavelFase2BTest(TestCase):
    def setUp(self):
        self.loja = 100
        self.conta = ContaBancaria.objects.create(
            nome='Caixa', loja_id_externo=self.loja,
            saldo_inicial=Decimal('100.00'), saldo_atual=Decimal('100.00'),
        )
        self.mov = MovimentacaoCaixa.objects.create(
            conta=self.conta, loja_id_externo=self.loja,
            tipo_movimentacao='ENTRADA', valor=Decimal('10.00'),
            descricao='Entrada original', data_ocorrencia=timezone.now(),
        )

    def test_save_existente_proibido(self):
        self.mov.valor = Decimal('500.00')
        with self.assertRaises(ValidationError):
            self.mov.save()
        self.mov.refresh_from_db()
        self.conta.refresh_from_db()
        self.assertEqual(self.mov.valor, Decimal('10.00'))
        self.assertEqual(self.conta.saldo_atual, Decimal('110.00'))

    def test_delete_individual_e_query_set_proibidos(self):
        with self.assertRaises(ValidationError):
            self.mov.delete()
        with self.assertRaises(ValidationError):
            MovimentacaoCaixa.objects.filter(pk=self.mov.pk).delete()
        self.assertTrue(MovimentacaoCaixa.objects.filter(pk=self.mov.pk).exists())

    def test_update_bulk_update_e_bulk_create_proibidos(self):
        with self.assertRaises(ValidationError):
            MovimentacaoCaixa.objects.filter(pk=self.mov.pk).update(valor=Decimal('70.00'))
        with self.assertRaises(ValidationError):
            MovimentacaoCaixa.objects.bulk_update([self.mov], ['valor'])
        with self.assertRaises(ValidationError):
            MovimentacaoCaixa.objects.bulk_create([self.mov])

    def test_apagar_conta_com_historico_fica_protegido(self):
        with self.assertRaises(ProtectedError):
            self.conta.delete()
        self.assertTrue(ContaBancaria.objects.filter(pk=self.conta.pk).exists())

    def test_estorno_sem_motivo_e_autor_nao_e_permitido(self):
        with self.assertRaises(ValidationError):
            MovimentacaoCaixa.objects.create(
                conta=self.conta, loja_id_externo=self.loja,
                tipo_movimentacao='SAIDA', valor=Decimal('10.00'),
                descricao='Estorno sem justificativa',
                estorno_de=self.mov, data_ocorrencia=timezone.now(),
            )
        self.assertEqual(MovimentacaoCaixa.objects.count(), 1)

    def test_estorno_com_valor_diferente_e_rejeitado(self):
        with self.assertRaises(ValidationError):
            MovimentacaoCaixa.objects.create(
                conta=self.conta, loja_id_externo=self.loja,
                tipo_movimentacao='SAIDA', valor=Decimal('9.00'),
                descricao='Valor diferente', estorno_de=self.mov,
                motivo_estorno='Erro confirmado na conciliacao',
                criado_por_id=123, data_ocorrencia=timezone.now(),
            )
        self.assertEqual(MovimentacaoCaixa.objects.count(), 1)


class EstornoApiFase2BTest(TestCase):
    databases = {'default', 'vendas'}

    def setUp(self):
        self.client = TestClient(router)
        self.loja = 10
        self.user = User.objects.using('vendas').create(username='estorno-user')
        self.headers = {
            'Authorization': f'Bearer {create_test_token(self.user.pk, self.loja)}'
        }
        self.conta = ContaBancaria.objects.create(
            nome='Conta de teste', loja_id_externo=self.loja,
            saldo_inicial=Decimal('100.00'), saldo_atual=Decimal('100.00'),
        )
        self.outra = ContaBancaria.objects.create(
            nome='Banco', loja_id_externo=self.loja,
            saldo_inicial=Decimal('40.00'), saldo_atual=Decimal('40.00'),
        )
        self.mov = MovimentacaoCaixa.objects.create(
            conta=self.conta, loja_id_externo=self.loja,
            tipo_movimentacao='SAIDA', valor=Decimal('25.50'),
            descricao='Saida original', data_ocorrencia=timezone.now(),
            criado_por_id=self.user.pk,
        )

    def api_estornar(self, pk, motivo='Lancamento realizado na conta errada', **kw):
        return self.client.post(
            f'/contas/movimentacoes/{pk}/estornar',
            json={'motivo': motivo}, headers=kw.get('headers', self.headers),
        )

    def test_estorno_cria_compensacao_com_autoria_motivo_e_saldo(self):
        response = self.api_estornar(self.mov.pk)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(MovimentacaoCaixa.objects.count(), 2)
        self.mov.refresh_from_db()
        reverso = MovimentacaoCaixa.objects.get(estorno_de=self.mov)
        self.assertEqual(reverso.tipo_movimentacao, 'ENTRADA')
        self.assertEqual(reverso.valor, Decimal('25.50'))
        self.assertEqual(reverso.criado_por_id, self.user.pk)
        self.assertIn('conta errada', reverso.motivo_estorno)
        self.assertEqual(self.mov.tipo_movimentacao, 'SAIDA')
        self.conta.refresh_from_db()
        self.assertEqual(self.conta.saldo_atual, Decimal('100.00'))

    def test_extrato_auditavel_da_loja_nao_expoe_outra_loja(self):
        response = self.client.get('/contas/movimentacoes', headers=self.headers)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual([item['id'] for item in response.json()], [self.mov.pk])
        self.assertEqual(response.json()[0]['estornado'], False)
        self.assertEqual(response.json()[0]['criado_por_id'], self.user.pk)
        self.assertEqual(self.api_estornar(self.mov.pk).status_code, 200)
        after = self.client.get('/contas/movimentacoes', headers=self.headers)
        self.assertEqual(len(after.json()), 2)
        self.assertEqual([item['id'] for item in after.json() if item['estornado']], [self.mov.pk])
        self.assertEqual(self.client.get('/contas/movimentacoes').status_code, 401)
        self.assertEqual(
            self.client.get('/contas/movimentacoes?conta_id=999999', headers=self.headers).status_code,
            404,
        )

    def test_estorno_repetido_gera_conflito_sem_duplicacao(self):
        self.assertEqual(self.api_estornar(self.mov.pk).status_code, 200)
        duplicate = self.api_estornar(self.mov.pk)
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(MovimentacaoCaixa.objects.count(), 2)
        self.conta.refresh_from_db()
        self.assertEqual(self.conta.saldo_atual, Decimal('100.00'))

    def test_estorno_de_outra_loja_retorna_404(self):
        terceiro = MovimentacaoCaixa.objects.create(
            conta=ContaBancaria.objects.create(nome='Outra loja', loja_id_externo=11),
            loja_id_externo=11, tipo_movimentacao='ENTRADA',
            valor=Decimal('5.00'), descricao='Outra loja',
            data_ocorrencia=timezone.now(),
        )
        self.assertEqual(self.api_estornar(terceiro.pk).status_code, 404)
        self.assertFalse(MovimentacaoCaixa.objects.filter(estorno_de=terceiro).exists())

    def test_estorno_exige_login_e_justificativa(self):
        self.assertEqual(self.api_estornar(self.mov.pk, headers={}).status_code, 401)
        self.assertEqual(self.api_estornar(self.mov.pk, motivo='curto').status_code, 400)
        self.assertEqual(MovimentacaoCaixa.objects.count(), 1)

    def test_transferencia_nova_estorna_ambas_as_pontas(self):
        transfer = self.client.post(
            '/contas/transferencia',
            json={
                'conta_origem_id': self.conta.pk,
                'conta_destino_id': self.outra.pk,
                'valor': '12.35', 'data': '2026-08-29',
                'descricao': 'Transferencia conciliacao',
            },
            headers=self.headers,
        )
        self.assertEqual(transfer.status_code, 200, transfer.content)
        pernas = list(MovimentacaoCaixa.objects.filter(
            tipo_movimentacao__startswith='TRANSFERENCIA_'
        ).order_by('pk'))
        self.assertEqual(len(pernas), 2)
        self.assertIsNotNone(pernas[0].grupo_transferencia)
        self.assertEqual(pernas[0].grupo_transferencia, pernas[1].grupo_transferencia)
        estorno = self.api_estornar(pernas[0].pk)
        self.assertEqual(estorno.status_code, 200, estorno.content)
        self.assertEqual(len(estorno.json()['estornos']), 2)
        self.assertEqual(MovimentacaoCaixa.objects.filter(estorno_de__isnull=False).count(), 2)
        self.assertEqual(self.api_estornar(pernas[1].pk).status_code, 409)
        self.conta.refresh_from_db()
        self.outra.refresh_from_db()
        self.assertEqual(self.conta.saldo_atual, Decimal('74.50'))
        self.assertEqual(self.outra.saldo_atual, Decimal('40.00'))

    def test_transferencia_legada_sem_par_nao_estorna(self):
        legado = MovimentacaoCaixa.objects.create(
            conta=self.conta, loja_id_externo=self.loja,
            tipo_movimentacao='TRANSFERENCIA_SAIDA',
            valor=Decimal('1.00'), descricao='Sem id historico',
            data_ocorrencia=timezone.now(),
        )
        self.assertIsNone(legado.grupo_transferencia)
        self.assertEqual(self.api_estornar(legado.pk).status_code, 409)
        self.assertEqual(MovimentacaoCaixa.objects.filter(estorno_de=legado).count(), 0)

    def test_estorno_em_periodo_atual_concluido_fica_bloqueado(self):
        today = timezone.localdate()
        FechamentoMensal.objects.create(
            loja_id_externo=self.loja,
            mes=today.month, ano=today.year,
            faturamento_bruto=Decimal('100.00'),
            total_taxas=Decimal('0.00'),
            receita_liquida=Decimal('100.00'),
            total_despesas=Decimal('0.00'),
            resultado_operacional=Decimal('100.00'),
            status='CONCLUIDO',
        )
        self.assertEqual(self.api_estornar(self.mov.pk).status_code, 409)
        self.assertEqual(MovimentacaoCaixa.objects.count(), 1)

    def test_falha_no_segundo_estorno_reverte_a_transferencia_inteira(self):
        transfer = self.client.post(
            '/contas/transferencia',
            json={
                'conta_origem_id': self.conta.pk,
                'conta_destino_id': self.outra.pk,
                'valor': '3.00', 'data': '2026-08-29',
                'descricao': 'Transferencia para rollback',
            }, headers=self.headers,
        )
        self.assertEqual(transfer.status_code, 200)
        original = MovimentacaoCaixa.objects.filter(
            tipo_movimentacao='TRANSFERENCIA_SAIDA',
        ).first()
        real_create = MovimentacaoCaixa.objects.create
        called = 0

        def fail_second(**kwargs):
            nonlocal called
            if kwargs.get('estorno_de') is not None:
                called += 1
                if called == 2:
                    raise RuntimeError('falha simulada da segunda ponta')
            return real_create(**kwargs)

        request = SimpleNamespace(active_loja_id=self.loja, user_id=self.user.pk)
        with patch.object(MovimentacaoCaixa.objects, 'create', side_effect=fail_second):
            with self.assertRaisesRegex(RuntimeError, 'falha simulada'):
                estornar_movimentacao(request, original.pk, EstornoMovimentacaoIn(
                    motivo='Reversao de transferencia com falha simulada',
                ))
        self.assertFalse(MovimentacaoCaixa.objects.filter(estorno_de__isnull=False).exists())
        self.conta.refresh_from_db()
        self.outra.refresh_from_db()
        self.assertEqual(self.conta.saldo_atual, Decimal('71.50'))
        self.assertEqual(self.outra.saldo_atual, Decimal('43.00'))
