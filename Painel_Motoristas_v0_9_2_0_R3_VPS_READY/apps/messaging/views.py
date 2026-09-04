from __future__ import annotations

from datetime import date, timedelta
import json
import os
import secrets
import signal
from pathlib import Path
import subprocess
import sys
import time

from django.contrib import messages
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import OuterRef, Subquery
from django.http import JsonResponse, HttpResponse, HttpResponseForbidden, FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.audit.models import AuditLog
from apps.core.services import manifests_for_operational_date, planned_manifests, operational_manifest_classification_map
from apps.drivers.models import Driver, DriverPortalAccess, DriverPortalAccessRequest
from apps.operations.models import Manifest
from apps.operations.services import build_manifest_cards, opportunities_summary
from .models import WhatsAppMessage
from .services import (
    normalize_whatsapp_phone, is_valid_whatsapp_phone, existing_portal_url, portal_url_for, driver_operation_summary,
    build_daily_message, build_manifest_message, build_general_portal_message, public_portal_ready,
    whatsapp_phone_candidates,
)
from .state import (
    BRIDGE_DIR, LOG_FILE, QR_FILE, bridge_dependencies_ready, clear_qr_artifacts, clear_stop_request,
    ensure_bridge_token, find_node_binary, process_alive, read_bridge_token, read_state, request_stop, request_reset,
    reset_baileys_session, reset_state, write_state,
)




