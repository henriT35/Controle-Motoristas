from __future__ import annotations
from dataclasses import dataclass
import os
from pathlib import Path
from dotenv import load_dotenv

class ConfigError(RuntimeError):
    pass

def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "sim", "on"}

def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ConfigError(f"{name} deve ser inteiro.") from exc

@dataclass(frozen=True)
class RobotConfig:
    ssw_url: str
    company: str
    cpf: str
    username: str
    password: str
    default_unit: str
    report_type: str
    option: str
    headless: bool
    slow_mo: int
    action_timeout_ms: int
    download_timeout_ms: int
    max_days: int
    inbox_dir: Path

    @classmethod
    def from_env(cls) -> "RobotConfig":
        load_dotenv()
        required = {
            "SSW_EMPRESA": os.getenv("SSW_EMPRESA", "").strip(),
            "SSW_CPF": os.getenv("SSW_CPF", "").strip(),
            "SSW_USUARIO": os.getenv("SSW_USUARIO", "").strip(),
            "SSW_SENHA": os.getenv("SSW_SENHA", "").strip(),
        }
        missing = [k for k, v in required.items() if not v]
        if missing:
            raise ConfigError("Configuração SSW incompleta no .env: " + ", ".join(missing))
        return cls(
            ssw_url=os.getenv("SSW_URL", "https://sistema.ssw.inf.br/bin/ssw0422").strip(),
            company=required["SSW_EMPRESA"],
            cpf=required["SSW_CPF"],
            username=required["SSW_USUARIO"],
            password=required["SSW_SENHA"],
            default_unit=os.getenv("SSW_UNIT", "BEL").strip().upper(),
            report_type=os.getenv("SSW_REPORT_TYPE", "ROMANEIOS").strip().upper(),
            option=os.getenv("SSW_OPTION", "036").strip(),
            headless=_bool_env("ROBOT_HEADLESS", False),
            slow_mo=_int_env("ROBOT_SLOW_MO", 800),
            action_timeout_ms=_int_env("ROBOT_ACTION_TIMEOUT_MS", 30000),
            download_timeout_ms=_int_env("ROBOT_DOWNLOAD_TIMEOUT_MS", 120000),
            max_days=_int_env("ROBOT_MAX_DAYS", 31),
            inbox_dir=Path(os.getenv("ROBOT_INBOX_DIR", r"C:\ControleMotoristas\imports\inbox")),
        )

    @property
    def secrets(self) -> tuple[str, ...]:
        return (self.company, self.cpf, self.username, self.password)
