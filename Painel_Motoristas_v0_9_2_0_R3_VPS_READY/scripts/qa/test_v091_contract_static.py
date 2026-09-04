from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def text(rel):
    return (ROOT / rel).read_text(encoding="utf-8")

def main():
    drivers = text("apps/drivers/views.py")
    messaging = text("apps/messaging/views.py")
    portal = text("apps/drivers/portal_views.py")
    geo = text("apps/operations/geodata_loader.py")
    geo_summary = text("apps/operations/geo.py")
    proofs = text("apps/proofs/views.py")
    perf = text("apps/core/performance.py")
    services = text("apps/core/services.py")
    cache_layer = text("apps/core/cache.py")
    signals = text("apps/core/signals.py")

    assert 'url_has_allowed_host_and_scheme' in drivers and '_safe_post_redirect' in drivers
    assert 'url_has_allowed_host_and_scheme' in messaging and '_safe_post_redirect' in messaging
    assert 'redirect(request.POST.get("next")' not in drivers
    assert 'redirect(request.POST.get("next")' not in messaging
    assert 'PANEL_PUBLIC_BASE_URL' in portal
    assert 'portal-access-request:' in portal and 'cache.add' in portal
    assert 'MUNICIPIO != BAIRRO' in geo and 'REJECT_TYPES' in geo
    assert 'districts[:25]' not in geo_summary
    assert 'versioned_key("geo-v3"' in geo_summary
    assert 'context:last_ssw_sync' in cache_layer
    assert 'SystemSettings' in signals
    assert 'ImportRun' not in signals, 'ImportRun não deve invalidar ranking a cada atualização de estado'
    assert 'recovery_driver = submission.driver' in proofs
    assert 'original_driver' in services and 'recovery_driver' in services
    assert 'from django.core.cache import cache' in services
    assert 'from .cache import versioned_key' in services
    assert 'versioned_key("operational-evidence"' in services and 'cache.get(key)' in services
    assert 'build_performance_v3_score' in perf and 'Produtividade bruta não participa da nota' in perf
    assert 'primary_issues' in services
    print('V0.9.1 CONTRACT STATIC QA: PASS')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
