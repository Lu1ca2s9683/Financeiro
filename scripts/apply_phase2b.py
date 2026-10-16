"""Aplicador da fase 2B: imutabilidade ORM e estornos rastreaveis.

Uso (na raiz do repositorio Financeiro):
  python scripts/apply_phase2b.py --check
  python scripts/apply_phase2b.py

Precondicao: PR #63 (fase 2A) integrado. Nao executa migracoes e nao
altera qualquer registro de producao; somente edita arquivos de codigo.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
MODEL = ROOT / 'financeiro_core/app/models/entidades.py'
API = ROOT / 'financeiro_core/app/api/endpoints.py'
MIG = ROOT / 'financeiro_core/migrations/0007_movimentacao_estorno_2b.py'
TEST = ROOT / 'financeiro_core/tests/test_balance_reversal_phase2b.py'

MIGRATION_TEXT = '"""Fase 2B: vinculo de estorno e identificador de transferencias futuras.\n\nA migracao NAO estorna nem recalcula nenhum saldo historico.\nTransferencias antigas ficam com grupo_transferencia=NULL e nao\npodem ser estornadas automaticamente por falta de pareamento seguro.\n"""\nfrom django.db import migrations, models\nimport django.db.models.deletion\n\n\nclass Migration(migrations.Migration):\n    dependencies = [\n        (\'financeiro_core\', \'0006_contapagar_descricao_original_extrato_and_more\'),\n    ]\n\n    operations = [\n        migrations.AlterField(\n            model_name=\'movimentacaocaixa\',\n            name=\'conta\',\n            field=models.ForeignKey(\n                on_delete=django.db.models.deletion.PROTECT,\n                related_name=\'movimentacoes\',\n                to=\'financeiro_core.contabancaria\',\n            ),\n        ),\n        migrations.AlterField(\n            model_name=\'movimentacaocaixa\',\n            name=\'categoria\',\n            field=models.ForeignKey(\n                blank=True, null=True,\n                on_delete=django.db.models.deletion.PROTECT,\n                related_name=\'movimentacoes_caixa\',\n                to=\'financeiro_core.categoriadespesa\',\n            ),\n        ),\n        migrations.AlterField(\n            model_name=\'movimentacaocaixa\',\n            name=\'despesa_vinculada\',\n            field=models.ForeignKey(\n                blank=True, null=True,\n                on_delete=django.db.models.deletion.PROTECT,\n                related_name=\'pagamentos_caixa\',\n                to=\'financeiro_core.contapagar\',\n            ),\n        ),\n        migrations.AddField(\n            model_name=\'movimentacaocaixa\',\n            name=\'estorno_de\',\n            field=models.OneToOneField(\n                blank=True,\n                null=True,\n                on_delete=django.db.models.deletion.PROTECT,\n                related_name=\'estorno\',\n                to=\'financeiro_core.movimentacaocaixa\',\n            ),\n        ),\n        migrations.AddField(\n            model_name=\'movimentacaocaixa\',\n            name=\'motivo_estorno\',\n            field=models.TextField(blank=True),\n        ),\n        migrations.AddField(\n            model_name=\'movimentacaocaixa\',\n            name=\'grupo_transferencia\',\n            field=models.UUIDField(blank=True, db_index=True, null=True),\n        ),\n    ]\n'
TEST_TEXT = '"""Fase 2B: nao editar/apagar movimentos; estornos auditaveis e atomicos."""\nfrom datetime import date\nfrom decimal import Decimal\nfrom types import SimpleNamespace\nfrom unittest.mock import patch\n\nfrom django.contrib.auth.models import User\nfrom django.core.exceptions import ValidationError\nfrom django.db.models.deletion import ProtectedError\nfrom django.test import TestCase\nfrom django.utils import timezone\nfrom ninja.testing import TestClient\n\nfrom financeiro_core.app.api.endpoints import (\n    EstornoMovimentacaoIn,\n    estornar_movimentacao,\n    router,\n)\nfrom financeiro_core.models import ContaBancaria, MovimentacaoCaixa, FechamentoMensal\nfrom .helpers import create_test_token\n\n\nclass MovimentacaoImutavelFase2BTest(TestCase):\n    def setUp(self):\n        self.loja = 100\n        self.conta = ContaBancaria.objects.create(\n            nome=\'Caixa\', loja_id_externo=self.loja,\n            saldo_inicial=Decimal(\'100.00\'), saldo_atual=Decimal(\'100.00\'),\n        )\n        self.mov = MovimentacaoCaixa.objects.create(\n            conta=self.conta, loja_id_externo=self.loja,\n            tipo_movimentacao=\'ENTRADA\', valor=Decimal(\'10.00\'),\n            descricao=\'Entrada original\', data_ocorrencia=timezone.now(),\n        )\n\n    def test_save_existente_proibido(self):\n        self.mov.valor = Decimal(\'500.00\')\n        with self.assertRaises(ValidationError):\n            self.mov.save()\n        self.mov.refresh_from_db()\n        self.conta.refresh_from_db()\n        self.assertEqual(self.mov.valor, Decimal(\'10.00\'))\n        self.assertEqual(self.conta.saldo_atual, Decimal(\'110.00\'))\n\n    def test_delete_individual_e_query_set_proibidos(self):\n        with self.assertRaises(ValidationError):\n            self.mov.delete()\n        with self.assertRaises(ValidationError):\n            MovimentacaoCaixa.objects.filter(pk=self.mov.pk).delete()\n        self.assertTrue(MovimentacaoCaixa.objects.filter(pk=self.mov.pk).exists())\n\n    def test_update_bulk_update_e_bulk_create_proibidos(self):\n        with self.assertRaises(ValidationError):\n            MovimentacaoCaixa.objects.filter(pk=self.mov.pk).update(valor=Decimal(\'70.00\'))\n        with self.assertRaises(ValidationError):\n            MovimentacaoCaixa.objects.bulk_update([self.mov], [\'valor\'])\n        with self.assertRaises(ValidationError):\n            MovimentacaoCaixa.objects.bulk_create([self.mov])\n\n    def test_apagar_conta_com_historico_fica_protegido(self):\n        with self.assertRaises(ProtectedError):\n            self.conta.delete()\n        self.assertTrue(ContaBancaria.objects.filter(pk=self.conta.pk).exists())\n\n    def test_estorno_sem_motivo_e_autor_nao_e_permitido(self):\n        with self.assertRaises(ValidationError):\n            MovimentacaoCaixa.objects.create(\n                conta=self.conta, loja_id_externo=self.loja,\n                tipo_movimentacao=\'SAIDA\', valor=Decimal(\'10.00\'),\n                descricao=\'Estorno sem justificativa\',\n                estorno_de=self.mov, data_ocorrencia=timezone.now(),\n            )\n        self.assertEqual(MovimentacaoCaixa.objects.count(), 1)\n\n    def test_estorno_com_valor_diferente_e_rejeitado(self):\n        with self.assertRaises(ValidationError):\n            MovimentacaoCaixa.objects.create(\n                conta=self.conta, loja_id_externo=self.loja,\n                tipo_movimentacao=\'SAIDA\', valor=Decimal(\'9.00\'),\n                descricao=\'Valor diferente\', estorno_de=self.mov,\n                motivo_estorno=\'Erro confirmado na conciliacao\',\n                criado_por_id=123, data_ocorrencia=timezone.now(),\n            )\n        self.assertEqual(MovimentacaoCaixa.objects.count(), 1)\n\n\nclass EstornoApiFase2BTest(TestCase):\n    databases = {\'default\', \'vendas\'}\n\n    def setUp(self):\n        self.client = TestClient(router)\n        self.loja = 10\n        self.user = User.objects.using(\'vendas\').create(username=\'estorno-user\')\n        self.headers = {\n            \'Authorization\': f\'Bearer {create_test_token(self.user.pk, self.loja)}\'\n        }\n        self.conta = ContaBancaria.objects.create(\n            nome=\'Conta de teste\', loja_id_externo=self.loja,\n            saldo_inicial=Decimal(\'100.00\'), saldo_atual=Decimal(\'100.00\'),\n        )\n        self.outra = ContaBancaria.objects.create(\n            nome=\'Banco\', loja_id_externo=self.loja,\n            saldo_inicial=Decimal(\'40.00\'), saldo_atual=Decimal(\'40.00\'),\n        )\n        self.mov = MovimentacaoCaixa.objects.create(\n            conta=self.conta, loja_id_externo=self.loja,\n            tipo_movimentacao=\'SAIDA\', valor=Decimal(\'25.50\'),\n            descricao=\'Saida original\', data_ocorrencia=timezone.now(),\n            criado_por_id=self.user.pk,\n        )\n\n    def api_estornar(self, pk, motivo=\'Lancamento realizado na conta errada\', **kw):\n        return self.client.post(\n            f\'/contas/movimentacoes/{pk}/estornar\',\n            json={\'motivo\': motivo}, headers=kw.get(\'headers\', self.headers),\n        )\n\n    def test_estorno_cria_compensacao_com_autoria_motivo_e_saldo(self):\n        response = self.api_estornar(self.mov.pk)\n        self.assertEqual(response.status_code, 200, response.content)\n        self.assertEqual(MovimentacaoCaixa.objects.count(), 2)\n        self.mov.refresh_from_db()\n        reverso = MovimentacaoCaixa.objects.get(estorno_de=self.mov)\n        self.assertEqual(reverso.tipo_movimentacao, \'ENTRADA\')\n        self.assertEqual(reverso.valor, Decimal(\'25.50\'))\n        self.assertEqual(reverso.criado_por_id, self.user.pk)\n        self.assertIn(\'conta errada\', reverso.motivo_estorno)\n        self.assertEqual(self.mov.tipo_movimentacao, \'SAIDA\')\n        self.conta.refresh_from_db()\n        self.assertEqual(self.conta.saldo_atual, Decimal(\'100.00\'))\n\n    def test_extrato_auditavel_da_loja_nao_expoe_outra_loja(self):\n        response = self.client.get(\'/contas/movimentacoes\', headers=self.headers)\n        self.assertEqual(response.status_code, 200, response.content)\n        self.assertEqual([item[\'id\'] for item in response.json()], [self.mov.pk])\n        self.assertEqual(response.json()[0][\'estornado\'], False)\n        self.assertEqual(response.json()[0][\'criado_por_id\'], self.user.pk)\n        self.assertEqual(self.api_estornar(self.mov.pk).status_code, 200)\n        after = self.client.get(\'/contas/movimentacoes\', headers=self.headers)\n        self.assertEqual(len(after.json()), 2)\n        self.assertEqual([item[\'id\'] for item in after.json() if item[\'estornado\']], [self.mov.pk])\n        self.assertEqual(self.client.get(\'/contas/movimentacoes\').status_code, 401)\n        self.assertEqual(\n            self.client.get(\'/contas/movimentacoes?conta_id=999999\', headers=self.headers).status_code,\n            404,\n        )\n\n    def test_estorno_repetido_gera_conflito_sem_duplicacao(self):\n        self.assertEqual(self.api_estornar(self.mov.pk).status_code, 200)\n        duplicate = self.api_estornar(self.mov.pk)\n        self.assertEqual(duplicate.status_code, 409)\n        self.assertEqual(MovimentacaoCaixa.objects.count(), 2)\n        self.conta.refresh_from_db()\n        self.assertEqual(self.conta.saldo_atual, Decimal(\'100.00\'))\n\n    def test_estorno_de_outra_loja_retorna_404(self):\n        terceiro = MovimentacaoCaixa.objects.create(\n            conta=ContaBancaria.objects.create(nome=\'Outra loja\', loja_id_externo=11),\n            loja_id_externo=11, tipo_movimentacao=\'ENTRADA\',\n            valor=Decimal(\'5.00\'), descricao=\'Outra loja\',\n            data_ocorrencia=timezone.now(),\n        )\n        self.assertEqual(self.api_estornar(terceiro.pk).status_code, 404)\n        self.assertFalse(MovimentacaoCaixa.objects.filter(estorno_de=terceiro).exists())\n\n    def test_estorno_exige_login_e_justificativa(self):\n        self.assertEqual(self.api_estornar(self.mov.pk, headers={}).status_code, 401)\n        self.assertEqual(self.api_estornar(self.mov.pk, motivo=\'curto\').status_code, 400)\n        self.assertEqual(MovimentacaoCaixa.objects.count(), 1)\n\n    def test_transferencia_nova_estorna_ambas_as_pontas(self):\n        transfer = self.client.post(\n            \'/contas/transferencia\',\n            json={\n                \'conta_origem_id\': self.conta.pk,\n                \'conta_destino_id\': self.outra.pk,\n                \'valor\': \'12.35\', \'data\': \'2026-08-29\',\n                \'descricao\': \'Transferencia conciliacao\',\n            },\n            headers=self.headers,\n        )\n        self.assertEqual(transfer.status_code, 200, transfer.content)\n        pernas = list(MovimentacaoCaixa.objects.filter(\n            tipo_movimentacao__startswith=\'TRANSFERENCIA_\'\n        ).order_by(\'pk\'))\n        self.assertEqual(len(pernas), 2)\n        self.assertIsNotNone(pernas[0].grupo_transferencia)\n        self.assertEqual(pernas[0].grupo_transferencia, pernas[1].grupo_transferencia)\n        estorno = self.api_estornar(pernas[0].pk)\n        self.assertEqual(estorno.status_code, 200, estorno.content)\n        self.assertEqual(len(estorno.json()[\'estornos\']), 2)\n        self.assertEqual(MovimentacaoCaixa.objects.filter(estorno_de__isnull=False).count(), 2)\n        self.assertEqual(self.api_estornar(pernas[1].pk).status_code, 409)\n        self.conta.refresh_from_db()\n        self.outra.refresh_from_db()\n        self.assertEqual(self.conta.saldo_atual, Decimal(\'74.50\'))\n        self.assertEqual(self.outra.saldo_atual, Decimal(\'40.00\'))\n\n    def test_transferencia_legada_sem_par_nao_estorna(self):\n        legado = MovimentacaoCaixa.objects.create(\n            conta=self.conta, loja_id_externo=self.loja,\n            tipo_movimentacao=\'TRANSFERENCIA_SAIDA\',\n            valor=Decimal(\'1.00\'), descricao=\'Sem id historico\',\n            data_ocorrencia=timezone.now(),\n        )\n        self.assertIsNone(legado.grupo_transferencia)\n        self.assertEqual(self.api_estornar(legado.pk).status_code, 409)\n        self.assertEqual(MovimentacaoCaixa.objects.filter(estorno_de=legado).count(), 0)\n\n    def test_estorno_em_periodo_atual_concluido_fica_bloqueado(self):\n        today = timezone.localdate()\n        FechamentoMensal.objects.create(\n            loja_id_externo=self.loja,\n            mes=today.month, ano=today.year,\n            faturamento_bruto=Decimal(\'100.00\'),\n            total_taxas=Decimal(\'0.00\'),\n            receita_liquida=Decimal(\'100.00\'),\n            total_despesas=Decimal(\'0.00\'),\n            resultado_operacional=Decimal(\'100.00\'),\n            status=\'CONCLUIDO\',\n        )\n        self.assertEqual(self.api_estornar(self.mov.pk).status_code, 409)\n        self.assertEqual(MovimentacaoCaixa.objects.count(), 1)\n\n    def test_falha_no_segundo_estorno_reverte_a_transferencia_inteira(self):\n        transfer = self.client.post(\n            \'/contas/transferencia\',\n            json={\n                \'conta_origem_id\': self.conta.pk,\n                \'conta_destino_id\': self.outra.pk,\n                \'valor\': \'3.00\', \'data\': \'2026-08-29\',\n                \'descricao\': \'Transferencia para rollback\',\n            }, headers=self.headers,\n        )\n        self.assertEqual(transfer.status_code, 200)\n        original = MovimentacaoCaixa.objects.filter(\n            tipo_movimentacao=\'TRANSFERENCIA_SAIDA\',\n        ).first()\n        real_create = MovimentacaoCaixa.objects.create\n        called = 0\n\n        def fail_second(**kwargs):\n            nonlocal called\n            if kwargs.get(\'estorno_de\') is not None:\n                called += 1\n                if called == 2:\n                    raise RuntimeError(\'falha simulada da segunda ponta\')\n            return real_create(**kwargs)\n\n        request = SimpleNamespace(active_loja_id=self.loja, user_id=self.user.pk)\n        with patch.object(MovimentacaoCaixa.objects, \'create\', side_effect=fail_second):\n            with self.assertRaisesRegex(RuntimeError, \'falha simulada\'):\n                estornar_movimentacao(request, original.pk, EstornoMovimentacaoIn(\n                    motivo=\'Reversao de transferencia com falha simulada\',\n                ))\n        self.assertFalse(MovimentacaoCaixa.objects.filter(estorno_de__isnull=False).exists())\n        self.conta.refresh_from_db()\n        self.outra.refresh_from_db()\n        self.assertEqual(self.conta.saldo_atual, Decimal(\'71.50\'))\n        self.assertEqual(self.outra.saldo_atual, Decimal(\'43.00\'))\n'


def once(source, old, new, label):
    n = source.count(old)
    if n != 1:
        raise ValueError(f'{label}: esperada 1 ocorrencia, encontradas {n}')
    return source.replace(old, new, 1)


def patch_model(text):
    text = once(text, 'from decimal import Decimal, InvalidOperation\n',
                'from decimal import Decimal, InvalidOperation\n', 'imports 2A')
    queryset = '''class MovimentoImutavelQuerySet(models.QuerySet):
    """Impede mutacoes em massa que escapariam ao save()/delete()."""

    def update(self, **kwargs):
        raise ValidationError('Movimentacoes financeiras sao imutaveis; utilize estorno.')

    def delete(self):
        raise ValidationError('Movimentacoes financeiras nao podem ser excluidas.')

    def bulk_update(self, objs, fields, batch_size=None):
        raise ValidationError('Atualizacao em massa de movimentacoes proibida.')

    def bulk_create(self, objs, **kwargs):
        raise ValidationError('Criacao em massa proibida: use save() para atualizar o saldo.')


class MovimentacaoCaixa(models.Model):'''
    text = once(text, 'class MovimentacaoCaixa(models.Model):', queryset, 'queryset imutavel')
    text = once(text, "    conta = models.ForeignKey(ContaBancaria, on_delete=models.CASCADE, related_name='movimentacoes')", 
                "    conta = models.ForeignKey(ContaBancaria, on_delete=models.PROTECT, related_name='movimentacoes')", 'FK protegida')
    for old_fk, new_fk, label in (
        (
            "categoria = models.ForeignKey(CategoriaDespesa, on_delete=models.SET_NULL, null=True, blank=True, related_name='movimentacoes_caixa')",
            "categoria = models.ForeignKey(CategoriaDespesa, on_delete=models.PROTECT, null=True, blank=True, related_name='movimentacoes_caixa')",
            'categoria historica protegida',
        ),
        (
            "despesa_vinculada = models.ForeignKey('ContaPagar', on_delete=models.SET_NULL, null=True, blank=True, related_name='pagamentos_caixa')",
            "despesa_vinculada = models.ForeignKey('ContaPagar', on_delete=models.PROTECT, null=True, blank=True, related_name='pagamentos_caixa')",
            'despesa historica protegida',
        ),
    ):
        text = once(text, old_fk, new_fk, label)
    old = '''    loja_id_externo = models.IntegerField(db_index=True)
    criado_por_id = models.IntegerField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Movimentação de Caixa"'''
    new = '''    loja_id_externo = models.IntegerField(db_index=True)
    criado_por_id = models.IntegerField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    estorno_de = models.OneToOneField(
        'self', on_delete=models.PROTECT, null=True, blank=True,
        related_name='estorno',
    )
    motivo_estorno = models.TextField(blank=True)
    grupo_transferencia = models.UUIDField(null=True, blank=True, db_index=True)

    objects = MovimentoImutavelQuerySet.as_manager()

    class Meta:
        verbose_name = "Movimentação de Caixa"'''
    text = once(text, old, new, 'campos do estorno')
    old = '''        # Fase 2A: a insercao e o ajuste de saldo formam uma transacao unica.
        # Atualizacoes/estornos de movimentos existentes serao tratadas na 2B.
        if self.pk is not None:
            return super().save(*args, **kwargs)
'''
    new = '''        # Fase 2B: somente novos movimentos. Um estorno gera outra linha.
        if self.pk is not None:
            raise ValidationError('Movimentacoes ja registradas sao imutaveis; estorne.')
'''
    text = once(text,old,new,'bloqueio de edicao')
    old = '''        using = kwargs.get('using') or router.db_for_write(type(self), instance=self)
        previous_state = (self.pk, self._state.adding, self._state.db)
'''
    new = '''        using = kwargs.get('using') or router.db_for_write(type(self), instance=self)

        if self.estorno_de_id is not None:
            original = type(self).objects.using(using).filter(pk=self.estorno_de_id).first()
            inversos = {
                'ENTRADA': 'SAIDA',
                'SAIDA': 'ENTRADA',
                'TRANSFERENCIA_SAIDA': 'TRANSFERENCIA_ENTRADA',
                'TRANSFERENCIA_ENTRADA': 'TRANSFERENCIA_SAIDA',
            }
            if original is None or original.estorno_de_id is not None:
                raise ValidationError('Movimentacao original invalida para estorno.')
            if not isinstance(self.criado_por_id, int) or self.criado_por_id <= 0:
                raise ValidationError('Estorno precisa identificar o usuario do ERP.')
            if len((self.motivo_estorno or '').strip()) < 10:
                raise ValidationError('O motivo do estorno deve ter ao menos 10 caracteres.')
            if (
                self.tipo_movimentacao != inversos[original.tipo_movimentacao]
                or self.conta_id != original.conta_id
                or self.loja_id_externo != original.loja_id_externo
                or valor != original.valor
                or self.grupo_transferencia != original.grupo_transferencia
            ):
                raise ValidationError('Estorno deve compensar exatamente o original.')
        elif (self.motivo_estorno or '').strip():
            raise ValidationError('Motivo de estorno sem vinculo com movimento original.')

        previous_state = (self.pk, self._state.adding, self._state.db)
'''
    text = once(text,old,new,'validacao de estorno')
    old = '''    def __str__(self):
        sinal = "+" if self.tipo_movimentacao in ['ENTRADA', 'TRANSFERENCIA_ENTRADA'] else "-"'''
    new = '''    def delete(self, *args, **kwargs):
        raise ValidationError('Movimentacoes financeiras nao podem ser excluidas.')

    def __str__(self):
        sinal = "+" if self.tipo_movimentacao in ['ENTRADA', 'TRANSFERENCIA_ENTRADA'] else "-"'''
    text = once(text,old,new,'bloqueio exclusao individual')
    return text


def patch_api(text):
    text = once(text, 'from datetime import date, datetime, time\n',
                'from datetime import date, datetime, time\nfrom uuid import uuid4\n', 'import uuid4')
    old = '''    data_ocorrencia = timezone.make_aware(
        datetime.combine(payload.data, time.min),
        timezone.get_current_timezone(),
    )

    with transaction.atomic():'''
    new = '''    data_ocorrencia = timezone.make_aware(
        datetime.combine(payload.data, time.min),
        timezone.get_current_timezone(),
    )
    grupo_transferencia = uuid4()

    with transaction.atomic():'''
    text = once(text, old, new, 'grupo da transferencia')
    old = '''            criado_por_id=user_id
        )

        MovimentacaoCaixa.objects.create(
            conta=conta_destino,'''
    new = '''            criado_por_id=user_id,
            grupo_transferencia=grupo_transferencia,
        )

        MovimentacaoCaixa.objects.create(
            conta=conta_destino,'''
    text = once(text,old,new,'referencia saida')
    old = '''            criado_por_id=user_id
        )

    return {"success": True, "message": "Transferência realizada com sucesso."}


class ExtratoItemOut(Schema):'''
    new = '''            criado_por_id=user_id,
            grupo_transferencia=grupo_transferencia,
        )

    return {"success": True, "message": "Transferência realizada com sucesso."}


class EstornoMovimentacaoIn(Schema):
    motivo: str


@router.post('/contas/movimentacoes/{movimentacao_id}/estornar', auth=AuthBearer())
def estornar_movimentacao(request, movimentacao_id: int, payload: EstornoMovimentacaoIn):
    """Estorna uma entrada/saida ou AMBAS as pontas de transferencia rastreada.

    Reversoes sao novas movimentacoes; nunca mudam nem removem o original.
    Transferencias legadas sem UUID ficam bloqueadas para estorno automatico.
    """
    loja_id = getattr(request, 'active_loja_id', None)
    user_id = getattr(request, 'user_id', None)
    if type(loja_id) is not int or type(user_id) is not int or user_id <= 0:
        raise HttpError(401, 'Sessao financeira invalida.')
    motivo = (payload.motivo or '').strip()
    if len(motivo) < 10 or len(motivo) > 1000:
        raise HttpError(400, 'Informe motivo de 10 a 1000 caracteres.')

    # O evento compensatorio pertence ao periodo ATUAL, nao retroage o caixa.
    agora = timezone.now()
    _garantir_periodo_caixa_aberto(loja_id, timezone.localdate(agora))

    with transaction.atomic():
        original = MovimentacaoCaixa.objects.filter(
            pk=movimentacao_id, loja_id_externo=loja_id,
            estorno_de__isnull=True,
        ).first()
        if original is None:
            raise Http404('Movimentacao original nao encontrada na loja ativa.')

        if original.tipo_movimentacao.startswith('TRANSFERENCIA_'):
            if original.grupo_transferencia is None:
                raise HttpError(409, 'Transferencia anterior ao rastreamento: estorno automatico indisponivel.')
            originais = list(MovimentacaoCaixa.objects.filter(
                loja_id_externo=loja_id,
                grupo_transferencia=original.grupo_transferencia,
                estorno_de__isnull=True,
            ).order_by('id'))
            if (
                len(originais) != 2
                or {m.tipo_movimentacao for m in originais}
                != {'TRANSFERENCIA_SAIDA', 'TRANSFERENCIA_ENTRADA'}
                or originais[0].valor != originais[1].valor
                or originais[0].conta_id == originais[1].conta_id
            ):
                raise HttpError(409, 'Transferencia sem par consistente; nenhuma alteracao realizada.')
        else:
            if original.grupo_transferencia is not None:
                raise HttpError(409, 'Agrupamento financeiro inconsistente.')
            originais = [original]

        ids = [m.pk for m in originais]
        contas_ids = {m.conta_id for m in originais}
        # Ordem de locks compativel com registrar_transferencia: contas, depois movimentos.
        contas = list(ContaBancaria.objects.select_for_update().filter(
            pk__in=contas_ids, loja_id_externo=loja_id, ativo=True,
        ).order_by('pk'))
        if len(contas) != len(contas_ids):
            raise HttpError(409, 'Existe conta inativa ou indisponivel; estorno nao executado.')
        bloqueados = list(MovimentacaoCaixa.objects.select_for_update().filter(
            pk__in=ids, loja_id_externo=loja_id,
        ).order_by('pk'))
        if len(bloqueados) != len(ids):
            raise HttpError(409, 'Movimentacao indisponivel; nenhuma alteracao realizada.')
        if MovimentacaoCaixa.objects.filter(estorno_de_id__in=ids).exists():
            raise HttpError(409, 'Movimentacao ja estornada; nenhuma duplicacao permitida.')

        inversos = {
            'ENTRADA': 'SAIDA',
            'SAIDA': 'ENTRADA',
            'TRANSFERENCIA_SAIDA': 'TRANSFERENCIA_ENTRADA',
            'TRANSFERENCIA_ENTRADA': 'TRANSFERENCIA_SAIDA',
        }
        compensacoes = []
        for mov in bloqueados:
            compensacoes.append(MovimentacaoCaixa.objects.create(
                conta_id=mov.conta_id,
                tipo_movimentacao=inversos[mov.tipo_movimentacao],
                descricao=f'Estorno do movimento #{mov.pk}',
                valor=mov.valor,
                data_ocorrencia=agora,
                loja_id_externo=loja_id,
                criado_por_id=user_id,
                estorno_de=mov,
                motivo_estorno=motivo,
                grupo_transferencia=mov.grupo_transferencia,
            ))

    return {
        'success': True,
        'originais': ids,
        'estornos': [m.pk for m in compensacoes],
        'message': 'Estorno registrado com rastreabilidade.',
    }


@router.get('/contas/movimentacoes', auth=AuthBearer())
def listar_movimentacoes_caixa(request, conta_id: Optional[int] = None, limit: int = 100):
    """Extrato auditavel restrito a loja ativa (ate 200 movimentos por consulta)."""
    loja_id = getattr(request, 'active_loja_id', None)
    if type(loja_id) is not int:
        raise HttpError(401, 'Sessao financeira invalida.')
    if limit < 1 or limit > 200:
        raise HttpError(400, 'Limite permitido: 1 a 200 movimentos.')
    movimentos = MovimentacaoCaixa.objects.filter(
        loja_id_externo=loja_id,
    ).select_related('conta').order_by('-id')
    if conta_id is not None:
        if not ContaBancaria.objects.filter(pk=conta_id, loja_id_externo=loja_id).exists():
            raise Http404('Conta nao encontrada na loja ativa.')
        movimentos = movimentos.filter(conta_id=conta_id)
    pagina = list(movimentos[:limit])
    ids_estornados = set(MovimentacaoCaixa.objects.filter(
        estorno_de_id__in=[m.pk for m in pagina],
    ).values_list('estorno_de_id', flat=True))
    return [
        {
            'id': m.pk,
            'conta_id': m.conta_id,
            'conta_nome': m.conta.nome,
            'loja_id': m.loja_id_externo,
            'tipo': m.tipo_movimentacao,
            'valor': str(m.valor),
            'descricao': m.descricao,
            'data_ocorrencia': m.data_ocorrencia.isoformat(),
            'criado_em': m.criado_em.isoformat(),
            'criado_por_id': m.criado_por_id,
            'estorno_de_id': m.estorno_de_id,
            'estornado': m.pk in ids_estornados,
            'motivo_estorno': m.motivo_estorno,
            'grupo_transferencia': str(m.grupo_transferencia) if m.grupo_transferencia else None,
        }
        for m in pagina
    ]


class ExtratoItemOut(Schema):'''
    text = once(text,old,new,'endpoint estorno e referencia entrada')
    return text


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true', help='Somente validar as alteracoes')
    args = parser.parse_args()
    try:
        if not (MODEL.exists() and API.exists()):
            raise ValueError('Execute na raiz do repositorio Financeiro.')
        for target in (MIG, TEST):
            if target.exists():
                raise ValueError(f'Arquivo ja existe, abortando: {target.relative_to(ROOT)}')
        patched_model = patch_model(MODEL.read_text(encoding='utf-8'))
        patched_api = patch_api(API.read_text(encoding='utf-8'))
        for f, content in ((MODEL, patched_model), (API, patched_api)):
            compile(content, str(f), 'exec')
        compile(MIGRATION_TEXT, str(MIG), 'exec')
        compile(TEST_TEXT, str(TEST), 'exec')
    except (OSError, ValueError, SyntaxError) as exc:
        print(f'ERRO: {exc}. Nenhum arquivo alterado.', file=sys.stderr)
        return 2
    print('Validacao OK: Fase 2A detectada; 2B aplicavel com migration 0007.')
    if args.check:
        return 0
    MODEL.write_text(patched_model, encoding='utf-8')
    API.write_text(patched_api, encoding='utf-8')
    MIG.write_text(MIGRATION_TEXT, encoding='utf-8')
    TEST.write_text(TEST_TEXT, encoding='utf-8')
    for f in (MODEL, API, MIG, TEST):
        print('Gravado:', f.relative_to(ROOT))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
