"""Captura opcional das 12 telas reais em 1672x941 (11 telas do produto + Caderno de Bugs).

Execute pelo CAPTURAR_TELAS.bat com o servidor local já iniciado.
"""
from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()

from apps.drivers.models import Driver
from apps.operations.models import Manifest
from apps.core.services import latest_operational_date
from apps.proofs.models import RetainedProof
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8000"
OUT = ROOT / "docs" / "homologacao" / "v0_2_2"
OUT.mkdir(parents=True, exist_ok=True)

latest_manifest = Manifest.objects.order_by("-date").first()
latest_route_date = latest_operational_date()
first_driver = Driver.objects.filter(active=True).first()
first_proof = RetainedProof.objects.first()

routes = [
    ("dashboard.png", "/dashboard/"),
    ("operacao_hoje.png", f"/operacao/hoje/?date={latest_route_date.isoformat()}" if latest_route_date else "/operacao/hoje/"),
    ("motoristas.png", "/motoristas/"),
    ("perfil_motorista.png", f"/motoristas/{first_driver.pk}/" if first_driver else "/motoristas/"),
    ("comprovantes.png", f"/comprovantes/?selected={first_proof.pk}" if first_proof else "/comprovantes/"),
    ("clientes.png", "/clientes/"),
    ("relatorios.png", "/relatorios/"),
    ("importacoes.png", "/ssw/importacoes/"),
    ("historico_robo.png", "/ssw/historico/"),
    ("configuracoes.png", "/configuracoes/"),
    ("caderno_bugs.png", "/bugs/"),
]

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1672, "height": 941}, device_scale_factor=1)
    page.goto(BASE + "/login/", wait_until="networkidle")
    page.screenshot(path=str(OUT / "login.png"), full_page=True)
    page.locator("#id_username").fill(os.getenv("LOCAL_ADMIN_USERNAME", "admin"))
    page.locator("#id_password").fill(os.getenv("LOCAL_ADMIN_PASSWORD", "Painel@2026!"))
    page.locator("button[type=submit]").click()
    page.wait_for_load_state("networkidle")
    for filename, route in routes:
        page.goto(BASE + route, wait_until="networkidle")
        page.screenshot(path=str(OUT / filename), full_page=True)
        print(filename, route)
    browser.close()
print(f"Capturas em: {OUT}")
