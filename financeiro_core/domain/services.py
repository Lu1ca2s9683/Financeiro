from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from datetime import date

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

@dataclass
class ResultadoFechamentoDTO:
    """Objeto de transferência com o resultado final do cálculo de fechamento."""
    faturamento_bruto: Decimal
    total_taxas: Decimal
    receita_liquida: Decimal
    despesas_totais: Decimal
    resultado_final: Decimal
    snapshot_dados: Dict[str, Any] # Dicionário para auditoria

# --- Interfaces (Adapters) ---

class IRepositorioTaxas:
    def buscar_taxa(self, loja_id: int, tipo: str, bandeira: str, parcelas: int) -> Optional[TaxaAplicavelDTO]:
        raise NotImplementedError

class IRepositorioDespesas:
    def somar_despesas_competencia(self, loja_id: int, mes: int, ano: int) -> Decimal:
        raise NotImplementedError

# --- Serviços de Domínio ---

class CalculadoraFinanceira:
    """
    Responsável exclusivamente pela matemática financeira de taxas.
    Utiliza arredondamento padrão bancário (ROUND_HALF_UP).
    """
    
    @staticmethod
    def _arredondar(valor: Decimal) -> Decimal:
        """Helper para garantir 2 casas decimais em tudo."""
        return valor.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
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
            
            # Busca a taxa aplicável para este item específico
            taxa = repositorio_taxas.buscar_taxa(
                loja_id, item.tipo_pagamento, item.bandeira, item.parcelas
            )
            
            if taxa:
                # Cálculo: (Valor * % / 100) + Taxa Fixa
                percentual_decimal = taxa.percentual / Decimal('100')
                custo_item = (valor_item * percentual_decimal) + taxa.valor_fixo
                
                # Importante: Arredondamos item a item para evitar acumulo de dízimas
                total_taxas += CalculadoraFinanceira._arredondar(custo_item)
            else:
                pass
                
        # Garante totais arredondados
        total_bruto = CalculadoraFinanceira._arredondar(total_bruto)
        total_taxas = CalculadoraFinanceira._arredondar(total_taxas)
        receita_liquida = total_bruto - total_taxas
        
        return {
            "total_bruto": total_bruto,
            "total_taxas": total_taxas,
            "receita_liquida": receita_liquida
        }

class ProcessadorFechamento:
    """
    Orquestrador do processo de fechamento mensal.
    """
    
    def __init__(self, repo_taxas: IRepositorioTaxas, repo_despesas: IRepositorioDespesas):
        self.repo_taxas = repo_taxas
        self.repo_despesas = repo_despesas

    def executar_fechamento(
        self, 
        loja_id: int, 
        mes: int, 
        ano: int, 
        dados_vendas_api: List[FaturamentoItemDTO]
    ) -> ResultadoFechamentoDTO:
        
        # 1. Calcular Receita Líquida (Vendas - Taxas)
        calculo_receita = CalculadoraFinanceira.calcular_liquido_vendas(
            dados_vendas_api, self.repo_taxas, loja_id
        )
        
        # 2. Obter Total de Despesas (Regime de Competência)
        despesas_raw = self.repo_despesas.somar_despesas_competencia(loja_id, mes, ano)
        total_despesas = CalculadoraFinanceira._arredondar(despesas_raw)
        
        # 3. Calcular Resultado Operacional
        resultado_operacional = calculo_receita['receita_liquida'] - total_despesas
        
        # 4. Preparar Snapshot para Auditoria
        snapshot = {
            "vendas_brutas_api": [
                {
                    "tipo": item.tipo_pagamento, 
                    "valor": float(CalculadoraFinanceira._arredondar(item.valor_bruto)),
                    "bandeira": item.bandeira
                } for item in dados_vendas_api
            ],
            "calculo_receita": {k: float(v) for k, v in calculo_receita.items()},
            "data_processamento": str(date.today())
        }
        
        return ResultadoFechamentoDTO(
            faturamento_bruto=calculo_receita['total_bruto'],
            total_taxas=calculo_receita['total_taxas'],
            receita_liquida=calculo_receita['receita_liquida'],
            despesas_totais=total_despesas,
            resultado_final=resultado_operacional,
            snapshot_dados=snapshot
        )