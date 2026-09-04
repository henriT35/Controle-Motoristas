FROM mcr.microsoft.com/playwright/python:v1.62.0-noble

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY requirements.txt /app/requirements.txt
COPY robot_ssw/requirements.txt /app/robot-requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt -r /app/robot-requirements.txt
COPY . /app
RUN chmod +x /app/scripts/docker/*.sh
ENTRYPOINT ["bash", "/app/scripts/docker/robot-entrypoint.sh"]
CMD ["celery", "-A", "config", "worker", "-Q", "ssw", "--loglevel=INFO", "--concurrency=1", "--hostname=ssw@%h"]
