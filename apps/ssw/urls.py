from django.urls import path

from . import views

urlpatterns = [
    path("importacoes/", views.imports, name="ssw_imports"),
    path("importacoes/progresso/", views.import_progress, name="ssw_import_progress"),
    path("automacao/salvar/", views.update_schedule, name="ssw_schedule_update"),
    path("automacao/atualizar-agora/", views.trigger_fast_sync, name="ssw_update_now"),
    path("fila/retomar/", views.resume_queue_view, name="ssw_queue_resume"),
    path("historico/", views.history, name="ssw_history"),
    path("historico/<int:pk>/log/", views.download_log, name="ssw_log_download"),
    path("historico/<int:pk>/diagnostico/", views.download_diagnostic, name="ssw_diagnostic_download"),
    path("historico/<int:pk>/reprocessar/", views.retry_failed_run, name="ssw_retry_failed"),
]
