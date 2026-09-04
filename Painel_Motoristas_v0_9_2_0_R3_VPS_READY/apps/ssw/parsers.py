from __future__ import annotations

import csv
import re
import unicodedata
from functools import lru_cache
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable

_NON_ALNUM_RE = re.compile(r"[^A-Z0-9]+")
_MULTI_SPACE_RE = re.compile(r"\s+")
_PERIOD_RE = re.compile(r"(\d{2}/\d{2}/\d{2,4})\s+A\s+(\d{2}/\d{2}/\d{2,4})", re.I)


@dataclass(frozen=True)
class ParsedSSWFile:
    period_start: date | None
    period_end: date | None
    company: str
    rows: list[dict[str, str]]


def clean(value: str | None) -> str:
    return (value or "").strip()


@lru_cache(maxsize=32768)
def parse_br_decimal(value: str | None) -> Decimal:
    raw = clean(value)
    if not raw:
        return Decimal("0")
    raw = raw.replace(".", "").replace(",", ".").replace(" ", "")
    try:
        return Decimal(raw)
    except InvalidOperation:
        return Decimal("0")


@lru_cache(maxsize=32768)
def parse_int(value: str | None) -> int:
    try:
        return int(parse_br_decimal(value))
    except (ValueError, TypeError):
        return 0


@lru_cache(maxsize=32768)
def parse_date(value: str | None) -> date | None:
    raw = clean(value)
    if not raw:
        return None
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            pass
    return None


@lru_cache(maxsize=32768)
def parse_time(value: str | None) -> time | None:
    raw = clean(value)
    if not raw:
        return None
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(raw, fmt).time()
        except ValueError:
            pass
    return None




def is_valid_br_decimal(value: str | None) -> bool:
    """Valida número no formato dos relatórios SSW sem converter erro em zero."""
    raw = clean(value)
    if not raw:
        return True
    normalized = raw.replace(".", "").replace(",", ".").replace(" ", "")
    try:
        Decimal(normalized)
        return True
    except InvalidOperation:
        return False


def is_valid_date(value: str | None) -> bool:
    raw = clean(value)
    if not raw:
        return True
    return parse_date(raw) is not None


def is_valid_time(value: str | None) -> bool:
    raw = clean(value)
    if not raw:
        return True
    return parse_time(raw) is not None


def validate_delivery_row(row: dict[str, str]) -> list[str]:
    """Retorna problemas de formato que antes eram silenciosamente convertidos em 0/None."""
    problems: list[str] = []
    for field in ("FRETE CTRC", "VLR MERC", "PESO CALCULO", "QTDE VOL"):
        if not is_valid_br_decimal(row.get(field)):
            problems.append(f"{field} inválido: {clean(row.get(field))!r}")
    for field in ("DATA EMISSAO", "DATA OCORR ROM", "DATA OCORR CTRC"):
        if not is_valid_date(row.get(field)):
            problems.append(f"{field} inválida: {clean(row.get(field))!r}")
    for field in ("HORA EMISSAO", "HORA OCORR ROM", "HORA OCORR CTRC"):
        if not is_valid_time(row.get(field)):
            problems.append(f"{field} inválida: {clean(row.get(field))!r}")
    return problems

def combine_datetime(date_value: str | None, time_value: str | None) -> datetime | None:
    d = parse_date(date_value)
    if not d:
        return None
    t = parse_time(time_value) or time.min
    return datetime.combine(d, t)


@lru_cache(maxsize=32768)
def normalize_text(value: str | None) -> str:
    raw = clean(value).upper()
    raw = unicodedata.normalize("NFKD", raw)
    raw = "".join(ch for ch in raw if not unicodedata.combining(ch))
    raw = _NON_ALNUM_RE.sub(" ", raw)
    return _MULTI_SPACE_RE.sub(" ", raw).strip()


