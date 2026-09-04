from django.urls import path
from . import views

urlpatterns = [
    path("", views.center, name="whatsapp_center"),
    path("conectar/", views.pairing, name="whatsapp_pairing"),
    path("iniciar/", views.start_bot, name="whatsapp_start_bot"),
    path("encerrar/", views.stop_bot, name="whatsapp_stop_bot"),
    path("redefinir-sessao/", views.reset_bot_session, name="whatsapp_reset_session"),
    path("qr/", views.qr_image, name="whatsapp_qr_image"),
    path("log/", views.bot_log, name="whatsapp_bot_log"),
    path("enviar-dia/", views.send_day, name="whatsapp_send_day"),
    path("enviar-todos/", views.send_all_registered, name="whatsapp_send_all_registered"),
    path("enviar-motorista/<int:pk>/", views.send_driver_day, name="whatsapp_send_driver_day"),
    path("enviar-romaneio/<int:pk>/", views.send_manifest, name="whatsapp_send_manifest"),
    path("reenviar/<int:pk>/", views.retry_message, name="whatsapp_retry_message"),
    path("motorista/<int:pk>/contato/", views.update_driver_contact, name="whatsapp_driver_contact"),
    path("motorista/<int:pk>/link/", views.ensure_driver_link, name="whatsapp_ensure_driver_link"),
    path("status/", views.status_api, name="whatsapp_status_api"),
    path("internal/claim/", views.internal_claim_message, name="whatsapp_internal_claim"),
    path("internal/result/<int:pk>/", views.internal_message_result, name="whatsapp_internal_result"),
]
