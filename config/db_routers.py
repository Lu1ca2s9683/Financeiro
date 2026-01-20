class VendasRouter:
    """
    Um router para controlar todas as operações de banco de dados no modelo de vendas.
    Garante que o banco de dados 'vendas_db' seja tratado como somente leitura
    e que nenhuma migração seja aplicada a ele.
    """
    
    # Se tivéssemos models importados do legado, poderíamos usar app_labels
    # route_app_labels = {'vendas'} 

    def db_for_read(self, model, **hints):
        """
        Direciona leituras. 
        Retorna None para permitir que o Django decida (normalmente 'default'),
        a menos que especificado explicitamente na query com .using('vendas_db').
        Como usaremos SQL direto, isso tem pouco efeito prático, mas mantém o padrão.
        """
        return None

    def db_for_write(self, model, **hints):
        """
        Direciona escritas.
        Retorna None para usar o padrão ('default').
        """
        return None

    def allow_relation(self, obj1, obj2, **hints):
        """
        Permite relações se ambos os objetos estiverem no mesmo banco.
        """
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """
        Impede migrações no banco de vendas_db.
        Esta é a regra de segurança mais importante.
        """
        if db == 'vendas_db':
            return False
        return None