"""Diagnósticos reais do robô homologado, sem heurísticas novas."""
from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

from robot_ssw import run_job
from robot_ssw.config import RobotConfig

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env", override=True)


def _login(page, cfg: RobotConfig):
    page.goto(cfg.ssw_url, wait_until="domcontentloaded")
    page.wait_for_timeout(1500)
    page.locator('[id="1"]').fill(cfg.company)
    page.locator('[id="2"]').fill(cfg.cpf)
    page.locator('[id="3"]').fill(cfg.username)
    page.locator('[id="4"]').fill(cfg.password)
    page.wait_for_timeout(700)
    page.get_by_role("link", name="►").click()
    page.wait_for_timeout(2000)
    # A tela autenticada usa id=3 para opção, mas não mantém o campo password id=4.
    if page.locator('[id="4"][type="password"]').count() and page.locator('[id="4"][type="password"]').first.is_visible():
        raise RuntimeError("Login permaneceu na tela de autenticação.")


def _open_036(page, cfg: RobotConfig):
    campo = page.locator('[id="3"]')
    campo.fill(cfg.option)
    page.wait_for_timeout(600)
    with page.expect_popup(timeout=cfg.action_timeout_ms) as popup_info:
        campo.press("Enter")
    popup = popup_info.value
    popup.wait_for_load_state("domcontentloaded")
    popup.wait_for_timeout(1500)
    return popup


def run_stage(stage: str, start: date, end: date) -> int:
    cfg = RobotConfig.from_env()
    evidence_dir = ROOT / "diagnostico_p13"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    if stage == "download":
        payload = {
            "execution_id": "SSW-P13-DIAG-DOWNLOAD",
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "mode": "MANUAL",
            "requested_by": "diagnostico",
            "download_dir": str(evidence_dir / "download"),
        }
        result = run_job(payload, status_callback=lambda e: print(f"[{e.state}] {e.detail or ''}"))
        print("Resultado:", result.get("robot_status"), result.get("error_code") or "")
        if result.get("robot_status") == "DOWNLOADED":
            print("Arquivo:", result.get("file_path"))
            print("SHA-256:", result.get("sha256"))
            return 0
        print("Erro:", result.get("error_message"))
        return 20

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=cfg.slow_mo)
        context = browser.new_context(accept_downloads=True)
        context.set_default_timeout(cfg.action_timeout_ms)
        page = context.new_page()
        try:
            print("Abrindo login homologado...")
            _login(page, cfg)
            print("LOGIN OK")
            if stage == "login":
                return 0

            print("Abrindo opção 036 com fill + Enter + expect_popup...")
            popup = _open_036(page, cfg)
            print("OPÇÃO 036 OK")
            if stage == "option":
                return 0

            popup.locator("#t_excel").fill("S")
            popup.locator("#t_unidade").fill("BEL")
            popup.locator("#t_dt_ini").fill(start.strftime("%d%m%y"))
            popup.locator("#t_dt_fin").fill(end.strftime("%d%m%y"))
            popup.wait_for_timeout(800)
            popup.screenshot(path=str(evidence_dir / "evidence_form_036.png"), full_page=True)
            print("FORMULÁRIO 036 OK - S / BEL / DDMMAA preenchidos. Nenhum relatório foi gerado.")
            return 0
        except Exception as exc:
            try:
                target = locals().get("popup", page)
                target.screenshot(path=str(evidence_dir / f"evidence_{stage}_erro.png"), full_page=True)
            except Exception:
                pass
            print(f"ERRO {stage}: {exc}")
            return 20
        finally:
            context.close()
            browser.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=["login", "option", "form", "download"], required=True)
    parser.add_argument("--start", default=date.today().replace(day=1).isoformat())
    parser.add_argument("--end", default=date.today().isoformat())
    args = parser.parse_args()
    return run_stage(args.stage, date.fromisoformat(args.start), date.fromisoformat(args.end))


if __name__ == "__main__":
    raise SystemExit(main())
