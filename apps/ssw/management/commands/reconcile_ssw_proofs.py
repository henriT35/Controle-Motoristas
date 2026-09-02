from __future__ import annotations

from collections import defaultdict
from datetime import datetime, time

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.operations.models import DeliveryOccurrence
from apps.proofs.models import RetainedProof
from apps.ssw.parsers import is_delivered_occurrence, is_retention_occurrence

AUTO_PREFIX = "[SSW AUTO]"


def _aware_midday(day):
    return timezone.make_aware(
        datetime.combine(day, time(hour=12)),
        timezone.get_current_timezone(),
    )


def _manual_recovery(proof: RetainedProof) -> bool:
    return bool(
        proof.status == RetainedProof.Status.RECOVERED
        and (proof.confirmed_by_id is not None or proof.recovery_driver_id is not None)
    )


def _latest_ctrc(occurrences):
    candidates = [
        o for o in occurrences
        if o.occurred_at is not None and (o.source or "").upper() == "SSW_CTRC"
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda o: (o.occurred_at, o.imported_at, o.pk or 0))


def _retention_time(proof: RetainedProof, occurrences):
    retained = [o for o in occurrences if is_retention_occurrence(o.code, o.description)]
    if not retained:
        return None, False

    explicit = [o.occurred_at for o in retained if o.occurred_at is not None]
    if explicit:
        return min(explicit), False

    # Quando ROM=34 vem sem DATA OCORR, a própria linha continua ligada ao
    # movimento/romaneio. Usamos a data do romaneio como data histórica inferida,
    # nunca a data de importação.
    manifest_days = [
        o.movement.manifest.date
        for o in retained
        if o.movement_id and o.movement and o.movement.manifest_id
    ]
    if manifest_days:
        return _aware_midday(min(manifest_days)), True
    if proof.original_manifest_id and proof.original_manifest:
        return _aware_midday(proof.original_manifest.date), True
    return None, True


class Command(BaseCommand):
    help = (
        "Recalcula datas/estado de comprovantes retidos usando ROM x CTRC do SSW. "
        "Sem --apply apenas mostra o que seria alterado."
    )

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Grava as correções no banco.")
        parser.add_argument("--limit", type=int, default=0, help="Limita a quantidade de comprovantes para diagnóstico.")

    def handle(self, *args, **options):
        apply_changes = bool(options["apply"])
        limit = max(int(options.get("limit") or 0), 0)

        proofs_qs = RetainedProof.objects.select_related(
            "cte", "original_manifest"
        ).order_by("pk")
        if limit:
            proofs = list(proofs_qs[:limit])
        else:
            proofs = list(proofs_qs)
        if not proofs:
            self.stdout.write(self.style.SUCCESS("Nenhum comprovante retido para reconciliar."))
            return

        cte_ids = [p.cte_id for p in proofs]
        occurrences = list(
            DeliveryOccurrence.objects.filter(cte_id__in=cte_ids)
            .select_related("movement__manifest")
            .order_by("cte_id", "occurred_at", "imported_at", "pk")
        )
        by_cte = defaultdict(list)
        for occurrence in occurrences:
            by_cte[occurrence.cte_id].append(occurrence)

        counters = defaultdict(int)
        updates = []
        now = timezone.now()

        for proof in proofs:
            occs = by_cte.get(proof.cte_id, [])
            target_retained_at, inferred = _retention_time(proof, occs)
            if target_retained_at is None:
                counters["sem_historico"] += 1
                continue

            changed = False
            manual = _manual_recovery(proof)

            # Se temos data explícita, ela é a fonte mais forte. Para data inferida,
            # corrigimos principalmente a assinatura do bug antigo (retained_at perto
            # de created_at) ou datas posteriores ao evento histórico inferido.
            if inferred:
                import_fallback = abs((proof.retained_at - proof.created_at).total_seconds()) <= 600
                should_fix_date = import_fallback or proof.retained_at.date() > target_retained_at.date()
            else:
                should_fix_date = proof.retained_at != target_retained_at
            if should_fix_date:
                proof.retained_at = target_retained_at
                counters["datas_corrigidas"] += 1
                if inferred:
                    counters["datas_inferidas"] += 1
                changed = True

            latest = _latest_ctrc(occs)
            if latest is not None and not manual and proof.status != RetainedProof.Status.CANCELED:
                effective_retained_at = proof.retained_at
                if (
                    is_delivered_occurrence(latest.code, latest.description)
                    and latest.occurred_at >= effective_retained_at
                ):
                    note = (
                        f"{AUTO_PREFIX} Baixa automática pelo estado consolidado do CTRC em "
                        f"{timezone.localtime(latest.occurred_at):%d/%m/%Y %H:%M}."
                    )
                    if proof.status != RetainedProof.Status.RECOVERED:
                        proof.status = RetainedProof.Status.RECOVERED
                        counters["baixados_auto"] += 1
                        changed = True
                    if proof.recovered_at != latest.occurred_at:
                        proof.recovered_at = latest.occurred_at
                        changed = True
                    if proof.recovery_driver_id is not None:
                        proof.recovery_driver = None
                        changed = True
                    if proof.confirmed_by_id is not None:
                        proof.confirmed_by = None
                        changed = True
                    if not proof.note or proof.note.startswith(AUTO_PREFIX):
                        if proof.note != note:
                            proof.note = note
                            changed = True
                elif is_retention_occurrence(latest.code, latest.description):
                    if proof.status == RetainedProof.Status.RECOVERED and proof.note.startswith(AUTO_PREFIX):
                        if proof.recovered_at is None or latest.occurred_at > proof.recovered_at:
                            proof.status = RetainedProof.Status.WAITING
                            proof.recovered_at = None
                            proof.recovery_driver = None
                            proof.confirmed_by = None
                            proof.note = f"{AUTO_PREFIX} Retenção reaberta pelo estado consolidado do CTRC."
                            counters["reabertos"] += 1
                            changed = True

            if manual:
                counters["manual_preservado"] += 1

            if changed:
                proof.updated_at = now
                updates.append(proof)

        mode = "APLICAR" if apply_changes else "SIMULAR"
        self.stdout.write(f"Modo: {mode}")
        for key in (
            "datas_corrigidas", "datas_inferidas", "baixados_auto", "reabertos",
            "manual_preservado", "sem_historico",
        ):
            self.stdout.write(f"{key}: {counters[key]}")
        self.stdout.write(f"objetos_alterados: {len(updates)}")

        if not apply_changes:
            self.stdout.write(self.style.WARNING("Nenhuma alteração gravada. Use --apply para confirmar."))
            return

        if updates:
            with transaction.atomic():
                RetainedProof.objects.bulk_update(
                    updates,
                    [
                        "retained_at", "status", "recovered_at", "recovery_driver",
                        "confirmed_by", "note", "updated_at",
                    ],
                    batch_size=1000,
                )
        self.stdout.write(self.style.SUCCESS("Reconciliação SSW concluída e gravada."))
