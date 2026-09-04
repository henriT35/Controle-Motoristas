from collections import defaultdict
from datetime import datetime, time

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.core.services import (
    RETENTION_CODE,
    RETENTION_TEXT,
    _canonical_manifest_evidence_rows,
    _local_date,
)
from apps.operations.models import DeliveryOccurrence
from apps.proofs.models import RetainedProof
from apps.ssw.parsers import is_delivered_occurrence, is_retention_occurrence


AUTO_PREFIX = "[SSW AUTO]"


def _manual_recovery(proof):
    return bool(
        proof.status == RetainedProof.Status.RECOVERED
        and (proof.confirmed_by_id is not None or proof.recovery_driver_id is not None)
    )


def _midday(day):
    return timezone.make_aware(
        datetime.combine(day, time(hour=12)), timezone.get_current_timezone()
    )


class Command(BaseCommand):
    help = (
        "Reconcilia a lógica v0.8.1.0 sobre dados já importados: origem ROM34, "
        "datas históricas reconstruídas e status VERIFICAR."
    )

    def handle(self, *args, **options):
        proofs = list(
            RetainedProof.objects.exclude(status=RetainedProof.Status.CANCELED)
            .select_related("cte", "original_manifest", "original_driver")
        )
        if not proofs:
            self.stdout.write(self.style.SUCCESS("Nenhum comprovante para reconciliar."))
            return

        cte_ids = {p.cte_id for p in proofs}
        route_evidence = _canonical_manifest_evidence_rows()
        rom34_by_cte = defaultdict(list)
        for occ in (
            DeliveryOccurrence.objects.filter(
                cte_id__in=cte_ids, movement__isnull=False, source="SSW_ROMANEIO"
            )
            .filter(Q(code=RETENTION_CODE) | Q(description__icontains=RETENTION_TEXT))
            .select_related("movement", "movement__manifest", "movement__driver")
            .order_by("cte_id", "occurred_at", "pk")
        ):
            rom34_by_cte[occ.cte_id].append(occ)

        latest_ctrc = {}
        for occ in (
            DeliveryOccurrence.objects.filter(
                cte_id__in=cte_ids, source="SSW_CTRC", occurred_at__isnull=False
            )
            .order_by("cte_id", "occurred_at", "imported_at", "pk")
        ):
            latest_ctrc[occ.cte_id] = occ

        changed_count = 0
        origin_fixed = 0
        date_fixed = 0
        to_verify = 0
        to_waiting = 0
        to_recovered = 0
        ambiguous_origin = 0

        with transaction.atomic():
            for proof in proofs:
                changed = False
                candidates = rom34_by_cte.get(proof.cte_id, [])
                chosen_manifest_id = None
                chosen_occurrences = []
                by_manifest = defaultdict(list)
                for occ in candidates:
                    by_manifest[occ.movement.manifest_id].append(occ)

                if len(by_manifest) == 1:
                    chosen_manifest_id = next(iter(by_manifest))
                    chosen_occurrences = by_manifest[chosen_manifest_id]
                elif len(by_manifest) > 1:
                    dated = []
                    for manifest_id, occs in by_manifest.items():
                        dates = [o.occurred_at for o in occs if o.occurred_at]
                        if dates:
                            dated.append((min(dates), manifest_id, occs))
                    if dated:
                        dated.sort(key=lambda item: item[0])
                        first_at = dated[0][0]
                        winners = [item for item in dated if item[0] == first_at]
                        if len(winners) == 1:
                            _, chosen_manifest_id, chosen_occurrences = winners[0]
                        else:
                            ambiguous_origin += 1
                    else:
                        # Sem data explícita, só decide se uma única tentativa tem
                        # data canônica segura. Caso contrário preserva para revisão.
                        anchored = [
                            (route_evidence[mid][0], mid, occs)
                            for mid, occs in by_manifest.items()
                            if mid in route_evidence
                        ]
                        if anchored:
                            anchored.sort(key=lambda item: item[0])
                            first_day = anchored[0][0]
                            winners = [item for item in anchored if item[0] == first_day]
                            if len(winners) == 1:
                                _, chosen_manifest_id, chosen_occurrences = winners[0]
                            else:
                                ambiguous_origin += 1
                        else:
                            ambiguous_origin += 1

                if chosen_manifest_id:
                    chosen_movement = chosen_occurrences[0].movement
                    if (
                        proof.original_manifest_id != chosen_manifest_id
                        or proof.original_driver_id != chosen_movement.driver_id
                    ):
                        proof.original_manifest_id = chosen_manifest_id
                        proof.original_driver_id = chosen_movement.driver_id
                        origin_fixed += 1
                        changed = True

                    explicit = [o.occurred_at for o in chosen_occurrences if o.occurred_at]
                    target_retained_at = min(explicit) if explicit else None
                    if target_retained_at is None and chosen_manifest_id in route_evidence:
                        target_retained_at = _midday(route_evidence[chosen_manifest_id][0])
                    if target_retained_at and _local_date(proof.retained_at) != _local_date(target_retained_at):
                        proof.retained_at = target_retained_at
                        date_fixed += 1
                        changed = True

                if not _manual_recovery(proof):
                    latest = latest_ctrc.get(proof.cte_id)
                    latest_code = latest.code if latest else ""
                    latest_desc = latest.description if latest else proof.cte.current_status
                    latest_at = latest.occurred_at if latest else None
                    active = is_retention_occurrence(latest_code, latest_desc)
                    delivered = bool(
                        is_delivered_occurrence(latest_code, latest_desc)
                        and latest_at is not None
                        and latest_at >= proof.retained_at
                    )
                    ambiguous = bool(
                        (latest_code or latest_desc)
                        and not active
                        and not is_delivered_occurrence(latest_code, latest_desc)
                        and (latest_at is None or latest_at >= proof.retained_at)
                    )

                    if delivered:
                        if proof.status != RetainedProof.Status.RECOVERED or proof.recovered_at != latest_at:
                            proof.status = RetainedProof.Status.RECOVERED
                            proof.recovered_at = latest_at
                            proof.recovery_driver = None
                            proof.confirmed_by = None
                            proof.note = f"{AUTO_PREFIX} Baixa automática reconciliada pela v0.8.1.0."
                            to_recovered += 1
                            changed = True
                    elif active:
                        if proof.status in {RetainedProof.Status.RECOVERED, RetainedProof.Status.VERIFY}:
                            proof.status = RetainedProof.Status.WAITING
                            proof.recovered_at = None
                            proof.recovery_driver = None
                            proof.confirmed_by = None
                            proof.note = f"{AUTO_PREFIX} Retenção confirmada na reconciliação v0.8.1.0."
                            to_waiting += 1
                            changed = True
                    elif ambiguous:
                        if proof.status != RetainedProof.Status.VERIFY:
                            proof.status = RetainedProof.Status.VERIFY
                            proof.recovered_at = None
                            proof.recovery_driver = None
                            proof.confirmed_by = None
                            proof.note = f"{AUTO_PREFIX} Requer verificação após status CTRC não conclusivo."
                            to_verify += 1
                            changed = True

                if changed:
                    proof.save()
                    changed_count += 1

        self.stdout.write(self.style.SUCCESS("Reconciliação v0.8.1.0 concluída."))
        self.stdout.write(f"Comprovantes alterados: {changed_count}")
        self.stdout.write(f"Origem ROM34 corrigida: {origin_fixed}")
        self.stdout.write(f"Data histórica corrigida: {date_fixed}")
        self.stdout.write(f"Marcados para VERIFICAR: {to_verify}")
        self.stdout.write(f"Retenção confirmada/reaberta: {to_waiting}")
        self.stdout.write(f"Recuperados por entrega comprovada: {to_recovered}")
        self.stdout.write(f"Origens ainda ambíguas preservadas: {ambiguous_origin}")
