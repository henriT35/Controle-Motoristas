from django.urls import path
from . import views
urlpatterns = [path("", views.index, name="clients"), path("<int:pk>/", views.detail, name="client_detail"), path("<int:pk>/regra-comprovante/", views.payment_rule, name="client_payment_rule")]
