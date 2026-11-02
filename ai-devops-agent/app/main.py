import requests

from prometheus_client import (
    get_cpu_usage,
    get_memory_usage,
    get_total_memory_bytes,
    get_disk_usage,
    get_load_average,
    get_container_cpu_usage,
    get_container_memory_usage,
)

from loki_client import get_recent_logs, analyze_logs
from incident_detector import build_incidents, print_incidents
from rca_engine import analyze_root_cause
from email_notifier import send_email
from alert_deduplicator import prepare_alerts, record_alert_success
from incident_history import record_run
from approval_client import submit_incident_approvals


WARNING_THRESHOLD = 70
CRITICAL_THRESHOLD = 90

LOG_LOOKBACK_MINUTES = 15
LOG_QUERY_LIMIT = 100


def get_status(value, warning, critical):
    if value >= critical:
        return "CRITICAL"
    if value >= warning:
        return "WARNING"
    return "NORMAL"


def get_overall_health(*statuses):
    if "CRITICAL" in statuses:
        return "CRITICAL"
    if "WARNING" in statuses:
        return "WARNING"
    return "NORMAL"


def bytes_to_mb(value):
    return value / (1024 * 1024)


def collect_loki_findings():
    """Retrieve and analyze logs without stopping metric monitoring."""
    try:
        logs = get_recent_logs(
            minutes=LOG_LOOKBACK_MINUTES,
            limit=LOG_QUERY_LIMIT,
        )
        findings = analyze_logs(logs)

        return {
            "available": True,
            "log_count": len(logs),
            "findings": findings,
            "error": None,
        }

    except (
        requests.RequestException,
        ValueError,
        RuntimeError,
    ) as error:
        return {
            "available": False,
            "log_count": 0,
            "findings": [],
            "error": str(error),
        }


def send_incident_alert(incidents, rca_result):
    """Send eligible incident alerts with persistent cooldown."""
    if not incidents:
        print("No incidents detected; email alert skipped.")
        return

    eligible = prepare_alerts(incidents)

    if not eligible:
        print("Duplicate incident alerts suppressed by cooldown.")
        return

    lines = [
        "AI DevOps Agent detected incident(s).",
        f"Total incidents in this alert: {len(eligible)}",
        "",
    ]

    for number, incident in enumerate(eligible, start=1):
        lines.extend([
            f"Incident {number}: {incident.get('title', 'Unknown')}",
            f"Severity: {incident.get('severity', 'UNKNOWN')}",
            f"Source: {incident.get('source', 'UNKNOWN')}",
            f"Occurrences: {incident.get('occurrences', 1)}",
            f"Details: {incident.get('details', 'No details available')}",
            "",
        ])

    lines.extend([
        f"RCA status: {rca_result.get('status', 'UNKNOWN')}",
        "",
        "RCA analysis:",
        rca_result.get("analysis", "RCA analysis was unavailable."),
        "",
        "No automatic remediation was performed.",
    ])

    if any(
        incident.get("severity") == "CRITICAL"
        for incident in eligible
    ):
        severity = "CRITICAL"
    elif any(
        incident.get("severity") == "WARNING"
        for incident in eligible
    ):
        severity = "WARNING"
    else:
        severity = "INFO"

    subject = (
        f"[{severity}] AI DevOps Agent: "
        f"{len(eligible)} incident(s) detected"
    )

    # Use actual newline characters in the email body.
    body = "\n".join(lines)

    try:
        send_email(subject, body)
    except Exception as error:
        print(f"Incident email delivery failed: {error}")
        return

    # Start the cooldown only after successful email delivery.
    try:
        record_alert_success(eligible)
        print("Incident email alert sent successfully.")
    except Exception as error:
        print(
            "Incident email was sent, but updating the "
            f"alert cooldown state failed: {error}"
        )


