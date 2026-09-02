from __future__ import annotations

import argparse
import getpass
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
ROBOT_DIR = ROOT / "robot_ssw"
ENV_PATH = ROBOT_DIR / ".env"
LEGACY_JSON = ROBOT_DIR / "credenciais.local.json"

DEFAULTS = {
    "SSW_URL": "https://sistema.ssw.inf.br/bin/ssw0422",
    "SSW_EMPRESA": "",
    "SSW_CPF": "",
    "SSW_USUARIO": "",
    "SSW_SENHA": "",
    "SSW_UNIT": "BEL",
    "SSW_REPORT_TYPE": "ROMANEIOS",
    "SSW_OPTION": "036",
    "ROBOT_HEADLESS": "false",
    "ROBOT_SLOW_MO": "800",
    "ROBOT_ACTION_TIMEOUT_MS": "30000",
    "ROBOT_DOWNLOAD_TIMEOUT_MS": "120000",
    "ROBOT_MAX_DAYS": "31",
    "ROBOT_INBOX_DIR": str((ROOT / "imports" / "inbox").resolve()),
}

ORDER = list(DEFAULTS)
REQUIRED = ("SSW_EMPRESA", "SSW_CPF", "SSW_USUARIO", "SSW_SENHA")


def _decode_value(raw: str) -> str:
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in {'"', "'"}:
        quote = raw[0]
        body = raw[1:-1]
        if quote == '"':
            body = body.replace(r"\n", "\n").replace(r"\r", "\r")
            body = body.replace(r'\"', '"').replace(r"\\", "\\")
        return body
    # dotenv treats unquoted # as comment when preceded by whitespace. Keep simple files safe.
    return raw


def _read_env(path: Path = ENV_PATH) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    text = path.read_text(encoding="utf-8-sig")
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            values[key] = _decode_value(value)
    return values


def _read_legacy_json() -> dict[str, str]:
    if not LEGACY_JSON.exists():
        return {}
    try:
        data = json.loads(LEGACY_JSON.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return {
        "SSW_EMPRESA": str(data.get("domain") or data.get("dominio") or "").strip(),
        "SSW_CPF": re.sub(r"\D", "", str(data.get("cpf") or "")),
        "SSW_USUARIO": str(data.get("username") or data.get("usuario") or "").strip(),
        "SSW_SENHA": str(data.get("password") or data.get("senha") or ""),
        "SSW_URL": str(data.get("login_url") or data.get("url") or "").strip(),
    }


def _merged_existing() -> dict[str, str]:
    result = dict(DEFAULTS)
    legacy = _read_legacy_json()
    for key, value in legacy.items():
        if value:
            result[key] = value
    current = _read_env()
    for key, value in current.items():
        if value or key not in result:
            result[key] = value
    return result


def _quote(value: str) -> str:
    value = str(value)
    # Always quote: passwords containing #, spaces, = or punctuation stay intact.
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\r", r"\r").replace("\n", r"\n")
    return f'"{escaped}"'


def _write_env(values: dict[str, str]) -> None:
    ROBOT_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Painel Motoristas - Robô SSW homologado",
        "# Gerado por CONFIGURAR_CREDENCIAIS_SSW.bat",
        "# Não compartilhar este arquivo: contém a senha do SSW.",
        "",
    ]
    for key in ORDER:
        lines.append(f"{key}={_quote(values.get(key, DEFAULTS[key]))}")
    # Preserve any extra keys already present, without duplicating standard keys.
    for key in sorted(k for k in values if k not in ORDER):
        lines.append(f"{key}={_quote(values[key])}")
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def _mask(value: str, *, keep: int = 2) -> str:
    if not value:
        return ""
    if len(value) <= keep:
        return "*" * len(value)
    return "*" * (len(value) - keep) + value[-keep:]


def _prompt(label: str, current: str = "", *, secret: bool = False, masked: bool = False) -> str:
    suffix = ""
    if current:
        shown = _mask(current, keep=4) if masked else current
        suffix = f" [{shown}] (Enter mantém)"
    prompt = f"{label}{suffix}: "
    value = getpass.getpass(prompt) if secret else input(prompt)
    if value == "" and current:
        return current
    return value


def _validate(values: dict[str, str]) -> list[str]:
    problems: list[str] = []
    for key in REQUIRED:
        if not str(values.get(key, "")).strip():
            problems.append(f"{key} não informado")
    cpf = re.sub(r"\D", "", values.get("SSW_CPF", ""))
    if cpf and len(cpf) != 11:
        problems.append("SSW_CPF deve possuir 11 dígitos")
    empresa = values.get("SSW_EMPRESA", "").strip()
    if empresa and len(empresa) > 3:
        problems.append("SSW_EMPRESA/Domínio possui mais de 3 caracteres; confira o domínio usado no login SSW")
    if values.get("SSW_OPTION", "036").strip() != "036":
        problems.append("SSW_OPTION deve permanecer 036")
    if values.get("SSW_UNIT", "BEL").strip().upper() != "BEL":
        problems.append("SSW_UNIT deve permanecer BEL")
    return problems


