from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from pathlib import Path
import hashlib

from django.db import transaction
from django.utils import timezone

from apps.clients.models import Client, ClientAddress
from apps.drivers.models import Driver, Vehicle
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
    row_is_retained,
    row_route_exit_date,
    split_city_state,
)


@dataclass
class ImportStats:
    new: int = 0
    updated: int = 0
    unchanged: int = 0
    ignored: int = 0
    errors: int = 0
    rows: int = 0
    proofs_created: int = 0


@dataclass
class ImportContext:
    """Caches de identidade para reduzir duplicidade e custo de consultas por linha."""

    clients_by_cnpj: dict[str, Client] = field(default_factory=dict)
    clients_by_normalized_name: dict[str, list[Client]] = field(default_factory=lambda: defaultdict(list))
    blank_clients_by_normalized_name: dict[str, list[Client]] = field(default_factory=lambda: defaultdict(list))

    @classmethod
    def from_database(cls):
        ctx = cls()
        for client in Client.objects.all().only("id", "name", "cnpj"):
            ctx.register(client)
        return ctx

    def register(self, client: Client):
        cnpj_key = digits_only(client.cnpj)
        name_key = normalize_text(client.name)
        if cnpj_key:
            self.clients_by_cnpj[cnpj_key] = client
        if client not in self.clients_by_normalized_name[name_key]:
            self.clients_by_normalized_name[name_key].append(client)
        if not cnpj_key and client not in self.blank_clients_by_normalized_name[name_key]:
            self.blank_clients_by_normalized_name[name_key].append(client)

    def promote_cnpj(self, client: Client, cnpj: str):
        name_key = normalize_text(client.name)
        if client in self.blank_clients_by_normalized_name.get(name_key, []):
            self.blank_clients_by_normalized_name[name_key].remove(client)
        client.cnpj = cnpj
        client.save(update_fields=["cnpj"])
        self.clients_by_cnpj[digits_only(cnpj)] = client


def digits_only(value: str | None) -> str:
    return "".join(ch for ch in (value or "") if ch.isdigit())


def aware(value: datetime | None):
    if value is None:
        return None
    if timezone.is_naive(value):
        return timezone.make_aware(value, timezone.get_current_timezone())
    return value


def _status_from_row(row: dict[str, str]) -> str:
    return (
        clean(row.get("DESC OCORR CTRC"))
        or clean(row.get("DESC OCORR ROM"))
        or clean(row.get("SITUACAO"))
    )


def _status_rank(value: str | None) -> int:
    normalized = normalize_text(value)
    return {"": 0, "PENDENTE": 1, "BAIXADO": 2, "CANCELADO": 3}.get(normalized, 0)


