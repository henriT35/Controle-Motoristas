from datetime import date, timedelta
from pathlib import Path

from django.contrib import messages
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Avg, F, ExpressionWrapper, DurationField, Q
from django.http import FileResponse, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.core.models import SystemSettings

from .diagnostics import build_diagnostic_zip, queue_pause_state, resume_queue, reconcile_orphan_runs
from .dispatch import dispatch_next_robot_run, dispatch_robot_run
from .import_lock import SSWImportLock
from .importer import import_ssw_delivery_file
from .models import ImportRun, ImportStep
from .parsers import read_ssw_delivery_file, read_ssw_delivery_metadata
from .progress import read_import_progress
from .robot_bridge import execution_id_for
from .services import queue_period_chunks, queue_import
from .schedule_config import load_schedule_config, save_schedule_config, interval_label


ALLOWED_EXTENSIONS = {".sswweb", ".csv"}
MAX_UPLOAD_BYTES = 25 * 1024 * 1024


def _save_upload(upload, inbox: Path, index: int) -> Path:
    suffix = Path(upload.name).suffix.lower()
    target = inbox / f"web_{timezone.now():%Y%m%d_%H%M%S_%f}_{index:03d}{suffix}"
    with target.open("wb") as handle:
        for chunk in upload.chunks():
            handle.write(chunk)
    return target




def _record_failed_manual_import(target: Path, requested_by, started_at, exc: Exception):
    """Garante rastreabilidade também quando o arquivo falha antes de criar ImportRun."""
    already_recorded = ImportRun.objects.filter(
        source_file=target.name,
        requested_by=requested_by,
        created_at__gte=started_at - timedelta(seconds=2),
    ).exists()
    if already_recorded:
        return
    today = timezone.localdate()
    run = ImportRun.objects.create(
        kind=ImportRun.Kind.MANUAL,
        start_date=today,
        end_date=today,
        status=ImportRun.Status.ERROR,
        started_at=started_at,
        finished_at=timezone.now(),
        source_file=target.name,
        error_count=1,
        message=str(exc)[:4000],
        requested_by=requested_by,
    )
    ImportStep.objects.create(
        run=run,
        name="Validação do arquivo",
        status="ERROR",
        occurred_at=timezone.now(),
        message=run.message,
    )