def _safe_post_redirect(request, fallback):
    target = (request.POST.get("next") or "").strip()
    if target and url_has_allowed_host_and_scheme(
        url=target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return redirect(target)
    return redirect(fallback)

def _can_manage(user):
    return user.is_superuser or user.is_staff or user.groups.filter(name__iexact="Coordenador").exists()


def _date(request):
    raw = request.GET.get("date") or request.POST.get("date")
    try:
        return date.fromisoformat(raw) if raw else timezone.localdate()
    except ValueError:
        return timezone.localdate()


def _operation_manifests(target_date):
    qs = manifests_for_operational_date(target_date).filter(driver__is_test=False).exclude(status__iexact="CANCELADO")
    return list(qs.select_related("driver", "vehicle").order_by("driver__name", "number"))


def _access_url(request, access):
    if not access or not access.active:
        return ""
    path = reverse("driver_portal", args=[access.token])
    public_base = getattr(settings, "PANEL_PUBLIC_BASE_URL", "") or ""
    return public_base.rstrip("/") + path if public_base else request.build_absolute_uri(path)


def _all_driver_rows(request, target_date, operation_rows=None):
    """Lista única: cadastro + Portal + operação + comunicação + problemas.

    Cards das rotas são calculados uma vez para todos os motoristas, evitando o
    N+1 que existia ao montar um resumo motorista por motorista.
    """
    manifests = _operation_manifests(target_date)
    cards = build_manifest_cards(manifests, persist_available=False, operational_date=target_date) if manifests else []
    by_driver = {}
    for card in cards:
        driver_id = card["manifest"].driver_id
        row = by_driver.setdefault(driver_id, {"cards": [], "manifests": []})
        row["cards"].append(card)
        row["manifests"].append(card["manifest"])

    latest_message_id = Subquery(
        WhatsAppMessage.objects.filter(driver_id=OuterRef("pk"))
        .order_by("-created_at").values("pk")[:1]
    )
    drivers = list(
        Driver.objects.filter(active=True, is_test=False)
        .annotate(latest_whatsapp_message_id=latest_message_id)
        .order_by("name")
    )
    driver_ids = [d.pk for d in drivers]
    accesses = {a.driver_id: a for a in DriverPortalAccess.objects.filter(driver_id__in=driver_ids)}
    pending_requests = {}
    for item in DriverPortalAccessRequest.objects.filter(
        driver_id__in=driver_ids, status=DriverPortalAccessRequest.Status.PENDING
    ).order_by("-requested_at"):
        # O primeiro é sempre o pedido pendente mais recente daquele motorista.
        pending_requests.setdefault(item.driver_id, item)
    latest_ids = [d.latest_whatsapp_message_id for d in drivers if d.latest_whatsapp_message_id]
    latest_by_id = {m.pk: m for m in WhatsAppMessage.objects.filter(pk__in=latest_ids)}
    latest_messages = {
        d.pk: latest_by_id.get(d.latest_whatsapp_message_id)
        for d in drivers if d.latest_whatsapp_message_id
    }

    rows = []
    portal_public = public_portal_ready(request)
    for driver in drivers:
        op = by_driver.get(driver.pk, {"cards": [], "manifests": []})
        op_cards = op["cards"]
        exact_ids, regional_ids = opportunities_summary(op_cards) if op_cards else (set(), set())
        summary = {
            "routes": len(op_cards),
            "clients": sum(int(c.get("clients", 0)) for c in op_cards),
            "movements": sum(int(c.get("movements", 0)) for c in op_cards),
            "opportunities": len(set(exact_ids) | set(regional_ids)),
            "exact": len(exact_ids),
            "gold": len(regional_ids),
            "cards": op_cards,
        }
        phone = normalize_whatsapp_phone(driver.whatsapp_phone)
        access = accesses.get(driver.pk)
        request_item = pending_requests.get(driver.pk)
        problems = []
        if not phone or not is_valid_whatsapp_phone(phone): problems.append("Telefone ausente/inválido")
        if not driver.whatsapp_enabled: problems.append("Envio desabilitado")
        if not portal_public: problems.append("Link público indisponível")
        if request_item: problems.append("Novo acesso solicitado")
        rows.append({
            "driver": driver, "manifests": op["manifests"], "summary": summary,
            "phone": phone, "phone_ready": bool(driver.whatsapp_enabled and is_valid_whatsapp_phone(phone)),
            "ready": bool(driver.whatsapp_enabled and is_valid_whatsapp_phone(phone) and portal_public),
            "has_operation": bool(op_cards), "last_message": latest_messages.get(driver.pk),
            "portal_access": access, "portal_url": _access_url(request, access),
            "link_ready": bool(access and access.active), "portal_request": request_item,
            "problems": problems,
        })
    return rows


def _driver_rows(request, target_date):
    return [row for row in _all_driver_rows(request, target_date) if row["has_operation"]]


@login_required
def center(request):
    if not _can_manage(request.user):
        return HttpResponseForbidden("Acesso restrito à coordenação.")
    target_date = _date(request)
    all_driver_rows = _all_driver_rows(request, target_date)
    rows = [r for r in all_driver_rows if r["has_operation"]]
    recent = WhatsAppMessage.objects.select_related("driver", "manifest", "created_by")[:40]
    planned = list(planned_manifests(timezone.localdate()).select_related("driver", "vehicle")[:30])
    access_requests = list(
        DriverPortalAccessRequest.objects.filter(status=DriverPortalAccessRequest.Status.PENDING)
        .select_related("driver").order_by("-requested_at")[:30]
    )
    bot = read_state()
    return render(request, "messaging/center.html", {
        "selected_date": target_date, "rows": rows, "all_driver_rows": all_driver_rows,
        "ready_count": sum(1 for r in rows if r["ready"]),
        "all_ready_count": sum(1 for r in all_driver_rows if r["ready"]),
        "all_pending_count": sum(1 for r in all_driver_rows if r["problems"]),
        "pending_rows": [r for r in all_driver_rows if r["problems"]],
        "access_requests": access_requests, "bot": bot, "recent": recent,
        "planned_manifests": planned, "public_portal_ready": public_portal_ready(request),
        "public_portal_base": getattr(settings, "PANEL_PUBLIC_BASE_URL", ""),
    })


@login_required
def pairing(request):
    """Tela dedicada exclusivamente ao pareamento/QR do WhatsApp."""
    if not _can_manage(request.user):
        return HttpResponseForbidden("Acesso restrito à coordenação.")
    bot = read_state()
    return render(request, "messaging/pairing.html", {"bot": bot})


def _bot_action_redirect(request):
    return redirect("whatsapp_pairing" if request.POST.get("return_to") == "pairing" else "whatsapp_center")


@require_POST
@login_required
def start_bot(request):
    if not _can_manage(request.user):
        return HttpResponseForbidden("Acesso restrito.")
    state = read_state()
    if getattr(settings, "WHATSAPP_BRIDGE_EXTERNAL_SERVICE", False):
        if state.get("process_alive"):
            messages.info(request, "O serviço Baileys da VPS já inicia automaticamente. Aguarde o QR ou use Novo pareamento.")
        else:
            messages.error(request, "O container WhatsApp da VPS não está respondendo. Reinicie o serviço whatsapp no Docker Compose.")
        return redirect("whatsapp_pairing")
    if state.get("process_alive"):
        messages.info(request, "O serviço WhatsApp já está em execução. Se estiver travado, use Encerrar.")
        return redirect("whatsapp_pairing")

    node = find_node_binary()
    if not node:
        messages.error(
            request,
            "Node.js 20+ não está instalado/preparado. Execute INSTALAR_BOT_WHATSAPP.bat uma vez e tente novamente.",
        )
        return redirect("whatsapp_pairing")
    if not bridge_dependencies_ready():
        messages.error(
            request,
            "As dependências do Baileys ainda não foram instaladas. Execute INSTALAR_BOT_WHATSAPP.bat uma vez.",
        )
        return redirect("whatsapp_pairing")

    base = Path(__file__).resolve().parents[2]
    bridge_script = BRIDGE_DIR / "server.mjs"
    clear_stop_request()
    clear_qr_artifacts()
    ensure_bridge_token()
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    log_handle = LOG_FILE.open("a", encoding="utf-8")
    try:
        log_handle.write(f"\n\n=== BAILEYS START {timezone.now().isoformat()} ===\n")
        log_handle.flush()
        env = os.environ.copy()
        env["PANEL_BASE_DIR"] = str(base)
        env.setdefault("PANEL_INTERNAL_URL", "http://127.0.0.1:8000")
        kwargs = {
            "cwd": str(BRIDGE_DIR),
            "env": env,
            "stdout": log_handle,
            "stderr": subprocess.STDOUT,
        }
        if sys.platform.startswith("win"):
            kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        process = subprocess.Popen([node, str(bridge_script)], **kwargs)
    except Exception as exc:
        reset_state(f"Falha ao iniciar Baileys: {exc}")
        messages.error(request, f"Não foi possível iniciar o serviço Baileys: {exc}")
        return redirect("whatsapp_pairing")
    finally:
        try:
            log_handle.close()
        except Exception:
            pass

    write_state(
        status="STARTING", connected=False, online=True, pid=process.pid,
        started_at=timezone.now().isoformat(), backend="Baileys / Node.js",
        message="Conectando diretamente ao WhatsApp e aguardando o QR Code…",
        qr_available=False, error_code="",
    )
    messages.success(request, "Baileys iniciado. Se a conta ainda não estiver vinculada, o QR Code aparecerá nesta tela.")
    return redirect("whatsapp_pairing")


def _hard_stop_bot(pid):
    if not pid:
        return True
    try:
        if sys.platform.startswith("win"):
            result = subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True, text=True, timeout=12,
            )
            return result.returncode == 0 or not process_alive(pid)
        os.kill(pid, signal.SIGTERM)
        return True
    except Exception:
        return not process_alive(pid)


