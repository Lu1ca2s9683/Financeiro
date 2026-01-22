from django.core.management.base import BaseCommand
from django.db import connections
from datetime import date

class Command(BaseCommand):
    help = 'Verifica se existem vendas para uma loja e período específicos'

    def handle(self, *args, **options):
        # CONFIGURAÇÃO DO TESTE
        LOJA_ID = 1
        MES = 12
        ANO = 2025
        
        self.stdout.write(f"--- DIAGNÓSTICO DE VENDAS (Loja {LOJA_ID} - {MES}/{ANO}) ---")

        query = """
            SELECT count(*), SUM(valor_pagamento_1)
            FROM vendas_venda 
            WHERE loja_id = %s 
            AND EXTRACT(MONTH FROM data_venda) = %s 
            AND EXTRACT(YEAR FROM data_venda) = %s
        """

        try:
            with connections['vendas_db'].cursor() as cursor:
                # 1. Teste Específico (Loja/Mês/Ano)
                cursor.execute(query, [LOJA_ID, MES, ANO])
                row = cursor.fetchone()
                qtd = row[0]
                total = row[1] or 0
                
                self.stdout.write(f"Resultado Filtro Exato:")
                self.stdout.write(f" - Quantidade de Vendas: {qtd}")
                self.stdout.write(f" - Total Bruto: R$ {total}")

                if qtd > 0:
                    self.stdout.write(self.style.SUCCESS("✅ SUCESSO: O sistema consegue ver as vendas!"))
                else:
                    self.stdout.write(self.style.WARNING("⚠️ ATENÇÃO: Nenhuma venda encontrada para este filtro."))
                    
                    # 2. Teste Genérico (Para ajudar a descobrir onde estão os dados)
                    self.stdout.write("\n--- Tentando encontrar QUALQUER venda desta loja ---")
                    cursor.execute("SELECT MIN(data_venda), MAX(data_venda) FROM vendas_venda WHERE loja_id = %s", [LOJA_ID])
                    datas = cursor.fetchone()
                    self.stdout.write(f"A Loja {LOJA_ID} tem vendas de {datas[0]} até {datas[1]}")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Erro ao executar query: {e}"))