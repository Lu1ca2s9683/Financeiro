from django.urls import path
from .endpoints import api

urlpatterns = [
    path('api/', api.urls),
]