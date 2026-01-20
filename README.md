# Financeiro Core

Sistema de Gestão Financeira seguindo Domain-Driven Design (DDD) para um projeto Django.

## Estrutura do Projeto

- `domain/`: Regras de negócio puras (Services, Value Objects)
- `infrastructure/`: Integrações externas (APIs, Repositórios)
- `app/`: Camada Django (Models, API Views, Admin)
  - `models/`: Modelos de dados
  - `api/`: Endpoints da API
- `reports/`: Geradores de arquivos

## Instalação e Configuração

1. Adicione `financeiro_core` ao `INSTALLED_APPS` no `settings.py`:
   ```python
   INSTALLED_APPS = [
       # ... outros apps
       'financeiro_core',
       'ninja',  # Para API
   ]
   ```

2. Inclua as URLs no `urls.py` principal:
   ```python
   from django.urls import path, include

   urlpatterns = [
       # ... outras URLs
       path('financeiro/', include('financeiro_core.app.api.urls')),
   ]
   ```

3. Execute as migrações:
   ```bash
   python manage.py makemigrations financeiro_core
   python manage.py migrate
   ```

## Funcionalidades

### API Endpoints

- `POST /financeiro/api/despesas/`: Criar nova conta a pagar
- `POST /financeiro/api/fechamento/calcular/{loja}/{mes}/{ano}`: Calcular prévia do fechamento

### Admin Django

Acesse `/admin/` para gerenciar:
- Contas Bancárias
- Perfis de Taxa de Cartão
- Taxas da Maquininha
- Contas a Pagar
- Fechamentos Mensais
- Logs de Auditoria

## Executando Testes

Para rodar os testes unitários:

```bash
python manage.py test financeiro_core
```

Ou usando pytest (se configurado):

```bash
pytest financeiro_core/tests.py
```

## Desenvolvimento

### Adicionando Novos Recursos

1. **Domínio**: Adicione lógica em `domain/services.py`
2. **Infraestrutura**: Implemente integrações em `infrastructure/`
3. **Aplicação**: Crie modelos em `app/models/` e endpoints em `app/api/`
4. **Testes**: Escreva testes em `tests.py`

### Boas Práticas

- Mantenha a lógica de negócio pura no domínio
- Use injeção de dependência para repositórios
- Adicione docstrings em português para documentação
- Utilize type hints para melhor manutenção
- Implemente tratamento de erros robusto

## Próximos Passos

- Implementar repositórios reais (substituir mocks)
- Adicionar autenticação e permissões
- Criar relatórios em PDF/Excel
- Implementar cache para melhor performance
- Adicionar validações de negócio avançadas