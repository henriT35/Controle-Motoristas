from decimal import Decimal
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test, login_required
from django.contrib.auth.views import LoginView
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.db import transaction, connection
from django.shortcuts import redirect, render
from django.utils.dateparse import parse_time
from django.views.static import serve as static_serve

from apps.audit.models import AuditLog
from .models import SystemSettings
from apps.ssw.schedule_config import load_schedule_config, interval_label


def _admin(user):
    return user.is_authenticated and (user.is_superuser or user.is_staff)


@user_passes_test(_admin, login_url="/login/")
def settings_view(request):
    obj = SystemSettings.load()
    if request.method == "POST":
        before = {f.name: str(getattr(obj, f.name)) for f in obj._meta.fields if f.name not in {"id", "updated_at"}}
        fields = [
            "period_default", "timezone_name", "currency", "decimal_places",
            "recent_window_days", "log_retention_days", "critical_days", "alert_min_days", "minimum_sample", "proof_sla_days",
            "driver_score_delivery_weight", "driver_score_clean_weight", "driver_score_retention_weight",
            "driver_score_time_window_weight", "driver_score_proof_weight", "driver_score_recovery_weight", "driver_rank_min_attempts",
            "operational_weight", "effort_weight", "effort_movements_weight", "effort_stops_weight",
            "effort_manifests_weight", "effort_weight_kg_weight", "theme", "accent", "density", "notification_emails",
        ]
        errors = []
        for field in fields:
            if field in request.POST:
                model_field = obj._meta.get_field(field)
                try:
                    setattr(obj, field, model_field.to_python(request.POST.get(field)))
                except Exception:
                    errors.append(f"Valor inválido para {field}.")
        for field in ["monthly_reconcile_time", "daily_summary_time"]:
            if request.POST.get(field):
                value = parse_time(request.POST[field])
                if value:
                    setattr(obj, field, value)
        obj.email_notifications_enabled = request.POST.get("email_notifications_enabled") == "on"
        obj.daily_summary_enabled = request.POST.get("daily_summary_enabled") == "on"
        if obj.operational_weight + obj.effort_weight != Decimal("100"):
            errors.append("Índice operacional + índice de esforço devem totalizar 100%.")
        effort_sum = obj.effort_movements_weight + obj.effort_stops_weight + obj.effort_manifests_weight + obj.effort_weight_kg_weight
        if effort_sum != Decimal("100"):
            errors.append("Os pesos internos do esforço devem totalizar 100%.")
        performance_sum = (
            obj.driver_score_delivery_weight + obj.driver_score_clean_weight + obj.driver_score_retention_weight
            + obj.driver_score_time_window_weight + obj.driver_score_proof_weight + obj.driver_score_recovery_weight
        )
        if performance_sum != Decimal("100"):
            errors.append("Os pesos da avaliação V2 devem totalizar 100%.")
        if errors:
            for err in errors:
                messages.error(request, err)
        else:
            with transaction.atomic():
                obj.save()
                after = {f.name: str(getattr(obj, f.name)) for f in obj._meta.fields if f.name not in {"id", "updated_at"}}
                AuditLog.objects.create(user=request.user, action="SETTINGS_UPDATED", entity="SystemSettings", entity_id=str(obj.pk), before=before, after=after)
            messages.success(request, "Configurações salvas com sucesso.")
            return redirect("settings")
    logs = AuditLog.objects.filter(entity="SystemSettings").select_related("user").order_by("-created_at")[:20]
    schedule_cfg = load_schedule_config()
    return render(request, "settings/index.html", {
        "settings_obj": obj, "settings_logs": logs,
        "ssw_schedule": schedule_cfg, "ssw_schedule_label": interval_label(schedule_cfg["interval_minutes"]),
    })


@login_required(login_url="/login/")
def protected_media(request, path):
    """Serve uploads no modo online sem tornar /media público sem autenticação."""
    return static_serve(request, path, document_root=settings.MEDIA_ROOT)


class RememberLoginView(LoginView):
    template_name = "registration/login.html"
    MAX_FAILURES = 5
    LOCK_SECONDS = 60

    def dispatch(self, request, *args, **kwargs):
        lock_until = request.session.get("login_lock_until")
        if lock_until and timezone.now().timestamp() < lock_until:
            return HttpResponse("Muitas tentativas de login. Aguarde 1 minuto e tente novamente.", status=429)
        return super().dispatch(request, *args, **kwargs)

    def form_invalid(self, form):
        failures = int(self.request.session.get("login_fail_count", 0)) + 1
        self.request.session["login_fail_count"] = failures
        if failures >= self.MAX_FAILURES:
            self.request.session["login_lock_until"] = timezone.now().timestamp() + self.LOCK_SECONDS
            self.request.session["login_fail_count"] = 0
        return super().form_invalid(form)

    def form_valid(self, form):
        response = super().form_valid(form)
        self.request.session.pop("login_fail_count", None)
        self.request.session.pop("login_lock_until", None)
        if self.request.POST.get("remember") == "on":
            self.request.session.set_expiry(60 * 60 * 24 * 30)
        else:
            self.request.session.set_expiry(0)
        return response


def healthz(request):
    """Healthcheck enxuto para Docker/Nginx, sem expor dados operacionais."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return JsonResponse({"ok": True, "service": "painel-motoristas"})
    except Exception:
        return JsonResponse({"ok": False, "service": "painel-motoristas"}, status=503)
