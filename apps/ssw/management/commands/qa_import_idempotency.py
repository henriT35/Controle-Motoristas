from __future__ import annotations

import hashlib
import json
import random
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.clients.models import Client, ClientAddress
from apps.drivers.models import Driver, Vehicle
from apps.operations.models import CTe, DeliveryMovement, DeliveryOccurrence, Manifest
from apps.proofs.models import RetainedProof
from apps.ssw.importer import import_ssw_delivery_file
from apps.ssw.models import ImportRun
from apps.ssw.parsers import read_ssw_delivery_file


BUSINESS_MODELS = [Driver, Vehicle, Client, ClientAddress, CTe, Manifest, DeliveryMovement, DeliveryOccurrence, RetainedProof]


def counts():
    return {model.__name__: model.objects.count() for model in BUSINESS_MODELS}


def _stable(value):
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def affected_fingerprint(ctrcs: set[str], manifests: set[str]) -> str:
    cte_rows = list(CTe.objects.filter(ctrc__in=ctrcs).values(
        "ctrc", "invoice_number", "sender_name", "client_id", "freight_value", "merchandise_value",
        "weight_kg", "volumes", "current_status", "delivered_at"
    ))
    cte_ids = [row["id"] for row in CTe.objects.filter(ctrc__in=ctrcs).values("id")]
    manifest_rows = list(Manifest.objects.filter(number__in=manifests).values(
        "number", "date", "driver_id", "vehicle_id", "status"
    ))
    manifest_ids = [row["id"] for row in Manifest.objects.filter(number__in=manifests).values("id")]
    movement_rows = list(DeliveryMovement.objects.filter(cte_id__in=cte_ids, manifest_id__in=manifest_ids).values(
        "cte_id", "manifest_id", "driver_id", "vehicle_id", "client_id", "address_id", "movement_date",
        "status", "occurrence_text", "attempt", "weight_kg", "volumes"
    ))
    occurrence_rows = list(DeliveryOccurrence.objects.filter(cte_id__in=cte_ids).values(
        "cte_id", "movement_id", "code", "description", "occurred_at", "source"
    ))
    proof_rows = list(RetainedProof.objects.filter(cte_id__in=cte_ids).values(
        "cte_id", "invoice_number", "client_id", "address_id", "original_driver_id", "original_manifest_id",
        "retained_at", "freight_value", "merchandise_value", "weight_kg", "volumes", "status", "recovered_at",
        "recovery_driver_id", "confirmed_by_id", "note"
    ))
    client_ids = {row["client_id"] for row in cte_rows if row.get("client_id")}
    client_ids.update(row["client_id"] for row in movement_rows if row.get("client_id"))
    client_ids.update(row["client_id"] for row in proof_rows if row.get("client_id"))
    address_ids = {row["address_id"] for row in movement_rows if row.get("address_id")}
    address_ids.update(row["address_id"] for row in proof_rows if row.get("address_id"))
    driver_ids = {row["driver_id"] for row in manifest_rows if row.get("driver_id")}
    driver_ids.update(row["driver_id"] for row in movement_rows if row.get("driver_id"))
    driver_ids.update(row["original_driver_id"] for row in proof_rows if row.get("original_driver_id"))
    driver_ids.update(row["recovery_driver_id"] for row in proof_rows if row.get("recovery_driver_id"))
    vehicle_ids = {row["vehicle_id"] for row in manifest_rows if row.get("vehicle_id")}
    vehicle_ids.update(row["vehicle_id"] for row in movement_rows if row.get("vehicle_id"))

    client_rows = list(Client.objects.filter(pk__in=client_ids).values("id", "name", "cnpj", "active", "first_delivery_at", "last_delivery_at"))
    address_rows = list(ClientAddress.objects.filter(pk__in=address_ids).values("id", "client_id", "street", "district", "postal_code", "city", "state", "normalized_address"))
    driver_rows = list(Driver.objects.filter(pk__in=driver_ids).values("id", "name", "cpf", "active"))
    vehicle_rows = list(Vehicle.objects.filter(pk__in=vehicle_ids).values("id", "plate", "description", "active"))

    payload = {
        "drivers": driver_rows,
        "vehicles": vehicle_rows,
        "clients": client_rows,
        "addresses": address_rows,
        "ctes": cte_rows,
        "manifests": manifest_rows,
        "movements": movement_rows,
        "occurrences": occurrence_rows,
        "proofs": proof_rows,
    }
    normalized = json.dumps(payload, default=_stable, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def make_shuffled_copy(source: Path, target: Path):
    raw = source.read_bytes()
    # O SSW usado pelo Painel possui duas linhas de cabeçalho e dados sem quebras internas.
    text = None
    encoding_used = None
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            text = raw.decode(encoding)
            encoding_used = encoding
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise ValueError("Não foi possível decodificar o relatório para teste embaralhado.")
    lines = text.splitlines()
    if len(lines) < 3:
        raise ValueError("Arquivo sem linhas de dados suficientes para teste embaralhado.")
    header = lines[:2]
    data = [line for line in lines[2:] if line.strip()]
    random.Random(20260831).shuffle(data)
    target.write_text("\n".join([*header, *data]) + "\n", encoding=encoding_used)


class Command(BaseCommand):
    help = "QA seguro de idempotência do importador. Faz rollback completo por padrão."

    def add_arguments(self, parser):
        parser.add_argument("file")
        parser.add_argument("--repeat", type=int, default=10)
        parser.add_argument("--commit", action="store_true", help="NÃO recomendado: persiste a rodada de QA.")

    def handle(self, *args, **options):
        source = Path(options["file"]).resolve()
        if not source.exists():
            raise CommandError(f"Arquivo não encontrado: {source}")
        repeat = max(2, int(options["repeat"] or 10))
        parsed = read_ssw_delivery_file(source)
        ctrcs = {str(row.get("CTRC") or "").strip() for row in parsed.rows if str(row.get("CTRC") or "").strip()}
        manifests = {str(row.get("ROMANEIO") or "").strip() for row in parsed.rows if str(row.get("ROMANEIO") or "").strip()}

        self.stdout.write("=" * 72)
        self.stdout.write(" QA IDEMPOTÊNCIA SSW — ROLLBACK SEGURO" if not options["commit"] else " QA IDEMPOTÊNCIA SSW — COMMIT ATIVADO")
        self.stdout.write("=" * 72)
        self.stdout.write(f"Arquivo: {source}")
        self.stdout.write(f"Linhas: {len(parsed.rows)} | CT-es: {len(ctrcs)} | Romaneios: {len(manifests)}")

        failures = []
        timings = []
        with transaction.atomic():
            baseline = counts()
            t0 = perf_counter()
            _run, first_stats = import_ssw_delivery_file(source)
            timings.append(perf_counter() - t0)
            reference_counts = counts()
            reference_hash = affected_fingerprint(ctrcs, manifests)
            self.stdout.write(f"1ª importação: {timings[-1]:.3f}s | novos={first_stats.new} atualizados={first_stats.updated} iguais={first_stats.unchanged}")

            for idx in range(2, repeat + 1):
                t0 = perf_counter()
                _run, stats = import_ssw_delivery_file(source)
                elapsed = perf_counter() - t0
                timings.append(elapsed)
                current_counts = counts()
                current_hash = affected_fingerprint(ctrcs, manifests)
                if current_counts != reference_counts:
                    failures.append(f"repetição #{idx}: contagens de negócio mudaram")
                if current_hash != reference_hash:
                    failures.append(f"repetição #{idx}: fingerprint operacional mudou")
                if stats.new != 0:
                    failures.append(f"repetição #{idx}: stats.new={stats.new}, esperado 0")
                self.stdout.write(f"#{idx}: {elapsed:.3f}s | novos={stats.new} atualizados={stats.updated} iguais={stats.unchanged}")

            with TemporaryDirectory(prefix="painel_qa_") as tmp:
                renamed = Path(tmp) / "MESMO_CONTEUDO_RENOMEADO.sswweb"
                shuffled = Path(tmp) / "LINHAS_EMBARALHADAS.sswweb"
                shutil.copy2(source, renamed)
                make_shuffled_copy(source, shuffled)
                for label, candidate in (("arquivo renomeado", renamed), ("linhas embaralhadas", shuffled)):
                    _run, stats = import_ssw_delivery_file(candidate)
                    current_counts = counts()
                    current_hash = affected_fingerprint(ctrcs, manifests)
                    if current_counts != reference_counts:
                        failures.append(f"{label}: contagens de negócio mudaram")
                    if current_hash != reference_hash:
                        failures.append(f"{label}: fingerprint operacional mudou")
                    if stats.new != 0:
                        failures.append(f"{label}: stats.new={stats.new}, esperado 0")
                    self.stdout.write(f"{label}: novos={stats.new} atualizados={stats.updated} iguais={stats.unchanged}")

            final_counts = counts()
            if not options["commit"]:
                transaction.set_rollback(True)

        self.stdout.write("-" * 72)
        self.stdout.write(f"Baseline banco: {baseline}")
        self.stdout.write(f"Após 1ª importação: {reference_counts}")
        self.stdout.write(f"Fingerprint: {reference_hash}")
        self.stdout.write(f"Tempo 1ª: {timings[0]:.3f}s | média reimportações: {sum(timings[1:]) / max(len(timings)-1,1):.3f}s")
        self.stdout.write("Rollback: " + ("NÃO (commit solicitado)" if options["commit"] else "SIM — banco original preservado"))

        if failures:
            for item in failures:
                self.stderr.write(self.style.ERROR("FAIL: " + item))
            raise CommandError(f"QA falhou com {len(failures)} divergência(s).")
        self.stdout.write(self.style.SUCCESS("PASS — repetição, rename e embaralhamento não alteraram a realidade operacional."))