def _get_client(row: dict[str, str], ctx: ImportContext) -> tuple[Client, ClientAddress | None]:
    name = clean(row.get("NOME DESTINATARIO")) or "DESTINATARIO NAO INFORMADO"
    payer_name = clean(row.get("NOME PAGADOR"))
    payer_cnpj = clean(row.get("CNPJ PAGADOR"))
    # O relatório não possui CNPJ DESTINATÁRIO explícito. Só utilizar CNPJ PAGADOR
    # quando pagador e destinatário representam a mesma entidade textual.
    safe_cnpj = (
        payer_cnpj
        if payer_cnpj and normalize_text(payer_name) == normalize_text(name)
        else ""
    )
    cnpj_key = digits_only(safe_cnpj)
    name_key = normalize_text(name)

    client = None
    if cnpj_key:
        # CNPJ é a identidade mais forte. Isso também une variações de pontuação do nome.
        client = ctx.clients_by_cnpj.get(cnpj_key)
        if client is None:
            blank_candidates = ctx.blank_clients_by_normalized_name.get(name_key, [])
            if blank_candidates:
                client = blank_candidates[0]
                ctx.promote_cnpj(client, safe_cnpj)
    else:
        blank_candidates = ctx.blank_clients_by_normalized_name.get(name_key, [])
        if blank_candidates:
            client = blank_candidates[0]
        else:
            all_candidates = ctx.clients_by_normalized_name.get(name_key, [])
            # Sem CNPJ, só reutilizar cliente fiscalizado se não houver ambiguidade.
            if len(all_candidates) == 1:
                client = all_candidates[0]

    if client is None:
        client = Client.objects.create(cnpj=safe_cnpj, name=name)
        ctx.register(client)

    street = clean(row.get("LOCAL DE ENTREGA"))
    district = clean(row.get("BAIRRO"))
    postal_code = clean(row.get("CEP ENTREGA"))
    city, state = split_city_state(row.get("CIDADE_ENTREGA"))
    if not (street or city or postal_code):
        return client, None

    normalized = " | ".join(
        part
        for part in [
            normalize_text(street),
            normalize_text(district),
            digits_only(postal_code),
            normalize_text(city),
            state,
        ]
        if part
    )
    address, created = ClientAddress.objects.get_or_create(
        client=client,
        normalized_address=normalized,
        defaults={
            "street": street or "Endereço não informado",
            "district": district,
            "postal_code": postal_code,
            "city": city or "Cidade não informada",
            "state": state,
        },
    )
    if not created:
        updates = {
            "street": street or address.street,
            "district": district or address.district,
            "postal_code": postal_code or address.postal_code,
            "city": city or address.city,
            "state": state or address.state,
        }
        changed = False
        for key, value in updates.items():
            if value and getattr(address, key) != value:
                setattr(address, key, value)
                changed = True
        if changed:
            address.save()
    return client, address


def _get_driver(row: dict[str, str]) -> Driver:
    name = clean(row.get("MOTORISTA")) or "MOTORISTA NAO INFORMADO"
    cpf = digits_only(clean(row.get("CPF DO MOTORISTA")))
    # Linhas atípicas sem CPF recebem chave técnica estável baseada no nome.
    if not cpf:
        cpf = "SEM" + hashlib.sha1(normalize_text(name).encode("utf-8")).hexdigest()[:11].upper()
    driver, _ = Driver.objects.get_or_create(cpf=cpf, defaults={"name": name})
    if driver.name != name and name:
        driver.name = name
        driver.save(update_fields=["name", "updated_at"])
    return driver


def _get_vehicle(row: dict[str, str]) -> Vehicle | None:
    plate = clean(row.get("PLACA")).upper()
    if not plate:
        return None
    vehicle, _ = Vehicle.objects.get_or_create(plate=plate)
    return vehicle


def _get_manifest(row: dict[str, str], driver: Driver, vehicle: Vehicle | None) -> Manifest:
    number = clean(row.get("ROMANEIO"))
    manifest_date = parse_date(row.get("DATA EMISSAO")) or timezone.localdate()
    new_status = clean(row.get("SITUACAO"))
    manifest, created = Manifest.objects.get_or_create(
        number=number,
        defaults={
            "date": manifest_date,
            "driver": driver,
            "vehicle": vehicle,
            "status": new_status,
        },
    )
    if not created:
        changed = False
        # Identidade do romaneio é estável; data, motorista e placa podem ser enriquecidos.
        for field_name, value in {
            "date": manifest_date,
            "driver": driver,
            "vehicle": vehicle,
        }.items():
            if value is not None and getattr(manifest, field_name) != value:
                setattr(manifest, field_name, value)
                changed = True
        # Não regredir BAIXADO/CANCELADO para PENDENTE ao reimportar arquivo antigo.
        if _status_rank(new_status) >= _status_rank(manifest.status) and manifest.status != new_status:
            manifest.status = new_status
            changed = True
        if changed:
            manifest.save()
    return manifest


