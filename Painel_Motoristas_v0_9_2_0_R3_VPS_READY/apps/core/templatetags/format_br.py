from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


def _decimal(value):
    try:
        return Decimal(str(value or 0))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def _br_number(value, places=2):
    value = _decimal(value)
    raw = f"{value:,.{places}f}"
    return raw.replace(",", "X").replace(".", ",").replace("X", ".")


@register.filter
def br_number(value, places=2):
    try:
        places = int(places)
    except (TypeError, ValueError):
        places = 2
    return _br_number(value, max(0, min(places, 4)))


@register.filter
def brl(value):
    return f"R$ {_br_number(value, 2)}"


@register.filter
def brl_compact(value):
    value = _decimal(value)
    abs_value = abs(value)
    if abs_value >= Decimal("1000000000"):
        return f"R$ {_br_number(value / Decimal('1000000000'), 2)} bi"
    if abs_value >= Decimal("1000000"):
        return f"R$ {_br_number(value / Decimal('1000000'), 2)} mi"
    if abs_value >= Decimal("1000"):
        return f"R$ {_br_number(value / Decimal('1000'), 1)} mil"
    return f"R$ {_br_number(value, 2)}"
