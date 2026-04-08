"""
URL configuration for config project.
"""
from django.contrib import admin
from django.urls import path
from ninja import NinjaAPI

# Importa o roteador definido no módulo financeiro
from financeiro_core.app.api.endpoints import router as financeiro_router
from financeiro_core.app.api.endpoints import fechamento_calcular_nativo
from financeiro_core.app.api.auth import router as auth_router

# Instancia a API do Django Ninja
api = NinjaAPI(
    title="Sistema Financeiro API",
    description="API para gestão de despesas e fechamento mensal (Clean Architecture)",
    version="1.0.0"
)

# Adiciona as rotas do módulo financeiro (ex: /api/financeiro/despesas)
api.add_router("/financeiro", financeiro_router)

# Adiciona as rotas de autenticação (ex: /api/financeiro/auth/login)
api.add_router("/financeiro/auth", auth_router)

urlpatterns = [
    # Rota para o painel administrativo do Django
    path('admin/', admin.site.urls),
    
    # Rota nativa de debug interceptando a rota de fechamento ANTES do NinjaAPI
    path('api/financeiro/fechamento/calcular/<int:loja_id>/<int:mes>/<int:ano>', fechamento_calcular_nativo),

    # Rota base para a API principal (inclui a documentação automática em /api/docs)
    path('api/', api.urls),
]