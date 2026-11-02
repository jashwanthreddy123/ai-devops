
# AI DevOps Agent – Monitoring Integration Flow

## 1. Overview

The monitoring layer collects infrastructure metrics and container logs. The Python AI DevOps Agent consumes this information to support incident detection and analysis.

## 2. Prometheus Integration

Prometheus is responsible for collecting and storing time-series metrics.

Typical metrics include:

- CPU utilization
- Memory utilization
- Disk utilization
- System load
- Host availability
- Docker container resource usage

The agent queries Prometheus through its HTTP API.

Local development endpoint:

http://localhost:9090

## 3. Docker and cAdvisor Integration

Docker runs the monitoring and application containers.

cAdvisor exposes container resource usage information, including:

- Container CPU usage
- Container memory usage
- Container activity

Node Exporter exposes host-level system metrics.

Prometheus scrapes the configured exporter endpoints.

## 4. Loki and Promtail Integration

Promtail collects logs from configured sources, including Docker container logs.

The collected logs are forwarded to Loki.

Loki provides log queries through its HTTP API.

Local development endpoint:

http://localhost:3100

The Python agent can query relevant logs to support incident detection and RCA.

## 5. Ollama Integration

Ollama runs the configured language model locally.

The Python RCA engine sends incident context to the Ollama API.

Configured model:

Qwen 2.5

Local development endpoint:

http://localhost:11434

The model provides AI-assisted explanations and recommendations based on the supplied context.

AI output must not replace metric validation, log evidence, or human review.

## 6. End-to-End Monitoring Flow

1. Infrastructure and Docker containers generate metrics and logs.
2. Node Exporter and cAdvisor expose infrastructure metrics.
3. Prometheus collects and stores the metrics.
4. Promtail collects configured logs.
5. Loki stores and provides access to the logs.
6. The Python agent queries Prometheus and Loki.
7. Incident detection evaluates the available information.
8. The RCA engine uses monitoring evidence and Ollama for AI-assisted analysis.
9. The agent can store incident details and send notifications.

See [Monitoring Integration Diagram](diagrams/system-architecture.md).

## 7. Important Notes

- Exporters expose metrics for the hosts or containers they monitor.
- Remote application servers require their own exporters and appropriate network access.
- Prometheus must be configured to scrape the correct exporter targets.
- Loki must receive logs from the intended sources.
- Ollama availability and model configuration must be checked before AI analysis.
- Monitoring endpoints should not be exposed publicly without appropriate access controls.
