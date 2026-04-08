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
    """Objeto de transferência com o resultado final do cálculo de fechamento e DRE."""
    faturamento_bruto: Decimal
    total_dinheiro: Decimal
    total_cartao: Decimal
    total_pix: Decimal

    impostos: Decimal
    receita_liquida: Decimal
    custos_produtos: Decimal
    lucro_bruto: Decimal
    despesas_operacionais: Decimal
    resultado_operacional: Decimal
    total_taxas: Decimal # Mantido para compatibilidade, mas compõe a despesa financeira
    despesas_financeiras: Decimal
    lucro_liquido: Decimal

    snapshot_dados: Dict[str, Any] # Dicionário para auditoria

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
        
        # Sumariza subtotais de pagamento
        total_dinheiro = sum(i.valor_bruto for i in itens_venda if i.tipo_pagamento == 'DINHEIRO')
        total_cartao = sum(i.valor_bruto for i in itens_venda if 'CREDITO' in i.tipo_pagamento or 'DEBITO' in i.tipo_pagamento or 'CARTAO' in i.tipo_pagamento)
        total_pix = sum(i.valor_bruto for i in itens_venda if i.tipo_pagamento == 'PIX')

        return {
            "total_bruto": total_bruto,
            "total_taxas": total_taxas,
            "total_dinheiro": CalculadoraFinanceira._arredondar(total_dinheiro),
            "total_cartao": CalculadoraFinanceira._arredondar(total_cartao),
            "total_pix": CalculadoraFinanceira._arredondar(total_pix)
        }

class ProcessadorFechamento:
    """
    Orquestrador do processo de fechamento mensal.
    Agora reflete um DRE estruturado em Cascata.
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
        
        # 1. Calcular Vendas Base e Taxas de Cartão
        vendas = CalculadoraFinanceira.calcular_liquido_vendas(
            dados_vendas_api, self.repo_taxas, loja_id
        )
        
        faturamento_bruto = vendas['total_bruto']
        total_taxas_cartao = vendas['total_taxas']

        # 2. Obter Despesas por Grupo Contábil
        grupos_despesa = self.repo_despesas.agrupar_despesas_por_grupo_contabil(loja_id, mes, ano)

        impostos = grupos_despesa.get('IMPOSTOS', Decimal('0.00'))
        custos = grupos_despesa.get('CUSTOS', Decimal('0.00'))
        pessoal = grupos_despesa.get('PESSOAL', Decimal('0.00'))
        adm = grupos_despesa.get('ADMINISTRATIVA', Decimal('0.00'))
        mkt = grupos_despesa.get('MARKETING', Decimal('0.00'))
        fin_outras = grupos_despesa.get('FINANCEIRA', Decimal('0.00'))

        # 3. Cascata DRE
        # Receita Bruta -> (-) Impostos = Receita Líquida
        receita_liquida = faturamento_bruto - impostos

        # Receita Líquida -> (-) Custos = Lucro Bruto
        lucro_bruto = receita_liquida - custos

        # Lucro Bruto -> (-) Despesas Operacionais = Resultado Operacional
        despesas_op = pessoal + adm + mkt
        resultado_operacional = lucro_bruto - despesas_op
        
        # Resultado Operacional -> (-) Despesas Financeiras = Lucro Líquido
        despesas_financeiras = fin_outras + total_taxas_cartao
        lucro_liquido = resultado_operacional - despesas_financeiras
        
        # Snapshot Auditoria
        snapshot = {
            "vendas_brutas_api": [
                {
                    "tipo": item.tipo_pagamento, 
                    "valor": float(CalculadoraFinanceira._arredondar(item.valor_bruto)),
                    "bandeira": item.bandeira
                } for item in dados_vendas_api
            ],
            "calculo_receita": {k: float(v) for k, v in vendas.items()},
            "dre": {
                "faturamento_bruto": float(faturamento_bruto),
                "impostos": float(impostos),
                "receita_liquida": float(receita_liquida),
                "custos": float(custos),
                "lucro_bruto": float(lucro_bruto),
                "despesas_op": float(despesas_op),
                "resultado_operacional": float(resultado_operacional),
                "despesas_financeiras": float(despesas_financeiras),
                "lucro_liquido": float(lucro_liquido),
            },
            "data_processamento": str(date.today())
        }
        
        return ResultadoFechamentoDTO(
            faturamento_bruto=faturamento_bruto,
            total_dinheiro=vendas['total_dinheiro'],
            total_cartao=vendas['total_cartao'],
            total_pix=vendas['total_pix'],
            impostos=impostos,
            receita_liquida=receita_liquida,
            custos_produtos=custos,
            lucro_bruto=lucro_bruto,
            despesas_operacionais=despesas_op,
            resultado_operacional=resultado_operacional,
            total_taxas=total_taxas_cartao,
            despesas_financeiras=despesas_financeiras,
            lucro_liquido=lucro_liquido,
            snapshot_dados=snapshot
        )