@login_required
def imports(request):
    uploads = request.FILES.getlist("ssw_files") or request.FILES.getlist("ssw_file")
    if request.method == "POST" and uploads:
        errors = []
        valid_uploads = []
        for upload in uploads:
            suffix = Path(upload.name).suffix.lower()
            if suffix not in ALLOWED_EXTENSIONS:
                errors.append(f"{upload.name}: formato inválido")
                continue
            if upload.size > MAX_UPLOAD_BYTES:
                errors.append(f"{upload.name}: acima do limite de 25 MB")
                continue
            valid_uploads.append(upload)

        for error in errors:
            messages.error(request, error)
        if not valid_uploads:
            return redirect("ssw_imports")

        inbox = Path(__file__).resolve().parents[2] / "imports" / "inbox"
        inbox.mkdir(parents=True, exist_ok=True)
        saved = [_save_upload(upload, inbox, idx) for idx, upload in enumerate(valid_uploads, start=1)]

        # Ordenação cronológica é importante para lotes mensais. A idempotência e a
        # cronologia das ocorrências ainda protegem o estado caso o usuário reimporte
        # um arquivo antigo depois.
        sortable = []
        for path in saved:
            try:
                period_start, period_end, _company = read_ssw_delivery_metadata(path)
                key = (period_start or date.max, period_end or date.max, path.name)
            except Exception:
                key = (date.max, date.max, path.name)
            sortable.append((key, path))
        sortable.sort(key=lambda item: item[0])

        totals = {"ok": 0, "error": 0, "new": 0, "updated": 0, "unchanged": 0, "proofs": 0}
        for _key, target in sortable:
            import_started_at = timezone.now()
            try:
                _run, stats = import_ssw_delivery_file(
                    target, kind=ImportRun.Kind.MANUAL, requested_by=request.user
                )
                totals["ok"] += 1
                totals["new"] += stats.new
                totals["updated"] += stats.updated
                totals["unchanged"] += stats.unchanged
                totals["proofs"] += stats.proofs_created
            except Exception as exc:
                totals["error"] += 1
                _record_failed_manual_import(target, request.user, import_started_at, exc)
                messages.error(request, f"{target.name}: falha na importação — {exc}")

        messages.success(
            request,
            f"Lote processado: {totals['ok']} arquivo(s) com sucesso, {totals['error']} erro(s), "
            f"{totals['new']} novos, {totals['updated']} atualizados, "
            f"{totals['unchanged']} sem alteração e {totals['proofs']} comprovantes retidos criados.",
        )
        return redirect("ssw_imports")

    if request.method == "POST":
        try:
            action = request.POST.get("action", "period")
            if action == "month_current":
                end = timezone.localdate()
                start = date(end.year, end.month, 1)
                kind = ImportRun.Kind.MONTH
            else:
                start = date.fromisoformat(request.POST.get("start_date"))
                end = date.fromisoformat(request.POST.get("end_date"))
                kind = request.POST.get("kind", ImportRun.Kind.HISTORY)
                if kind not in {choice[0] for choice in ImportRun.Kind.choices}:
                    kind = ImportRun.Kind.HISTORY
                if start > end:
                    start, end = end, start
            if (end - start).days >= 31:
                ids = queue_period_chunks(start, end, kind=kind, requested_by=request.user)
                if getattr(settings, "SSW_ROBOT_ENABLED", False):
                    messages.success(
                        request,
                        f"Período dividido em {len(ids)} janelas mensais. O robô processará uma janela por vez para evitar sessões concorrentes no SSW.",
                    )
                else:
                    messages.info(
                        request,
                        f"Período dividido em {len(ids)} janelas mensais. O executor do robô está desabilitado; as solicitações ficaram na fila.",
                    )
            else:
                run_id = queue_import(start, end, kind=kind, requested_by=request.user)
                run = ImportRun.objects.get(pk=run_id)
                if run.status == ImportRun.Status.ERROR:
                    messages.error(request, f"O robô SSW não pôde iniciar: {run.message}")
                elif run.message == "Execução enviada ao robô SSW.":
                    messages.success(request, "Solicitação enviada ao robô SSW. Acompanhe o progresso nesta tela.")
                else:
                    messages.info(
                        request,
                        "Solicitação registrada. O executor do robô está desabilitado ou indisponível; a execução permanece na fila.",
                    )
        except (TypeError, ValueError):
            messages.error(request, "Período inválido.")
        return redirect("ssw_imports")

    # A tela também atua como observador de saúde: se um Popen/worker morreu
    # antes de assumir a tarefa, não deixamos o status congelado para sempre.
    try:
        reconcile_orphan_runs(Path(settings.BASE_DIR))
    except Exception:
        # Observabilidade nunca deve impedir a abertura da tela.
        pass

    runs = list(ImportRun.objects.prefetch_related("steps").order_by("-created_at")[:30])
    latest_run = runs[0] if runs else None
    pause_state = queue_pause_state(Path(settings.BASE_DIR))
    latest_run_active = bool(
        latest_run
        and not pause_state.get("paused")
        and latest_run.status in {ImportRun.Status.QUEUED, ImportRun.Status.DISPATCHED, ImportRun.Status.RUNNING}
    )
    schedule_cfg = load_schedule_config()
    last_fast = ImportRun.objects.filter(kind=ImportRun.Kind.FAST).order_by("-created_at").first()
    next_sync_at = None
    if schedule_cfg["enabled"]:
        if last_fast:
            next_sync_at = timezone.localtime(last_fast.created_at) + timedelta(minutes=int(schedule_cfg["interval_minutes"]))
        else:
            next_sync_at = timezone.localtime()
    return render(
        request,
        "ssw/imports.html",
        {
            "runs": runs,
            "latest_run": latest_run,
            "robot_enabled": getattr(settings, "SSW_ROBOT_ENABLED", False),
            "robot_unit": getattr(settings, "SSW_ROBOT_UNIT", "BEL"),
            "robot_option": getattr(settings, "SSW_ROBOT_OPTION", "036"),
            "queue_pause": pause_state,
            "latest_run_active": latest_run_active,
            "schedule_cfg": schedule_cfg,
            "schedule_label": interval_label(schedule_cfg["interval_minutes"]),
            "last_fast": last_fast,
            "next_sync_at": next_sync_at,
        },
    )


