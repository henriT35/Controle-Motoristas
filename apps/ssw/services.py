from datetime import date, timedelta
from django.utils import timezone
from .models import ImportRun, ImportStep
from .dispatch import dispatch_robot_run
from .import_lock import SSWImportLock


def queue_import(start_date, end_date, kind="MANUAL", requested_by=None):
    # Lock curto cross-processo fecha a corrida entre duas abas/processos que
    # consultariam "não existe" ao mesmo tempo e criariam jobs duplicados.
    with SSWImportLock(timeout=10, lock_name="ssw-queue.lock"):
        active = (
            ImportRun.objects.filter(
                kind=kind,
                start_date=start_date,
                end_date=end_date,
                status__in=[
                    ImportRun.Status.QUEUED,
                    ImportRun.Status.DISPATCHED,
                    ImportRun.Status.RUNNING,
                ],
            )
            .order_by("created_at", "pk")
            .first()
        )
        if active:
            return active.pk

        run = ImportRun.objects.create(
            kind=kind, start_date=start_date, end_date=end_date, requested_by=requested_by,
            status=ImportRun.Status.QUEUED, message="Aguardando executor do robô SSW real."
        )
        ImportStep.objects.create(run=run, name="Solicitação", status="SUCCESS", occurred_at=timezone.now(), message="Período registrado pelo orquestrador.")
        ImportStep.objects.create(run=run, name="Robô SSW", status="PENDING", message="Aguardando executor do robô SSW.")

    # Despacho fica fora do lock de fila para não bloquear novas consultas durante
    # preflight/Playwright. O status já existe e impede duplicidade.
    dispatch_robot_run(run.pk)
    run.refresh_from_db(fields=["status", "message"])
    if run.status == ImportRun.Status.DISPATCHED:
        run.message = "Execução enviada ao robô SSW."
        run.save(update_fields=["message"])
    return run.pk


def month_chunks(start_date: date, end_date: date):
    """Divide qualquer intervalo em janelas mensais fechadas.

    Evita pedir ao SSW uma consulta anual gigante e respeita o comportamento de
    relatórios que trabalham melhor com aproximadamente um mês por execução.
    """
    if start_date > end_date:
        start_date, end_date = end_date, start_date
    cursor = start_date
    while cursor <= end_date:
        if cursor.month == 12:
            next_month = date(cursor.year + 1, 1, 1)
        else:
            next_month = date(cursor.year, cursor.month + 1, 1)
        chunk_end = min(end_date, next_month - timedelta(days=1))
        yield cursor, chunk_end
        cursor = chunk_end + timedelta(days=1)


def queue_period_chunks(start_date: date, end_date: date, kind=ImportRun.Kind.HISTORY, requested_by=None):
    """Quebra qualquer solicitação acima de 31 dias em janelas mensais.

    O limite pertence ao executor SSW, portanto vale para HISTORY, MONTH e FAST
    quando alguém informar manualmente um intervalo maior que um mês.
    """
    return [
        queue_import(a, b, kind=kind, requested_by=requested_by)
        for a, b in month_chunks(start_date, end_date)
    ]


def queue_history(start_date: date, end_date: date, requested_by=None):
    # Compatibilidade com chamadas antigas.
    return queue_period_chunks(
        start_date, end_date, kind=ImportRun.Kind.HISTORY, requested_by=requested_by
    )
