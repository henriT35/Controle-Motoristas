"""Exemplo de chamada pelo worker/job do Painel."""
from robot_ssw import run_job

def executar_relatorio_ssw(execution_id, start_date, end_date, requested_by="system", mode="INCREMENTAL"):
    payload = {
        "execution_id": execution_id,
        "start_date": start_date,
        "end_date": end_date,
        "requested_by": requested_by,
        "mode": mode,
    }

    def status_callback(event):
        # Adapte aqui para atualizar ImportRun/ImportStep do Painel.
        # O Playwright não toca nas tabelas operacionais.
        print("STATUS PARA O PAINEL:", event.to_dict())

    return run_job(payload, status_callback=status_callback)

if __name__ == "__main__":
    print(executar_relatorio_ssw(
        "SSW-20260831-TESTE001", "2026-08-01", "2026-08-31",
        requested_by="homologacao", mode="HISTORICAL"
    ))
