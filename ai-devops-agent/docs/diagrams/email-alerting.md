
# Email Alerting Diagram

```mermaid
flowchart TD
    A[Incident Detected] --> B[Prepare Alert]
    B --> C[Check Deduplication]
    C --> D{Notification Allowed?}

    D -->|No| E[Skip Duplicate Notification]
    E --> F[Continue Monitoring]

    D -->|Yes| G[Apply Cooldown Rules]
    G --> H[Prepare Email Message]

    H --> I[SMTP Configuration]
    I --> J[Send Email]

    J --> K{Send Successful?}

    K -->|Yes| L[Record Notification Success]
    K -->|No| M[Handle Notification Failure]

    L --> F
    M --> F
