from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def text(rel):
    return (ROOT / rel).read_text(encoding="utf-8")

settings = text("config/settings.py")
core_services = text("apps/core/services.py")
dashboard = text("apps/dashboard/views.py")
proofs = text("apps/proofs/views.py")
drivers = text("apps/drivers/views.py")
evaluation = text("apps/drivers/evaluation.py")
operations = text("apps/operations/views.py")
ops_services = text("apps/operations/services.py")
template = text("templates/drivers/quality_reviews.html")

assert "FileBasedCache" in settings, "Windows deve compartilhar cache entre Waitress/scheduler/comandos"
assert 'versioned_key("canonical-manifest-evidence")' in core_services
assert 'cache.set(key, result, timeout=900)' in core_services
assert "refresh_today_opportunities()" not in dashboard
assert "refresh_today_opportunities()" not in proofs
quality_block = drivers.split("def quality_reviews", 1)[1].split("def quality_review_action", 1)[0]
assert "sync_quality_events_for_movements" not in quality_block
assert 'V3_ROLLOUT_DATE = date(2026, 9, 1)' in evaluation
assert 'operation_date__gte=activation' in quality_block
assert 'operational_manifest_evidence_map(d, d)' in operations
assert 'persist_available=False' in operations
assert '_candidate_open_proofs_for_moves' in ops_services
assert 'id="quality-review-modal"' in template and '<details class="quality-review-box">' not in template
assert 'warm_navigation_cache' in text("apps/drivers/management/commands/sync_driver_evaluation_events.py")
assert 'warm_navigation_cache' in text("apps/ssw/import_engine_v2.py")
print("NAVIGATION PERFORMANCE V0.9.2 STATIC QA: PASS")
