from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP


HUNDRED = Decimal('100')


def _d(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value or 0))


def clamp(value, low=0, high=100) -> Decimal:
    value = _d(value)
    return max(_d(low), min(_d(high), value))


def percent(numerator, denominator) -> Decimal:
    denominator = _d(denominator)
    if denominator <= 0:
        return Decimal('0')
    return (_d(numerator) / denominator * HUNDRED).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def sample_confidence(attempts: int, minimum: int) -> str:
    minimum = max(int(minimum or 1), 1)
    attempts = int(attempts or 0)
    if attempts < minimum:
        return 'LOW'
    if attempts < minimum * 3:
        return 'MEDIUM'
    return 'HIGH'


@dataclass(frozen=True)
class PerformanceResult:
    score: Decimal
    breakdown: dict[str, dict[str, Decimal | str]]


def build_performance_score(
    *,
    success_rate,
    clean_rate,
    retention_rate,
    time_window_rate,
    overdue_proof_rate,
    recovery_rate=0,
    weights: dict[str, Decimal | int | float] | None = None,
) -> PerformanceResult:
    """Calcula a NOTA DE SIMULAÇÃO V2.

    A função é deliberadamente pura para permitir testar a fórmula sem banco.
    Retenção/horário/prova são convertidos em índices de qualidade antes dos
    pesos. Os limites não tentam afirmar uma regra definitiva de RH/bonificação;
    servem como simulação operacional transparente até homologação.
    """
    weights = weights or {}
    weight_map = {
        'delivery': _d(weights.get('delivery', 35)),
        'clean': _d(weights.get('clean', 20)),
        'retention': _d(weights.get('retention', 20)),
        'time_window': _d(weights.get('time_window', 15)),
        'proofs': _d(weights.get('proofs', 10)),
        'recovery': _d(weights.get('recovery', 0)),
    }

    # Qualidade: 0% de evento negativo = 100. A escala é intencionalmente
    # conservadora; a UI informa que se trata de SIMULAÇÃO e mostra o breakdown.
    quality = {
        'delivery': clamp(success_rate),
        'clean': clamp(clean_rate),
        'retention': clamp(HUNDRED - _d(retention_rate) * Decimal('8')),
        'time_window': clamp(HUNDRED - _d(time_window_rate) * Decimal('6')),
        'proofs': clamp(HUNDRED - _d(overdue_proof_rate)),
        'recovery': clamp(_d(recovery_rate) * Decimal('5')),
    }
    labels = {
        'delivery': 'Taxa de sucesso',
        'clean': 'Entrega limpa',
        'retention': 'Baixa retenção',
        'time_window': 'Baixo retorno por horário',
        'proofs': 'Comprovantes dentro do prazo',
        'recovery': 'Comprovantes resgatados',
    }
    total_weight = sum(weight_map.values(), Decimal('0')) or HUNDRED
    weighted = sum((quality[key] * weight_map[key] for key in quality), Decimal('0'))
    score = (weighted / total_weight).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)
    breakdown = {
        key: {
            'label': labels[key],
            'quality': quality[key].quantize(Decimal('0.1'), rounding=ROUND_HALF_UP),
            'weight': weight_map[key],
            'points': (quality[key] * weight_map[key] / total_weight).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP),
        }
        for key in quality
    }
    return PerformanceResult(score=score, breakdown=breakdown)


@dataclass(frozen=True)
class PerformanceV3Result:
    score: Decimal
    base_score: Decimal
    bonus: Decimal
    components: dict[str, Decimal]
    breakdown: dict[str, dict[str, Decimal | str]]


def build_performance_v3_score(
    *,
    success_rate,
    primary_issue_rate,
    overdue_proof_rate=0,
    proof_management_score=None,
    quality_failure_rate=None,
    exact_recoveries=0,
    gold_recoveries=0,
    regularity_score=100,
    weights=None,
    exact_bonus=Decimal("0.30"),
    gold_bonus=Decimal("0.90"),
    bonus_cap=Decimal("5.00"),
) -> PerformanceV3Result:
    """Nota Geral V3.

    Produtividade bruta não participa da nota. Eventos operacionais negativos são
    previamente normalizados para uma causa principal por tentativa, evitando
    penalização múltipla do mesmo fato. Recuperações só chegam aqui após validação.
    """
    weights = weights or {}
    weight_map = {
        "proofs": _d(weights.get("proofs", 50)),
        "quality": _d(weights.get("quality", 35)),
        "regularity": _d(weights.get("regularity", 15)),
    }
    overdue = clamp(overdue_proof_rate)
    primary = clamp(primary_issue_rate if quality_failure_rate is None else quality_failure_rate)
    success = clamp(success_rate)

    # v0.9.2: idade do comprovante é indicador operacional, não culpa automática.
    # Quando o serviço fornece uma nota de gestão atribuível ao motorista, ela
    # substitui a antiga penalização por estoque/SLA. O fallback existe apenas
    # para compatibilidade com chamadas legadas/testes.
    proof_management = clamp(HUNDRED - overdue if proof_management_score is None else proof_management_score)
    # Qualidade é proporcional SOMENTE a ROM13 validado pelo coordenador como
    # responsabilidade do motorista. ROM13 pendente/neutro e ROM34 não entram.
    operational_quality = clamp(HUNDRED - primary)
    regularity = clamp(regularity_score)

    components = {
        "proofs": proof_management.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP),
        "quality": operational_quality.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP),
        "regularity": regularity.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP),
    }
    total_weight = sum(weight_map.values(), Decimal("0")) or HUNDRED
    base = sum(components[k] * weight_map[k] for k in components) / total_weight
    bonus = min(_d(bonus_cap), _d(exact_recoveries) * _d(exact_bonus) + _d(gold_recoveries) * _d(gold_bonus))
    score = min(HUNDRED, base + bonus).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    base = base.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    bonus = bonus.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    breakdown = {
        "proofs": {"label": "Gestão de comprovantes", "quality": components["proofs"], "weight": weight_map["proofs"], "points": (components["proofs"] * weight_map["proofs"] / total_weight).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)},
        "quality": {"label": "Qualidade operacional", "quality": components["quality"], "weight": weight_map["quality"], "points": (components["quality"] * weight_map["quality"] / total_weight).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)},
        "regularity": {"label": "Regularidade", "quality": components["regularity"], "weight": weight_map["regularity"], "points": (components["regularity"] * weight_map["regularity"] / total_weight).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)},
        "bonus": {"label": "Bônus de recuperações validadas", "quality": bonus, "weight": Decimal("0"), "points": bonus},
    }
    return PerformanceV3Result(score=score, base_score=base, bonus=bonus, components=components, breakdown=breakdown)
