import logging
from decimal import Decimal
from typing import List

from django.db import connections

from ..domain.services import FaturamentoItemDTO


logger = logging.getLogger(__name__)

class VendasClientSQL:
    """
    Cliente SQL otimizado para ler dados do banco legado (vendas).
    Nome da tabela identificada: vendas_venda
    """

    def _mapear_tipo_pagamento(
        self,
        forma_raw: str | None,
        subtipo_raw: str | None,
    ) -> str:
        """Mapeia a família e a modalidade comprovadas pelo Sales."""
        forma = (forma_raw or '').upper().strip()
        subtipo = (subtipo_raw or '').upper().strip()

        if forma == 'DINHEIRO':
            return 'DINHEIRO'
        if forma == 'PIX_CONTA':
            return 'PIX_CONTA'
        if forma == 'VOUCHER':
            return 'VOUCHER'
        if forma == 'CARTAO':
            return {
                'DEBITO': 'DEBITO',
                'CREDITO': 'CREDITO_NAO_IDENTIFICADO',
                'PIX_MAQUINA': 'PIX_MAQUINA',
            }.get(subtipo, 'CARTAO_NAO_IDENTIFICADO')
        return 'OUTRO'

    def get_faturamento_por_loja(self, loja_id: int, mes: int, ano: int) -> List[FaturamentoItemDTO]:
        
        # SQL Otimizado para vendas_venda: Pagamentos Múltiplos (Caixa-based)
        query = """
            WITH vendas_validas AS (
                SELECT v.id
                FROM vendas_venda v
                INNER JOIN vendas_caixadiario c ON v.caixa_id = c.id
                LEFT JOIN vendas_estorno e ON v.id = e.venda_id
                WHERE v.loja_id = %s
                  AND EXTRACT(MONTH FROM c.data) = %s
                  AND EXTRACT(YEAR FROM c.data) = %s
                  AND v.ignorar_faturamento = FALSE
                  AND e.id IS NULL
            ),
            transacoes_unificadas AS (
                -- Pagamento 1
                SELECT 
                    v.forma_pagamento as forma,
                    v.subtipo_pagamento_1 as subtipo,
                    v.valor_pagamento_1 as valor
                FROM vendas_venda v
                JOIN vendas_validas vv ON v.id = vv.id
                WHERE v.valor_pagamento_1 > 0

                UNION ALL

                -- Pagamento 2
                SELECT
                    v.forma_pagamento_2 as forma,
                    v.subtipo_pagamento_2 as subtipo,
                    v.valor_pagamento_2 as valor
                FROM vendas_venda v
                JOIN vendas_validas vv ON v.id = vv.id
                WHERE v.valor_pagamento_2 > 0
            )
            SELECT 
                forma,
                subtipo,
                SUM(valor) as total
            FROM transacoes_unificadas
            GROUP BY forma, subtipo
        """
        
        resultado_dtos = []
        
        try:
            with connections['vendas'].cursor() as cursor:
                cursor.execute(query, [loja_id, mes, ano])
                rows = cursor.fetchall()
                
                for row in rows:
                    forma_raw = row[0] if row[0] else ''
                    subtipo_raw = row[1] if row[1] else ''
                    valor = row[2] if row[2] else Decimal('0.00')
                    
                    # Compatibilidade do DTO: o Sales não fornece parcelas. O mapper
                    # não usa este placeholder para inferir modalidade de crédito.
                    parcelas = 1
                    tipo_mapeado = self._mapear_tipo_pagamento(
                        forma_raw,
                        subtipo_raw,
                    )
                    
                    dto = FaturamentoItemDTO(
                        tipo_pagamento=tipo_mapeado,
                        # O Venda atual não persiste a bandeira do cartão.
                        bandeira='GERAL',
                        parcelas=parcelas,
                        valor_bruto=Decimal(valor)
                    )
                    resultado_dtos.append(dto)

                    logger.debug(
                        "Pagamento Sales agregado: forma=%s subtipo=%s tipo=%s valor=%s",
                        forma_raw,
                        subtipo_raw,
                        tipo_mapeado,
                        valor,
                    )

        except Exception:
            logger.exception("Erro ao consultar banco vendas")
            raise

        return resultado_dtos

    def get_vendedores_ativos_por_loja(self, loja_id: int) -> list[dict]:
        """Retorna a dimensão pública e somente leitura de vendedores ativos."""
        query = """
            SELECT id, nome, loja_id
            FROM vendas_vendedor
            WHERE loja_id = %s
              AND ativo = TRUE
            ORDER BY nome, id
        """
        try:
            with connections['vendas'].cursor() as cursor:
                cursor.execute(query, [loja_id])
                return [
                    {"id": row[0], "nome": row[1], "loja_id": row[2]}
                    for row in cursor.fetchall()
                ]
        except Exception:
            logger.exception("Erro ao consultar vendedores ativos no banco vendas")
            raise

class VendasAPIClientMock:
    """
    Mock mantido para compatibilidade.
    """
    def get_faturamento_por_loja(self, loja_id: int, mes: int, ano: int) -> List[FaturamentoItemDTO]:
        return []
