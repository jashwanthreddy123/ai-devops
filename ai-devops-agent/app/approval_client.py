"""Submit incidents for human approval; never execute remediation."""

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import requests

TOKEN_FILE = Path("/etc/ai-devops-approval.token")
API_PORT = 8089
DEDUPLICATION_SECONDS = 3600
REQUEST_TIMEOUT = 5


def _api_base_url():
    """Discover the approval API's current monitoring-network IP."""
    result = subprocess.run(
        [
            "docker", "inspect", "-f",
            '{{(index .NetworkSettings.Networks "monitoring").IPAddress}}',
            "approval-api",
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=5,
    )
    ip = result.stdout.strip()

    if not ip:
        raise RuntimeError("Approval API monitoring IP was not found")

    return f"http://{ip}:{API_PORT}"


def _incident_reference(incident):
    """Generate a stable reference for the same incident signature."""
    signature = "|".join([
        str(incident.get("source", "unknown")),
        str(incident.get("title", "unknown")),
        str(incident.get("details", "")),
    ])
    digest = hashlib.sha256(signature.encode("utf-8")).hexdigest()[:32]
    return f"agent-{digest}"


def _is_duplicate(records, incident_ref, now):
    """Suppress pending duplicates and recently created repeat requests."""
    for record in records:
        if record.get("incident_ref") != incident_ref:
            continue

        # Never create a second request while this one is pending.
        if record.get("status") == "pending":
            return True

        created_at = record.get("created_at")
        if not created_at:
            continue

        try:
            created = datetime.fromisoformat(
                created_at.replace("Z", "+00:00")
            )
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)

            age = (now - created).total_seconds()
            if 0 <= age < DEDUPLICATION_SECONDS:
                return True
        except (TypeError, ValueError):
            continue

    return False


def submit_incident_approvals(incidents, rca_result, dry_run=False):
    """
    Submit WARNING/CRITICAL incidents for human review.

    The API records approval decisions only. This client does not execute
    collect_diagnostics, restart_container, rollback_deployment, or commands.
    """
    candidates = [
        item for item in incidents
        if item.get("severity") in ("WARNING", "CRITICAL")
    ]

    if not candidates:
        print("Approval workflow: no WARNING/CRITICAL incidents to submit.")
        return

    try:
        token = TOKEN_FILE.read_text(encoding="utf-8").strip()
        if not token:
            raise RuntimeError("Approval API token file is empty")

        base_url = _api_base_url()
        headers = {"Authorization": f"Bearer {token}"}

        response = requests.get(
            f"{base_url}/api/approvals",
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        records = response.json()

        if not isinstance(records, list):
            raise RuntimeError("Approval API returned an unexpected response")

        now = datetime.now(timezone.utc)
        submitted = 0
        skipped = 0

        for incident in candidates:
            incident_ref = _incident_reference(incident)

            if _is_duplicate(records, incident_ref, now):
                print(
                    "Approval request skipped (duplicate): "
                    f"{incident.get('title', 'Unknown incident')}"
                )
                skipped += 1
                continue

            severity = (
                "critical"
                if incident.get("severity") == "CRITICAL"
                else "medium"
            )

            payload = {
                "incident_ref": incident_ref,
                "severity": severity,
                "title": str(
                    incident.get("title", "Monitoring incident")
                )[:500],
                "action": "collect_diagnostics",
                "action_params": {
                    "source": str(incident.get("source", "unknown")),
                    "details": str(incident.get("details", ""))[:1000],
                    "occurrences": incident.get("occurrences", 1),
                    "rca_status": str(
                        rca_result.get("status", "UNKNOWN")
                    )[:100],
                    "rca_summary": str(
                        rca_result.get("analysis", "")
                    )[:1000],
                    "execution_enabled": False,
                },
                "requested_by": "ai-devops-agent",
            }

            if dry_run:
                print(
                    "DRY RUN — approval request payload:\n"
                    + json.dumps(payload, indent=2)
                )
                continue

            response = requests.post(
                f"{base_url}/api/approvals",
                headers=headers,
                json=payload,
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            record = response.json()

            # Track this run's submissions to prevent in-run duplicates.
            records.insert(0, record)
            submitted += 1
            print(
                "Approval request created: "
                f"id={record.get('id')}, "
                f"status={record.get('status')}, "
                f"title={payload['title']}"
            )

        print(
            "Approval workflow summary: "
            f"created={submitted}, duplicate_skipped={skipped}, "
            f"execution_enabled=false"
        )

    except Exception as error:
        # Approval API failure must not stop monitoring or email alerts.
        print(
            "WARNING: approval workflow unavailable; "
            f"monitoring will continue ({type(error).__name__}: {error})"
        )