@require_POST
@login_required
def stop_bot(request):
    if not _can_manage(request.user):
        return HttpResponseForbidden("Acesso restrito.")
    if getattr(settings, "WHATSAPP_BRIDGE_EXTERNAL_SERVICE", False):
        request_stop()
        messages.info(request, "Encerramento solicitado. Na VPS o Docker reinicia o serviço automaticamente para manter o WhatsApp 24h.")
        return _bot_action_redirect(request)
    raw = read_state(raw=True)
    pid = int(raw.get("pid") or 0)
    if not pid or not process_alive(pid):
        reset_state("Bot desligado")
        messages.info(request, "O bot já estava offline. O estado local foi limpo.")
        return _bot_action_redirect(request)

    request_stop()
    write_state(
        status="STOPPING", connected=False, online=True, pid=pid,
        message="Encerrando serviço Baileys…",
    )
    deadline = time.monotonic() + 7
    while time.monotonic() < deadline and process_alive(pid):
        time.sleep(0.25)
    if process_alive(pid):
        _hard_stop_bot(pid)
    if process_alive(pid):
        write_state(
            status="UNRESPONSIVE", connected=False, online=True, pid=pid,
            message="O serviço Baileys não respondeu ao encerramento automático. Tente novamente.",
        )
        messages.error(request, "Não foi possível encerrar completamente o processo do bot.")
    else:
        reset_state("Bot encerrado pelo coordenador")
        messages.success(request, "Serviço WhatsApp/Baileys encerrado.")
    return _bot_action_redirect(request)


