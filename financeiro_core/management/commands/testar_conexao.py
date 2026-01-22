from django.core.management.base import BaseCommand
from django.db import connections
from django.db.utils import OperationalError
import os

class Command(BaseCommand):
    help = 'Testa a conexão com o banco de dados de Vendas configurado'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('--- INICIANDO TESTE DE CONEXÃO ---'))
        
        # 1. Verifica se a variável existe
        url = os.environ.get('VENDAS_DATABASE_URL')
        if not url:
            self.stdout.write(self.style.ERROR('ERRO: Variável VENDAS_DATABASE_URL não encontrada no ambiente!'))
            return

        # Mascara a senha para mostrar no log
        url_mascarada = url.split('@')[1] if '@' in url else 'URL INVÁLIDA'
        self.stdout.write(f"URL Configurada (host): ...@{url_mascarada}")

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