from decimal import Decimal
from financeiro_core.app.models.entidades import TaxaMaquininha, ContaPagar
from financeiro_core.domain.services import IRepositorioTaxas, TaxaAplicavelDTO, IRepositorioDespesas

class DjangoRepositorioTaxas(IRepositorioTaxas):
    def buscar_taxa(self, loja_id: int, tipo: str, bandeira: str, parcelas: int) -> TaxaAplicavelDTO | None:
        qs = TaxaMaquininha.objects.filter(
            perfil__loja_id_externo=loja_id,
            perfil__ativo=True,
            tipo=tipo,
            parcela_inicial__lte=parcelas,
            parcela_final__gte=parcelas
        )

        if bandeira:
            qs_bandeira = qs.filter(bandeira__iexact=bandeira)
            if qs_bandeira.exists():
                taxa = qs_bandeira.first()
                return TaxaAplicavelDTO(taxa.taxa_percentual, taxa.taxa_fixa)

        qs_geral = qs.filter(bandeira='GERAL')
        if qs_geral.exists():
            taxa = qs_geral.first()
            return TaxaAplicavelDTO(taxa.taxa_percentual, taxa.taxa_fixa)

        return None

class DjangoRepositorioDespesas(IRepositorioDespesas):
    """Soma despesas para o fechamento."""
    def somar_despesas_competencia(self, loja_id, mes, ano):
        from django.db.models import Sum
        val = ContaPagar.objects.filter(
            loja_id_externo=loja_id,
            data_transacao__month=mes,
            data_transacao__year=ano
        ).aggregate(Sum('valor_liquido'))['valor_liquido__sum']
        return val or Decimal('0.00')

    def agrupar_despesas_por_grupo_contabil(self, loja_id, mes, ano):
        from django.db.models import Sum
        qs = ContaPagar.objects.filter(
            loja_id_externo=loja_id,
            data_competencia__month=mes,
            data_transacao__year=ano
        ).values('categoria__grupo_contabil').annotate(total=Sum('valor_liquido'))

        return {item['categoria__grupo_contabil']: item['total'] for item in qs if item['categoria__grupo_contabil']}
