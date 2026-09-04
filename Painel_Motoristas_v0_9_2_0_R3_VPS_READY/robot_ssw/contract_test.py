from robot_ssw.config import RobotConfig
from robot_ssw.models import JobRequest

config = RobotConfig.from_env()
payload = {
    "execution_id": "SSW-CONTRACT-TEST",
    "start_date": "2026-08-01",
    "end_date": "2026-08-31",
    "mode": "HISTORICAL",
    "requested_by": "homologacao",
}
job = JobRequest.from_dict(payload, config)
print("Contrato OK:")
print(job.to_public_dict())
