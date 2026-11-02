
# AI DevOps Agent – Operational Workflows

## 1. Incident Detection Workflow

1. The agent retrieves relevant infrastructure metrics from Prometheus.
2. The agent retrieves relevant application or container logs from Loki.
3. Detection logic evaluates the available monitoring information.
4. Potential incidents are identified.
5. Incident details are prepared for analysis.
6. Alert deduplication checks whether the incident has already been notified.

Diagram: [Incident Detection](diagrams/incident-detection.md).

## 2. Root Cause Analysis (RCA) Workflow

1. The detected incident is passed to the RCA engine.
2. Relevant metrics and logs are considered as evidence.
3. The RCA engine prepares the analysis request.
4. Ollama runs the configured Qwen 2.5 model.
5. The model generates an explanation and possible causes.
6. The agent processes the analysis result.
7. Incident information can be stored in incident history.

AI-generated explanations must be distinguished from confirmed monitoring evidence.

Diagram: [RCA Workflow](diagrams/rca-workflow.md).

## 3. Email Alerting Workflow

1. An incident requiring notification is identified.
2. Alert deduplication and cooldown logic are evaluated.
3. The email notifier prepares the incident notification.
4. SMTP configuration is used to send the email.
5. Successful notification handling updates the alert state.

SMTP credentials must be stored securely outside the Git repository.

Diagram: [Email Alerting](diagrams/email-alerting.md).

## 4. Human Approval Workflow

1. The agent identifies an incident.
2. A remediation recommendation may be prepared.
3. The proposed action is submitted to the approval workflow.
4. An authorized human reviews the proposed action.
5. The action is approved or rejected.
6. Only an approved action may proceed to the remediation component.

Diagram: [Approval and Remediation](diagrams/approval-remediation.md).

## 5. Controlled Remediation Workflow

1. The remediation executor receives an approved action.
2. The action and its parameters are validated.
3. Execution takes place with restricted permissions.
4. The execution result is captured.
5. The result is made available for review and audit.

The system must not execute arbitrary AI-generated shell commands without validation and explicit authorization.

## 6. Safety Requirements

- Require human approval before controlled remediation.
- Validate commands and parameters before execution.
- Use least-privilege permissions.
- Record approval and execution outcomes.
- Do not expose credentials in notifications or logs.
- Provide a safe rejection path when approval is denied.
