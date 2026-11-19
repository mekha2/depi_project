"""Prometheus instrumentation for the existing Flask application.

This file imports the unmodified Flask object from app.py and adds:
  * HTTP request metrics (count by method/endpoint/status, latency histogram, in-flight)
  * a /metrics endpoint
  * a data-source collector that reads the same CSV the app serves, at scrape time,
    and reports its health, size, freshness and per-sensor values

Every value comes from real requests and the real CSV file. Nothing is generated.
"""
import csv
import math
import os
import time

from flask import Response, g, request
from prometheus_client import CONTENT_TYPE_LATEST, REGISTRY, Counter, Gauge, Histogram, generate_latest
from prometheus_client.core import GaugeMetricFamily

from app import app  # the existing application, unchanged

DATA_FILE = os.environ.get("TRAFFIC_DATA_FILE", "traffic_data.csv")  # same relative path app.py opens

# ---------------------------------------------------------------- HTTP metrics
HTTP_REQUESTS = Counter(
    "traffic_http_requests_total",
    "HTTP requests handled by the traffic app, excluding /metrics.",
    ["method", "endpoint", "status"],
)
HTTP_LATENCY = Histogram(
    "traffic_http_request_duration_seconds",
    "Time spent handling HTTP requests, excluding /metrics.",
    ["method", "endpoint"],
    buckets=(0.001, 0.0025, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5),
)
HTTP_IN_PROGRESS = Gauge(
    "traffic_http_requests_in_progress",
    "HTTP requests currently being handled, excluding /metrics.",
)


@app.before_request
def _start_timer():
    if request.path == "/metrics":
        return
    g._metrics_start = time.perf_counter()
    HTTP_IN_PROGRESS.inc()


@app.after_request
def _record_request(response):
    start = getattr(g, "_metrics_start", None)
    if start is not None:
        # Unknown URLs share one label value so scanners cannot create unlimited series.
        endpoint = request.url_rule.rule if request.url_rule else "unmatched"
        HTTP_LATENCY.labels(request.method, endpoint).observe(time.perf_counter() - start)
        HTTP_REQUESTS.labels(request.method, endpoint, str(response.status_code)).inc()
    return response


@app.teardown_request
def _finish_request(_exc):
    if getattr(g, "_metrics_start", None) is not None:
        HTTP_IN_PROGRESS.dec()
        g._metrics_start = None


@app.route("/metrics")
def metrics():
    return Response(generate_latest(REGISTRY), content_type=CONTENT_TYPE_LATEST)


# ------------------------------------------------------- traffic data collector
class TrafficDataCollector:
    """Reads the CSV on every scrape, so a missing, unreadable or malformed file is visible
    even when nobody is calling the API. Stale series disappear when a sensor disappears."""

    def collect(self):
        sensors, invalid, readable = [], 0, 1
        began = time.perf_counter()
        try:
            with open(DATA_FILE, "r", newline="") as handle:
                for row in csv.DictReader(handle):
                    try:
                        sensor, location, status = row["sensor_id"], row["location"], row["status"]
                        vehicles = float(row["vehicles_per_hour"])
                        if None in (sensor, location, status) or not math.isfinite(vehicles) or vehicles < 0:
                            raise ValueError("invalid row")
                        sensors.append((sensor, location, status, vehicles))
                    except (KeyError, TypeError, ValueError):
                        invalid += 1
        except (OSError, csv.Error, UnicodeDecodeError):
            readable = 0
        parse_seconds = time.perf_counter() - began

        yield GaugeMetricFamily(
            "traffic_data_source_up", "1 if the traffic CSV could be read and parsed, else 0.", value=readable)
        yield GaugeMetricFamily(
            "traffic_data_rows", "Valid sensor rows in the traffic CSV.", value=len(sensors))
        yield GaugeMetricFamily(
            "traffic_data_invalid_rows", "Rows skipped because of missing or non-numeric values.", value=invalid)
        yield GaugeMetricFamily(
            "traffic_data_parse_duration_seconds", "Time taken to read and validate the CSV.", value=parse_seconds)

        try:
            info = os.stat(DATA_FILE)
            yield GaugeMetricFamily(
                "traffic_data_file_modified_timestamp_seconds", "Last modification time of the CSV (unix seconds).",
                value=info.st_mtime)
            yield GaugeMetricFamily("traffic_data_file_size_bytes", "Size of the CSV file.", value=info.st_size)
        except OSError:
            pass

        vehicles_metric = GaugeMetricFamily(
            "traffic_sensor_vehicles_per_hour", "Vehicles per hour reported by each sensor.",
            labels=["sensor_id", "location"])
        status_metric = GaugeMetricFamily(
            "traffic_sensor_status_info", "Congestion status reported by each sensor (value is always 1).",
            labels=["sensor_id", "location", "status"])
        for sensor, location, status, vehicles in sensors:
            vehicles_metric.add_metric([sensor, location], vehicles)
            status_metric.add_metric([sensor, location, status], 1)
        yield vehicles_metric
        yield status_metric


REGISTRY.register(TrafficDataCollector())

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
