from django.urls import path
from . import views

urlpatterns = [
    path("hoje/", views.today, name="operations_today"),
    path("entregas/", views.deliveries, name="deliveries"),
    path("cte/<int:pk>/", views.cte_detail, name="cte_detail"),
    path("mapa/", views.map_operational, name="map_operational"),
    path("api/geografia/resumo/", views.geo_summary_api, name="geo_summary_api"),
    path("api/geografia/bairros/", views.geo_neighborhood_geometry_api, name="geo_neighborhood_geometry_api"),
    path("api/geografia/diagnostico/", views.geo_diagnostics_api, name="geo_diagnostics_api"),
    path("romaneio/<int:pk>/", views.manifest_detail, name="manifest_detail"),
]