def configure() -> int:
    existing = _merged_existing()
    print("=" * 66)
    print(" CONFIGURAR CREDENCIAIS - ROBÔ SSW HOMOLOGADO (P13.4)")
    print("=" * 66)
    print(f"Arquivo usado pelo robô: {ENV_PATH}")
    print("Os valores ficam somente neste arquivo local e não entram no task.json.\n")

    empresa = _prompt("Domínio/Empresa SSW", existing.get("SSW_EMPRESA", ""))
    cpf = _prompt("CPF SSW", existing.get("SSW_CPF", ""), masked=True)
    cpf = re.sub(r"\D", "", cpf)
    usuario = _prompt("Usuário SSW", existing.get("SSW_USUARIO", ""))
    senha = _prompt("Senha SSW", existing.get("SSW_SENHA", ""), secret=True, masked=True)
    url = _prompt("URL do SSW", existing.get("SSW_URL", DEFAULTS["SSW_URL"]))

    values = dict(existing)
    values.update({
        "SSW_EMPRESA": empresa.strip(),
        "SSW_CPF": cpf,
        "SSW_USUARIO": usuario.strip(),
        "SSW_SENHA": senha,
        "SSW_URL": url.strip() or DEFAULTS["SSW_URL"],
        "SSW_UNIT": "BEL",
        "SSW_REPORT_TYPE": "ROMANEIOS",
        "SSW_OPTION": "036",
        "ROBOT_INBOX_DIR": str((ROOT / "imports" / "inbox").resolve()),
    })

    problems = _validate(values)
    if problems:
        print("\n[ERRO] Configuração não foi salva:")
        for item in problems:
            print(f" - {item}")
        return 2

    _write_env(values)
    check = _read_env()
    problems = _validate(check)
    if problems:
        print("\n[ERRO] O arquivo foi escrito, mas falhou na leitura de retorno:")
        for item in problems:
            print(f" - {item}")
        return 3

    print("\nCREDENCIAIS ATUALIZADAS COM SUCESSO.")
    print(f"Arquivo: {ENV_PATH}")
    print("Domínio/Empresa : SIM")
    print("CPF             : SIM (11 dígitos)")
    print("Usuário         : SIM")
    print("Senha           : SIM")
    print("URL             : SIM")
    print("Opção           : 036")
    print("Unidade         : BEL")
    return 0


def verify() -> int:
    print("=" * 66)
    print(" VERIFICAR CREDENCIAIS - ROBÔ SSW HOMOLOGADO (P13.4)")
    print("=" * 66)
    print(f"Arquivo esperado: {ENV_PATH}")
    if not ENV_PATH.exists():
        print("Existe           : NÃO")
        if LEGACY_JSON.exists():
            print("Observação        : credenciais.local.json antigo encontrado; execute MIGRAR_CREDENCIAIS_SSW_P13.bat ou CONFIGURAR_CREDENCIAIS_SSW.bat.")
        return 2

    values = _read_env()
    print("Existe           : SIM")
    print(f"SSW_EMPRESA      : {'SIM' if values.get('SSW_EMPRESA') else 'NÃO'}")
    cpf = re.sub(r"\D", "", values.get("SSW_CPF", ""))
    print(f"SSW_CPF          : {'SIM (11 dígitos)' if len(cpf) == 11 else 'NÃO/INVÁLIDO'}")
    print(f"SSW_USUARIO      : {'SIM' if values.get('SSW_USUARIO') else 'NÃO'}")
    print(f"SSW_SENHA        : {'SIM' if values.get('SSW_SENHA') else 'NÃO'}")
    print(f"SSW_URL          : {'SIM' if values.get('SSW_URL') else 'NÃO'}")
    print(f"SSW_OPTION       : {values.get('SSW_OPTION', '(ausente)')}")
    print(f"SSW_UNIT         : {values.get('SSW_UNIT', '(ausente)')}")

    problems = _validate(values)
    if problems:
        print("\nRESULTADO: INCOMPLETO")
        for item in problems:
            print(f" - {item}")
        return 4

    print("\nRESULTADO: CREDENCIAIS COMPLETAS E NO ARQUIVO CORRETO.")
    return 0


def migrate() -> int:
    if not LEGACY_JSON.exists():
        print(f"Arquivo antigo não encontrado: {LEGACY_JSON}")
        return 2
    legacy = _read_legacy_json()
    current = _read_env()
    values = dict(DEFAULTS)
    values.update(current)
    for key, value in legacy.items():
        if value and not values.get(key):
            values[key] = value
    # If .env is absent, legacy values should overwrite defaults such as URL.
    if not ENV_PATH.exists():
        for key, value in legacy.items():
            if value:
                values[key] = value
    values["SSW_UNIT"] = "BEL"
    values["SSW_OPTION"] = "036"
    values["SSW_REPORT_TYPE"] = "ROMANEIOS"
    values["ROBOT_INBOX_DIR"] = str((ROOT / "imports" / "inbox").resolve())
    problems = _validate(values)
    if problems:
        print("Credencial antiga encontrada, mas não possui todos os campos do robô homologado:")
        for item in problems:
            print(f" - {item}")
        print("Execute CONFIGURAR_CREDENCIAIS_SSW.bat para completar os campos.")
        return 3
    _write_env(values)
    print(f"Migração concluída: {LEGACY_JSON.name} -> {ENV_PATH}")
    return verify()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["configure", "verify", "migrate"])
    args = parser.parse_args()
    if args.mode == "configure":
        return configure()
    if args.mode == "verify":
        return verify()
    return migrate()


if __name__ == "__main__":
    raise SystemExit(main())
