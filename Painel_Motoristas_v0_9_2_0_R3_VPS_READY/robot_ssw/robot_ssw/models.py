from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import date
from pathlib import Path
from typing import Any

class JobValidationError(ValueError):
    pass

@dataclass(frozen=True)
class JobRequest:
    execution_id: str
    start_date: date
    end_date: date
    mode: str
    requested_by: str
    report_type: str
    unit: str
    download_dir: Path

    @classmethod
    def from_dict(cls, data: dict[str, Any], config) -> "JobRequest":
        execution_id = str(data.get("execution_id", "")).strip()
        if not execution_id:
            raise JobValidationError("execution_id é obrigatório.")
        try:
            start = date.fromisoformat(str(data.get("start_date", "")))
            end = date.fromisoformat(str(data.get("end_date", "")))
        except ValueError as exc:
            raise JobValidationError("start_date e end_date devem estar em YYYY-MM-DD.") from exc
        if start > end:
            raise JobValidationError("start_date não pode ser maior que end_date.")
        days = (end - start).days + 1
        if days > config.max_days:
            raise JobValidationError(
                f"Janela de {days} dias excede o limite do executor ({config.max_days}). "
                "O Painel deve quebrar o período."
            )
        report_type = str(data.get("report_type") or config.report_type).strip().upper()
        if report_type not in {"ROMANEIOS", "ROMANEIOS_036", "DELIVERIES"}:
            raise JobValidationError(f"report_type não suportado pela opção 036: {report_type}")
        unit = str(data.get("unit") or config.default_unit).strip().upper()
        mode = str(data.get("mode") or "INCREMENTAL").strip().upper()
        requested_by = str(data.get("requested_by") or "system").strip()
        raw_dir = data.get("download_dir")
        download_dir = Path(str(raw_dir)) if raw_dir else config.inbox_dir / execution_id
        return cls(execution_id, start, end, mode, requested_by, report_type, unit, download_dir)

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "mode": self.mode,
            "requested_by": self.requested_by,
            "report_type": self.report_type,
            "unit": self.unit,
            "download_dir": str(self.download_dir),
        }

@dataclass(frozen=True)
class RobotEvent:
    execution_id: str
    state: str
    timestamp: str
    detail: str | None = None
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass
class RobotResult:
    execution_id: str
    robot_status: str
    started_at: str
    finished_at: str | None = None
    file_path: str | None = None
    file_size: int | None = None
    sha256: str | None = None
    messages: list[str] = field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
