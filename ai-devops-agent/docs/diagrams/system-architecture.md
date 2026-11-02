
# System Architecture Diagram

```mermaid
flowchart TD
    A[Infrastructure and Docker Containers]

    A --> B[Node Exporter]
    A --> C[cAdvisor]
    A --> D[Promtail]

    B --> E[Prometheus]
    C --> E
    D --> F[Loki]

    E --> G[Python AI DevOps Agent]
    F --> G

    G --> H[Incident Detection]
    H --> I[Alert Deduplication]
    I --> J[RCA Engine]

    J --> K[Ollama - Qwen 2.5]
    J --> L[Incident History]
    J --> M[Email Notification]
    J --> N[Human Approval]

    N --> O[Controlled Remediation]
    O --> P[Execution Result and Audit]