def _upsert_cte(row: dict[str, str], client: Client) -> tuple[CTe, str]:
    ctrc = clean(row.get("CTRC"))
    static_defaults = {
        "invoice_number": clean(row.get("NUMERO NF")),
        "sender_name": clean(row.get("NOME REMETENTE")),
        "client": client,
        "freight_value": parse_br_decimal(row.get("FRETE CTRC")),
        "merchandise_value": parse_br_decimal(row.get("VLR MERC")),
        "weight_kg": parse_br_decimal(row.get("PESO CALCULO")),
        "volumes": max(parse_int(row.get("QTDE VOL")), 0),
    }
    create_defaults = {**static_defaults, "current_status": _status_from_row(row)}
    cte, created = CTe.objects.get_or_create(ctrc=ctrc, defaults=create_defaults)
    if created:
        return cte, "new"

    changed = False
    for field_name, value in static_defaults.items():
        if getattr(cte, field_name) != value:
            setattr(cte, field_name, value)
            changed = True
    if changed:
        cte.save()
        return cte, "updated"
    return cte, "unchanged"


def _upsert_movement(
    row: dict[str, str],
    cte: CTe,
    manifest: Manifest,
    driver: Driver,
    vehicle: Vehicle | None,
    client: Client,
    address: ClientAddress | None,
):
    movement_date = parse_date(row.get("DATA EMISSAO")) or manifest.date
    new_status = clean(row.get("SITUACAO"))
    defaults = {
        "driver": driver,
        "vehicle": vehicle,
        "client": client,
        "address": address,
        "movement_date": movement_date,
        "status": new_status,
        "occurrence_text": _status_from_row(row),
        "attempt": 1,
        "weight_kg": parse_br_decimal(row.get("PESO CALCULO")),
        "volumes": max(parse_int(row.get("QTDE VOL")), 0),
    }
    movement, created = DeliveryMovement.objects.get_or_create(
        cte=cte, manifest=manifest, defaults=defaults
    )
    if not created:
        changed = False
        for field_name, value in {
            "driver": driver,
            "vehicle": vehicle,
            "client": client,
            "address": address,
            "movement_date": movement_date,
            "weight_kg": parse_br_decimal(row.get("PESO CALCULO")),
            "volumes": max(parse_int(row.get("QTDE VOL")), 0),
        }.items():
            if getattr(movement, field_name) != value:
                setattr(movement, field_name, value)
                changed = True
        if _status_rank(new_status) >= _status_rank(movement.status) and movement.status != new_status:
            movement.status = new_status
            changed = True
        # occurrence_text será recalculado pela ocorrência mais recente após o upsert.
        if changed:
            movement.save()

    # Primeira/última visita usam SAIDA PARA ENTREGA quando ela está disponível na linha.
    service_date = row_route_exit_date(row) or movement_date
    client_changed = False
    if client.first_delivery_at is None or service_date < client.first_delivery_at:
        client.first_delivery_at = service_date
        client_changed = True
    if client.last_delivery_at is None or service_date > client.last_delivery_at:
        client.last_delivery_at = service_date
        client_changed = True
    if client_changed:
        client.save(update_fields=["first_delivery_at", "last_delivery_at"])
    return movement


def _refresh_cte_current_status(cte: CTe, fallback_status: str) -> bool:
    """Deriva status atual apenas da trilha CTRC; ROM é histórico da rota."""
    latest = (
        cte.occurrences.filter(occurred_at__isnull=False, source="SSW_CTRC")
        .order_by("-occurred_at", "-imported_at")
        .first()
    )
    status = clean(latest.description) if latest and clean(latest.description) else clean(fallback_status)
    if status and cte.current_status != status:
        cte.current_status = status
        cte.save(update_fields=["current_status", "last_seen_at"])
        return True
    return False


def _refresh_movement_occurrence_text(movement: DeliveryMovement, fallback_status: str):
    latest = (
        movement.occurrences.filter(occurred_at__isnull=False)
        .order_by("-occurred_at", "-imported_at")
        .first()
    )
    text = clean(latest.description) if latest and clean(latest.description) else clean(fallback_status)
    if text and movement.occurrence_text != text:
        movement.occurrence_text = text
        movement.save(update_fields=["occurrence_text"])


