from __future__ import annotations

from collections import defaultdict

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count, Sum

from apps.clients.models import Client, ClientAddress
from apps.drivers.models import Driver, Vehicle
from apps.operations.models import CTe, DeliveryMovement, DeliveryOccurrence, Manifest
from apps.proofs.models import RetainedProof
from apps.ssw.models import ImportRun
from apps.ssw.parsers import normalize_text


def digits_only(value):
    return "".join(ch for ch in (value or "") if ch.isdigit())


class Command(BaseCommand):
    help = "Auditoria somente leitura de duplicidade/integridade operacional SSW."

    def handle(self, *args, **options):
        issues = []

        def duplicate_count(qs, *fields):
            return list(qs.values(*fields).annotate(n=Count("id")).filter(n__gt=1))

        checks = {
            "Driver.cpf": duplicate_count(Driver.objects.all(), "cpf"),
            "Vehicle.plate": duplicate_count(Vehicle.objects.all(), "plate"),
            "CTe.ctrc": duplicate_count(CTe.objects.all(), "ctrc"),
            "Manifest.number": duplicate_count(Manifest.objects.all(), "number"),
            "ClientAddress(client,address)": duplicate_count(ClientAddress.objects.all(), "client_id", "normalized_address"),
            "Movement(cte,manifest)": duplicate_count(DeliveryMovement.objects.all(), "cte_id", "manifest_id"),
            "Proof.cte": duplicate_count(RetainedProof.objects.all(), "cte_id"),
        }
        for label, rows in checks.items():
            if rows:
                issues.append(f"{label}: {len(rows)} chave(s) duplicada(s)")

        # CNPJ é normalizado em Python porque o banco pode conter pontuação diferente.
        clients_by_cnpj = defaultdict(list)
        for client in Client.objects.exclude(cnpj="").only("id", "cnpj", "name"):
            key = digits_only(client.cnpj)
            if key:
                clients_by_cnpj[key].append(client)
        duplicate_cnpj = {k: v for k, v in clients_by_cnpj.items() if len(v) > 1}
        if duplicate_cnpj:
            issues.append(f"Client.cnpj normalizado: {len(duplicate_cnpj)} CNPJ(s) com mais de um Client")

        # Fingerprint semântico das ocorrências, igual ao engine v0.3.0.3.
        occurrences = defaultdict(list)
        for o in DeliveryOccurrence.objects.only("id", "cte_id", "code", "description", "occurred_at", "source"):
            key = (o.cte_id, (o.code or "").strip(), normalize_text(o.description), o.occurred_at, (o.source or "").strip().upper())
            occurrences[key].append(o.id)
        duplicate_occurrences = {k: ids for k, ids in occurrences.items() if len(ids) > 1}
        if duplicate_occurrences:
            issues.append(f"DeliveryOccurrence semântica: {len(duplicate_occurrences)} evento(s) duplicado(s)")

        metrics = CTe.objects.aggregate(
            ctes=Count("id"),
            freight=Sum("freight_value"),
            weight=Sum("weight_kg"),
        )
        counts = {
            "Drivers": Driver.objects.count(),
            "Vehicles": Vehicle.objects.count(),
            "Clients": Client.objects.count(),
            "Addresses": ClientAddress.objects.count(),
            "CTes": CTe.objects.count(),
            "Manifests": Manifest.objects.count(),
            "Movements": DeliveryMovement.objects.count(),
            "Occurrences": DeliveryOccurrence.objects.count(),
            "RetainedProofs": RetainedProof.objects.count(),
            "ImportRuns": ImportRun.objects.count(),
        }

        self.stdout.write("=" * 72)
        self.stdout.write(" QA INTEGRIDADE — PAINEL MOTORISTAS")
        self.stdout.write("=" * 72)
        for label, value in counts.items():
            self.stdout.write(f"{label:18}: {value}")
        self.stdout.write(f"Frete total        : {metrics['freight'] or 0}")
        self.stdout.write(f"Peso total         : {metrics['weight'] or 0}")
        self.stdout.write("-" * 72)
        if duplicate_cnpj:
            self.stdout.write("Amostra CNPJ duplicado:")
            for cnpj, clients in list(duplicate_cnpj.items())[:10]:
                self.stdout.write(f"  {cnpj}: " + ", ".join(f"#{c.id} {c.name}" for c in clients))
        if duplicate_occurrences:
            self.stdout.write("Amostra ocorrência duplicada:")
            for key, ids in list(duplicate_occurrences.items())[:10]:
                self.stdout.write(f"  {key} -> IDs {ids}")

        if issues:
            for issue in issues:
                self.stderr.write(self.style.ERROR("FAIL: " + issue))
            raise CommandError(f"Foram encontrados {len(issues)} grupo(s) de integridade com problema.")
        self.stdout.write(self.style.SUCCESS("PASS — nenhuma duplicidade indevida detectada nas regras auditadas."))
