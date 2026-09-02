from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
bridge = (ROOT / "whatsapp_bridge" / "server.mjs").read_text(encoding="utf-8")
views = (ROOT / "apps" / "messaging" / "views.py").read_text(encoding="utf-8")
state = (ROOT / "apps" / "messaging" / "state.py").read_text(encoding="utf-8")
pairing = (ROOT / "templates" / "messaging" / "pairing.html").read_text(encoding="utf-8")

assert not (ROOT / "apps" / "messaging" / "cdp_session.py").exists(), "CDP antigo ainda existe"
assert not (ROOT / "apps" / "messaging" / "management" / "commands" / "whatsapp_bot.py").exists(), "bot Playwright antigo ainda existe"
assert "connection.update" in bridge and "qr" in bridge, "bridge não trata QR do Baileys"
assert "sendMessage" in bridge, "bridge não envia mensagens"
assert "messages.upsert" not in bridge, "bridge não deve registrar leitura de mensagens"
assert "baileys_auth" in bridge and "baileys_auth" in state, "sessão Baileys não está em local_data"
assert "internal_claim_message" in views and "internal_message_result" in views, "fila local não está ligada ao bridge"
assert "Baileys / Node.js" in pairing and "Chrome/Edge" not in pairing, "tela de pareamento ainda descreve navegador antigo"
assert "Playwright.connect_over_cdp" not in views, "views ainda dependem de CDP"
print("WHATSAPP BAILEYS STATIC QA: PASS")

installer = (ROOT / "scripts" / "windows" / "install-whatsapp-baileys.ps1").read_text(encoding="utf-8")
assert '$env:Path = "$NodeDir;$env:Path"' in installer, "Node portátil não é exportado para PATH"
assert "npm_node_execpath" in installer, "npm_node_execpath não configurado"
assert "Remove-PartialNodeModules" in installer, "instalação parcial de node_modules não é tratada"
assert "Get-Command node.exe" in installer and "& node.exe -v" in installer, "instalador não prova node no PATH antes do npm"
print("WHATSAPP BAILEYS INSTALLER QA: PASS")
