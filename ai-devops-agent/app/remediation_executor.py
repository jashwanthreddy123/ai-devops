"""
Controlled remediation executor.

Initial implementation:
- Executes only collect_diagnostics.
- Requires an approved API record.
- Requires exact approval ID, incident reference, action and parameters.
- Uses a persistent one-time execution ledger.
- Never executes arbitrary shell commands.
- Container restart and deployment rollback are disabled.
"""

import json
import os
import shutil
import socket
import sqlite3
import subprocess
from pathlib import Path

import requests


TOKEN_FILE = Path("/etc/ai-devops-approval.token")
AUDIT_DB = Path("/var/lib/ai-devops-agent/remediation-executions.db")

API_PORT = 8089
REQUEST_TIMEOUT = 5
EXECUTION_TIMEOUT = 10

EXECUTABLE_ACTIONS = {"collect_diagnostics"}

# Global kill switch: execution stays disabled unless explicitly enabled.
REMEDIATION_EXECUTION_ENABLED = (
    os.environ.get("REMEDIATION_EXECUTION_ENABLED", "false").lower()
    == "true"
)


def _api_base_url():
    result = subprocess.run(
        [
            "docker", "inspect", "-f",
            '{{(index .NetworkSettings.Networks "monitoring").IPAddress}}',
            "approval-api",
        ],
        capture_output=True,
        text=True,
        timeout=5,
        check=True,
    )

    ip = result.stdout.strip()
    if not ip:
        raise RuntimeError("Approval API address not found")

    return f"http://{ip}:{API_PORT}"


