from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Optional
from dataclasses import dataclass

# --- Value Objects / DTOs (Data Transfer Objects) ---

@dataclass
class FaturamentoItemDTO:
    """
    Representa um grupo de vendas vindo da API externa (sistema de vendas).
    Usado para trafegar dados brutos entre a camada de Infra e Domínio.
    """
    tipo_pagamento: str  # Ex: CREDITO_AVISTA, DEBITO, PIX
    bandeira: str        # Ex: VISA, MASTER, GERAL
    parcelas: int        # Quantidade de parcelas
    valor_bruto: Decimal # Valor total vendido nessa modalidade

@dataclass
class TaxaAplicavelDTO:
    """Representa a taxa configurada no sistema para um tipo de transação."""
    percentual: Decimal
    valor_fixo: Decimal

# --- Interfaces (Adapters) ---

class IRepositorioTaxas:
    def buscar_taxa(self, loja_id: int, tipo: str, bandeira: str, parcelas: int) -> Optional[TaxaAplicavelDTO]:
        raise NotImplementedError

class IRepositorioDespesas:
    def somar_despesas_competencia(self, loja_id: int, mes: int, ano: int) -> Decimal:
        raise NotImplementedError

    def agrupar_despesas_por_grupo_contabil(self, loja_id: int, mes: int, ano: int) -> Dict[str, Decimal]:
        """Retorna as despesas agrupadas por GRUPO_CONTABIL."""
        raise NotImplementedError

# --- Serviços de Domínio ---

class CalculadoraFinanceira:
    """
    Responsável exclusivamente pela matemática financeira de taxas.
    Utiliza arredondamento padrão bancário (ROUND_HALF_UP).
    """

    _TIPOS_TAXA_APLICAVEL = {
        'CREDITO_AVISTA': 'CREDITO_AVISTA',
        'CREDITO_PARCELADO': 'CREDITO_PARCELADO',
        'DEBITO': 'DEBITO',
        'PIX': 'PIX',
        'PIX_MAQUINA': 'PIX',
    }
    _TIPOS_PIX = {'PIX', 'PIX_CONTA', 'PIX_MAQUINA'}
    _TIPOS_CARTAO = {
        'DEBITO',
        'CREDITO_AVISTA',
        'CREDITO_PARCELADO',
        'CREDITO_NAO_IDENTIFICADO',
        'CARTAO_NAO_IDENTIFICADO',
    }

    @staticmethod
    def _arredondar(valor: Decimal) -> Decimal:
        """Helper para garantir 2 casas decimais em tudo."""
        return valor.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    @staticmethod
    def _tipo_taxa_aplicavel(tipo_pagamento: str) -> Optional[str]:
        """Retorna o tipo de taxa apenas quando a modalidade é comprovada."""
        return CalculadoraFinanceira._TIPOS_TAXA_APLICAVEL.get(tipo_pagamento)
    
    @staticmethod
    def calcular_liquido_vendas(
        itens_venda: List[FaturamentoItemDTO], 
        repositorio_taxas: IRepositorioTaxas,
        loja_id: int
    ) -> Dict[str, Decimal]:
        """
        Calcula o total de taxas e o valor líquido a receber.
        """
        total_bruto = Decimal('0.00')
        total_taxas = Decimal('0.00')
        
        for item in itens_venda:
            valor_item = item.valor_bruto
            total_bruto += valor_item
            
            tipo_taxa = CalculadoraFinanceira._tipo_taxa_aplicavel(
                item.tipo_pagamento
            )
            taxa = None
            if tipo_taxa:
                taxa = repositorio_taxas.buscar_taxa(
                    loja_id,
                    tipo_taxa,
                    item.bandeira,
                    item.parcelas,
                )
            
            if taxa:
                # O contrato atual representa um agregado por forma/bandeira. Sem uma
                # contagem de ocorrências comprovada no Sales, a taxa fixa permanece
                # aplicada uma vez por DTO agregado.
                percentual_decimal = taxa.percentual / Decimal('100')
                custo_item = (valor_item * percentual_decimal) + taxa.valor_fixo
                
                # Importante: Arredondamos item a item para evitar acumulo de dízimas
                total_taxas += CalculadoraFinanceira._arredondar(custo_item)
            else:
                pass
                
        # Garante totais arredondados
        total_bruto = CalculadoraFinanceira._arredondar(total_bruto)
        total_taxas = CalculadoraFinanceira._arredondar(total_taxas)

        # Cada item entra em exatamente uma categoria, inclusive formas desconhecidas.
        total_dinheiro = Decimal('0.00')
        total_cartao = Decimal('0.00')
        total_pix = Decimal('0.00')
        total_outros = Decimal('0.00')
        for item in itens_venda:
            if item.tipo_pagamento == 'DINHEIRO':
                total_dinheiro += item.valor_bruto
            elif item.tipo_pagamento in CalculadoraFinanceira._TIPOS_PIX:
                total_pix += item.valor_bruto
            elif item.tipo_pagamento in CalculadoraFinanceira._TIPOS_CARTAO:
                total_cartao += item.valor_bruto
            else:
                total_outros += item.valor_bruto

        return {
            "total_bruto": total_bruto,
            "total_taxas": total_taxas,
            "total_dinheiro": CalculadoraFinanceira._arredondar(total_dinheiro),
            "total_cartao": CalculadoraFinanceira._arredondar(total_cartao),
            "total_pix": CalculadoraFinanceira._arredondar(total_pix),
            "total_outros": CalculadoraFinanceira._arredondar(total_outros),
        }
