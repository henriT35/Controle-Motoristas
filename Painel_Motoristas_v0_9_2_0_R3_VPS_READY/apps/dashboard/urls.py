from django.urls import path
from . import views

urlpatterns = [
    path("", views.index, name="dashboard"),
    path("evolucao/", views.evolution_data, name="dashboard_evolution"),
]
