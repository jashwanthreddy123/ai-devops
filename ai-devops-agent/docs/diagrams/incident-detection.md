# Incident Detection Diagram

```mermaid
flowchart TD
    A[Start Monitoring] --> B[Collect Prometheus Metrics]
    A --> C[Collect Loki Logs]

    B --> D[Evaluate Monitoring Data]
    C --> D

    D --> E{Potential Incident?}

    E -->|No| F[Continue Monitoring]
    F --> A

    E -->|Yes| G[Prepare Incident Details]
    G --> H[Check Alert Deduplication]

    H --> I{Already Notified?}

    I -->|Yes| J[Apply Cooldown Logic]
    I -->|No| K[Process New Incident]

    J --> F
    K --> L[Send for RCA]
