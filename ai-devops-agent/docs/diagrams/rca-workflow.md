
# Root Cause Analysis Diagram

```mermaid
flowchart TD
    A[Detected Incident] --> B[Collect Relevant Metrics]
    A --> C[Collect Relevant Logs]

    B --> D[Prepare RCA Context]
    C --> D

    D --> E[RCA Engine]
    E --> F[Check Available Evidence]

    F --> G[Send Context to Ollama]
    G --> H[Qwen 2.5 Analysis]

    H --> I[Generate Explanation and Possible Causes]
    I --> J[Separate Evidence from Hypotheses]
    J --> K[Prepare RCA Result]

    K --> L[Incident History]
    K --> M[Notification or Approval Workflow]