@require_POST
@login_required
def update_schedule(request):
    if not (request.user.is_staff or request.user.is_superuser or request.user.groups.filter(name__iexact="Coordenador").exists()):
        return HttpResponse(status=403)
    enabled = request.POST.get("enabled") == "on"
    try:
        interval = int(request.POST.get("interval_minutes") or 60)
    except (TypeError, ValueError):
        interval = 60
    saved = save_schedule_config(enabled=enabled, interval_minutes=interval)
    AuditLog.objects.create(
        user=request.user, action="SSW_SCHEDULE_UPDATED", entity="SSWSchedule", entity_id="singleton",
        before={}, after=saved,
    )
    messages.success(request, f"Automação SSW {'ativada' if saved['enabled'] else 'desativada'} · {interval_label(saved['interval_minutes'])}.")
    return redirect("ssw_imports")


@require_POST
@login_required
def trigger_fast_sync(request):
    if queue_pause_state(Path(settings.BASE_DIR)).get("paused"):
        messages.error(request, "A fila SSW está pausada. Retome a fila antes de solicitar uma atualização.")
        return redirect("ssw_imports")
    today = timezone.localdate()
    cfg = SystemSettings.load()
    start = today - timedelta(days=max(cfg.recent_window_days - 1, 0))
    run_id = queue_import(start, today, kind=ImportRun.Kind.FAST, requested_by=request.user)
    run = ImportRun.objects.get(pk=run_id)
    AuditLog.objects.create(
        user=request.user, action="SSW_FAST_SYNC_REQUESTED", entity="ImportRun", entity_id=str(run.pk),
        before={}, after={"status": run.status, "start_date": str(start), "end_date": str(today)},
    )
    if run.status in {ImportRun.Status.DISPATCHED, ImportRun.Status.RUNNING}:
        messages.success(request, "Atualização imediata solicitada. O robô SSW já está processando a janela recente.")
    elif run.status == ImportRun.Status.QUEUED:
        messages.info(request, "Atualização colocada na fila. Ela será executada assim que o worker SSW estiver livre.")
    elif run.status == ImportRun.Status.ERROR:
        messages.error(request, f"A atualização não pôde iniciar: {run.message}")
    else:
        messages.info(request, f"Solicitação registrada com status {run.get_status_display()}.")
    return redirect("ssw_imports")


