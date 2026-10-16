"""Fase 2B: vinculo de estorno e identificador de transferencias futuras.

A migracao NAO estorna nem recalcula nenhum saldo historico.
Transferencias antigas ficam com grupo_transferencia=NULL e nao
podem ser estornadas automaticamente por falta de pareamento seguro.
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('financeiro_core', '0006_contapagar_descricao_original_extrato_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='movimentacaocaixa',
            name='conta',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='movimentacoes',
                to='financeiro_core.contabancaria',
            ),
        ),
        migrations.AlterField(
            model_name='movimentacaocaixa',
            name='categoria',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='movimentacoes_caixa',
                to='financeiro_core.categoriadespesa',
            ),
        ),
        migrations.AlterField(
            model_name='movimentacaocaixa',
            name='despesa_vinculada',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='pagamentos_caixa',
                to='financeiro_core.contapagar',
            ),
        ),
        migrations.AddField(
            model_name='movimentacaocaixa',
            name='estorno_de',
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='estorno',
                to='financeiro_core.movimentacaocaixa',
            ),
        ),
        migrations.AddField(
            model_name='movimentacaocaixa',
            name='motivo_estorno',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='movimentacaocaixa',
            name='grupo_transferencia',
            field=models.UUIDField(blank=True, db_index=True, null=True),
        ),
    ]