def main():
    # ==================================================
    # 1. HOST METRICS
    # ==================================================

    try:
        cpu = get_cpu_usage()
        memory = get_memory_usage()
        total_memory = get_total_memory_bytes()
        disk = get_disk_usage()
        load = get_load_average()

    except Exception as error:
        print(f"Could not retrieve host metrics: {error}")
        return

    if any(
        value is None
        for value in (cpu, memory, total_memory, disk, load)
    ):
        print("Could not retrieve all server metrics.")
        return

    if total_memory <= 0:
        print("Invalid total host memory value.")
        return

    host_cpu_status = get_status(
        cpu, WARNING_THRESHOLD, CRITICAL_THRESHOLD
    )
    host_memory_status = get_status(
        memory, WARNING_THRESHOLD, CRITICAL_THRESHOLD
    )
    host_disk_status = get_status(
        disk, WARNING_THRESHOLD, CRITICAL_THRESHOLD
    )

    host_health = get_overall_health(
        host_cpu_status,
        host_memory_status,
        host_disk_status,
    )

    host_metrics = [
        {
            "name": "Host CPU",
            "value": round(cpu, 2),
            "unit": "%",
            "status": host_cpu_status,
        },
        {
            "name": "Host Memory",
            "value": round(memory, 2),
            "unit": "%",
            "status": host_memory_status,
        },
        {
            "name": "Host Disk",
            "value": round(disk, 2),
            "unit": "%",
            "status": host_disk_status,
        },
        {
            "name": "Host Load Average",
            "value": round(load, 2),
            "unit": "",
            "status": "INFO",
        },
    ]

    # ==================================================
    # 2. CONTAINER METRICS
    # ==================================================

    try:
        container_cpu = get_container_cpu_usage()
        container_memory = get_container_memory_usage()

    except Exception as error:
        print(f"Could not retrieve container metrics: {error}")
        return

    if not container_cpu or not container_memory:
        print("Could not retrieve container metrics.")
        return

    container_details = []
    container_statuses = []
    container_metrics = []

    for name in sorted(container_cpu):
        cpu_value = container_cpu[name]
        memory_value = container_memory.get(name)

        if memory_value is None:
            print(f"Missing memory metrics for container: {name}")
            continue

        memory_mb = bytes_to_mb(memory_value)

        # Container memory percentage is relative to host RAM,
        # not the container's configured memory limit.
        memory_percent = (memory_value / total_memory) * 100

        cpu_status = get_status(
            cpu_value, WARNING_THRESHOLD, CRITICAL_THRESHOLD
        )
        memory_status = get_status(
            memory_percent, WARNING_THRESHOLD, CRITICAL_THRESHOLD
        )
        container_status = get_overall_health(
            cpu_status, memory_status
        )

        container_statuses.append(container_status)

        container_details.append({
            "name": name,
            "cpu": cpu_value,
            "memory_mb": memory_mb,
            "memory_percent": memory_percent,
            "cpu_status": cpu_status,
            "memory_status": memory_status,
            "status": container_status,
        })

        container_metrics.extend([
            {
                "name": f"Container {name} CPU",
                "value": round(cpu_value, 2),
                "unit": "%",
                "status": cpu_status,
            },
            {
                "name": f"Container {name} Memory",
                "value": round(memory_percent, 2),
                "unit": "% of host RAM",
                "status": memory_status,
            },
        ])

    if not container_details:
        print("No complete container metrics are available.")
        return

    overall_health = get_overall_health(
        host_health,
        *container_statuses,
    )

    print("\n===== SERVER HEALTH =====\n")
    print(f"Overall Resource Health: {overall_health}")
    print(f"CPU:    {cpu:.2f}% [{host_cpu_status}]")
    print(f"Memory: {memory:.2f}% [{host_memory_status}]")
    print(f"Disk:   {disk:.2f}% [{host_disk_status}]")
    print(f"Load:   {load:.2f}")

    print("\n===== CONTAINER HEALTH =====\n")

    for container in container_details:
        print(f"Container: {container['name']}")
        print(
            f"CPU:       {container['cpu']:.2f}% "
            f"[{container['cpu_status']}]"
        )
        print(f"Memory:    {container['memory_mb']:.2f} MB")
        print(
            f"Memory %:  {container['memory_percent']:.2f}% "
            f"[{container['memory_status']}]"
        )
        print(f"Status:    {container['status']}\n")

    # ==================================================
    # 3. LOKI LOG ANALYSIS
    # ==================================================

    print("\n===== LOKI LOG ANALYSIS =====\n")

    loki_result = collect_loki_findings()
    log_findings = loki_result["findings"]

    if loki_result["available"]:
        print(f"Recent logs retrieved: {loki_result['log_count']}")
        print(f"Potential log findings: {len(log_findings)}")

        if log_findings:
            for entry in log_findings[:20]:
                print(
                    f"\nContainer: {entry.get('container', 'unknown')}"
                )
                print(
                    "Categories: "
                    f"{', '.join(entry.get('categories', []))}"
                )
                print(f"Log: {entry.get('line', '')[:500]}")

            if len(log_findings) > 20:
                print(
                    f"\n{len(log_findings) - 20} additional findings "
                    "not displayed."
                )
        else:
            print("No matching error patterns in returned logs.")
    else:
        print("Log analysis status: UNAVAILABLE")
        print(f"Reason: {loki_result['error']}")

    # ==================================================
    # 4. INCIDENT DETECTION
    # ==================================================

    incidents = build_incidents(
        host_metrics + container_metrics,
        log_findings,
    )

    print_incidents(incidents)

    # ==================================================
    # 5. AI ROOT CAUSE ANALYSIS
    # ==================================================

    print("\n===== AI ROOT CAUSE ANALYSIS =====\n")

    if not loki_result["available"]:
        print(
            "Note: Loki was unavailable. RCA will not have "
            "access to current log findings."
        )

    rca_result = {
        "status": "NOT_COMPLETED",
        "analysis": "RCA did not return a result.",
    }

    try:
        rca_result = analyze_root_cause(
            incidents=incidents,
            host_metrics=host_metrics,
            container_metrics=container_metrics,
            log_findings=log_findings,
        )

        print(f"RCA Status: {rca_result['status']}")
        print(rca_result["analysis"])

    except Exception as error:
        rca_result["status"] = "FAILED"
        rca_result["analysis"] = (
            "RCA analysis failed. Check the monitoring logs "
            "for details."
        )
        print(f"RCA analysis failed: {error}")
        print(
            "Collected metrics and detected incidents remain available."
        )

    # ==================================================
    # ==================================================
    # 5B. HUMAN APPROVAL WORKFLOW — NO REMEDIATION
    # ==================================================

    submit_incident_approvals(incidents, rca_result)

    # 6. SAVE HISTORY
    # ==================================================

    try:
        run_id = record_run(overall_health, incidents, rca_result)
        print(f"Monitoring history saved. Run ID: {run_id}")
    except Exception as error:
        print(f"Warning: unable to save monitoring history: {error}")

    # ==================================================
    # 7. EMAIL ALERTS — INCIDENTS ONLY
    # ==================================================

    send_incident_alert(incidents, rca_result)

    print("\n===== MONITORING RUN COMPLETE =====")
    print("No automatic remediation was performed.")


if __name__ == "__main__":
    main()
