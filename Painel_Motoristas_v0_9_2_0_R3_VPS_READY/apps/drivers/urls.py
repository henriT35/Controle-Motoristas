from django.urls import path
from . import views, portal_views
urlpatterns = [
    path("", views.index, name="drivers"),
    path("ranking/premios/", views.ranking_rewards_update, name="ranking_rewards_update"),
    path("avaliacoes/", views.quality_reviews, name="driver_quality_reviews"),
    path("avaliacoes/<int:pk>/revisar/", views.quality_review_action, name="driver_quality_review_action"),
    path("<int:pk>/", views.detail, name="driver_detail"),
    path("<int:pk>/portal/", portal_views.portal_access_manage, name="driver_portal_manage"),
    path("<int:pk>/alternar-teste/", views.toggle_test, name="driver_toggle_test"),
]