def _upsert_occurrences(row: dict[str, str], cte: CTe, movement: DeliveryMovement):
    snapshot = retention_snapshot(row)
    retained_occurrence_at = None
    for code, description, occurred_at, scope in iter_occurrences(row):
        occurred_at = aware(occurred_at)
        source = f"SSW_{scope}"
        lookup = {
            "cte": cte,
            "code": code,
            "description": description or "Ocorrência sem descrição",
            "occurred_at": occurred_at,
            "source": source,
        }
        if scope == "ROMANEIO":
            lookup["movement"] = movement
        occurrence, _created = DeliveryOccurrence.objects.get_or_create(
            **lookup,
            defaults={"movement": movement if scope == "ROMANEIO" else None},
        )
        desired_movement = movement if scope == "ROMANEIO" else None
        if occurrence.movement_id != getattr(desired_movement, "pk", None):
            occurrence.movement = desired_movement
            occurrence.save(update_fields=["movement"])

        normalized_description = normalize_text(description)
        if normalized_description == "ENTREGUE" or normalized_description.startswith("ENTREGUE "):
            if occurred_at and (cte.delivered_at is None or occurred_at > cte.delivered_at):
                cte.delivered_at = occurred_at
                cte.save(update_fields=["delivered_at", "last_seen_at"])
        if code.strip() == "34" or "MERCADORIA EM CONFERENCIA NO CLIENTE" in normalized_description:
            if occurred_at is not None:
                if retained_occurrence_at is None or occurred_at < retained_occurrence_at:
                    retained_occurrence_at = occurred_at

    _refresh_cte_current_status(cte, _status_from_row(row))
    _refresh_movement_occurrence_text(movement, _status_from_row(row))
    return retained_occurrence_at, snapshot