@login_required
def import_progress(request):
    """Estado leve para o feedback ao vivo da importação manual.

    A importação continua síncrona no modo local, mas o navegador consegue
    acompanhar upload + estágio corrente por uma segunda requisição enquanto
    o servidor processa o arquivo.
    """
    try:
        # BUG-001: o polling precisa reconciliar tarefas órfãs; antes a rotina só
        # era chamada quando um NOVO despacho acontecia, deixando a UI infinita.
        reconcile_orphan_runs(Path(settings.BASE_DIR))
    except Exception:
        pass

    run = (
        ImportRun.objects.filter(requested_by=request.user)
        .prefetch_related("steps")
        .order_by("-created_at")
        .first()
    )
    if not run:
        return JsonResponse({"active": False, "run": None})

    steps = list(run.steps.all().order_by("id"))
    current_step = next((step for step in reversed(steps) if step.status in {"RUNNING", "PENDING"}), None)
    if current_step is None and steps:
        current_step = steps[-1]
    pause_state = queue_pause_state(Path(settings.BASE_DIR))
    active = (
        run.status in {ImportRun.Status.QUEUED, ImportRun.Status.DISPATCHED, ImportRun.Status.RUNNING}
        and not pause_state.get("paused")
    )
    live = read_import_progress(run.pk) or {}
    live_metrics = live.get("metrics") or {}
    return JsonResponse({
        "active": active,
        "queue_paused": bool(pause_state.get("paused")),
        "queue_pause": pause_state,
        "run": {
            "id": run.pk,
            "status": run.status,
            "status_display": run.get_status_display(),
            "file": run.source_file,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
            "new": run.new_count,
            "updated": run.updated_count,
            "unchanged": run.unchanged_count,
            "ignored": run.ignored_count,
            "errors": run.error_count,
            "message": run.message,
            "step": current_step.name if current_step else "Preparando",
            "step_status": current_step.status if current_step else "PENDING",
            "step_message": current_step.message if current_step else "Aguardando início do processamento.",
            "rows_read": getattr(run, "rows_read", 0),
            "rows_valid": getattr(run, "rows_valid", 0),
            "parse_seconds": live_metrics.get("parse_seconds", getattr(run, "parse_seconds", 0)),
            "normalize_seconds": live_metrics.get("normalize_seconds", getattr(run, "normalize_seconds", 0)),
            "preload_seconds": live_metrics.get("preload_seconds", getattr(run, "preload_seconds", 0)),
            "compare_seconds": live_metrics.get("compare_seconds", getattr(run, "compare_seconds", 0)),
            "database_seconds": live_metrics.get("database_seconds", getattr(run, "database_seconds", 0)),
            "postprocess_seconds": live_metrics.get("postprocess_seconds", getattr(run, "postprocess_seconds", 0)),
            "process_seconds": live_metrics.get("total_seconds", live_metrics.get("elapsed_seconds", getattr(run, "total_seconds", 0))),
            "live_phase": live.get("phase") or (current_step.name if current_step else "Preparando"),
            "live_message": live.get("message") or (current_step.message if current_step else "Aguardando início do processamento."),
            "live_percent": live.get("percent"),
            "live_current": live.get("current"),
            "live_total": live.get("total"),
            "live_status": live.get("status"),
        },
    })


@login_required
def history(request):
    qs = ImportRun.objects.order_by("-created_at")
    status = request.GET.get("status", "")
    kind = request.GET.get("kind", "")
    if status:
        qs = qs.filter(status=status)
    if kind:
        qs = qs.filter(kind=kind)
    page = Paginator(qs, 25).get_page(request.GET.get("page"))
    selected = None
    if request.GET.get("selected"):
        selected = get_object_or_404(
            ImportRun.objects.prefetch_related("steps"), pk=request.GET["selected"]
        )
    summary = ImportRun.objects.aggregate(
        total=Count("id"),
        success=Count("id", filter=Q(status=ImportRun.Status.SUCCESS)),
        errors=Count("id", filter=Q(status=ImportRun.Status.ERROR)),
        reprocess=Count("id", filter=Q(kind=ImportRun.Kind.HISTORY)),
    )
    total = summary["total"] or 0
    success = summary["success"] or 0
    rate = (success / total * 100) if total else 0
    duration_expr = ExpressionWrapper(F("finished_at") - F("started_at"), output_field=DurationField())
    avg_delta = ImportRun.objects.exclude(started_at=None).exclude(finished_at=None).aggregate(avg=Avg(duration_expr))["avg"]
    avg_duration = avg_delta.total_seconds() if avg_delta else 0
    return render(
        request,
        "ssw/history.html",
        {
            "page_obj": page,
            "selected_run": selected,
            "total_runs": total,
            "success_rate": rate,
            "avg_duration": avg_duration,
            "error_runs": summary["errors"] or 0,
            "reprocess_runs": summary["reprocess"] or 0,
            "status_choices": ImportRun.Status.choices,
            "kind_choices": ImportRun.Kind.choices,
            "queue_pause": queue_pause_state(Path(settings.BASE_DIR)),
        },
    )