@require_POST
@login_required
def reset_bot_session(request):
    if not _can_manage(request.user):
        return HttpResponseForbidden("Acesso restrito.")
    if getattr(settings, "WHATSAPP_BRIDGE_EXTERNAL_SERVICE", False):
        request_reset()
        write_state(
            status="RESETTING", connected=False, online=True,
            message="Novo pareamento solicitado. O serviço Baileys está limpando a sessão e gerará outro QR Code.",
            error_code="",
        )
        messages.success(request, "Novo pareamento solicitado. Aguarde alguns segundos pelo QR Code.")
        return _bot_action_redirect(request)
    raw = read_state(raw=True)
    pid = int(raw.get("pid") or 0)
    if pid and process_alive(pid):
        request_stop()
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and process_alive(pid):
            time.sleep(0.2)
        if process_alive(pid):
            _hard_stop_bot(pid)
    if pid and process_alive(pid):
        messages.error(request, "Não foi possível encerrar o serviço Baileys. Tente Encerrar novamente antes de apagar a sessão.")
        return _bot_action_redirect(request)

    try:
        reset_baileys_session()
        reset_state("Sessão Baileys removida. Clique em Gerar QR Code para vincular um novo aparelho.")
        messages.success(request, "Sessão do WhatsApp removida. O próximo início gerará um QR Code totalmente novo.")
    except Exception as exc:
        write_state(
            status="ERROR", connected=False, online=False, pid=None, backend="Baileys / Node.js",
            message=f"Falha ao remover a sessão Baileys: {exc}", error_code="BAILEYS_RESET_ERROR",
        )
        messages.error(request, f"Não foi possível redefinir a sessão: {exc}")
    return _bot_action_redirect(request)


@login_required
def qr_image(request):
    if not _can_manage(request.user):
        return HttpResponseForbidden("Acesso restrito.")
    if not QR_FILE.exists():
        raise Http404("QR Code ainda não disponível")
    response = FileResponse(QR_FILE.open("rb"), content_type="image/png")
    response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return response


@login_required
def bot_log(request):
    if not _can_manage(request.user):
        return HttpResponseForbidden("Acesso restrito.")
    if not LOG_FILE.exists():
        raise Http404("Log do bot ainda não existe")
    return FileResponse(LOG_FILE.open("rb"), as_attachment=True, filename="whatsapp_baileys.log", content_type="text/plain")


@require_POST
@login_required
def send_day(request):
    if not _can_manage(request.user):
        return HttpResponseForbidden("Acesso restrito.")
    if not public_portal_ready(request):
        messages.error(request, "Configure PANEL_PUBLIC_BASE_URL com um endereço que o celular do motorista consiga abrir antes de enviar links.")
        return _safe_post_redirect(request, "whatsapp_center")
    target_date = _date(request)
    rows = _driver_rows(request, target_date)
    queued = 0
    skipped = []
    already = []
    for row in rows:
        if not row["ready"]:
            skipped.append(row["driver"].name)
            continue
        driver = row["driver"]
        # Clique duplo/repetição do lote não deve gerar duplicidade. Reenvio
        # consciente continua disponível pela ação individual/histórico.
        exists = WhatsAppMessage.objects.filter(
            driver=driver, operation_date=target_date, kind=WhatsAppMessage.Kind.DAILY,
            status__in=[WhatsAppMessage.Status.PENDING, WhatsAppMessage.Status.SENDING, WhatsAppMessage.Status.SENT],
        ).exists()
        if exists:
            already.append(driver.name)
            continue
        portal_url = portal_url_for(request, driver)
        body = build_daily_message(driver, target_date, row["summary"], portal_url)
        WhatsAppMessage.objects.create(
            driver=driver, operation_date=target_date, phone=row["phone"], portal_url=portal_url,
            body=body, kind=WhatsAppMessage.Kind.DAILY, created_by=request.user,
        )
        queued += 1
    AuditLog.objects.create(user=request.user, action="WHATSAPP_DAY_QUEUED", entity="WhatsAppMessage", entity_id=str(target_date), before={}, after={"queued": queued, "skipped": skipped, "already": already})
    if queued:
        messages.success(request, f"{queued} mensagem(ns) colocada(s) na fila do WhatsApp.")
    if already:
        messages.info(request, f"{len(already)} motorista(s) já possuíam envio desta operação; não foram duplicados.")
    if skipped:
        messages.warning(request, f"{len(skipped)} motorista(s) ficaram de fora por cadastro incompleto.")
    return redirect(f"/whatsapp/?date={target_date.isoformat()}")