def _upsert_retained_proof(
    row: dict[str, str],
    cte: CTe,
    manifest: Manifest,
    driver: Driver,
    client: Client,
    address: ClientAddress | None,
    retained_at,
    snapshot,
):
    if not snapshot.historically_retained:
        return False
    if retained_at is None:
        fallback_date = row_route_exit_date(row)
        planned = parse_date(row.get("PREV ENTREGA CTRC"))
        recovery_date = snapshot.recovered_at.date() if snapshot.recovered_at else None
        if fallback_date is None and planned and planned >= manifest.date and (recovery_date is None or planned <= recovery_date):
            fallback_date = planned
        fallback_date = fallback_date or manifest.date
        retained_at = timezone.make_aware(
            datetime.combine(fallback_date, time(hour=12)),
            timezone.get_current_timezone(),
        )

    latest_ctrc = (
        cte.occurrences.filter(occurred_at__isnull=False, source="SSW_CTRC")
        .order_by("-occurred_at", "-imported_at")
        .first()
    )
    latest_code = clean(latest_ctrc.code) if latest_ctrc else snapshot.ctrc_code
    latest_desc = clean(latest_ctrc.description) if latest_ctrc else snapshot.ctrc_description
    latest_at = latest_ctrc.occurred_at if latest_ctrc else aware(snapshot.ctrc_occurred_at)
    delivered_after_retention = bool(
        is_delivered_occurrence(latest_code, latest_desc)
        and latest_at is not None
        and latest_at >= retained_at
    )

    proof, created = RetainedProof.objects.get_or_create(
        cte=cte,
        defaults={
            "invoice_number": clean(row.get("NUMERO NF")),
            "client": client,
            "address": address,
            "original_driver": driver,
            "original_manifest": manifest,
            "retained_at": retained_at,
            "freight_value": parse_br_decimal(row.get("FRETE CTRC")),
            "merchandise_value": parse_br_decimal(row.get("VLR MERC")),
            "weight_kg": parse_br_decimal(row.get("PESO CALCULO")),
            "volumes": max(parse_int(row.get("QTDE VOL")), 0),
            "status": RetainedProof.Status.RECOVERED if delivered_after_retention else RetainedProof.Status.WAITING,
            "recovered_at": latest_at if delivered_after_retention else None,
            "note": (
                f"[SSW AUTO] Baixa automática pelo estado consolidado do CTRC em "
                f"{timezone.localtime(latest_at):%d/%m/%Y %H:%M}."
                if delivered_after_retention else ""
            ),
        },
    )
    if created:
        return True

    changed = False
    if retained_at and retained_at < proof.retained_at:
        proof.retained_at = retained_at
        proof.original_driver = driver
        proof.original_manifest = manifest
        changed = True

    updates = {
        "invoice_number": clean(row.get("NUMERO NF")),
        "client": client,
        "address": address,
        "freight_value": parse_br_decimal(row.get("FRETE CTRC")),
        "merchandise_value": parse_br_decimal(row.get("VLR MERC")),
        "weight_kg": parse_br_decimal(row.get("PESO CALCULO")),
        "volumes": max(parse_int(row.get("QTDE VOL")), 0),
    }
    for field_name, value in updates.items():
        if getattr(proof, field_name) != value:
            setattr(proof, field_name, value)
            changed = True

    manual_recovery = bool(
        proof.status == RetainedProof.Status.RECOVERED
        and (proof.confirmed_by_id is not None or proof.recovery_driver_id is not None)
    )
    if not manual_recovery and proof.status != RetainedProof.Status.CANCELED:
        if delivered_after_retention:
            auto_note = (
                f"[SSW AUTO] Baixa automática pelo estado consolidado do CTRC em "
                f"{timezone.localtime(latest_at):%d/%m/%Y %H:%M}."
            )
            if proof.status != RetainedProof.Status.RECOVERED:
                proof.status = RetainedProof.Status.RECOVERED
                changed = True
            if proof.recovered_at != latest_at:
                proof.recovered_at = latest_at
                changed = True
            if not proof.note or proof.note.startswith("[SSW AUTO]"):
                if proof.note != auto_note:
                    proof.note = auto_note
                    changed = True
        elif is_retention_occurrence(latest_code, latest_desc):
            if proof.status == RetainedProof.Status.RECOVERED and proof.note.startswith("[SSW AUTO]"):
                if proof.recovered_at is None or latest_at is None or latest_at > proof.recovered_at:
                    proof.status = RetainedProof.Status.WAITING
                    proof.recovered_at = None
                    proof.note = "[SSW AUTO] Retenção reaberta pelo estado consolidado do CTRC."
                    changed = True
    if changed:
        proof.save()
    return False