@login_required
def resume_queue_view(request):
    if request.method != "POST":
        return redirect("ssw_imports")
    resume_queue(Path(settings.BASE_DIR))
    try:
        dispatched = dispatch_next_robot_run()
    except Exception as exc:
        dispatched = False
        messages.error(request, f"Fila liberada, mas o próximo despacho falhou: {exc}")
    state_after = queue_pause_state(Path(settings.BASE_DIR))
    if state_after.get("paused"):
        messages.error(
            request,
            f"A fila voltou a pausar no preflight: {state_after.get('error_code', 'ERRO')} — {state_after.get('reason', '')}",
        )
    elif dispatched:
        messages.success(request, "Fila SSW retomada. A próxima janela pendente foi despachada.")
    else:
        messages.success(request, "Fila SSW retomada. Não havia janela pendente pronta para despacho.")
    return redirect("ssw_imports")


@login_required
def retry_failed_run(request, pk):
    if request.method != "POST":
        return redirect("ssw_history")
    failed = get_object_or_404(ImportRun, pk=pk)
    if failed.status != ImportRun.Status.ERROR:
        messages.info(request, "Somente execuções com erro podem ser reprocessadas por este atalho.")
        return redirect("ssw_history")

    with SSWImportLock(timeout=10, lock_name="ssw-queue.lock"):
        active = (
            ImportRun.objects.filter(
                kind=failed.kind,
                start_date=failed.start_date,
                end_date=failed.end_date,
                status__in=[ImportRun.Status.QUEUED, ImportRun.Status.DISPATCHED, ImportRun.Status.RUNNING],
            )
            .order_by("created_at", "pk")
            .first()
        )
        if active:
            new_run = active
        else:
            new_run = ImportRun.objects.create(
                kind=failed.kind,
                start_date=failed.start_date,
                end_date=failed.end_date,
                status=ImportRun.Status.QUEUED,
                requested_by=request.user,
                message=f"Retry isolado da execução #{failed.pk}; demais janelas preservadas.",
            )
            ImportStep.objects.create(
                run=new_run,
                name="Retry isolado",
                status="SUCCESS",
                occurred_at=timezone.now(),
                message=f"Criado a partir da execução com erro #{failed.pk}.",
            )

    # O botão de retry significa: corrigir a janela que falhou e só então seguir a fila.
    resume_queue(Path(settings.BASE_DIR))
    started = dispatch_robot_run(new_run.pk, priority=True)
    if started:
        messages.success(
            request,
            f"Retry da janela {failed.start_date:%d/%m/%Y}–{failed.end_date:%d/%m/%Y} iniciado como execução #{new_run.pk}. As outras janelas não foram recriadas.",
        )
    else:
        messages.info(
            request,
            f"Retry da janela foi preservado na fila como execução #{new_run.pk}; existe outra execução ativa ou o robô está indisponível.",
        )
    return redirect("ssw_imports")


@login_required
def download_diagnostic(request, pk):
    run = get_object_or_404(ImportRun, pk=pk)
    execution_id = execution_id_for(run)
    try:
        package = build_diagnostic_zip(Path(settings.BASE_DIR), execution_id)
    except FileNotFoundError:
        messages.error(request, "Ainda não existem artefatos técnicos para esta execução.")
        return redirect("ssw_history")
    return FileResponse(
        package.open("rb"),
        as_attachment=True,
        filename=f"diagnostico_{execution_id}.zip",
        content_type="application/zip",
    )


@login_required
def download_log(request, pk):
    run = get_object_or_404(ImportRun.objects.prefetch_related("steps"), pk=pk)
    lines = [
        f"Execução #{run.pk}",
        f"Tipo: {run.get_kind_display()}",
        f"Período: {run.start_date} a {run.end_date}",
        f"Status: {run.get_status_display()}",
        f"Arquivo: {run.source_file or '-'}",
        f"Novos: {run.new_count}",
        f"Atualizados: {run.updated_count}",
        f"Sem alteração: {run.unchanged_count}",
        f"Ignorados: {run.ignored_count}",
        f"Erros: {run.error_count}",
        f"Mensagem: {run.message}",
        "",
        "Etapas:",
    ]
    for step in run.steps.all():
        lines.append(
            f"- {step.name} | {step.status} | {step.occurred_at or '-'} | {step.message}"
        )
    response = HttpResponse("\n".join(lines), content_type="text/plain; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="ssw_execucao_{run.pk}.log.txt"'
    return response
