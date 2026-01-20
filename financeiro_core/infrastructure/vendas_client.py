from decimal import Decimal
from typing import List
from django.db import connections
from ..domain.services import FaturamentoItemDTO
import re

class VendasClientSQL:
    """
    Cliente SQL otimizado para ler dados do banco legado (vendas_db).
    Nome da tabela identificada: vendas_venda
    """

    def _mapear_tipo_pagamento(self, tipo_raw: str, parcelas: int) -> str:
        """
        Traduz a string do banco legado para o Enum do sistema financeiro.
        Ajustado para lidar com o termo genérico 'CARTAO' encontrado nos logs.
        """
        if not tipo_raw:
            return 'OUTRO'
            
        tipo = tipo_raw.upper().strip()
        
        # Mapeamento baseado em strings comuns de sistemas de varejo
        if 'DEBITO' in tipo or 'DÉBITO' in tipo:
            return 'DEBITO'
        
        # Mapeia 'CREDITO' explícito ou o genérico 'CARTAO' / 'CARTÃO'
        # Assumimos que se está escrito apenas 'CARTAO', trataremos como Crédito
        # para garantir o cálculo de taxas (geralmente mais altas que débito).
        if 'CREDITO' in tipo or 'CRÉDITO' in tipo or 'CARTAO' in tipo or 'CARTÃO' in tipo:
            if parcelas > 1:
                return 'CREDITO_PARCELADO'
            return 'CREDITO_AVISTA'
            
        if 'PIX' in tipo:
            return 'PIX'
            
        if 'DINHEIRO' in tipo:
            return 'DINHEIRO' 
            
        return 'OUTRO'

    def get_faturamento_por_loja(self, loja_id: int, mes: int, ano: int) -> List[FaturamentoItemDTO]:
        
        # SQL Otimizado para vendas_venda
        # REMOVIDO: v.parcelas (coluna não existe no banco legado restaurado)
        query = """
            WITH vendas_validas AS (
                SELECT v.id
                FROM vendas_venda v
                LEFT JOIN vendas_estorno e ON v.id = e.venda_id
                WHERE v.loja_id = %s
                  AND EXTRACT(MONTH FROM v.data_venda) = %s
                  AND EXTRACT(YEAR FROM v.data_venda) = %s
                  AND v.ignorar_faturamento = FALSE
                  AND e.id IS NULL
            ),
            transacoes_unificadas AS (
                -- Pagamento 1
                SELECT 
                    v.forma_pagamento as forma,
                    COALESCE(v.subtipo_pagamento_1, 'GERAL') as bandeira,
                    v.valor_pagamento_1 as valor
                FROM vendas_venda v
                JOIN vendas_validas vv ON v.id = vv.id
                WHERE v.valor_pagamento_1 > 0

                UNION ALL

                -- Pagamento 2
                SELECT 
                    v.forma_pagamento_2 as forma,
                    COALESCE(v.subtipo_pagamento_2, 'GERAL') as bandeira,
                    v.valor_pagamento_2 as valor
                FROM vendas_venda v
                JOIN vendas_validas vv ON v.id = vv.id
                WHERE v.valor_pagamento_2 > 0
            )
            SELECT 
                forma,
                bandeira,
                SUM(valor) as total
            FROM transacoes_unificadas
            GROUP BY forma, bandeira
        """
        
        resultado_dtos = []
        
        try:
            with connections['vendas_db'].cursor() as cursor:
                cursor.execute(query, [loja_id, mes, ano])
                rows = cursor.fetchall()
                
                for row in rows:
                    tipo_raw = row[0] if row[0] else ''
                    bandeira_raw = row[1] if row[1] else 'GERAL'
                    valor = row[2] if row[2] else Decimal('0.00')
                    
                    # Assumimos 1 parcela por padrão já que a coluna não existe
                    parcelas = 1 
                    
                    # Usa o mapeador atualizado
                    tipo_mapeado = self._mapear_tipo_pagamento(tipo_raw, parcelas)
                    
                    # Normaliza bandeira
                    bandeira_normalizada = bandeira_raw.upper().strip()
                    
                    dto = FaturamentoItemDTO(
                        tipo_pagamento=tipo_mapeado,
                        bandeira=bandeira_normalizada,
                        parcelas=parcelas,
                        valor_bruto=Decimal(valor)
                    )
                    resultado_dtos.append(dto)
                    
                    print(f"DEBUG SQL: Raw='{tipo_raw}' -> Mapeado='{tipo_mapeado}' | Valor={valor}")

        except Exception as e:
            print(f"Erro ao consultar banco vendas_db: {e}")
            raise e

        return resultado_dtos

class VendasAPIClientMock:
    """
    Mock mantido para compatibilidade.
    """
    def get_faturamento_por_loja(self, loja_id: int, mes: int, ano: int) -> List[FaturamentoItemDTO]:
        return []