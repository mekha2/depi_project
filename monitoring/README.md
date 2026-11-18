# Monitoring (Prometheus + Grafana + cAdvisor)

Adds monitoring on top of the existing stack. No existing file is modified: `docker-compose.monitoring.yml`
is merged over `docker-compose.yml`, and the metrics endpoint is added by `monitoring/app/metrics_wrapper.py`,
which imports the unchanged `app/app.py`.

## Run

```bash
# from the repository root
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d --build
```

| Service | URL | Notes |
|---|---|---|
| Dashboard | http://localhost | unchanged |
| Prometheus | http://localhost:9090 | Status > Targets, Alerts |
| Grafana | http://localhost:3000 | login `admin` / `admin`; dashboard "Traffic Dashboard - Monitoring" in folder "Traffic" |

Change the Grafana login with a git-ignored `.env` file next to the compose files:

```
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=choose-a-password
```

Run without monitoring exactly as before: `docker compose up -d --build`.

## Check

```bash
curl -s localhost:9090/api/v1/targets | grep -o '"health":"[a-z]*"'      # traffic-app, cadvisor, prometheus = up
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml exec traffic-app python -c "import urllib.request;print(urllib.request.urlopen('http://localhost:5000/metrics').read().decode()[:300])"
curl -s localhost:3000/api/health
curl -s -u admin:admin localhost:3000/api/datasources | grep -o '"name":"[A-Za-z]*"'
```

## Metrics (job `traffic-app`)

| Metric | Meaning |
|---|---|
| `traffic_http_requests_total{method,endpoint,status}` | request count by status code (`/metrics` excluded; unknown URLs use `endpoint="unmatched"`) |
| `traffic_http_request_duration_seconds_bucket` | latency histogram |
| `traffic_http_requests_in_progress` | in-flight requests |
| `traffic_data_source_up`, `traffic_data_rows`, `traffic_data_invalid_rows` | CSV readable / valid rows / skipped rows |
| `traffic_data_parse_duration_seconds`, `traffic_data_file_size_bytes`, `traffic_data_file_modified_timestamp_seconds` | CSV read time, size, last change |
| `traffic_sensor_vehicles_per_hour{sensor_id,location}`, `traffic_sensor_status_info{...,status}` | values and status from the CSV |
| `process_*`, `python_gc_*` | CPU and memory of the Flask process |

Container CPU and memory come from cAdvisor (`container_cpu_usage_seconds_total`, `container_memory_working_set_bytes`).

The CSV is read at scrape time (every 15 s), so data-source health is visible even when nobody calls the API.

## Alerts (`prometheus/rules/traffic_alerts.yml`)

| Alert | Condition |
|---|---|
| TrafficAppDown | scrape of traffic-app fails for 1 m |
| TrafficAppHighErrorRate | more than 5% of requests are 5xx for 2 m |
| TrafficAppHighLatency | p95 of `GET /` above 0.5 s for 5 m |
| TrafficDataSourceUnreadable / TrafficDataEmpty / TrafficDataInvalidRows | CSV missing or unparsable / no valid rows / invalid rows for 5 m |
| SensorSevereCongestion | a sensor reports 2000 vehicles/hour or more for 2 m (80% of the dashboard's 2500 capacity) |
| MonitoringTargetDown | Prometheus or cAdvisor target down for 2 m |
| TrafficContainerMissing | `traffic_dashboard` or `traffic_nginx` not seen by cAdvisor for 1 m |
| ContainerHighCpu / ContainerHighMemory | above 80% of one core / above 512 MiB for 5 m |

With the sample CSV, `SensorSevereCongestion` fires for October Bridge (2450) and Ring Road (2100). That is real data, not a fault.
Alerts are visible in Prometheus and in the Grafana "Firing alerts" panel. No Alertmanager is included (no notification channel was required).

## Notes

- `monitoring/app/Dockerfile` repeats the steps of `app/Dockerfile` (same base image, requirements and files) and adds `prometheus-client` plus the wrapper. If `app/Dockerfile` or `app/requirements.txt` changes, mirror the change there.
- cAdvisor runs privileged and mounts Docker's directories (Docker's documented setup). On Docker Desktop (Windows/macOS) container-level metrics may be incomplete.
- Ports 9090 and 3000 must be free on the host.