def split_city_state(value: str | None) -> tuple[str, str]:
    raw = clean(value)
    if "/" in raw:
        city, state = raw.rsplit("/", 1)
        return city.strip(), state.strip()[:2].upper()
    return raw, ""


def _extract_period(meta_text: str) -> tuple[date | None, date | None]:
    match = _PERIOD_RE.search(meta_text)
    if not match:
        return None, None
    return parse_date(match.group(1)), parse_date(match.group(2))



def read_ssw_delivery_metadata(path: str | Path) -> tuple[date | None, date | None, str]:
    """Lê apenas metadados/cabeçalho; usado para ordenar lotes sem parsear o arquivo inteiro duas vezes."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    last_error: Exception | None = None
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            with path.open("r", encoding=encoding, newline="") as handle:
                reader = csv.reader(handle, delimiter=";")
                meta = next(reader)
                header = next(reader)
                if len(header) < 40 or "CTRC" not in header:
                    raise ValueError("Arquivo não parece ser o relatório de entregas esperado do SSW.")
                period_start, period_end = _extract_period(meta[1] if len(meta) > 1 else "")
                company = clean(meta[2] if len(meta) > 2 else "")
                return period_start, period_end, company
        except UnicodeDecodeError as exc:
            last_error = exc
            continue
    if last_error:
        raise last_error
    raise ValueError("Não foi possível ler o cabeçalho do arquivo SSW.")

def read_ssw_delivery_file(path: str | Path) -> ParsedSSWFile:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)

    # Os relatórios atuais do SSW chegam em Latin-1/Windows-1252. Tentar UTF-8 primeiro
    # permite compatibilidade caso uma exportação futura mude de encoding.
    last_error: Exception | None = None
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            with path.open("r", encoding=encoding, newline="") as handle:
                reader = csv.reader(handle, delimiter=";")
                meta = next(reader)
                header = next(reader)
                if len(header) < 40 or "CTRC" not in header:
                    raise ValueError("Arquivo não parece ser o relatório de entregas esperado do SSW.")

                period_start, period_end = _extract_period(meta[1] if len(meta) > 1 else "")
                company = clean(meta[2] if len(meta) > 2 else "")
                rows: list[dict[str, str]] = []
                for values in reader:
                    if not values:
                        continue
                    if len(values) < len(header):
                        values = values + [""] * (len(header) - len(values))
                    if len(values) > len(header):
                        values = values[: len(header)]
                    row = dict(zip(header, values))
                    # Linhas de dados do relatório começam com marcador 2.
                    if clean(row.get("1")) != "2":
                        continue
                    rows.append(row)
                return ParsedSSWFile(period_start, period_end, company, rows)
        except UnicodeDecodeError as exc:
            last_error = exc
            continue
    if last_error:
        raise last_error
    raise ValueError("Não foi possível ler o arquivo SSW.")


RETENTION_CODE = "34"
RETENTION_TEXT = "MERCADORIA EM CONFERENCIA NO CLIENTE"
DELIVERED_CODE = "1"
DELIVERED_TEXT = "ENTREGUE"


@dataclass(frozen=True)
class RetentionSnapshot:
    """Leitura semântica das duas trilhas de ocorrência do relatório 036.

    ROMANEIO registra o que ocorreu naquela tentativa/rota. CTRC registra o
    estado consolidado do documento. Portanto, ROM=34 preserva o fato histórico
    de que houve retenção, enquanto CTRC=34 indica que a retenção continua ativa.
    Se houve retenção no ROM e o CTRC já está ENTREGUE, o relatório informa que
    o documento saiu da retenção em ``ctrc_occurred_at``.
    """

    historically_retained: bool
    active_retention: bool
    delivered_after_retention: bool
    explicit_retained_at: datetime | None
    recovered_at: datetime | None
    rom_code: str
    rom_description: str
    rom_occurred_at: datetime | None
    ctrc_code: str
    ctrc_description: str
    ctrc_occurred_at: datetime | None


def is_retention_occurrence(code: str | None, description: str | None) -> bool:
    return clean(code) == RETENTION_CODE or RETENTION_TEXT in normalize_text(description)


def is_delivered_occurrence(code: str | None, description: str | None) -> bool:
    normalized = normalize_text(description)
    return clean(code) == DELIVERED_CODE or normalized == DELIVERED_TEXT or normalized.startswith(DELIVERED_TEXT + " ")


def retention_snapshot(row: dict[str, str]) -> RetentionSnapshot:
    rom_code = clean(row.get("COD OCORR ROM"))
    rom_desc = clean(row.get("DESC OCORR ROM"))
    rom_at = combine_datetime(row.get("DATA OCORR ROM"), row.get("HORA OCORR ROM"))
    ctrc_code = clean(row.get("COD OCORR CTRC"))
    ctrc_desc = clean(row.get("DESC OCORR CTRC"))
    ctrc_at = combine_datetime(row.get("DATA OCORR CTRC"), row.get("HORA OCORR CTRC"))

    rom_retained = is_retention_occurrence(rom_code, rom_desc)
    ctrc_retained = is_retention_occurrence(ctrc_code, ctrc_desc)
    historically_retained = rom_retained or ctrc_retained

    explicit_candidates = []
    if rom_retained and rom_at is not None:
        explicit_candidates.append(rom_at)
    if ctrc_retained and ctrc_at is not None:
        explicit_candidates.append(ctrc_at)
    explicit_retained_at = min(explicit_candidates) if explicit_candidates else None

    delivered = is_delivered_occurrence(ctrc_code, ctrc_desc)
    # v0.9.2: o CTRC do 036 é o estado consolidado atual. O SSW pode corrigir
    # retroativamente a data de entrega e a retenção histórica pode ter horário
    # técnico/inferido. Portanto, se há evidência histórica de retenção e o CTRC
    # atual está ENTREGUE, a retenção está operacionalmente resolvida. A data é
    # preservada como evidência, mas nunca veta a baixa por comparação artificial.
    delivered_after_retention = bool(historically_retained and delivered)
    recovered_at = ctrc_at if delivered_after_retention else None

    return RetentionSnapshot(
        historically_retained=historically_retained,
        active_retention=ctrc_retained,
        delivered_after_retention=delivered_after_retention,
        explicit_retained_at=explicit_retained_at,
        recovered_at=recovered_at,
        rom_code=rom_code,
        rom_description=rom_desc,
        rom_occurred_at=rom_at,
        ctrc_code=ctrc_code,
        ctrc_description=ctrc_desc,
        ctrc_occurred_at=ctrc_at,
    )


def iter_occurrences(row: dict[str, str]) -> Iterable[tuple[str, str, datetime | None, str]]:
    snap = retention_snapshot(row)
    if snap.rom_code or snap.rom_description:
        yield snap.rom_code, snap.rom_description, snap.rom_occurred_at, "ROMANEIO"
    if snap.ctrc_code or snap.ctrc_description:
        yield snap.ctrc_code, snap.ctrc_description, snap.ctrc_occurred_at, "CTRC"


def row_is_retained(row: dict[str, str]) -> bool:
    """Compatibilidade: indica que o relatório contém histórico de retenção."""
    return retention_snapshot(row).historically_retained


ROUTE_EXIT_CODE = "85"
ROUTE_EXIT_TEXT = "SAIDA PARA ENTREGA"


def is_route_exit(code: str | None, description: str | None) -> bool:
    return clean(code) == ROUTE_EXIT_CODE or ROUTE_EXIT_TEXT in normalize_text(description)


def row_route_exit_date(row: dict[str, str]) -> date | None:
    """Data operacional explícita da rota, quando o SSW informa SAIDA PARA ENTREGA."""
    dates = []
    for code, description, occurred_at, _scope in iter_occurrences(row):
        if is_route_exit(code, description) and occurred_at is not None:
            dates.append(occurred_at.date())
    return min(dates) if dates else None