@require_POST
@login_required
def send_all_registered(request):
    """Gera uma mensagem por motorista ativo e deixa o Baileys consumir a fila.

    Motorista com operação recebe o resumo do dia; sem operação recebe apenas
    o link do portal. Repetir o clique não duplica envios já pendentes/enviados
    daquela data.
    """
    if not _can_manage(request.user):
        return HttpResponseForbidden("Acesso restrito.")
    if not public_portal_ready(request):
        messages.error(request, "O endereço público do Painel precisa estar acessível aos motoristas antes do envio em lote.")
        return redirect("whatsapp_center")
    target_date = _date(request)
    rows = _all_driver_rows(request, target_date)
    queued = 0
    already = 0
    skipped = 0
    for row in rows:
        if not row["ready"]:
            skipped += 1
            continue
        driver = row["driver"]
        exists = WhatsAppMessage.objects.filter(
            driver=driver, operation_date=target_date, kind=WhatsAppMessage.Kind.DAILY,
            status__in=[WhatsAppMessage.Status.PENDING, WhatsAppMessage.Status.SENDING, WhatsAppMessage.Status.SENT],
        ).exists()
        if exists:
            already += 1
            continue
        portal_url = portal_url_for(request, driver)
        body = (
            build_daily_message(driver, target_date, row["summary"], portal_url)
            if row["has_operation"]
            else build_general_portal_message(driver, portal_url)
        )
        WhatsAppMessage.objects.create(
            driver=driver, operation_date=target_date, phone=row["phone"], portal_url=portal_url,
            body=body, kind=WhatsAppMessage.Kind.DAILY, created_by=request.user,
        )
        queued += 1
    AuditLog.objects.create(
        user=request.user, action="WHATSAPP_ALL_DRIVERS_QUEUED", entity="WhatsAppMessage",
        entity_id=str(target_date), before={},
        after={"queued": queued, "already": already, "skipped": skipped},
    )
    if queued:
        messages.success(request, f"{queued} mensagem(ns) gerada(s). O Baileys enviará automaticamente uma por vez.")
    if already:
        messages.info(request, f"{already} motorista(s) já tinham mensagem diária nesta data e não foram duplicados.")
    if skipped:
        messages.warning(request, f"{skipped} motorista(s) ficaram de fora por telefone inválido/desabilitado.")
    return redirect(f"/whatsapp/?date={target_date.isoformat()}")


@require_POST
@login_required
def send_driver_day(request, pk):
    if not _can_manage(request.user):
        return HttpResponseForbidden("Acesso restrito.")
    if not public_portal_ready(request):
        messages.error(request, "Configure PANEL_PUBLIC_BASE_URL com um endereço que o celular do motorista consiga abrir antes de enviar links.")
        return _safe_post_redirect(request, "whatsapp_center")
    target_date = _date(request)
    driver = get_object_or_404(Driver, pk=pk, is_test=False)
    manifests = [m for m in _operation_manifests(target_date) if m.driver_id == driver.pk]
    if not manifests:
        messages.error(request, f"{driver.name} não possui operação identificada em {target_date:%d/%m/%Y}.")
        return redirect(f"/whatsapp/?date={target_date.isoformat()}")
    phone = normalize_whatsapp_phone(driver.whatsapp_phone)
    if not driver.whatsapp_enabled or not is_valid_whatsapp_phone(phone):
        messages.error(request, f"WhatsApp de {driver.name} não está pronto para envio.")
        return redirect(f"/whatsapp/?date={target_date.isoformat()}")
    portal_url = portal_url_for(request, driver)
    summary = driver_operation_summary(manifests, target_date)
    body = build_daily_message(driver, target_date, summary, portal_url)
    WhatsAppMessage.objects.create(
        driver=driver, operation_date=target_date, phone=phone, portal_url=portal_url, body=body,
        kind=WhatsAppMessage.Kind.MANUAL, created_by=request.user,
    )
    messages.success(request, f"Mensagem individual colocada na fila para {driver.name}.")
    return redirect(f"/whatsapp/?date={target_date.isoformat()}")


