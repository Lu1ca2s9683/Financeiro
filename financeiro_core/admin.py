from django.contrib import admin
from .models import (
    ContaBancaria,
    PerfilTaxaCartao,
    TaxaMaquininha,
    ContaPagar,
    CategoriaDespesa,
    Fornecedor,
    FechamentoMensal,
    AuditoriaLog
)

@admin.register(ContaBancaria)
class ContaBancariaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'loja_id_externo', 'saldo_atual', 'ativo')
    list_filter = ('loja_id_externo', 'ativo')

@admin.register(ContaPagar)
class ContaPagarAdmin(admin.ModelAdmin):
    list_display = ('descricao', 'valor_liquido', 'data_vencimento', 'status', 'loja_id_externo')
    list_filter = ('status', 'loja_id_externo', 'data_competencia')
    search_fields = ('descricao', 'numero_documento')

@admin.register(FechamentoMensal)
class FechamentoMensalAdmin(admin.ModelAdmin):
    list_display = ('loja_id_externo', 'mes', 'ano', 'resultado_operacional', 'status')
    list_filter = ('ano', 'mes', 'status')

# Registros simples para cadastros auxiliares
admin.site.register(CategoriaDespesa)
admin.site.register(Fornecedor)
admin.site.register(AuditoriaLog)

class TaxaInline(admin.TabularInline):
    model = TaxaMaquininha
    extra = 1

@admin.register(PerfilTaxaCartao)
class PerfilTaxaCartaoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'loja_id_externo', 'data_inicio_vigencia', 'ativo')
    inlines = [TaxaInline]