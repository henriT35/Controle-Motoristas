"""Teste contratual do core homologado sem navegador/SSW real.

Monkeypatcha apenas o transporte Playwright. O worker.py permanece intocado e o
teste prova a sequência homologada: login ►, 036+Enter, popup, S/BEL/DDMMAA,
#btn_env_periodo.click() dentro de expect_download() e DOWNLOADED.
"""
from __future__ import annotations

from pathlib import Path
import tempfile

from robot_ssw import run_job
from robot_ssw.config import RobotConfig
import robot_ssw.worker as worker

REPORT = b"ROMANEIO;CTRC;STATUS\nR1;123;OK\n"


class Box:
    def __init__(self, value): self.value = value
    def __enter__(self): return self
    def __exit__(self, *args): return False


class FakeDownload:
    suggested_filename = "mock_036.sswweb"
    def save_as(self, path): Path(path).write_bytes(REPORT)
    def failure(self): return None


class FakeLocator:
    def __init__(self, owner, selector): self.owner, self.selector = owner, selector
    def fill(self, value): self.owner.calls.append(("fill", self.selector, value))
    def press(self, key): self.owner.calls.append(("press", self.selector, key))
    def click(self): self.owner.calls.append(("click", self.selector))
    def count(self): return 0
    @property
    def first(self): return self


class FakePage:
    def __init__(self, name="page"):
        self.name = name
        self.calls = []
        self.popup = None
    def goto(self, url, wait_until=None): self.calls.append(("goto", url, wait_until))
    def wait_for_timeout(self, ms): self.calls.append(("wait", ms))
    def locator(self, selector): return FakeLocator(self, selector)
    def get_by_role(self, role, name=None): return FakeLocator(self, f"role={role};name={name}")
    def expect_popup(self, timeout=None):
        self.calls.append(("expect_popup", timeout))
        return Box(self.popup)
    def wait_for_load_state(self, state): self.calls.append(("load_state", state))
    def expect_download(self, timeout=None):
        self.calls.append(("expect_download", timeout))
        return Box(FakeDownload())
    def screenshot(self, **kwargs): self.calls.append(("screenshot", kwargs))


class FakeContext:
    def __init__(self, page): self.page = page
    def set_default_timeout(self, ms): self.page.calls.append(("default_timeout", ms))
    def new_page(self): return self.page
    def close(self): pass


class FakeBrowser:
    def __init__(self, page): self.page = page
    def new_context(self, accept_downloads=True): return FakeContext(self.page)
    def close(self): pass


class FakeChromium:
    def __init__(self, page): self.page = page
    def launch(self, headless=False, slow_mo=0):
        self.page.calls.append(("launch", headless, slow_mo))
        return FakeBrowser(self.page)


class FakePlaywright:
    def __init__(self, page): self.chromium = FakeChromium(page)


class FakeSync:
    def __init__(self, pw): self.pw = pw
    def __enter__(self): return self.pw
    def __exit__(self, *args): return False


def main() -> int:
    main_page = FakePage("login_menu")
    popup = FakePage("036")
    main_page.popup = popup
    fake_pw = FakePlaywright(main_page)
    original = worker.sync_playwright
    worker.sync_playwright = lambda: FakeSync(fake_pw)
    states = []
    try:
        with tempfile.TemporaryDirectory(prefix="robot_p13_") as tmp:
            cfg = RobotConfig(
                ssw_url="https://mock.invalid/bin/ssw0422",
                company="001", cpf="12345678901", username="usuario", password="senha123",
                default_unit="BEL", report_type="ROMANEIOS", option="036",
                headless=True, slow_mo=0, action_timeout_ms=30000, download_timeout_ms=120000,
                max_days=31, inbox_dir=Path(tmp),
            )
            payload = {
                "execution_id": "SSW-MOCK-P13",
                "start_date": "2026-08-01", "end_date": "2026-08-31",
                "mode": "HISTORICAL", "requested_by": "qa",
                "download_dir": str(Path(tmp) / "SSW-MOCK-P13"),
            }
            result = run_job(payload, status_callback=lambda e: states.append(e.state), config=cfg)
            assert result["robot_status"] == "DOWNLOADED", result
            assert states == ["ROBOT_STARTING", "AUTHENTICATING", "REQUESTING_REPORT", "WAITING_DOWNLOAD", "DOWNLOADED"], states
            assert ("fill", '[id="1"]', "001") in main_page.calls
            assert ("fill", '[id="2"]', "12345678901") in main_page.calls
            assert ("fill", '[id="3"]', "usuario") in main_page.calls
            assert ("fill", '[id="4"]', "senha123") in main_page.calls
            assert ("click", "role=link;name=►") in main_page.calls
            assert ("fill", '[id="3"]', "036") in main_page.calls
            assert ("press", '[id="3"]', "Enter") in main_page.calls
            assert ("fill", "#t_excel", "S") in popup.calls
            assert ("fill", "#t_unidade", "BEL") in popup.calls
            assert ("fill", "#t_dt_ini", "010826") in popup.calls
            assert ("fill", "#t_dt_fin", "310826") in popup.calls
            assert any(c[0] == "expect_download" for c in popup.calls)
            assert ("click", "#btn_env_periodo") in popup.calls
            output = Path(result["file_path"])
            assert output.exists() and output.read_bytes() == REPORT
            print("P13 CORE CONTRACT: PASS")
            print("Fluxo: login ► -> 036+Enter -> popup -> S/BEL/DDMMAA -> click -> download")
            return 0
    finally:
        worker.sync_playwright = original


if __name__ == "__main__":
    raise SystemExit(main())
