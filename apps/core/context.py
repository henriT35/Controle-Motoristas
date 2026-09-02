from django.urls import reverse
from apps.ssw.models import ImportRun
from django.core.cache import cache
from .models import SystemSettings


BUG_SCREEN_BY_URL = {
    "dashboard": "DASHBOARD",
    "operations_today": "OPERATIONS",
    "manifest_detail": "OPERATIONS",
    "deliveries": "OPERATIONS",
    "cte_detail": "OPERATIONS",
    "drivers": "DRIVERS",
    "driver_detail": "DRIVER_PROFILE",
    "proofs": "PROOFS",
    "proof_recover": "PROOFS",
    "clients": "CLIENTS",
    "reports": "REPORTS",
    "report_preview": "REPORTS",
    "ssw_imports": "SSW_IMPORTS",
    "ssw_history": "SSW_HISTORY",
    "settings": "SETTINGS",
}

NAV_STATE_ROOTS = {
    "dashboard": "dashboard",
    "operations_today": "operations",
    "deliveries": "deliveries",
    "drivers": "drivers",
    "proofs": "proofs",
    "clients": "clients",
    "reports": "reports",
    "map_operational": "map",
}

NAV_DEFAULT_ROUTES = {
    "dashboard": "dashboard",
    "operations": "operations_today",
    "deliveries": "deliveries",
    "drivers": "drivers",
    "proofs": "proofs",
    "clients": "clients",
    "reports": "reports",
    "map": "map_operational",
}


def global_context(request):
    settings_obj = None
    last_sync = None
    try:
        settings_obj = SystemSettings.load()
        last_sync = cache.get("context:last_ssw_sync")
        if last_sync is None:
            last_sync = ImportRun.objects.filter(status=ImportRun.Status.SUCCESS).only("id", "finished_at").order_by("-finished_at").first()
            cache.set("context:last_ssw_sync", last_sync, 15)
    except Exception:
        # Migrations ainda podem não ter sido executadas na primeira abertura.
        pass
    active_url_name = getattr(getattr(request, "resolver_match", None), "url_name", "")
    is_authenticated = bool(getattr(request.user, "is_authenticated", False))
    is_coordinator = False
    if is_authenticated and not (getattr(request.user, "is_staff", False) or getattr(request.user, "is_superuser", False)):
        try:
            is_coordinator = request.user.groups.filter(name__iexact="Coordenador").exists()
        except Exception:
            is_coordinator = False
    can_coordinate = bool(is_authenticated and (getattr(request.user, "is_staff", False) or getattr(request.user, "is_superuser", False) or is_coordinator))

    # Persistência global de contexto: as páginas-raiz guardam a própria URL
    # (filtros, período, busca, ordenação, paginação etc.) na sessão. O menu
    # lateral passa a devolver o usuário exatamente ao estado consultado.
    nav_state = {}
    if is_authenticated:
        try:
            nav_state = dict(request.session.get("nav_state_v1", {}))
            nav_key = NAV_STATE_ROOTS.get(active_url_name)
            if request.method == "GET" and nav_key:
                full_path = request.get_full_path()
                if len(full_path) <= 2048:
                    nav_state[nav_key] = full_path
                    request.session["nav_state_v1"] = nav_state
                    request.session.modified = True
        except Exception:
            nav_state = {}
    nav_urls = {}
    for key, route_name in NAV_DEFAULT_ROUTES.items():
        try:
            nav_urls[key] = nav_state.get(key) or reverse(route_name)
        except Exception:
            nav_urls[key] = "/"

    return {
        "system_settings": settings_obj,
        "last_ssw_sync": last_sync,
        "active_url_name": active_url_name,
        "bug_screen_code": BUG_SCREEN_BY_URL.get(active_url_name, ""),
        "can_report_bug": bool(is_authenticated and (getattr(request.user, "is_staff", False) or getattr(request.user, "is_superuser", False))),
        "can_coordinate": can_coordinate,
        "nav_urls": nav_urls,
    }
