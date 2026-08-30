from decimal import Decimal
from django.db.models import Q
from financeiro_core.app.models.entidades import TaxaMaquininha, ContaPagar
from financeiro_core.domain.services import IRepositorioTaxas, TaxaAplicavelDTO, IRepositorioDespesas

class DjangoRepositorioTaxas(IRepositorioTaxas):
    def buscar_taxa(self, loja_id: int, tipo: str, bandeira: str, parcelas: int) -> TaxaAplicavelDTO | None:
        candidatos = TaxaMaquininha.objects.filter(
            perfil__loja_id_externo=loja_id,
            perfil__ativo=True,
            tipo=tipo,
            parcela_inicial__lte=parcelas,
            parcela_final__gte=parcelas
        )

        bandeiras_aplicaveis = Q(bandeira__iexact='GERAL')
        if bandeira:
            bandeiras_aplicaveis |= Q(bandeira__iexact=bandeira)
        candidatos = candidatos.filter(bandeiras_aplicaveis)

        # O DTO de Sales não possui data confiável da transação; portanto não é
        # possível aplicar vigência histórica aqui. Entre perfis ativos aplicáveis,
        # vence deterministicamente o de início mais recente e, no empate, maior ID.
        perfil_id = candidatos.order_by(
            '-perfil__data_inicio_vigencia', '-perfil_id'
        ).values_list('perfil_id', flat=True).first()
        if perfil_id is None:
            return None

        taxas_perfil = candidatos.filter(perfil_id=perfil_id)

        if bandeira:
            taxa = taxas_perfil.filter(bandeira__iexact=bandeira).order_by('id').first()
            if taxa:
                return TaxaAplicavelDTO(taxa.taxa_percentual, taxa.taxa_fixa)

        taxa = taxas_perfil.filter(bandeira__iexact='GERAL').order_by('id').first()
        if taxa:
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
            data_transacao__month=mes,
            data_transacao__year=ano
        ).values('categoria__grupo_contabil').annotate(total=Sum('valor_liquido'))

        return {item['categoria__grupo_contabil']: item['total'] for item in qs if item['categoria__grupo_contabil']}
