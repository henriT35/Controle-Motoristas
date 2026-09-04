from __future__ import annotations

import logging
from datetime import date, timedelta

from django.utils import timezone

logger = logging.getLogger("apps.performance")


def _period_for_mode(mode: str, today: date) -> tuple[date, date]:
    """Resolve a janela padrão sem depender de uma request HTTP.

    Mantém o warmup alinhado ao mesmo período que o Dashboard abrirá por
    padrão. Antes da R3 o warmup sempre aquecia o mês, então trocar o período
    padrão para 30d/90d/ano fazia o primeiro clique reconstruir tudo de novo.
    """
    mode = (mode or "month").strip().lower()
    if mode == "today":
        return today, today
    if mode == "yesterday":
        day = today - timedelta(days=1)
        return day, day
    if mode == "week":
        return today - timedelta(days=today.weekday()), today
    rolling_days = {"7d": 7, "30d": 30, "60d": 60, "90d": 90}
    if mode in rolling_days:
        days = rolling_days[mode]
        return today - timedelta(days=days - 1), today
    if mode == "year":
        return date(today.year, 1, 1), today
    return date(today.year, today.month, 1), today


def warm_navigation_cache(*, reference_date: date | None = None) -> dict:
    """Pré-aquece fotografias usadas pelas telas críticas.

    Regras de performance:
    - o período aquecido é exatamente o período padrão configurado;
    - Ranking tem snapshot persistente + cache compartilhado;
    - KPIs e gráfico do Dashboard também são aquecidos fora do GET;
    - oportunidades do dia são materializadas antes da navegação.

    No Windows o cache local é compartilhado por arquivo entre Waitress,
    scheduler e comandos de manutenção. Na VPS o mesmo fluxo usa Redis.
    """
    from apps.core.models import SystemSettings
    from apps.core.services import (
        calculate_driver_metrics,
        operational_manifest_evidence_map,
        previous_period,
    )
    from apps.dashboard.views import _basic_kpis, _evolution_payload
    from apps.operations.services import refresh_today_opportunities
    from apps.drivers.evaluation import load_driver_score_snapshots, snapshot_driver_scores

    today = reference_date or timezone.localdate()
    settings_obj = SystemSettings.load()
    period_start, period_end = _period_for_mode(settings_obj.period_default, today)
    prev_start, prev_end = previous_period(period_start, period_end)
    result = {
        "period_mode": settings_obj.period_default,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
    }

    # Fonte temporal global: uma construção por versão do cache.
    evidence = operational_manifest_evidence_map()
    result["evidence_manifests"] = len(evidence)

    # Persiste antes de aquecer cache. Assim qualquer invalidação posterior
    # ainda possui uma fotografia rápida no banco e nunca devolve o custo do
    # primeiro clique ao usuário.
    result["snapshots_current"] = snapshot_driver_scores(
        score_date=period_end, period_start=period_start, period_end=period_end, force=True
    )
    previous_snapshot = load_driver_score_snapshots(prev_start, prev_end)
    if previous_snapshot is None:
        result["snapshots_previous"] = snapshot_driver_scores(
            score_date=prev_end, period_start=prev_start, period_end=prev_end, force=True
        )
    else:
        result["snapshots_previous"] = len(previous_snapshot)

    metrics = calculate_driver_metrics(period_start, period_end)
    prev_metrics = calculate_driver_metrics(prev_start, prev_end)
    result["metrics"] = len(metrics)
    result["previous_metrics"] = len(prev_metrics)

    # KPIs usam exatamente a mesma janela que o Dashboard abrirá por padrão.
    current_kpis = _basic_kpis(period_start, period_end)
    previous_kpis = _basic_kpis(prev_start, prev_end)
    result["current_ctes"] = len(current_kpis.get("cte_ids", ()))
    result["previous_ctes"] = len(previous_kpis.get("cte_ids", ()))

    # O gráfico era o próximo gargalo visível (~2s). Ele continua lazy-loaded,
    # porém seu payload padrão já fica pronto no startup/pós-import.
    evolution = _evolution_payload(period_start, period_end)
    result["graph_points"] = len(evolution.get("dates", ()))

    # Disponibilidade de hoje é estado derivado e deve ser atualizada fora do GET.
    exact_ids = refresh_today_opportunities(today)
    result["today_exact"] = len(exact_ids)

    logger.info(
        "PERF warmup.done mode=%s period=%s..%s evidence=%s metrics=%s prev=%s current_ctes=%s graph=%s exact=%s",
        result["period_mode"], result["period_start"], result["period_end"],
        result["evidence_manifests"], result["metrics"], result["previous_metrics"],
        result["current_ctes"], result["graph_points"], result["today_exact"],
    )
    return result