def import_ssw_delivery_file(
    file_path: str | Path,
    kind: str = ImportRun.Kind.MANUAL,
    requested_by=None,
    *,
    existing_run: ImportRun | None = None,
    source_label: str = "Importação manual",
) -> tuple[ImportRun, ImportStats]:
    import os
    if os.getenv("SSW_IMPORT_ENGINE", "v2").strip().lower() not in {"v1", "legacy"}:
        from .import_engine_v2 import import_ssw_delivery_file_v2
        return import_ssw_delivery_file_v2(
            file_path, kind=kind, requested_by=requested_by, existing_run=existing_run, source_label=source_label
        )
    parsed = read_ssw_delivery_file(file_path)
    start_date = parsed.period_start or timezone.localdate()
    end_date = parsed.period_end or start_date
    if existing_run is None:
        run = ImportRun.objects.create(
            kind=kind,
            start_date=start_date,
            end_date=end_date,
            status=ImportRun.Status.RUNNING,
            started_at=timezone.now(),
            source_file=Path(file_path).name,
            requested_by=requested_by,
        )
        ImportStep.objects.create(
            run=run,
            name="Solicitação",
            status="SUCCESS",
            occurred_at=timezone.now(),
            message=f"{source_label} recebida pelo sistema.",
        )
    else:
        run = existing_run
        run.status = ImportRun.Status.RUNNING
        run.started_at = run.started_at or timezone.now()
        run.source_file = Path(file_path).name
        # O período solicitado continua sendo a referência da execução. O período
        # lido é registrado nos passos e pode ser diferente apenas em arquivos
        # parciais/limítrofes, sem criar outro ImportRun.
        run.save(update_fields=["status", "started_at", "source_file"])

    ImportStep.objects.filter(run=run, name="Validação", status="RUNNING").update(
        status="SUCCESS",
        occurred_at=timezone.now(),
        message=f"Arquivo validado; {len(parsed.rows)} linhas válidas; período detectado {start_date:%d/%m/%Y} a {end_date:%d/%m/%Y}.",
    )
    ImportStep.objects.create(
        run=run,
        name="Leitura e validação",
        status="SUCCESS",
        occurred_at=timezone.now(),
        message=f"{len(parsed.rows)} linhas válidas lidas; período {start_date:%d/%m/%Y} a {end_date:%d/%m/%Y}.",
    )
    ImportStep.objects.create(
        run=run,
        name="Normalização e comparação",
        status="RUNNING",
        occurred_at=timezone.now(),
        message="Normalizando entidades e comparando com o banco.",
    )

    stats = ImportStats(rows=len(parsed.rows))
    try:
        with transaction.atomic():
            ctx = ImportContext.from_database()
            for row in parsed.rows:
                ctrc = clean(row.get("CTRC"))
                romaneio = clean(row.get("ROMANEIO"))
                if not ctrc or not romaneio:
                    stats.ignored += 1
                    continue
                try:
                    driver = _get_driver(row)
                    vehicle = _get_vehicle(row)
                    client, address = _get_client(row, ctx)
                    manifest = _get_manifest(row, driver, vehicle)
                    cte, result = _upsert_cte(row, client)
                    if result == "new":
                        stats.new += 1
                    elif result == "updated":
                        stats.updated += 1
                    else:
                        stats.unchanged += 1
                    movement = _upsert_movement(
                        row, cte, manifest, driver, vehicle, client, address
                    )
                    retained_at, retention_state = _upsert_occurrences(row, cte, movement)
                    if _upsert_retained_proof(
                        row,
                        cte,
                        manifest,
                        driver,
                        client,
                        address,
                        retained_at,
                        retention_state,
                    ):
                        stats.proofs_created += 1
                except Exception:
                    stats.errors += 1
                    raise

        ImportStep.objects.filter(
            run=run, name="Normalização e comparação", status="RUNNING"
        ).update(
            status="SUCCESS",
            message=f"Comparação concluída: {stats.new} novos, {stats.updated} atualizados, {stats.unchanged} sem alteração.",
        )
        ImportStep.objects.create(
            run=run,
            name="Processamento",
            status="SUCCESS",
            occurred_at=timezone.now(),
            message=f"{stats.rows} linhas processadas; {stats.proofs_created} comprovantes retidos criados.",
        )
        run.status = ImportRun.Status.WARNING if stats.errors or stats.ignored else ImportRun.Status.SUCCESS
        run.new_count = stats.new
        run.updated_count = stats.updated
        run.unchanged_count = stats.unchanged
        run.ignored_count = stats.ignored
        run.error_count = stats.errors
        run.finished_at = timezone.now()
        run.message = f"Linhas: {stats.rows}; comprovantes retidos criados: {stats.proofs_created}"
        run.save()
        ImportStep.objects.create(
            run=run,
            name="Banco atualizado",
            status="SUCCESS",
            occurred_at=timezone.now(),
            message=run.message,
        )
        return run, stats
    except Exception as exc:
        ImportStep.objects.filter(
            run=run, name="Normalização e comparação", status="RUNNING"
        ).update(
            status="ERROR",
            occurred_at=timezone.now(),
            message="Processamento interrompido por erro.",
        )
        run.status = ImportRun.Status.ERROR
        run.error_count = stats.errors or 1
        run.finished_at = timezone.now()
        run.message = str(exc)[:4000]
        run.save()
        ImportStep.objects.create(
            run=run,
            name="Erro",
            status="ERROR",
            occurred_at=timezone.now(),
            message=run.message,
        )
        raise
