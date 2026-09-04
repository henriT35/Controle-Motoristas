from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
def text(rel): return (ROOT / rel).read_text(encoding="utf-8")

evaluation = text("apps/drivers/evaluation.py")
services = text("apps/core/services.py")
ops = text("apps/operations/services.py")
warmup = text("apps/core/warmup.py")
signals = text("apps/core/signals.py")
command = text("apps/drivers/management/commands/sync_driver_evaluation_events.py")
engine = text("apps/ssw/import_engine_v2.py")
views = text("apps/drivers/views.py")
dashboard = text("apps/dashboard/views.py")

assert 'SNAPSHOT_METRIC_KEY = "_metric_v1"' in evaluation
assert 'def load_driver_score_snapshots' in evaluation
assert 'force_recompute=force, allow_snapshot=False' in evaluation
assert 'timer.mark("snapshot_hit")' in services
assert 'allow_snapshot=True' in services and 'force_recompute=False' in services
assert 'snapshot_driver_scores(' in warmup and 'snapshots_current' in warmup
assert 'ImportRun' not in signals
assert 'def materialize_exact_pickup_opportunities' in evaluation
assert 'Source.SYSTEM' in evaluation
assert 'manifests_for_operational_date(day)' in evaluation
assert 'proof__client_id' in services and 'stop_states' in services
assert '"FULFILLED" in states' in services
assert 'delivered_at' in ops and 'evidência mais forte' in ops
assert 'materialize_exact_pickup_opportunities(start=activation)' in command
assert 'materialize_exact_pickup_opportunities(start=start_date, end=end_date, force=True)' in engine
assert 'proof_count=Count("proof_id", distinct=True)' in views
assert '.values("driver_id", "proof__client_id", "operation_date")' in dashboard
print("SNAPSHOT + EXACT HISTORY V0.9.2 STATIC QA: PASS")
