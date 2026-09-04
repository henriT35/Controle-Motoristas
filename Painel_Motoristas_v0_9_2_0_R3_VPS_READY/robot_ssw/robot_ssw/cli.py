from __future__ import annotations
import argparse
import json
from pathlib import Path
from .worker import run_job

def main() -> int:
    parser = argparse.ArgumentParser(description="Executor do Robô SSW - Painel Motoristas")
    parser.add_argument("--job", required=True, help="Arquivo JSON criado pelo Painel/integração.")
    args = parser.parse_args()
    job_path = Path(args.job)
    try:
        payload = json.loads(job_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(json.dumps({
            "execution_id": "UNKNOWN", "robot_status": "ERROR",
            "error_code": "JOB_FILE_ERROR", "error_message": str(exc),
        }, ensure_ascii=False, indent=2))
        return 2
    result = run_job(payload)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("robot_status") == "DOWNLOADED" else 1
