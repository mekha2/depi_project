# Monitoring build of the traffic-app service.
# Used ONLY through docker-compose.monitoring.yml (build context = repository root).
# It builds the same image as app/Dockerfile (same base, same requirements, same
# app/ files) and adds prometheus-client plus metrics_wrapper.py, which exposes /metrics.
# app/app.py itself is not modified.
FROM python:3.11-slim
WORKDIR /app
COPY app/requirements.txt monitoring/app/requirements-metrics.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-metrics.txt
COPY app/ .
COPY monitoring/app/metrics_wrapper.py .
EXPOSE 5000
CMD ["python", "metrics_wrapper.py"]
