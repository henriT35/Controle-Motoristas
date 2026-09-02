from __future__ import annotations

import re

from django.urls import reverse
from django.conf import settings

from apps.drivers.models import DriverPortalAccess
from apps.operations.services import build_manifest_cards, opportunities_summary

_DIGITS = re.compile(r"\D+")


def normalize_whatsapp_phone(value: str | None) -> str:
    digits = _DIGITS.sub("", value or "")
    if not digits:
        return ""
    if digits.startswith("00"):
        digits = digits[2:]
    if len(digits) in {10, 11}:
        digits = "55" + digits
    return digits



def whatsapp_phone_candidates(value: str | None) -> list[str]:
    """Retorna variações brasileiras com e sem o 9º dígito.

    O WhatsApp/Baileys pode devolver o JID brasileiro legado sem o nono dígito
    mesmo quando o cadastro humano possui 9 na frente. O bridge verifica as
    duas formas no próprio WhatsApp antes de enviar.
    """
    digits = normalize_whatsapp_phone(value)
    if not is_valid_whatsapp_phone(digits):
        return []
    candidates = [digits]
    if digits.startswith("55"):
        national = digits[2:]
        if len(national) == 11 and national[2:3] == "9":
            candidates.append("55" + national[:2] + national[3:])
        elif len(national) == 10:
            candidates.append("55" + national[:2] + "9" + national[2:])
    return list(dict.fromkeys(candidates))

def ensure_portal_access(driver):
    access, _ = DriverPortalAccess.objects.get_or_create(driver=driver)
    if not access.active:
        access.active = True
        access.save(update_fields=["active"])
    return access


def is_valid_whatsapp_phone(value: str | None) -> bool:
    digits = normalize_whatsapp_phone(value)
    return digits.startswith("55") and len(digits) in {12, 13}




def public_portal_ready(request=None) -> bool:
    public_base = (getattr(settings, "PANEL_PUBLIC_BASE_URL", "") or "").strip()
    if public_base:
        return public_base.lower().startswith(("https://", "http://"))
    if request is None:
        return False
    host = (request.get_host() or "").split(":", 1)[0].strip().lower()
    return host not in {"127.0.0.1", "localhost", "::1", "0.0.0.0"}

def _portal_url(request, access) -> str:
    path = reverse("driver_portal", args=[access.token])
    public_base = getattr(settings, "PANEL_PUBLIC_BASE_URL", "") or ""
    if public_base:
        return public_base.rstrip("/") + path
    if request is not None:
        return request.build_absolute_uri(path)
    return path


def existing_portal_url(request, driver) -> str:
    access = DriverPortalAccess.objects.filter(driver=driver, active=True).first()
    return _portal_url(request, access) if access else ""


def portal_url_for(request, driver) -> str:
    # A criação/ativação é feita somente quando existe intenção de envio. Abrir a
    # central não deve alterar segurança/estado do motorista por efeito colateral.
    access = ensure_portal_access(driver)
    return _portal_url(request, access)


def driver_operation_summary(manifests, operation_date):
    cards = build_manifest_cards(list(manifests), persist_available=False, operational_date=operation_date)
    exact_ids, regional_ids = opportunities_summary(cards)
    clients = sum(int(c.get("clients", 0)) for c in cards)
    movements = sum(int(c.get("movements", 0)) for c in cards)
    return {
        "routes": len(cards),
        "clients": clients,
        "movements": movements,
        "opportunities": len(set(exact_ids) | set(regional_ids)),
        "cards": cards,
    }


def build_daily_message(driver, operation_date, summary, portal_url):
    day = operation_date.strftime("%d/%m/%Y")
    opportunities = int(summary.get("opportunities", 0))
    extra = (
        f"\nHá {opportunities} comprovante(s) pendente(s) em clientes/regiões compatíveis com sua operação."
        if opportunities else
        "\nNo momento não há comprovantes pendentes identificados para sua rota/região."
    )
    return (
        f"Olá, {driver.name}.\n\n"
        f"Sua operação de {day} está disponível no Painel Motoristas.\n"
        f"Rotas/romaneios: {summary.get('routes', 0)}\n"
        f"Clientes: {summary.get('clients', 0)}\n"
        f"CT-es/tentativas: {summary.get('movements', 0)}"
        f"{extra}\n\n"
        f"Abra seu painel individual:\n{portal_url}\n\n"
        "O link mostra sua operação e permite enviar foto de comprovantes recuperados para validação."
    )


def build_manifest_message(driver, operation_date, manifest, card, portal_url, *, planned=False):
    day = operation_date.strftime("%d/%m/%Y")
    opportunities = len(card.get("exact", ())) + len(card.get("regional", ()))
    if planned:
        intro = (
            f"Há um romaneio preparado no Painel (referência {day}), mas a data de execução "
            "ainda não foi confirmada pela saída para entrega.\n"
        )
    else:
        intro = f"Atualização da sua operação de {day}.\n"
    return (
        f"Olá, {driver.name}.\n\n"
        f"{intro}"
        f"Romaneio: {manifest.number}\n"
        f"Clientes: {card.get('clients', 0)}\n"
        f"CT-es/tentativas: {card.get('movements', 0)}\n"
        f"Oportunidades de comprovante: {opportunities}\n\n"
        f"Acesse seu painel individual:\n{portal_url}"
    )


def build_general_portal_message(driver, portal_url):
    return (
        f"Olá, {driver.name}.\n\n"
        "Seu acesso ao Painel Motoristas está disponível. "
        "Por esse link você acompanha sua operação e pode enviar comprovantes para validação quando necessário.\n\n"
        f"Acesse seu painel individual:\n{portal_url}"
    )
