"""
URL configuration for config project.
"""
from django.contrib import admin
from django.urls import path
from ninja import NinjaAPI

# Importa o roteador definido no módulo financeiro
from financeiro_core.app.api.endpoints import router as financeiro_router
from financeiro_core.app.api.auth import router as auth_router

# Instancia a API do Django Ninja
api = NinjaAPI(
    title="Sistema Financeiro API",
    description="API para gestão de despesas e fechamento mensal (Clean Architecture)",
    version="1.0.0"
)

# Adiciona as rotas de autenticação (ex: /auth/login/ ou /api/auth/login)
api.add_router("/auth", auth_router)

# Adiciona as rotas do módulo financeiro (ex: /api/financeiro/despesas)
api.add_router("/financeiro", financeiro_router)

urlpatterns = [
    # Rota para o painel administrativo do Django
    path('admin/', admin.site.urls),
    
    # Rota base para a API (inclui a documentação automática em /api/docs)
    path('api/', api.urls),

    # Rota para expor /auth/login/ diretamente na raiz do backend se o frontend não estiver usando /api/
    # Usaremos um router isolado para /auth na raiz se necessário, ou podemos expor tudo da api.
    # Optando por uma nova instância NinjaAPI ou simplesmente path('auth/', ...) para evitar poluir a raiz.
]

# Use api.urls again or separate paths for auth directly if needed,
# But since we already added the router to `api` via `api.add_router("/auth", auth_router)`,
# the URL will be `/api/auth/login`.
# If we want `/auth/login/` on the root, we shouldn't add it to `auth_api` using the exact same `auth_router` instance
# because Django Ninja does not allow attaching the same router instance to multiple APIs without cloning.
# Instead, we will rely on `/api/auth/login/` which is the standard, and we already map the `api` router to `api/`.
# For `/auth/login/` (without `api/`), we could create a view manually, but it's cleaner to let the frontend use `/api/auth/login/`
# or just route `path('auth/', api.urls)` (though that would expose all api endpoints under `/auth/`).

# Let's remove the duplicated attach attempt. We already added it to `api` in line 19.