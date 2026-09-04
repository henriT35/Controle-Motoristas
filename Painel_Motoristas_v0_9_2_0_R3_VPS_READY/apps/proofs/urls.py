from django.urls import path
from . import views

urlpatterns = [
    path("", views.index, name="proofs"),
    path("<int:pk>/recuperar/", views.recover, name="proof_recover"),
    path("recuperacao/<int:submission_pk>/validar/", views.validate_submission, name="proof_recovery_validate"),
]
