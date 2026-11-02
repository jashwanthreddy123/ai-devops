
# AI DevOps Agent – System Architecture

## 1. Introduction

The AI DevOps Agent is an AI-assisted infrastructure monitoring and incident analysis platform. It combines traditional observability tools with Python-based automation and a locally hosted Large Language Model (LLM).

The system is designed to help DevOps engineers detect infrastructure issues, investigate logs and metrics, understand possible root causes, and review controlled remediation actions.

## 2. Architecture Overview

The system contains these major layers:

1. Infrastructure and container layer
2. Monitoring and logging layer
3. Python agent and incident processing layer
4. AI-assisted analysis layer
5. Notification and incident history layer
6. Human approval and remediation layer

## 3. Main Components

| Component | Responsibility |
|---|---|
| Prometheus | Collects and stores monitoring metrics |
| Node Exporter | Exposes host-level metrics |
| cAdvisor | Exposes Docker container metrics |
| Promtail | Collects and forwards container logs |
| Loki | Stores and queries logs |
| Python Agent | Coordinates monitoring and incident processing |
| Incident Detector | Identifies potential incidents |
| Alert Deduplicator | Prevents repeated notifications |
| RCA Engine | Analyzes incident evidence |
| Ollama | Runs the local AI model |
| Qwen 2.5 | Generates AI-assisted explanations |
| Incident History | Stores and retrieves incident records |
| Email Notifier | Sends incident notifications |
| Approval Client | Handles human approval workflow |
| Remediation Executor | Executes approved remediation actions |

## 4. Architecture Diagram

See [System Architecture Diagram](diagrams/system-architecture.md).

## 5. Design Principles

- Monitoring metrics and logs are the primary operational evidence.
- AI-generated explanations are recommendations, not confirmed facts.
- Incident notifications should be deduplicated.
- Incident information should be available for historical review.
- Human approval must be required before controlled remediation.
- Credentials and secrets must never be committed to source control.
- Remediation execution must use restricted permissions and audit logging.

## 6. Technology Stack

- Python
- Ollama
- Qwen 2.5
- Prometheus
- Grafana
- Loki
- Promtail
- Node Exporter
- cAdvisor
- Docker
- Docker Compose
- Pytest
- Git and GitHub
