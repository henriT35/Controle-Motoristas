from django.urls import path
from . import portal_views

urlpatterns = [
    path("<str:token>/", portal_views.portal_home, name="driver_portal"),
    path("<str:token>/comprovante/<int:proof_pk>/enviar/", portal_views.portal_submit_proof, name="driver_portal_submit_proof"),
]
