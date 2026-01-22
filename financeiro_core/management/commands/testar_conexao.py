from django.core.management.base import BaseCommand
from django.db import connections
from django.db.utils import OperationalError
from django.conf import settings
import os

class Command(BaseCommand):
    help = 'Testa a conexão com o banco de dados de Vendas configurado'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('--- INICIANDO TESTE DE CONEXÃO ---'))
        
        # 1. Verifica qual configuração está sendo usada
        db_config = settings.DATABASES.get('vendas_db', {})
        db_name = db_config.get('NAME', 'Desconhecido')
        db_host = db_config.get('HOST', 'Desconhecido')
        
        if os.environ.get('VENDAS_DATABASE_URL'):
            self.stdout.write("Modo: Conexão Externa Dedicada (Variável encontrada)")
        else:
            self.stdout.write("Modo: Conexão Compartilhada/Fallback (Usando credenciais do banco principal)")

        self.stdout.write(f"Alvo: Banco '{db_name}' em '{db_host}'")

        # 2. Tenta conectar
        try:
            db_conn = connections['vendas_db']
            c = db_conn.cursor()
            self.stdout.write(self.style.SUCCESS('1. Conexão TCP estabelecida com sucesso!'))
            
            c.execute("SELECT count(*) FROM vendas_venda") # Tenta ler a tabela
            row = c.fetchone()
            
            self.stdout.write(self.style.SUCCESS(f'2. Query executada com sucesso!'))
            self.stdout.write(self.style.SUCCESS(f'3. Total de vendas encontradas: {row[0]}'))
            
        except OperationalError as e:
            self.stdout.write(self.style.ERROR(f'ERRO DE CONEXÃO: {e}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'ERRO GENÉRICO: {e}'))