@require_POST
@login_required
def send_manifest(request, pk):
    if not _can_manage(request.user):
        return HttpResponseForbidden("Acesso restrito.")
    if not public_portal_ready(request):
        messages.error(request, "Configure PANEL_PUBLIC_BASE_URL com um endereço que o celular do motorista consiga abrir antes de enviar links.")
        return _safe_post_redirect(request, "whatsapp_center")
    manifest = get_object_or_404(Manifest.objects.select_related("driver", "vehicle"), pk=pk)
    target_date = _date(request)
    driver = manifest.driver
    phone = normalize_whatsapp_phone(driver.whatsapp_phone)
    if not driver.whatsapp_enabled or not is_valid_whatsapp_phone(phone):
        messages.error(request, f"{driver.name} não possui WhatsApp pronto para envio.")
        return _safe_post_redirect(request, "operations_today")
    pending_duplicate = WhatsAppMessage.objects.filter(
        manifest=manifest, operation_date=target_date, kind=WhatsAppMessage.Kind.MANIFEST,
        status__in=[WhatsAppMessage.Status.PENDING, WhatsAppMessage.Status.SENDING],
    ).exists()
    if pending_duplicate:
        messages.info(request, f"Já existe um envio do romaneio {manifest.number} aguardando processamento.")
        return _safe_post_redirect(request, f"/operacao/hoje/?date={target_date.isoformat()}")
    portal_url = portal_url_for(request, driver)
    card = build_manifest_cards([manifest], persist_available=False, operational_date=target_date)[0]
    classification = operational_manifest_classification_map(target_date).get(manifest.pk, "PLANNED")
    body = build_manifest_message(driver, target_date, manifest, card, portal_url, planned=(classification == "PLANNED"))
    WhatsAppMessage.objects.create(
        driver=driver, manifest=manifest, operation_date=target_date, phone=phone, portal_url=portal_url,
        body=body, kind=WhatsAppMessage.Kind.MANIFEST, created_by=request.user,
    )
    if classification == "PLANNED":
        messages.success(request, f"Link do romaneio {manifest.number} colocado na fila como planejamento ainda não confirmado.")
    else:
        messages.success(request, f"Mensagem do romaneio {manifest.number} colocada na fila para {driver.name}.")
    return _safe_post_redirect(request, f"/operacao/hoje/?date={target_date.isoformat()}")


@require_POST
@login_required
def retry_message(request, pk):
    if not _can_manage(request.user):
        return HttpResponseForbidden("Acesso restrito.")
    old = get_object_or_404(WhatsAppMessage, pk=pk)
    WhatsAppMessage.objects.create(
        driver=old.driver, manifest=old.manifest, operation_date=old.operation_date, phone=old.phone,
        portal_url=old.portal_url, body=old.body, kind=old.kind, created_by=request.user,
    )
    messages.success(request, "Mensagem recolocada na fila.")
    return redirect("whatsapp_center")


@require_POST
@login_required
def update_driver_contact(request, pk):
    if not _can_manage(request.user):
        return HttpResponseForbidden("Acesso restrito.")
    driver = get_object_or_404(Driver, pk=pk)
    raw = (request.POST.get("whatsapp_phone") or "").strip()
    digits = normalize_whatsapp_phone(raw)
    if raw and not is_valid_whatsapp_phone(digits):
        messages.error(request, "Telefone inválido. Informe DDD + número brasileiro com 10 ou 11 dígitos.")
    else:
        driver.whatsapp_phone = digits
        driver.whatsapp_enabled = bool(request.POST.get("whatsapp_enabled"))
        driver.save(update_fields=["whatsapp_phone", "whatsapp_enabled", "updated_at"])
        messages.success(request, f"WhatsApp de {driver.name} atualizado.")
    return _safe_post_redirect(request, "whatsapp_center")


