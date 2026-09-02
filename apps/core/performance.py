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
