from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from apps.core.views import settings_view, RememberLoginView, protected_media, healthz

urlpatterns = [
    path("healthz/", healthz, name="healthz"),
    path("admin/", admin.site.urls),
    path("login/", RememberLoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", RedirectView.as_view(pattern_name="dashboard", permanent=False)),
    path("dashboard/", include("apps.dashboard.urls")),
    path("operacao/", include("apps.operations.urls")),
    path("motoristas/", include("apps.drivers.urls")),
    path("p/motorista/", include("apps.drivers.portal_urls")),
    path("comprovantes/", include("apps.proofs.urls")),
    path("clientes/", include("apps.clients.urls")),
    path("relatorios/", include("apps.reports.urls")),
    path("ssw/", include("apps.ssw.urls")),
    path("bugs/", include("apps.bugs.urls")),
    path("whatsapp/", include("apps.messaging.urls")),
    path("configuracoes/", settings_view, name="settings"),
]

if settings.SERVE_PROTECTED_MEDIA:
    urlpatterns += [path("media/<path:path>", protected_media, name="protected_media")]
elif settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