@require_POST
@login_required
def ensure_driver_link(request, pk):
    if not _can_manage(request.user):
        return HttpResponseForbidden("Acesso restrito.")
    driver = get_object_or_404(Driver, pk=pk, is_test=False)
    before = bool(DriverPortalAccess.objects.filter(driver=driver, active=True).exists())
    portal_url = portal_url_for(request, driver)
    AuditLog.objects.create(
        user=request.user, action="DRIVER_PORTAL_ENSURED_FROM_WHATSAPP", entity="DriverPortalAccess",
        entity_id=str(driver.pk), before={"active": before}, after={"active": True},
    )
    messages.success(request, f"Link individual de {driver.name} está pronto para copiar/enviar.")
    return _safe_post_redirect(request, "whatsapp_center")


def _bridge_authorized(request) -> bool:
    expected = read_bridge_token()
    supplied = (request.headers.get("Authorization") or "").strip()
    if supplied.lower().startswith("bearer "):
        supplied = supplied[7:].strip()
    if not (expected and supplied and secrets.compare_digest(expected, supplied)):
        return False
    remote = (request.META.get("REMOTE_ADDR") or "").strip()
    if remote in {"127.0.0.1", "::1"}:
        return True
    # Na VPS o Node/Baileys roda em outro container na rede interna Docker.
    # O Nginx bloqueia /whatsapp/internal/ externamente; o token compartilhado
    # continua obrigatório para qualquer chamada entre containers.
    return bool(getattr(settings, "WHATSAPP_BRIDGE_TRUSTED_INTERNAL", False))


@csrf_exempt
@require_POST
def internal_claim_message(request):
    """Fila local consumida exclusivamente pelo bridge Baileys em 127.0.0.1."""
    if not _bridge_authorized(request):
        return JsonResponse({"error": "unauthorized"}, status=403)

    stale_before = timezone.now() - timedelta(minutes=3)
    stale_error = (
        "O bridge Baileys foi interrompido durante o envio e não há confirmação segura do resultado. "
        "A mensagem foi marcada como falha para evitar duplicidade; use Reenviar se necessário."
    )
    WhatsAppMessage.objects.filter(
        status=WhatsAppMessage.Status.SENDING,
        started_at__lt=stale_before,
    ).update(status=WhatsAppMessage.Status.FAILED, error=stale_error)
    WhatsAppMessage.objects.filter(
        status=WhatsAppMessage.Status.SENDING,
        started_at__isnull=True,
    ).update(status=WhatsAppMessage.Status.FAILED, error=stale_error)

    with transaction.atomic():
        msg = (
            WhatsAppMessage.objects.select_for_update()
            .filter(status=WhatsAppMessage.Status.PENDING)
            .order_by("created_at")
            .first()
        )
        if not msg:
            return HttpResponse(status=204)
        msg.mark_sending()
        return JsonResponse({
            "id": msg.pk,
            "phone": msg.phone,
            "phone_candidates": whatsapp_phone_candidates(msg.phone),
            "body": msg.body,
            "kind": msg.kind,
            "operation_date": msg.operation_date.isoformat(),
        })


@csrf_exempt
@require_POST
def internal_message_result(request, pk):
    if not _bridge_authorized(request):
        return JsonResponse({"error": "unauthorized"}, status=403)
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        return JsonResponse({"error": "invalid_json"}, status=400)

    msg = get_object_or_404(WhatsAppMessage, pk=pk)
    if bool(payload.get("ok")):
        resolved_phone = normalize_whatsapp_phone(payload.get("resolved_phone"))
        if resolved_phone and is_valid_whatsapp_phone(resolved_phone) and resolved_phone != msg.phone:
            msg.phone = resolved_phone
            msg.save(update_fields=["phone"])
        msg.mark_sent()
    else:
        msg.mark_failed(payload.get("error") or "Falha informada pelo bridge Baileys")
    return JsonResponse({"ok": True, "status": msg.status})


@login_required
def status_api(request):
    if not _can_manage(request.user):
        return JsonResponse({"error": "forbidden"}, status=403)
    state = read_state()
    state["pending"] = WhatsAppMessage.objects.filter(status=WhatsAppMessage.Status.PENDING).count()
    state["can_start"] = not bool(state.get("process_alive"))
    state["can_stop"] = bool(state.get("process_alive"))
    state["qr_url"] = reverse("whatsapp_qr_image") if state.get("qr_available") else ""
    state["log_url"] = reverse("whatsapp_bot_log") if LOG_FILE.exists() else ""
    return JsonResponse(state)