def _get_approval(approval_id):
    token = TOKEN_FILE.read_text(encoding="utf-8").strip()

    if len(token) < 32:
        raise RuntimeError("Approval API token is missing or invalid")

    response = requests.get(
        f"{_api_base_url()}/api/approvals",
        headers={"Authorization": f"Bearer {token}"},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()

    records = response.json()
    if not isinstance(records, list):
        raise RuntimeError("Invalid approval API response")

    matches = [
        item for item in records
        if item.get("id") == approval_id
    ]

    if len(matches) != 1:
        raise RuntimeError(
            "Approval not found in the API's returned records"
        )

    return matches[0]


def _initialize_audit_db():
    AUDIT_DB.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(AUDIT_DB, timeout=5) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS executions (
                approval_id INTEGER PRIMARY KEY,
                incident_ref TEXT NOT NULL,
                action TEXT NOT NULL,
                status TEXT NOT NULL,
                started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                finished_at TEXT,
                result_json TEXT
            )
        """)

    os.chmod(AUDIT_DB, 0o600)


def _claim_execution(approval):
    """Atomically reserve this approval ID; never execute it twice."""
    with sqlite3.connect(AUDIT_DB, timeout=5) as con:
        con.execute("BEGIN IMMEDIATE")
        try:
            con.execute("""
                INSERT INTO executions (
                    approval_id, incident_ref, action, status
                ) VALUES (?, ?, ?, 'running')
            """, (
                approval["id"],
                approval["incident_ref"],
                approval["action"],
            ))
            con.commit()
        except sqlite3.IntegrityError:
            con.rollback()
            raise RuntimeError(
                "This approval ID has already been used or reserved"
            )


def _finish_execution(approval_id, status, result):
    """Finalize a running execution exactly once."""

    if isinstance(approval_id, bool) or not isinstance(approval_id, int) or approval_id < 1:
        raise ValueError("A valid approval ID is required")

    if status not in {"completed", "failed"}:
        raise ValueError("Final status must be completed or failed")

    if not isinstance(result, dict):
        raise ValueError("Execution result must be an object")

    result_json = json.dumps(result, sort_keys=True)

    with sqlite3.connect(AUDIT_DB, timeout=5) as con:
        cursor = con.execute("""
            UPDATE executions
            SET status = ?,
                finished_at = CURRENT_TIMESTAMP,
                result_json = ?
            WHERE approval_id = ?
              AND status = 'running'
        """, (
            status,
            result_json,
            approval_id,
        ))

        if cursor.rowcount != 1:
            raise RuntimeError(
                "Execution record is missing or is not in running status"
            )


def _read_memory():
    """Read basic memory information from Linux /proc."""
    values = {}

    with open("/proc/meminfo", encoding="utf-8") as handle:
        for line in handle:
            key, value = line.split(":", 1)
            if key in ("MemTotal", "MemAvailable"):
                values[key] = value.strip()

    return values


def _collect_diagnostics():
    """Collect basic read-only host and Docker diagnostics."""
    disk = shutil.disk_usage("/")
    load_average = Path("/proc/loadavg").read_text(
        encoding="utf-8"
    ).strip()

    docker = subprocess.run(
        [
            "docker", "ps",
            "--no-trunc",
            "--format", "{{.Names}} | {{.Status}}",
        ],
        capture_output=True,
        text=True,
        timeout=EXECUTION_TIMEOUT,
        check=True,
    )

    return {
        "hostname": socket.gethostname(),
        "load_average": load_average,
        "memory": _read_memory(),
        "root_disk": {
            "total_bytes": disk.total,
            "used_bytes": disk.used,
            "free_bytes": disk.free,
        },
        "running_containers": docker.stdout.splitlines(),
        "diagnostic_type": "read_only",
    }


def _validate_approval(
    approval,
    approval_id,
    expected_incident_ref,
    expected_action,
    expected_params,
):
    """Validate an approval without performing any action."""

    if not isinstance(approval, dict):
        raise RuntimeError("Approval record is invalid")

    if approval.get("id") != approval_id:
        raise RuntimeError("Approval ID does not match")

    if approval.get("status") != "approved":
        raise RuntimeError("Approval is not in approved status")

    if approval.get("incident_ref") != expected_incident_ref:
        raise RuntimeError("Incident reference does not match")

    if expected_action not in EXECUTABLE_ACTIONS:
        raise RuntimeError("Action is not enabled in the executor")

    if approval.get("action") != expected_action:
        raise RuntimeError("Approved action does not match")

    approved_params = approval.get("action_params")
    if not isinstance(approved_params, dict):
        raise RuntimeError("Approval parameters are invalid")

    if approved_params != expected_params:
        raise RuntimeError("Approved parameters do not match exactly")

    if approved_params.get("execution_enabled") is not False:
        raise RuntimeError("Execution flag is not explicitly false")

    return True


def execute_approved_action(
    approval_id,
    expected_incident_ref,
    expected_action,
    expected_params,
):
    """
    Execute one exact, approved action.

    expected_params must be the exact parameter object presented
    for human approval. No defaults or partial parameter matching.
    """

    if not isinstance(approval_id, int) or approval_id < 1:
        raise ValueError("A valid approval ID is required")

    if not isinstance(expected_incident_ref, str) or not expected_incident_ref:
        raise ValueError("Expected incident reference is required")

    if not REMEDIATION_EXECUTION_ENABLED:
        raise RuntimeError("Remediation execution is globally disabled")

    if expected_action not in EXECUTABLE_ACTIONS:
        raise RuntimeError("Action is not enabled in the executor")

    if not isinstance(expected_params, dict):
        raise ValueError("Expected parameters must be an object")

    approval = _get_approval(approval_id)

    _validate_approval(
        approval=approval,
        approval_id=approval_id,
        expected_incident_ref=expected_incident_ref,
        expected_action=expected_action,
        expected_params=expected_params,
    )

    _initialize_audit_db()
    _claim_execution(approval)

    try:
        if expected_action == "collect_diagnostics":
            result = _collect_diagnostics()
        else:
            # Defensive fallback if the allowlist is expanded later.
            raise RuntimeError("No executor is implemented for this action")

        _finish_execution(approval_id, "completed", result)

        return {
            "approval_id": approval_id,
            "status": "completed",
            "action": expected_action,
            "result": result,
        }

    except Exception as error:
        _finish_execution(
            approval_id,
            "failed",
            {"error_type": type(error).__name__},
        )
        raise


if __name__ == "__main__":
    print("Remediation executor loaded.")
    print("Enabled actions:", sorted(EXECUTABLE_ACTIONS))
    print("No action was executed.")
