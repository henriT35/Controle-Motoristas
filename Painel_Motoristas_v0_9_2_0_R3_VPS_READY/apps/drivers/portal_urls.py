from django.urls import path
from . import portal_views

urlpatterns = [
    path("solicitar-acesso/", portal_views.portal_request_access, name="driver_portal_request_access"),
    path("solicitacao/<int:request_pk>/revisar/", portal_views.portal_review_access_request, name="driver_portal_request_review"),
    path("<str:token>/", portal_views.portal_home, name="driver_portal"),
    path("<str:token>/comprovante/<int:proof_pk>/enviar/", portal_views.portal_submit_proof, name="driver_portal_submit_proof"),
    path("<str:token>/comprovante/<int:proof_pk>/acao/", portal_views.portal_pickup_action, name="driver_portal_pickup_action"),
    path("<str:token>/movimento/<int:movement_pk>/reter/", portal_views.portal_report_retention, name="driver_portal_report_retention"),
]
