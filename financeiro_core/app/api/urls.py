from django.urls import path
from .endpoints import api
from .mock_auth import router as auth_router

api.add_router("/auth", auth_router)

urlpatterns = [
    path('api/', api.urls),
]