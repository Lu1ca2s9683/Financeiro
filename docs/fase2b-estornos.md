# Financeiro — Fase 2B: estornos e imutabilidade

**Base:** `main` com PR #63 (Fase 2A). Criar branch `fix/financial-audit-reversals`.

## O que implementa

- Protege as movimentações já registradas contra `save`, `delete`, `QuerySet.update/delete`, `bulk_update` e `bulk_create` no ORM.
- Protege exclusão de contas, categorias e despesas com movimentações vinculadas (`PROTECT`).
- Adiciona `estorno_de` (único), `motivo_estorno` e `grupo_transferencia` (UUID, nulo para registros antigos).
- Vincula as **duas pontas das novas transferências** por UUID.
- Adiciona `POST /contas/movimentacoes/{movimentacao_id}/estornar`, autenticado, restrito à loja ativa, justificativa de 10–1000 caracteres, gravação do usuário ERP, lançamentos compensatórios atômicos, prevenção de duplo estorno e período atual aberto.
- Quando a movimentação é uma transferência nova com par íntegro, reverte ambos os lados numa transação. **Transferências antigas sem UUID são recusadas**, pois emparelhar por data/valor seria inseguro.
- Não recalcula nem altera movimentos ou saldos antigos.

## Aplicação

Descompacte o ZIP na raiz do Codespaces (`/workspaces/Financeiro`) preservando a pasta `scripts`.

```bash
cd /workspaces/Financeiro
git switch main
git pull --ff-only origin main
git switch -c fix/financial-audit-reversals

python scripts/apply_phase2b.py --check
python scripts/apply_phase2b.py

DJANGO_SETTINGS_MODULE=config.settings_test python manage.py makemigrations --check --dry-run
DJANGO_SETTINGS_MODULE=config.settings_test python manage.py test financeiro_core

git diff --check
git status --short
git diff --stat
```

**Se já existir uma branch em andamento**, use-a em vez de criar outra.

Antes do deploy: fazer revisão do schema da migration e testar em banco de homologação PostgreSQL. Render deve executar `python manage.py migrate` **com backup e janela controlada** antes de ativar a nova versão do backend. Verificar consistência visual/operacional e executar testes em ambiente de homologação. Não migrar dados históricos automaticamente.

## Limites deliberados

- Imutabilidade ORM **não é proteção contra SQL direto**, acesso de DBA, operações SQL manuais, nem alterações no `saldo_atual` de `ContaBancaria` por outro código. Requer controles adicionais de privilégios de banco e, se desejado, triggers PostgreSQL em entrega separada.
- Não acrescenta um botão de estorno no frontend: endpoint pronto para posterior integração visual. Requer chamada autenticada, POST JSON `{ "motivo": "..." }`.
- Reversão de despesas (`ContaPagar`) com pagamentos vinculados exige tratamento de domínio separado. Este pacote protege **MovimentacaoCaixa**, não transforma exclusão de despesa em estorno.
- Concorrência está protegida por locks e unicidade, mas teste de estresse real em PostgreSQL (múltiplas conexões) ainda é pendente.
- Estornos no mês fechado são bloqueados; o estorno é datado com hora atual, não retroativo.
- O `django.contrib.admin` atual permite mudanças no saldo de `ContaBancaria`; recomendamos bloquear esses campos para edição de saldos fora de serviços controlados numa etapa subsequente.

## Segurança

Nunca compartilhe credenciais, `DATABASE_URL` ou `SECRET_KEY`. Migrações e deploy somente após revisão do resultado dos testes.

## Consulta do historico de estornos

`GET /contas/movimentacoes` (JWT obrigatório) retorna, para a loja ativa, até 100 movimentos por padrão (máximo 200), incluindo conta, tipo, valor, autor, data, `estorno_de_id`, `estornado`, justificativa e grupo da transferência. Aceita `conta_id` para filtrar, sempre verificando a loja. **Não** altera nenhum registro. A integração dessa consulta com o frontend poderá ser feita em etapa separada.

## Proteção de relações históricas

As FKs de movimento para conta, categoria e despesa foram ajustadas para `PROTECT`. O endpoint de exclusão de categoria/despesa passa a rejeitar objetos com movimentações vinculadas em vez de apagar ou desvincular dados auditáveis.
