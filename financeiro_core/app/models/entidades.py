from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal

# --- Cadastros de Apoio ---

class CategoriaDespesa(models.Model):
    """
    Categorização de despesas para relatórios financeiros.
    """
    nome = models.CharField(max_length=100)
    codigo_contabil = models.CharField(max_length=20, blank=True, null=True)
    ativa = models.BooleanField(default=True)

    def __str__(self):
        return self.nome

class Fornecedor(models.Model):
    """Entidade recebedora de pagamentos."""
    razao_social = models.CharField(max_length=200)
    cnpj_cpf = models.CharField(max_length=18, unique=True)
    
    def __str__(self):
        return self.razao_social

# --- Entidades Principais ---

class ContaBancaria(models.Model):
    nome = models.CharField(max_length=100, help_text="Ex: Bradesco Loja Centro")
    banco_codigo = models.CharField(max_length=10, blank=True)
    agencia = models.CharField(max_length=20, blank=True)
    conta = models.CharField(max_length=30, blank=True)
    loja_id_externo = models.IntegerField(verbose_name="ID da Loja (Sistema Vendas)", db_index=True)
    saldo_atual = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Conta Bancária"
        verbose_name_plural = "Contas Bancárias"

    def __str__(self):
        return f"{self.nome} (Loja {self.loja_id_externo})"

class PerfilTaxaCartao(models.Model):
    nome = models.CharField(max_length=100, help_text="Ex: Contrato Stone 2024")
    loja_id_externo = models.IntegerField(verbose_name="ID da Loja (Sistema Vendas)")
    data_inicio_vigencia = models.DateField()
    data_fim_vigencia = models.DateField(null=True, blank=True)
    ativo = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.nome} - Início: {self.data_inicio_vigencia}"

class TaxaMaquininha(models.Model):
    TIPO_CARTAO = [
        ('DEBITO', 'Débito'),
        ('CREDITO_AVISTA', 'Crédito à Vista'),
        ('CREDITO_PARCELADO', 'Crédito Parcelado'),
        ('PIX', 'Pix (Maquininha)'),
    ]
    
    perfil = models.ForeignKey(PerfilTaxaCartao, on_delete=models.CASCADE, related_name='taxas')
    tipo = models.CharField(max_length=20, choices=TIPO_CARTAO)
    bandeira = models.CharField(max_length=20, default='GERAL', help_text="Visa, Master, Elo ou GERAL")
    parcela_inicial = models.IntegerField(default=1)
    parcela_final = models.IntegerField(default=1)
    
    taxa_percentual = models.DecimalField(max_digits=5, decimal_places=2, help_text="Ex: 1.50 para 1.5%")
    taxa_fixa = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    dias_para_recebimento = models.IntegerField(default=1)

    class Meta:
        unique_together = ('perfil', 'tipo', 'bandeira', 'parcela_inicial', 'parcela_final')

class ContaPagar(models.Model):
    STATUS_CHOICES = [
        ('PREVISTO', 'Previsto'),
        ('PAGO', 'Pago'),
        ('ATRASADO', 'Atrasado'),
        ('CANCELADO', 'Cancelado'),
    ]

    descricao = models.CharField(max_length=255)
    loja_id_externo = models.IntegerField(verbose_name="ID da Loja", db_index=True)
    fornecedor = models.ForeignKey(Fornecedor, on_delete=models.PROTECT, null=True, blank=True)
    categoria = models.ForeignKey(CategoriaDespesa, on_delete=models.PROTECT)
    
    valor_bruto = models.DecimalField(max_digits=12, decimal_places=2)
    valor_desconto = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    valor_acrescimo = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    valor_liquido = models.DecimalField(max_digits=12, decimal_places=2, editable=False)
    
    data_competencia = models.DateField(help_text="Mês de referência (Regime de Competência)")
    data_vencimento = models.DateField()
    data_pagamento = models.DateField(null=True, blank=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PREVISTO')
    conta_origem = models.ForeignKey(ContaBancaria, on_delete=models.PROTECT, null=True, blank=True)
    
    criado_em = models.DateTimeField(auto_now_add=True)
    criado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    class Meta:
        verbose_name = "Conta a Pagar"
        verbose_name_plural = "Contas a Pagar"

    def save(self, *args, **kwargs):
        self.valor_liquido = self.valor_bruto - self.valor_desconto + self.valor_acrescimo
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.descricao} - R$ {self.valor_liquido}"

class FechamentoMensal(models.Model):
    loja_id_externo = models.IntegerField(db_index=True)
    mes = models.IntegerField()
    ano = models.IntegerField()
    
    faturamento_bruto = models.DecimalField(max_digits=15, decimal_places=2)
    total_taxas = models.DecimalField(max_digits=12, decimal_places=2)
    receita_liquida = models.DecimalField(max_digits=15, decimal_places=2)
    
    total_despesas = models.DecimalField(max_digits=15, decimal_places=2)
    resultado_operacional = models.DecimalField(max_digits=15, decimal_places=2)
    
    status = models.CharField(max_length=20, choices=[('ABERTO', 'Aberto'), ('CONCLUIDO', 'Concluído')], default='ABERTO')
    data_fechamento = models.DateTimeField(auto_now=True)
    
    dados_auditoria_snapshot = models.JSONField(null=True, blank=True)

    class Meta:
        unique_together = ('loja_id_externo', 'mes', 'ano')

class AuditoriaLog(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    acao = models.CharField(max_length=100)
    tabela_afetada = models.CharField(max_length=100)
    registro_id = models.IntegerField()
    dados_anteriores = models.JSONField(null=True, blank=True)
    dados_novos = models.JSONField(null=True, blank=True)
    data_hora = models.DateTimeField(auto_now_add=True)