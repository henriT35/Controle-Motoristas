from __future__ import annotations

"""Motor de importação SSW v2.

Pipeline em lote: parse -> normalização -> preload -> comparação em memória -> bulk
persistence -> ocorrências/comprovantes -> refresh de status.

O módulo não conhece Playwright e é usado tanto pela importação manual quanto pelo
resultado do robô homologado.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from functools import lru_cache
from datetime import datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from time import perf_counter
import hashlib

from django.db import transaction
from django.utils import timezone

from apps.clients.models import Client, ClientAddress
from apps.drivers.models import Driver, Vehicle
from apps.drivers.evaluation import ensure_actions_activation_date, materialize_exact_pickup_opportunities, sync_quality_events_for_movements, sync_retention_obligations
from apps.core.cache import invalidate_operational_cache
from apps.operations.models import CTe, DeliveryMovement, DeliveryOccurrence, Manifest
from apps.proofs.models import RetainedProof
from .models import ImportRun, ImportStep
from .parsers import (
    clean,
    is_delivered_occurrence,
    is_retention_occurrence,
    iter_occurrences,
    normalize_text,
    parse_br_decimal,
    parse_date,
    parse_int,
    read_ssw_delivery_file,
    retention_snapshot,
    split_city_state,
    validate_delivery_row,
)
from .progress import publish_import_progress
from .import_lock import SSWImportLock


BATCH_SIZE = 1000
IMPORT_ENGINE_BUILD = "0.9.2.0-evaluation-v3+proof-current-state"


@dataclass
class ImportStats:
    new: int = 0
    updated: int = 0
    unchanged: int = 0
    ignored: int = 0
    errors: int = 0
    rows: int = 0
    proofs_created: int = 0
    proofs_recovered: int = 0
    proofs_reopened: int = 0


@dataclass
class TimingBook:
    started: float = field(default_factory=perf_counter)
    values: dict[str, float] = field(default_factory=dict)

    def start(self):
        return perf_counter()

    def stop(self, name: str, started: float):
        self.values[name] = self.values.get(name, 0.0) + (perf_counter() - started)

    @property
    def total(self):
        return perf_counter() - self.started


@dataclass
class PreparedRow:
    ctrc: str
    manifest_number: str
    driver_name: str
    driver_cpf: str
    plate: str
    client_name: str
    safe_cnpj: str
    street: str
    district: str
    postal_code: str
    city: str
    state: str
    normalized_address: str
    manifest_date: object
    movement_date: object
    manifest_status: str
    row_status: str
    invoice_number: str
    sender_name: str
    freight_value: Decimal
    merchandise_value: Decimal
    weight_kg: Decimal
    volumes: int
    occurrences: list[tuple[str, str, datetime | None, str]]
    retained: bool
    rom_retained: bool
    ctrc_retained: bool
    retained_at: datetime | None
    retention_active: bool
    recovered_at: datetime | None
    ctrc_code: str
    ctrc_description: str
    ctrc_occurred_at: datetime | None
    route_exit_date: object
    planned_delivery_date: object


class ClientResolver:
    """Replica a identidade da v1, mas sem queries dentro do loop."""

    def __init__(self, clients):
        self.by_cnpj: dict[str, Client] = {}
        self.by_name: dict[str, list[Client]] = defaultdict(list)
        self.blank_by_name: dict[str, list[Client]] = defaultdict(list)
        for client in clients:
            self.register(client)

    def register(self, client: Client):
        cnpj = digits_only(client.cnpj)
        name = normalize_text(client.name)
        if cnpj:
            self.by_cnpj[cnpj] = client
        if client not in self.by_name[name]:
            self.by_name[name].append(client)
        if not cnpj and client not in self.blank_by_name[name]:
            self.blank_by_name[name].append(client)

    def resolve(self, row: PreparedRow, new_clients: list[Client], promoted: dict[int, Client]):
        cnpj_key = digits_only(row.safe_cnpj)
        name_key = normalize_text(row.client_name)
        client = None
        if cnpj_key:
            client = self.by_cnpj.get(cnpj_key)
            if client is None:
                blank = self.blank_by_name.get(name_key, [])
                if blank:
                    client = blank[0]
                    if client.pk:
                        promoted[client.pk] = client
                    try:
                        self.blank_by_name[name_key].remove(client)
                    except ValueError:
                        pass
                    client.cnpj = row.safe_cnpj
                    self.by_cnpj[cnpj_key] = client
        else:
            blank = self.blank_by_name.get(name_key, [])
            if blank:
                client = blank[0]
            else:
                candidates = self.by_name.get(name_key, [])
                if len(candidates) == 1:
                    client = candidates[0]
        if client is None:
            client = Client(cnpj=row.safe_cnpj, name=row.client_name)
            new_clients.append(client)
            self.register(client)
        return client


@lru_cache(maxsize=65536)
def digits_only(value: str | None) -> str:
    return "".join(ch for ch in (value or "") if ch.isdigit())


def aware(value: datetime | None):
    if value is None:
        return None
    if timezone.is_naive(value):
        return timezone.make_aware(value, timezone.get_current_timezone())
    return value


def _retained_at_or_operational_fallback(row: "PreparedRow") -> datetime:
    """Data determinística para retenção histórica sem DATA OCORR.

    O relatório 036 pode manter ROM=34 sem repetir a data da ocorrência. Nessa
    situação nunca usamos o instante da importação. A ordem de evidência é:
    ocorrência explícita -> SAIDA PARA ENTREGA -> previsão coerente -> emissão do
    romaneio. O meio-dia é usado apenas para representar uma data inferida sem
    inventar uma hora operacional.
    """
    if row.retained_at is not None:
        return row.retained_at
    fallback_date = row.route_exit_date
    if fallback_date is None and row.planned_delivery_date is not None:
        planned = row.planned_delivery_date
        recovered_date = row.recovered_at.date() if row.recovered_at else None
        if planned >= row.manifest_date and (recovered_date is None or planned <= recovered_date):
            fallback_date = planned
    fallback_date = fallback_date or row.manifest_date
    return timezone.make_aware(
        datetime.combine(fallback_date, time(hour=12)),
        timezone.get_current_timezone(),
    )


AUTO_SSW_NOTE_PREFIX = "[SSW AUTO]"


def _manual_recovery_is_authoritative(proof: RetainedProof) -> bool:
    """Baixa confirmada por usuário/motorista nunca é desfeita por reimportação."""
    return bool(
        proof.status == RetainedProof.Status.RECOVERED
        and (proof.confirmed_by_id is not None or proof.recovery_driver_id is not None)
    )


def _automatic_note(action: str, occurred_at: datetime | None) -> str:
    when = timezone.localtime(occurred_at).strftime("%d/%m/%Y %H:%M") if occurred_at else "data não informada"
    return f"{AUTO_SSW_NOTE_PREFIX} {action} pelo estado consolidado do CTRC em {when}."


def _replace_automatic_note(proof: RetainedProof, value: str) -> bool:
    if not proof.note or proof.note.startswith(AUTO_SSW_NOTE_PREFIX):
        if proof.note != value:
            proof.note = value
            return True
    return False


def _status_rank(value: str | None) -> int:
    return {"": 0, "PENDENTE": 1, "BAIXADO": 2, "CANCELADO": 3}.get(normalize_text(value), 0)


def _occurrence_identity(cte_id, code: str | None, description: str | None, occurred_at, source: str | None, movement_id=None):
    """Chave semântica com escopo operacional correto.

    ROMANEIO é evento da tentativa e precisa distinguir o movimento/romaneio.
    CTRC é estado consolidado do documento e sua identidade é apenas do CT-e.
    """
    source_n = clean(source).upper()
    scoped_movement = movement_id if source_n == "SSW_ROMANEIO" else None
    return (cte_id, clean(code), normalize_text(description), occurred_at, source_n, scoped_movement)


def _occurrence_semantic_identity(cte_id, code, description, occurred_at, source):
    """Identidade sem movimento, usada somente para reparar vínculos legados."""
    return (cte_id, clean(code), normalize_text(description), occurred_at, clean(source).upper())


def _row_status(row: dict[str, str]) -> str:
    return clean(row.get("DESC OCORR CTRC")) or clean(row.get("DESC OCORR ROM")) or clean(row.get("SITUACAO"))


def _prepare(raw: dict[str, str]) -> PreparedRow | None:
    ctrc = clean(raw.get("CTRC"))
    manifest_number = clean(raw.get("ROMANEIO"))
    if not ctrc or not manifest_number:
        return None

    driver_name = clean(raw.get("MOTORISTA")) or "MOTORISTA NAO INFORMADO"
    driver_cpf = digits_only(clean(raw.get("CPF DO MOTORISTA")))
    if not driver_cpf:
        driver_cpf = "SEM" + hashlib.sha1(normalize_text(driver_name).encode("utf-8")).hexdigest()[:11].upper()

    client_name = clean(raw.get("NOME DESTINATARIO")) or "DESTINATARIO NAO INFORMADO"
    payer_name = clean(raw.get("NOME PAGADOR"))
    payer_cnpj = clean(raw.get("CNPJ PAGADOR"))
    safe_cnpj = payer_cnpj if payer_cnpj and normalize_text(payer_name) == normalize_text(client_name) else ""

    street = clean(raw.get("LOCAL DE ENTREGA"))
    district = clean(raw.get("BAIRRO"))
    postal_code = clean(raw.get("CEP ENTREGA"))
    city, state = split_city_state(raw.get("CIDADE_ENTREGA"))
    normalized_address = " | ".join(
        p for p in (
            normalize_text(street), normalize_text(district), digits_only(postal_code),
            normalize_text(city), state,
        ) if p
    )

    manifest_date = parse_date(raw.get("DATA EMISSAO")) or timezone.localdate()

    # ROM e CTRC têm semânticas diferentes no relatório 036:
    # - ROMANEIO preserva o evento daquela tentativa/rota;
    # - CTRC representa o estado consolidado do documento.
    snapshot = retention_snapshot(raw)
    occurrences: list[tuple[str, str, datetime | None, str]] = []
    route_exit_date = None
    for code, description, raw_dt, scope in iter_occurrences(raw):
        occurred_at = aware(raw_dt)
        occurrences.append((code, description, occurred_at, scope))
        normalized_description = normalize_text(description)
        if (clean(code) == "85" or "SAIDA PARA ENTREGA" in normalized_description) and occurred_at is not None:
            candidate = occurred_at.date()
            if route_exit_date is None or candidate < route_exit_date:
                route_exit_date = candidate

    rom_retained = is_retention_occurrence(snapshot.rom_code, snapshot.rom_description)
    ctrc_retained = is_retention_occurrence(snapshot.ctrc_code, snapshot.ctrc_description)
    retained_at = aware(snapshot.explicit_retained_at)
    recovered_at = aware(snapshot.recovered_at)
    ctrc_occurred_at = aware(snapshot.ctrc_occurred_at)
    planned_delivery_date = parse_date(raw.get("PREV ENTREGA CTRC"))

    return PreparedRow(
        ctrc=ctrc,
        manifest_number=manifest_number,
        driver_name=driver_name,
        driver_cpf=driver_cpf,
        plate=clean(raw.get("PLACA")).upper(),
        client_name=client_name,
        safe_cnpj=safe_cnpj,
        street=street,
        district=district,
        postal_code=postal_code,
        city=city,
        state=state,
        normalized_address=normalized_address,
        manifest_date=manifest_date,
        movement_date=manifest_date,
        manifest_status=clean(raw.get("SITUACAO")),
        row_status=_row_status(raw),
        invoice_number=clean(raw.get("NUMERO NF")),
        sender_name=clean(raw.get("NOME REMETENTE")),
        freight_value=parse_br_decimal(raw.get("FRETE CTRC")),
        merchandise_value=parse_br_decimal(raw.get("VLR MERC")),
        weight_kg=parse_br_decimal(raw.get("PESO CALCULO")),
        volumes=max(parse_int(raw.get("QTDE VOL")), 0),
        occurrences=occurrences,
        retained=snapshot.historically_retained,
        rom_retained=rom_retained,
        ctrc_retained=ctrc_retained,
        retained_at=retained_at,
        retention_active=snapshot.active_retention,
        recovered_at=recovered_at,
        ctrc_code=snapshot.ctrc_code,
        ctrc_description=snapshot.ctrc_description,
        ctrc_occurred_at=ctrc_occurred_at,
        route_exit_date=route_exit_date,
        planned_delivery_date=planned_delivery_date,
    )


def _step(run: ImportRun, name: str, status: str, message: str):
    existing = ImportStep.objects.filter(run=run, name=name, status="RUNNING").order_by("-id").first()
    if existing:
        existing.status = status
        existing.occurred_at = timezone.now()
        existing.message = message
        existing.save(update_fields=["status", "occurred_at", "message"])
        return existing
    return ImportStep.objects.create(run=run, name=name, status=status, occurred_at=timezone.now(), message=message)


def _set_run_metrics(run: ImportRun, timings: TimingBook, parsed_rows: int, stats: ImportStats):
    mapping = {
        "parse_seconds": timings.values.get("parse", 0.0),
        "normalize_seconds": timings.values.get("normalize", 0.0),
        "preload_seconds": timings.values.get("preload", 0.0),
        "compare_seconds": timings.values.get("compare", 0.0),
        "database_seconds": timings.values.get("database", 0.0),
        "postprocess_seconds": timings.values.get("postprocess", 0.0),
        "total_seconds": timings.total,
        "rows_read": parsed_rows,
        "rows_valid": stats.rows,
    }
    update_fields = []
    for field_name, value in mapping.items():
        if hasattr(run, field_name):
            setattr(run, field_name, value)
            update_fields.append(field_name)
    return update_fields


def import_ssw_delivery_file_v2(
    file_path: str | Path,
    kind: str = ImportRun.Kind.MANUAL,
    requested_by=None,
    *,
    existing_run: ImportRun | None = None,
    source_label: str = "Importação manual",
):
    timings = TimingBook()
    t = timings.start()
    parsed = read_ssw_delivery_file(file_path)
    timings.stop("parse", t)
    start_date = parsed.period_start or timezone.localdate()
    end_date = parsed.period_end or start_date

    if existing_run is None:
        run = ImportRun.objects.create(
            kind=kind, start_date=start_date, end_date=end_date,
            status=ImportRun.Status.RUNNING, started_at=timezone.now(),
            source_file=Path(file_path).name, requested_by=requested_by,
        )
        _step(run, "Solicitação", "SUCCESS", f"{source_label} recebida pelo sistema.")
    else:
        run = existing_run
        run.status = ImportRun.Status.RUNNING
        run.started_at = run.started_at or timezone.now()
        run.source_file = Path(file_path).name
        run.save(update_fields=["status", "started_at", "source_file"])

    def report(phase: str, message: str, percent: float, current: int | None = None, total: int | None = None):
        publish_import_progress(
            run.pk,
            phase=phase,
            message=message,
            percent=percent,
            current=current,
            total=total,
            metrics={
                "parse_seconds": round(timings.values.get("parse", 0.0), 6),
                "normalize_seconds": round(timings.values.get("normalize", 0.0), 6),
                "preload_seconds": round(timings.values.get("preload", 0.0), 6),
                "compare_seconds": round(timings.values.get("compare", 0.0), 6),
                "database_seconds": round(timings.values.get("database", 0.0), 6),
                "elapsed_seconds": round(timings.total, 6),
                "rows": len(parsed.rows),
            },
        )

    _step(run, "Leitura", "SUCCESS", f"{len(parsed.rows)} linhas físicas válidas lidas em {timings.values['parse']:.3f}s.")
    stats = ImportStats()
    report("Leitura", f"{len(parsed.rows)} linhas lidas em {timings.values['parse']:.3f}s.", 8, len(parsed.rows), len(parsed.rows))
    _step(run, "Normalização", "RUNNING", "Normalizando o relatório em memória.")
    report("Normalização", "Normalizando o relatório em memória.", 10, 0, len(parsed.rows))

    import_lock = SSWImportLock()
    try:
        _step(run, "Fila do importador", "RUNNING", "Aguardando exclusividade para aplicar dados SSW.")
        report("Fila do importador", "Aguardando outra importação terminar, se houver.", 9, 0, len(parsed.rows))
        import_lock.acquire()
        _step(run, "Fila do importador", "SUCCESS", "Importador exclusivo adquirido; nenhuma aplicação concorrente será executada.")

        t = timings.start()
        prepared: list[PreparedRow] = []
        validation_examples: list[str] = []
        for row_number, raw in enumerate(parsed.rows, start=1):
            problems = validate_delivery_row(raw)
            if problems:
                stats.errors += 1
                stats.ignored += 1
                if len(validation_examples) < 20:
                    validation_examples.append(f"linha {row_number}: " + "; ".join(problems))
                continue
            row = _prepare(raw)
            if row is None:
                stats.ignored += 1
            else:
                prepared.append(row)
        stats.rows = len(prepared)
        # Snapshot CTRC do próprio relatório atual. Diferente do histórico de
        # DeliveryOccurrence, este dicionário representa o estado consolidado
        # entregue pelo 036 nesta importação e não depende da ordem cronológica
        # dos timestamps, que podem ser corrigidos retroativamente pelo SSW.
        current_ctrc_snapshot = {}
        for item in prepared:
            # A fotografia do CTRC vale para a tentativa representada pela linha.
            # Guardamos também a melhor data operacional disponível para impedir
            # que um arquivo antigo importado depois regrida o estado consolidado
            # já observado em uma tentativa mais nova. A data da ocorrência CTRC
            # NÃO é usada para essa decisão, pois o SSW pode corrigi-la para trás.
            rom_dates = [
                occurred_at.date() for _code, _desc, occurred_at, scope in item.occurrences
                if scope == "ROMANEIO" and occurred_at is not None
            ]
            operational_date = item.route_exit_date or (min(rom_dates) if rom_dates else item.movement_date)
            candidate = (
                clean(item.ctrc_code), clean(item.ctrc_description), item.ctrc_occurred_at, operational_date
            )
            previous = current_ctrc_snapshot.get(item.ctrc)
            has_state = bool(candidate[0] or candidate[1])
            if has_state and (
                previous is None
                or previous[3] is None
                or (candidate[3] is not None and candidate[3] >= previous[3])
            ):
                current_ctrc_snapshot[item.ctrc] = candidate
        timings.stop("normalize", t)
        if validation_examples:
            _step(
                run,
                "Validação de linhas",
                "WARNING",
                f"{stats.errors} linha(s) com formato inválido foram ignoradas. Exemplos: " + " | ".join(validation_examples),
            )
        else:
            _step(run, "Validação de linhas", "SUCCESS", "Nenhum valor numérico/data/hora inválido detectado.")
        _step(run, "Normalização", "SUCCESS", f"{stats.rows} linhas normalizadas em {timings.values['normalize']:.3f}s; {stats.ignored} ignoradas.")
        report("Normalização", f"{stats.rows} linhas normalizadas em {timings.values['normalize']:.3f}s.", 18, stats.rows, stats.rows)

        _step(run, "Pré-carga", "RUNNING", "Carregando referências do banco em lote.")
        report("Pré-carga", "Carregando referências do banco em lote.", 20, 0, stats.rows)
        t = timings.start()
        cpfs = {r.driver_cpf for r in prepared}
        plates = {r.plate for r in prepared if r.plate}
        manifests_keys = {r.manifest_number for r in prepared}
        ctrcs = {r.ctrc for r in prepared}
        existing_drivers = {x.cpf: x for x in Driver.objects.filter(cpf__in=cpfs)}
        existing_vehicles = {x.plate: x for x in Vehicle.objects.filter(plate__in=plates)}
        # A identidade sem CNPJ depende do nome normalizado. Carrega clientes uma única
        # vez por arquivo; a v0.3.0 recarregava toda a tabela novamente após bulk_create.
        client_resolver = ClientResolver(
            Client.objects.all().only("id", "name", "cnpj", "first_delivery_at", "last_delivery_at")
        )
        timings.stop("preload", t)
        _step(run, "Pré-carga", "SUCCESS", f"Referências carregadas em {timings.values['preload']:.3f}s.")
        report("Pré-carga", f"Referências carregadas em {timings.values['preload']:.3f}s.", 26, stats.rows, stats.rows)

        _step(run, "Comparação", "RUNNING", "Comparando entidades em memória e preparando operações bulk.")
        report("Comparação", "Comparando entidades e preparando operações bulk.", 28, 0, stats.rows)
        t = timings.start()
        now = timezone.now()

        # Drivers
        new_drivers: list[Driver] = []
        update_drivers: dict[int, Driver] = {}
        for r in prepared:
            driver = existing_drivers.get(r.driver_cpf)
            if driver is None:
                driver = Driver(cpf=r.driver_cpf, name=r.driver_name, active=True, created_at=now, updated_at=now)
                existing_drivers[r.driver_cpf] = driver
                new_drivers.append(driver)
            elif r.driver_name and driver.name != r.driver_name:
                driver.name = r.driver_name
                driver.updated_at = now
                update_drivers[driver.pk] = driver

        # Vehicles
        new_vehicles: list[Vehicle] = []
        for r in prepared:
            if r.plate and r.plate not in existing_vehicles:
                vehicle = Vehicle(plate=r.plate, active=True)
                existing_vehicles[r.plate] = vehicle
                new_vehicles.append(vehicle)

        # Clients
        new_clients: list[Client] = []
        promoted_clients: dict[int, Client] = {}
        row_client_refs: list[Client] = []
        for r in prepared:
            row_client_refs.append(client_resolver.resolve(r, new_clients, promoted_clients))

        timings.stop("compare", t)
        report("Comparação", f"Comparação em memória concluída em {timings.values['compare']:.3f}s.", 30, stats.rows, stats.rows)

        _step(run, "Persistência base", "RUNNING", "Persistindo identidades e relações em lote.")
        report("Banco · identidades", "Gravando motoristas, veículos e clientes em lote.", 32, 0, stats.rows)
        db_t = timings.start()
        db_phase_times: dict[str, float] = {}
        with transaction.atomic():
            phase_t = perf_counter()
            if new_drivers:
                Driver.objects.bulk_create(new_drivers, batch_size=BATCH_SIZE)
            if update_drivers:
                Driver.objects.bulk_update(list(update_drivers.values()), ["name", "updated_at"], batch_size=BATCH_SIZE)
            if new_vehicles:
                Vehicle.objects.bulk_create(new_vehicles, batch_size=BATCH_SIZE)

            # Clientes exigem uma garantia mais forte que o bulk_create puro.
            # Em bases históricas/reprocessadas pode existir a mesma combinação
            # (cnpj, name) entre o preload e a persistência, ou duas referências
            # legadas convergirem para a mesma identidade. O banco possui UNIQUE
            # (cnpj, name), portanto um único conflito derrubava todo o mês.
            #
            # Persistimos apenas as identidades NOVAS com get_or_create e remapeamos
            # as referências em memória para a linha já existente quando houver
            # conflito. O custo é limitado ao número de clientes novos, não às
            # milhares de linhas do relatório, e elimina a falha por UNIQUE sem
            # usar ignore_conflicts (que esconderia outros erros).
            client_replacements: dict[int, Client] = {}
            for candidate in new_clients:
                persisted, _created = Client.objects.get_or_create(
                    cnpj=candidate.cnpj,
                    name=candidate.name,
                )
                client_replacements[id(candidate)] = persisted

            # Promoções de cliente sem CNPJ -> com CNPJ também podem colidir com
            # uma identidade já consolidada. Nesse caso a linha passa a apontar
            # para o cliente consolidado e o registro legado sem CNPJ é preservado
            # para auditoria, em vez de provocar IntegrityError.
            for candidate in promoted_clients.values():
                conflict = (
                    Client.objects.filter(cnpj=candidate.cnpj, name=candidate.name)
                    .exclude(pk=candidate.pk)
                    .first()
                )
                if conflict is not None:
                    client_replacements[id(candidate)] = conflict
                else:
                    candidate.save(update_fields=["cnpj"])

            row_clients = [client_replacements.get(id(client), client) for client in row_client_refs]

            # Django 5 + SQLite moderno/PostgreSQL devolvem PK no bulk_create para
            # motoristas/veículos. Reconsultar só quando o backend não preencher.
            drivers_by_cpf = existing_drivers
            if new_drivers and any(x.pk is None for x in new_drivers):
                drivers_by_cpf = {x.cpf: x for x in Driver.objects.filter(cpf__in=cpfs)}
            vehicles_by_plate = existing_vehicles
            if new_vehicles and any(x.pk is None for x in new_vehicles):
                vehicles_by_plate = {x.plate: x for x in Vehicle.objects.filter(plate__in=plates)}

            db_phase_times["Identidades"] = perf_counter() - phase_t

            # Endereços: limita a pré-carga aos endereços presentes no lote, em vez
            # de carregar todos os endereços históricos dos clientes envolvidos.
            report("Banco · endereços", "Conferindo endereços do lote.", 42, stats.rows, stats.rows)
            phase_t = perf_counter()
            involved_client_ids = {c.pk for c in row_clients if c and c.pk}
            normalized_address_keys = {
                r.normalized_address for r in prepared if (r.street or r.city or r.postal_code)
            }
            address_qs = ClientAddress.objects.filter(client_id__in=involved_client_ids)
            if normalized_address_keys:
                address_qs = address_qs.filter(normalized_address__in=normalized_address_keys)
            addresses = {(a.client_id, a.normalized_address): a for a in address_qs}
            new_addresses: list[ClientAddress] = []
            update_addresses: dict[int, ClientAddress] = {}
            row_addresses: list[ClientAddress | None] = []
            for r, client in zip(prepared, row_clients):
                if not (r.street or r.city or r.postal_code):
                    row_addresses.append(None)
                    continue
                key = (client.pk, r.normalized_address)
                address = addresses.get(key)
                if address is None:
                    address = ClientAddress(
                        client=client,
                        street=r.street or "Endereço não informado",
                        district=r.district,
                        postal_code=r.postal_code,
                        city=r.city or "Cidade não informada",
                        state=r.state,
                        normalized_address=r.normalized_address,
                    )
                    addresses[key] = address
                    new_addresses.append(address)
                else:
                    changed = False
                    for f, value in {
                        "street": r.street or address.street,
                        "district": r.district or address.district,
                        "postal_code": r.postal_code or address.postal_code,
                        "city": r.city or address.city,
                        "state": r.state or address.state,
                    }.items():
                        if value and getattr(address, f) != value:
                            setattr(address, f, value)
                            changed = True
                    if changed:
                        update_addresses[address.pk] = address
                row_addresses.append(address)
            if new_addresses:
                ClientAddress.objects.bulk_create(new_addresses, batch_size=BATCH_SIZE)
            if update_addresses:
                ClientAddress.objects.bulk_update(
                    list(update_addresses.values()),
                    ["street", "district", "postal_code", "city", "state"],
                    batch_size=BATCH_SIZE,
                )
            if new_addresses and any(a.pk is None for a in new_addresses):
                address_qs = ClientAddress.objects.filter(
                    client_id__in=involved_client_ids,
                    normalized_address__in=normalized_address_keys,
                )
                addresses = {(a.client_id, a.normalized_address): a for a in address_qs}
                row_addresses = [
                    addresses.get((c.pk, r.normalized_address))
                    if (r.street or r.city or r.postal_code) else None
                    for r, c in zip(prepared, row_clients)
                ]
            db_phase_times["Endereços"] = perf_counter() - phase_t

            # Romaneios
            report("Banco · romaneios", "Comparando romaneios em lote.", 52, stats.rows, stats.rows)
            phase_t = perf_counter()
            manifests = {x.number: x for x in Manifest.objects.filter(number__in=manifests_keys)}
            new_manifests: list[Manifest] = []
            update_manifests: dict[int, Manifest] = {}
            for r in prepared:
                driver = drivers_by_cpf[r.driver_cpf]
                vehicle = vehicles_by_plate.get(r.plate) if r.plate else None
                manifest = manifests.get(r.manifest_number)
                if manifest is None:
                    manifest = Manifest(
                        number=r.manifest_number,
                        date=r.manifest_date,
                        driver=driver,
                        vehicle=vehicle,
                        status=r.manifest_status,
                    )
                    manifests[r.manifest_number] = manifest
                    new_manifests.append(manifest)
                else:
                    changed = False
                    for f, value in {"date": r.manifest_date, "driver": driver, "vehicle": vehicle}.items():
                        if value is not None and getattr(manifest, f) != value:
                            setattr(manifest, f, value)
                            changed = True
                    if _status_rank(r.manifest_status) >= _status_rank(manifest.status) and manifest.status != r.manifest_status:
                        manifest.status = r.manifest_status
                        changed = True
                    if changed and manifest.pk:
                        update_manifests[manifest.pk] = manifest
            if new_manifests:
                Manifest.objects.bulk_create(new_manifests, batch_size=BATCH_SIZE)
            if update_manifests:
                Manifest.objects.bulk_update(
                    list(update_manifests.values()),
                    ["date", "driver", "vehicle", "status"],
                    batch_size=BATCH_SIZE,
                )
            if new_manifests and any(m.pk is None for m in new_manifests):
                manifests = {x.number: x for x in Manifest.objects.filter(number__in=manifests_keys)}
            db_phase_times["Romaneios"] = perf_counter() - phase_t

            # CT-es
            report("Banco · CT-es", "Comparando CT-es e evitando UPDATE sem alteração.", 62, stats.rows, stats.rows)
            phase_t = perf_counter()
            ctes = {x.ctrc: x for x in CTe.objects.filter(ctrc__in=ctrcs)}
            new_ctes: list[CTe] = []
            update_ctes: dict[int, CTe] = {}
            fallback_cte_status: dict[str, str] = {}
            for r, client in zip(prepared, row_clients):
                fallback_cte_status[r.ctrc] = r.row_status
                cte = ctes.get(r.ctrc)
                values = {
                    "invoice_number": r.invoice_number,
                    "sender_name": r.sender_name,
                    "client": client,
                    "freight_value": r.freight_value,
                    "merchandise_value": r.merchandise_value,
                    "weight_kg": r.weight_kg,
                    "volumes": r.volumes,
                }
                if cte is None:
                    cte = CTe(
                        ctrc=r.ctrc,
                        current_status=r.row_status,
                        first_seen_at=now,
                        last_seen_at=now,
                        **values,
                    )
                    ctes[r.ctrc] = cte
                    new_ctes.append(cte)
                    stats.new += 1
                else:
                    changed = False
                    for f, value in values.items():
                        if getattr(cte, f) != value:
                            setattr(cte, f, value)
                            changed = True
                    if changed:
                        cte.last_seen_at = now
                        if cte.pk:
                            update_ctes[cte.pk] = cte
                        stats.updated += 1
                    else:
                        stats.unchanged += 1
            if new_ctes:
                CTe.objects.bulk_create(new_ctes, batch_size=BATCH_SIZE)
            if update_ctes:
                CTe.objects.bulk_update(
                    list(update_ctes.values()),
                    ["invoice_number", "sender_name", "client", "freight_value", "merchandise_value", "weight_kg", "volumes", "last_seen_at"],
                    batch_size=BATCH_SIZE,
                )
            if new_ctes and any(c.pk is None for c in new_ctes):
                ctes = {x.ctrc: x for x in CTe.objects.filter(ctrc__in=ctrcs)}
            db_phase_times["CT-es"] = perf_counter() - phase_t

            # Movimentos
            report("Banco · movimentos", "Consolidando movimentos de entrega.", 72, stats.rows, stats.rows)
            phase_t = perf_counter()
            cte_ids = {x.pk for x in ctes.values() if x.pk}
            manifest_ids = {x.pk for x in manifests.values() if x.pk}
            movements = {
                (m.cte_id, m.manifest_id): m
                for m in DeliveryMovement.objects.filter(cte_id__in=cte_ids, manifest_id__in=manifest_ids)
            }
            new_movements: list[DeliveryMovement] = []
            update_movements: dict[int, DeliveryMovement] = {}
            fallback_movement_status: dict[tuple[int, int], str] = {}
            row_movements: list[DeliveryMovement] = []
            client_first: dict[int, object] = {}
            client_last: dict[int, object] = {}
            for r, client, address in zip(prepared, row_clients, row_addresses):
                cte = ctes[r.ctrc]
                manifest = manifests[r.manifest_number]
                driver = drivers_by_cpf[r.driver_cpf]
                vehicle = vehicles_by_plate.get(r.plate) if r.plate else None
                key = (cte.pk, manifest.pk)
                fallback_movement_status[key] = r.row_status
                movement = movements.get(key)
                if movement is None:
                    movement = DeliveryMovement(
                        cte=cte,
                        manifest=manifest,
                        driver=driver,
                        vehicle=vehicle,
                        client=client,
                        address=address,
                        movement_date=r.movement_date,
                        status=r.manifest_status,
                        occurrence_text=r.row_status,
                        attempt=1,
                        weight_kg=r.weight_kg,
                        volumes=r.volumes,
                    )
                    movements[key] = movement
                    new_movements.append(movement)
                else:
                    changed = False
                    for f, value in {
                        "driver": driver,
                        "vehicle": vehicle,
                        "client": client,
                        "address": address,
                        "movement_date": r.movement_date,
                        "weight_kg": r.weight_kg,
                        "volumes": r.volumes,
                    }.items():
                        if getattr(movement, f) != value:
                            setattr(movement, f, value)
                            changed = True
                    if _status_rank(r.manifest_status) >= _status_rank(movement.status) and movement.status != r.manifest_status:
                        movement.status = r.manifest_status
                        changed = True
                    if changed and movement.pk:
                        update_movements[movement.pk] = movement
                row_movements.append(movement)
                service_date = r.route_exit_date or r.movement_date
                if client.pk:
                    if client.pk not in client_first or service_date < client_first[client.pk]:
                        client_first[client.pk] = service_date
                    if client.pk not in client_last or service_date > client_last[client.pk]:
                        client_last[client.pk] = service_date
            if new_movements:
                DeliveryMovement.objects.bulk_create(new_movements, batch_size=BATCH_SIZE)
            if update_movements:
                DeliveryMovement.objects.bulk_update(
                    list(update_movements.values()),
                    ["driver", "vehicle", "client", "address", "movement_date", "weight_kg", "volumes", "status"],
                    batch_size=BATCH_SIZE,
                )
            if new_movements and any(m.pk is None for m in new_movements):
                movements = {
                    (m.cte_id, m.manifest_id): m
                    for m in DeliveryMovement.objects.filter(cte_id__in=cte_ids, manifest_id__in=manifest_ids)
                }
                row_movements = [
                    movements[(ctes[r.ctrc].pk, manifests[r.manifest_number].pk)] for r in prepared
                ]

            clients_to_update = []
            client_by_id = {c.pk: c for c in row_clients if c.pk}
            for client_id, client in client_by_id.items():
                changed = False
                first = client_first.get(client_id)
                last = client_last.get(client_id)
                if first is not None and (client.first_delivery_at is None or first < client.first_delivery_at):
                    client.first_delivery_at = first
                    changed = True
                if last is not None and (client.last_delivery_at is None or last > client.last_delivery_at):
                    client.last_delivery_at = last
                    changed = True
                if changed:
                    clients_to_update.append(client)
            if clients_to_update:
                Client.objects.bulk_update(
                    clients_to_update,
                    ["first_delivery_at", "last_delivery_at"],
                    batch_size=BATCH_SIZE,
                )
            db_phase_times["Movimentos"] = perf_counter() - phase_t

            # Ocorrências: uma única leitura do histórico afetado. A v0.3.0 fazia
            # uma segunda query grande depois do bulk_create só para recalcular o
            # status atual; agora o cálculo usa existing + new em memória.
            report("Banco · ocorrências", "Consolidando histórico e status cronológico.", 84, stats.rows, stats.rows)
            phase_t = perf_counter()
            existing_occurrences = list(
                DeliveryOccurrence.objects.filter(cte_id__in=cte_ids).only(
                    "id", "cte_id", "movement_id", "code", "description", "occurred_at", "source", "imported_at"
                )
            )
            occurrence_by_key = {
                _occurrence_identity(o.cte_id, o.code, o.description, o.occurred_at, o.source, o.movement_id): o
                for o in existing_occurrences
            }
            semantic_existing = defaultdict(list)
            for o in existing_occurrences:
                semantic_existing[_occurrence_semantic_identity(o.cte_id, o.code, o.description, o.occurred_at, o.source)].append(o)
            new_occurrences: list[DeliveryOccurrence] = []
            movement_occurrence_updates: dict[int, DeliveryOccurrence] = {}
            # Origem da retenção: ROM34 é fato da tentativa e SEMPRE vence CTRC34
            # consolidado. O rank impede que um CT-e com várias tentativas fique
            # atribuído ao primeiro romaneio que repetiu CTRC=34.
            retained_by_cte: dict[int, tuple[int, datetime, PreparedRow, DeliveryMovement, Client, ClientAddress | None]] = {}
            for r, movement, client, address in zip(prepared, row_movements, row_clients, row_addresses):
                cte = ctes[r.ctrc]
                if r.retained:
                    evidence_rank = 2 if r.rom_retained else (1 if r.ctrc_retained else 0)
                    prev = retained_by_cte.get(cte.pk)
                    candidate = _retained_at_or_operational_fallback(r)
                    if (
                        prev is None
                        or evidence_rank > prev[0]
                        or (evidence_rank == prev[0] and candidate < prev[1])
                    ):
                        retained_by_cte[cte.pk] = (evidence_rank, candidate, r, movement, client, address)
                for code, description, occurred_at, scope in r.occurrences:
                    desc = description or "Ocorrência sem descrição"
                    source = f"SSW_{scope}"
                    expected_movement_id = movement.pk if source == "SSW_ROMANEIO" else None
                    key = _occurrence_identity(cte.pk, code, desc, occurred_at, source, expected_movement_id)
                    occurrence = occurrence_by_key.get(key)
                    if occurrence is None and source == "SSW_ROMANEIO":
                        # Repara base criada por versões antigas cuja identidade ROM
                        # ignorava o movimento e podia prender um evento ao romaneio
                        # errado quando o mesmo CT-e tinha mais de uma tentativa.
                        semantic_key = _occurrence_semantic_identity(cte.pk, code, desc, occurred_at, source)
                        candidates = semantic_existing.get(semantic_key, [])
                        if len(candidates) == 1 and candidates[0].pk and candidates[0].movement_id is None:
                            # Só repara vínculo comprovadamente ausente. Se a ocorrência
                            # já pertence a outro movimento, criar uma ocorrência nova é
                            # mais seguro do que migrar um fato histórico entre tentativas.
                            occurrence = candidates[0]
                            occurrence.movement = movement
                            movement_occurrence_updates[occurrence.pk] = occurrence
                            occurrence_by_key[key] = occurrence
                    if occurrence is None:
                        occurrence = DeliveryOccurrence(
                            cte=cte,
                            movement=movement if source == "SSW_ROMANEIO" else None,
                            code=code,
                            description=desc,
                            occurred_at=occurred_at,
                            source=source,
                            imported_at=now,
                        )
                        occurrence_by_key[key] = occurrence
                        semantic_existing[_occurrence_semantic_identity(cte.pk, code, desc, occurred_at, source)].append(occurrence)
                        new_occurrences.append(occurrence)
                    elif occurrence.pk:
                        # CTRC é consolidado e não deve continuar parecendo evento da
                        # tentativa. Limpa vínculo legado de versões anteriores.
                        desired_movement = movement if source == "SSW_ROMANEIO" else None
                        if occurrence.movement_id != getattr(desired_movement, "pk", None):
                            occurrence.movement = desired_movement
                            movement_occurrence_updates[occurrence.pk] = occurrence
            if new_occurrences:
                DeliveryOccurrence.objects.bulk_create(new_occurrences, batch_size=BATCH_SIZE)
            if movement_occurrence_updates:
                DeliveryOccurrence.objects.bulk_update(
                    list(movement_occurrence_updates.values()), ["movement"], batch_size=BATCH_SIZE
                )

            # O status consolidado do CT-e vem exclusivamente da trilha CTRC.
            # ROMANEIO descreve a tentativa/rota e não pode sobrescrever AD/AE.
            latest_cte: dict[int, tuple[tuple, str, str, datetime]] = {}
            latest_move: dict[int, tuple[tuple, str]] = {}
            delivered_at: dict[int, datetime] = {}
            for o in [*existing_occurrences, *new_occurrences]:
                if not o.occurred_at:
                    continue
                order_key = (o.occurred_at, o.imported_at or now, o.pk or 0)
                if clean(o.source).upper() == "SSW_CTRC":
                    cte_current = latest_cte.get(o.cte_id)
                    if cte_current is None or order_key > cte_current[0]:
                        latest_cte[o.cte_id] = (order_key, clean(o.code), clean(o.description), o.occurred_at)
                    if is_delivered_occurrence(o.code, o.description):
                        if o.cte_id not in delivered_at or o.occurred_at > delivered_at[o.cte_id]:
                            delivered_at[o.cte_id] = o.occurred_at
                if o.movement_id:
                    move_current = latest_move.get(o.movement_id)
                    if move_current is None or order_key > move_current[0]:
                        latest_move[o.movement_id] = (order_key, clean(o.description))

            # Data operacional mais recente já conhecida por CT-e. Isso é a
            # proteção contra reimportação fora de ordem: um snapshot de uma
            # tentativa antiga não pode apagar o estado que já foi observado em
            # uma tentativa posterior. Usamos movimentos + fatos ROM datados;
            # nunca a data do CTRC consolidado, que pode ser retrocorrigida.
            latest_known_operational_date: dict[int, object] = {}
            known_movement_dates = list(
                DeliveryMovement.objects.filter(cte_id__in=cte_ids).values_list("cte_id", "movement_date")
            )
            for known_cte_id, movement_date in known_movement_dates:
                previous_date = latest_known_operational_date.get(known_cte_id)
                if movement_date and (previous_date is None or movement_date > previous_date):
                    latest_known_operational_date[known_cte_id] = movement_date
            for o in [*existing_occurrences, *new_occurrences]:
                if clean(o.source).upper() != "SSW_ROMANEIO" or not o.occurred_at:
                    continue
                event_date = o.occurred_at.date()
                previous_date = latest_known_operational_date.get(o.cte_id)
                if previous_date is None or event_date > previous_date:
                    latest_known_operational_date[o.cte_id] = event_date

            effective_ctrc_snapshot = {}
            for ctrc, cte in ctes.items():
                snapshot = current_ctrc_snapshot.get(ctrc)
                if snapshot is None:
                    continue
                snapshot_operational_date = snapshot[3]
                latest_known_date = latest_known_operational_date.get(cte.pk)
                if (
                    snapshot_operational_date is not None
                    and latest_known_date is not None
                    and snapshot_operational_date < latest_known_date
                ):
                    # Snapshot antigo: o histórico persistido continua governando.
                    continue
                effective_ctrc_snapshot[ctrc] = snapshot

            cte_updates = []
            for ctrc, cte in ctes.items():
                changed = False
                snapshot = effective_ctrc_snapshot.get(ctrc)
                latest = latest_cte.get(cte.pk)
                status = (snapshot[1] if snapshot else "") or (latest[2] if latest else fallback_cte_status.get(ctrc, ""))
                if status and cte.current_status != status:
                    cte.current_status = status
                    changed = True
                # delivered_at é histórico e pode usar o evento ENTREGUE mais
                # recente conhecido; ele não governa o estado consolidado atual.
                dt = delivered_at.get(cte.pk)
                if dt and (cte.delivered_at is None or dt > cte.delivered_at):
                    cte.delivered_at = dt
                    changed = True
                if changed:
                    cte.last_seen_at = now
                    cte_updates.append(cte)
            if cte_updates:
                CTe.objects.bulk_update(
                    cte_updates,
                    ["current_status", "delivered_at", "last_seen_at"],
                    batch_size=BATCH_SIZE,
                )

            movement_updates = []
            for key, movement in movements.items():
                latest = latest_move.get(movement.pk)
                text = latest[1] if latest else fallback_movement_status.get(key, "")
                if text and movement.occurrence_text != text:
                    movement.occurrence_text = text
                    movement_updates.append(movement)
            if movement_updates:
                DeliveryMovement.objects.bulk_update(
                    movement_updates, ["occurrence_text"], batch_size=BATCH_SIZE
                )
            db_phase_times["Ocorrências"] = perf_counter() - phase_t

            # Comprovantes retidos. ROM=34 cria/preserva o histórico; o estado
            # atual é decidido pelo CTRC mais novo. CTRC=34 mantém a pendência;
            # CTRC=1/ENTREGUE depois da retenção baixa automaticamente o comprovante.
            report("Banco · comprovantes", "Reconciliando retenção histórica x estado atual do CTRC.", 94, len(retained_by_cte), len(retained_by_cte))
            phase_t = perf_counter()
            existing_proofs = {
                p.cte_id: p for p in RetainedProof.objects.filter(cte_id__in=cte_ids)
            }
            new_proofs: list[RetainedProof] = []
            update_proofs: list[RetainedProof] = []
            proof_update_fields = [
                "retained_at", "original_driver", "original_manifest", "invoice_number",
                "client", "address", "freight_value", "merchandise_value", "weight_kg",
                "volumes", "status", "recovered_at", "recovery_driver", "confirmed_by",
                "note", "resolution_source", "last_ssw_code", "last_ssw_description", "last_ssw_at", "updated_at",
            ]

            for cte_id, (retention_rank, retained_at, r, movement, client, address) in retained_by_cte.items():
                cte = ctes[r.ctrc]
                manifest = manifests[r.manifest_number]
                driver = drivers_by_cpf[r.driver_cpf]
                snapshot = effective_ctrc_snapshot.get(r.ctrc)
                latest_state = latest_cte.get(cte_id)
                latest_code = snapshot[0] if snapshot else (latest_state[1] if latest_state else r.ctrc_code)
                latest_desc = snapshot[1] if snapshot else (latest_state[2] if latest_state else r.ctrc_description)
                latest_at = snapshot[2] if snapshot else (latest_state[3] if latest_state else r.ctrc_occurred_at)
                active_retention = is_retention_occurrence(latest_code, latest_desc)
                # v0.9.2: CTRC é o estado consolidado ATUAL. Se o estado atual
                # é 1/ENTREGUE, a retenção histórica está operacionalmente
                # resolvida mesmo quando o SSW corrigiu a data retroativamente
                # ou retained_at foi reconstruído com horário técnico (12:00).
                delivered_current = is_delivered_occurrence(latest_code, latest_desc)
                has_latest_state = bool(clean(latest_code) or clean(latest_desc))
                tracking_state = bool(has_latest_state and not active_retention and not delivered_current)

                proof = existing_proofs.get(cte_id)
                if proof is None:
                    initial_status = (
                        RetainedProof.Status.RECOVERED if delivered_current
                        else RetainedProof.Status.TRACKING if tracking_state
                        else RetainedProof.Status.WAITING
                    )
                    proof = RetainedProof(
                        cte=cte,
                        invoice_number=r.invoice_number,
                        client=client,
                        address=address,
                        original_driver=driver,
                        original_manifest=manifest,
                        retained_at=retained_at,
                        freight_value=r.freight_value,
                        merchandise_value=r.merchandise_value,
                        weight_kg=r.weight_kg,
                        volumes=r.volumes,
                        status=initial_status,
                        recovered_at=latest_at if delivered_current else None,
                        note=(
                            _automatic_note("Resolvido automaticamente pelo SSW", latest_at) if delivered_current
                            else _automatic_note("Acompanhando alteração do SSW", latest_at) if tracking_state
                            else ""
                        ),
                        resolution_source="SSW" if delivered_current else "",
                        last_ssw_code=clean(latest_code),
                        last_ssw_description=clean(latest_desc),
                        last_ssw_at=latest_at,
                        created_at=now,
                        updated_at=now,
                    )
                    new_proofs.append(proof)
                    existing_proofs[cte_id] = proof
                    stats.proofs_created += 1
                    if delivered_current:
                        stats.proofs_recovered += 1
                    continue

                changed = False
                # Corrige bases antigas: data contaminada pelo instante da
                # importação E, principalmente, origem escolhida por CTRC34.
                # Quando existe ROM34, a tentativa real vence mesmo que a data
                # inferida não seja anterior à persistida.
                if retained_at and retained_at < proof.retained_at:
                    proof.retained_at = retained_at
                    changed = True
                if retention_rank >= 2 and (
                    proof.original_driver_id != driver.pk
                    or proof.original_manifest_id != manifest.pk
                ):
                    proof.original_driver = driver
                    proof.original_manifest = manifest
                    changed = True

                for f, value in {
                    "invoice_number": r.invoice_number,
                    "client": client,
                    "address": address,
                    "freight_value": r.freight_value,
                    "merchandise_value": r.merchandise_value,
                    "weight_kg": r.weight_kg,
                    "volumes": r.volumes,
                }.items():
                    if getattr(proof, f) != value:
                        setattr(proof, f, value)
                        changed = True

                for f, value in {
                    "last_ssw_code": clean(latest_code),
                    "last_ssw_description": clean(latest_desc),
                    "last_ssw_at": latest_at,
                }.items():
                    if getattr(proof, f) != value:
                        setattr(proof, f, value)
                        changed = True

                manual_recovery = _manual_recovery_is_authoritative(proof)
                if not manual_recovery and proof.status != RetainedProof.Status.CANCELED:
                    if delivered_current:
                        if proof.status != RetainedProof.Status.RECOVERED:
                            proof.status = RetainedProof.Status.RECOVERED
                            stats.proofs_recovered += 1
                            changed = True
                        if proof.recovered_at != latest_at:
                            proof.recovered_at = latest_at
                            changed = True
                        if proof.recovery_driver_id is not None:
                            proof.recovery_driver = None
                            changed = True
                        if proof.confirmed_by_id is not None:
                            proof.confirmed_by = None
                            changed = True
                        if proof.resolution_source != "SSW":
                            proof.resolution_source = "SSW"
                            changed = True
                        changed = _replace_automatic_note(
                            proof, _automatic_note("Resolvido automaticamente pelo SSW", latest_at)
                        ) or changed
                    elif active_retention:
                        # CTRC34 confirma retenção ativa. Reabre somente baixas
                        # automáticas/estados de acompanhamento; nunca desfaz
                        # recuperação manual validada.
                        if proof.status in {RetainedProof.Status.RECOVERED, RetainedProof.Status.VERIFY, RetainedProof.Status.TRACKING}:
                            if proof.status != RetainedProof.Status.RECOVERED or proof.note.startswith(AUTO_SSW_NOTE_PREFIX):
                                if proof.status == RetainedProof.Status.RECOVERED:
                                    stats.proofs_reopened += 1
                                proof.status = RetainedProof.Status.WAITING
                                proof.recovered_at = None
                                proof.recovery_driver = None
                                proof.confirmed_by = None
                                proof.resolution_source = ""
                                _replace_automatic_note(proof, _automatic_note("Retenção confirmada", latest_at))
                                changed = True
                    elif tracking_state:
                        # 60/53/91/etc. mudaram o estado consolidado, mas não
                        # provam recuperação. Acompanhamos automaticamente sem
                        # criar retirada obrigatória nem penalizar motorista.
                        can_override = (
                            proof.status != RetainedProof.Status.RECOVERED
                            or proof.note.startswith(AUTO_SSW_NOTE_PREFIX)
                        )
                        if can_override and proof.status != RetainedProof.Status.TRACKING:
                            proof.status = RetainedProof.Status.TRACKING
                            proof.recovered_at = None
                            proof.recovery_driver = None
                            proof.confirmed_by = None
                            proof.resolution_source = ""
                            _replace_automatic_note(proof, _automatic_note("Acompanhando alteração do SSW", latest_at))
                            changed = True

                if changed:
                    proof.updated_at = now
                    update_proofs.append(proof)

            if new_proofs:
                RetainedProof.objects.bulk_create(new_proofs, batch_size=BATCH_SIZE)
            if update_proofs:
                # Deduplica por PK caso uma futura extensão passe pelo mesmo objeto mais de uma vez.
                deduped = {p.pk: p for p in update_proofs if p.pk}
                RetainedProof.objects.bulk_update(
                    list(deduped.values()),
                    proof_update_fields,
                    batch_size=BATCH_SIZE,
                )
            db_phase_times["Comprovantes"] = perf_counter() - phase_t

        timings.stop("database", db_t)
        _step(run, "Persistência base", "SUCCESS", f"Banco atualizado em {timings.values['database']:.3f}s usando operações em lote.")
        for phase_name, phase_seconds in db_phase_times.items():
            _step(run, f"DB · {phase_name}", "SUCCESS", f"{phase_name}: {phase_seconds:.3f}s")
        report("Banco concluído", f"Persistência concluída em {timings.values['database']:.3f}s.", 97, stats.rows, stats.rows)

        post_t = timings.start()
        # Materializa ROM13 como evento PENDENTE, sem atribuir culpa. A operação
        # é idempotente e acontece fora do core robot_ssw.
        try:
            ensure_actions_activation_date()
            sync_quality_events_for_movements([m.pk for m in movements.values() if getattr(m, "pk", None)])
            sync_retention_obligations()
            # Materializa a obrigação pela rota, não pela abertura do Portal.
            materialize_exact_pickup_opportunities(start=start_date, end=end_date, force=True)
        except Exception as exc:
            _step(run, "Avaliação V3", "WARNING", f"Falha ao sincronizar eventos/obrigações: {exc}")
        invalidate_operational_cache("ssw-import-completed")
        # O custo de reconstruir as fotografias mais acessadas fica no
        # pós-processamento da importação, nunca no primeiro clique do usuário.
        try:
            from apps.core.warmup import warm_navigation_cache
            warmed = warm_navigation_cache()
            _step(run, "Cache de navegação", "SUCCESS", f"Fotografias preparadas: {warmed}")
        except Exception as exc:
            _step(run, "Cache de navegação", "WARNING", f"Pré-aquecimento não concluído: {exc}")
        timings.stop("postprocess", post_t)
        _step(run, "Pós-processamento", "SUCCESS", "Histórico, ocorrências e comprovantes consolidados sem recalcular períodos não afetados.")
        report("Finalizando", "Atualizando métricas e liberando a execução.", 99, stats.rows, stats.rows)

        run.status = ImportRun.Status.WARNING if stats.errors or stats.ignored else ImportRun.Status.SUCCESS
        run.new_count = stats.new
        run.updated_count = stats.updated
        run.unchanged_count = stats.unchanged
        run.ignored_count = stats.ignored
        run.error_count = stats.errors
        run.finished_at = timezone.now()
        run.message = (
            f"Engine {IMPORT_ENGINE_BUILD} · {stats.rows} linhas · {stats.new} novos · {stats.updated} atualizados · "
            f"{stats.unchanged} sem alteração · {stats.proofs_created} retenções criadas · "
            f"{stats.proofs_recovered} baixas automáticas · {stats.proofs_reopened} reaberturas · {timings.total:.2f}s"
        )
        metric_fields = _set_run_metrics(run, timings, len(parsed.rows), stats)
        run.save(update_fields=["status", "new_count", "updated_count", "unchanged_count", "ignored_count", "error_count", "finished_at", "message", *metric_fields])
        _step(run, "Banco atualizado", "SUCCESS", run.message)
        publish_import_progress(
            run.pk, phase="Concluído", message=run.message, percent=100, current=stats.rows, total=stats.rows,
            metrics={
                "parse_seconds": round(timings.values.get("parse", 0.0), 6),
                "normalize_seconds": round(timings.values.get("normalize", 0.0), 6),
                "preload_seconds": round(timings.values.get("preload", 0.0), 6),
                "compare_seconds": round(timings.values.get("compare", 0.0), 6),
                "database_seconds": round(timings.values.get("database", 0.0), 6),
                "postprocess_seconds": round(timings.values.get("postprocess", 0.0), 6),
                "total_seconds": round(timings.total, 6),
            },
            status=run.status,
        )
        return run, stats
    except Exception as exc:
        stats.errors += 1
        run.status = ImportRun.Status.ERROR
        run.error_count = stats.errors
        run.finished_at = timezone.now()
        run.message = str(exc)[:4000]
        metric_fields = _set_run_metrics(run, timings, len(parsed.rows), stats)
        run.save(update_fields=["status", "error_count", "finished_at", "message", *metric_fields])
        _step(run, "Erro", "ERROR", run.message)
        publish_import_progress(
            run.pk, phase="Erro", message=run.message, percent=100, current=stats.rows, total=stats.rows,
            metrics={"total_seconds": round(timings.total, 6)}, status="ERROR"
        )
        raise
    finally:
        import_lock.release()
