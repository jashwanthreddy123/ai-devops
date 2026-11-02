
import re
from collections import defaultdict


# Severity mapping for the existing Loki detection categories.
LOG_SEVERITY = {
    "HTTP 5xx": "WARNING",
    "Connection refused": "WARNING",
    "Timeout": "WARNING",
    "Exception": "WARNING",
    "Error or failure": "WARNING",
}

CRITICAL_LOG_PATTERNS = [
    re.compile(r"\b(?:panic|fatal)\b", re.IGNORECASE),
]


def classify_log_severity(entry):
    """Classify a log finding using explicit, conservative rules."""
    line = str(entry.get("line", ""))

    # Strong fatal signatures take priority.
    if any(pattern.search(line) for pattern in CRITICAL_LOG_PATTERNS):
        return "CRITICAL"

    categories = entry.get("categories", [])

    if categories:
        return max(
            (LOG_SEVERITY.get(category, "INFO") for category in categories),
            key=lambda level: {
                "INFO": 0,
                "WARNING": 1,
                "CRITICAL": 2,
            }.get(level, 0),
        )

    return "INFO"


def normalize_message(line):
    """Normalize variable values to help group repeated log messages."""
    message = str(line).lower()
    message = re.sub(r"\b\d{4}-\d{2}-\d{2}[t ][\w:.+-]+", "<timestamp>", message)
    message = re.sub(r"\b0x[0-9a-f]+\b", "<hex>", message)
    message = re.sub(r"\b\d+\b", "<number>", message)
    message = re.sub(r"\s+", " ", message).strip()
    return message[:300]


def build_incidents(
    concerning_metrics,
    log_findings,
):
    """
    Build incident records from Python-calculated resource concerns
    and Loki pattern matches.

    concerning_metrics should contain dictionaries with:
    name, value, status, unit (optional).
    """
    incidents = []

    # Resource incidents use statuses already calculated by Python.
    for metric in concerning_metrics:
        status = metric.get("status", "INFO")

        if status not in ("WARNING", "CRITICAL"):
            continue

        incidents.append({
            "source": "Prometheus",
            "severity": status,
            "title": f"{metric.get('name', 'Resource metric')} is {status}",
            "details": (
                f"value={metric.get('value', 'unknown')}"
                f"{metric.get('unit', '')}"
            ),
            "occurrences": 1,
        })

    # Group log matches by container, category, and normalized message.
    grouped = defaultdict(list)

    for entry in log_findings:
        severity = classify_log_severity(entry)
        categories = entry.get("categories") or ["Uncategorized"]
        container = entry.get("container", "unknown")
        message_key = normalize_message(entry.get("line", ""))

        for category in categories:
            key = (container, category, message_key)
            grouped[key].append((entry, severity))

    for (container, category, _), matches in grouped.items():
        entries = [item[0] for item in matches]
        severities = [item[1] for item in matches]

        severity = (
            "CRITICAL" if "CRITICAL" in severities
            else "WARNING" if "WARNING" in severities
            else "INFO"
        )

        incidents.append({
            "source": "Loki",
            "severity": severity,
            "title": f"{category} detected in {container}",
            "details": str(entries[0].get("line", ""))[:500],
            "container": container,
            "occurrences": len(entries),
            "first_timestamp": entries[-1].get("timestamp", "unknown"),
            "last_timestamp": entries[0].get("timestamp", "unknown"),
        })

    severity_rank = {
        "CRITICAL": 0,
        "WARNING": 1,
        "INFO": 2,
    }

    incidents.sort(
        key=lambda incident: (
            severity_rank.get(incident["severity"], 3),
            incident["source"],
            incident["title"],
        )
    )

    return incidents


def print_incidents(incidents):
    """Print a concise incident report."""
    print("\n===== INCIDENT DETECTION =====\n")

    if not incidents:
        print("No incidents detected from the supplied findings.")
        return

    print(f"Total incidents: {len(incidents)}")

    for number, incident in enumerate(incidents, start=1):
        print(f"\nIncident {number}: {incident['title']}")
        print(f"Severity: {incident['severity']}")
        print(f"Source: {incident['source']}")
        print(f"Occurrences: {incident['occurrences']}")
        print(f"Details: {incident['details']}")


if __name__ == "__main__":
    # Local sample only; does not contact or change live services.
    sample_metrics = [
        {
            "name": "Host CPU",
            "value": 92.0,
            "status": "CRITICAL",
            "unit": "%",
        }
    ]

    sample_logs = [
        {
            "timestamp": "2026-10-09T07:00:00+00:00",
            "container": "sample-app",
            "service_name": "sample-app",
            "categories": ["HTTP 5xx"],
            "line": "HTTP/1.1 502 Bad Gateway",
        },
        {
            "timestamp": "2026-10-09T07:00:05+00:00",
            "container": "sample-app",
            "service_name": "sample-app",
            "categories": ["HTTP 5xx"],
            "line": "HTTP/1.1 502 Bad Gateway",
        },
        {
            "timestamp": "2026-10-09T07:01:00+00:00",
            "container": "sample-app",
            "service_name": "sample-app",
            "categories": ["Exception"],
            "line": "FATAL: sample application failure",
        },
    ]

    sample_incidents = build_incidents(
        sample_metrics,
        sample_logs,
    )
    print_incidents(sample_incidents)
