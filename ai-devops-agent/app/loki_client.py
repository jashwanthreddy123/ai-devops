
import re
import time
import requests
from datetime import datetime, timezone

LOKI_QUERY_URL = "http://localhost:3100/loki/api/v1/query_range"

# Detect specific HTTP server errors, exceptions, and connectivity issues.
ERROR_PATTERNS = {
    "HTTP 5xx": re.compile(
        r'(?:'
        r'\b(?:HTTP/\d(?:\.\d)?\s+5\d{2}|'
        r'HTTP\s+5\d{2}|'
        r'status(?:_code)?\s*[=: ]+\s*5\d{2}|'
        r'returned HTTP status\s+5\d{2})\b'
        r'|'
        r'["\']status["\']\s*:\s*5\d{2}(?!\d)'
        r')',
        re.IGNORECASE,
    ),
    "Connection refused": re.compile(
        r"\bconnection refused\b",
        re.IGNORECASE,
    ),
    "Timeout": re.compile(
        r"\b(?:timeout|timed out|deadline exceeded)\b",
        re.IGNORECASE,
    ),
    "Exception": re.compile(
        r"\b(?:"
        r"exception|traceback|panic|fatal|"
        r"runtimeerror|valueerror|typeerror|"
        r"keyerror|attributeerror|importerror|"
        r"assertionerror|indexerror|nameerror|"
        r"zerodivisionerror|oserror"
        r")\b",
        re.IGNORECASE,
    ),
    "Error or failure": re.compile(
        r"\b(?:error|failed|failure)\b",
        re.IGNORECASE,
    ),
}

# Ignore known harmless noise.
IGNORED_PATTERNS = [
    re.compile(
        r"failed mapping AST.*context canceled",
        re.IGNORECASE,
    ),
]


def get_recent_logs(minutes=15, limit=100):
    """Fetch recent container logs from Loki."""
    end_ns = time.time_ns()
    start_ns = end_ns - minutes * 60 * 1_000_000_000

    params = {
        "query": '{container=~".+"}',
        "start": str(start_ns),
        "end": str(end_ns),
        "limit": limit,
        "direction": "backward",
    }

    response = requests.get(
        LOKI_QUERY_URL,
        params=params,
        timeout=10,
    )
    response.raise_for_status()

    payload = response.json()

    if payload.get("status") != "success":
        raise RuntimeError(
            "Loki returned an unsuccessful query response"
        )

    logs = []

    for result in payload.get("data", {}).get("result", []):
        labels = result.get("stream", {})

        for timestamp_ns, line in result.get("values", []):
            timestamp = datetime.fromtimestamp(
                int(timestamp_ns) / 1_000_000_000,
                tz=timezone.utc,
            ).isoformat()

            logs.append({
                "timestamp": timestamp,
                "container": labels.get("container", "unknown"),
                "service_name": labels.get("service_name", "unknown"),
                "stream": labels.get("stream", "unknown"),
                "line": line,
            })

    return logs


def analyze_logs(logs):
    """Identify log entries matching configured error patterns."""
    findings = []

    for entry in logs:
        line = entry["line"]

        if any(
            pattern.search(line)
            for pattern in IGNORED_PATTERNS
        ):
            continue

        matched_categories = [
            category
            for category, pattern in ERROR_PATTERNS.items()
            if pattern.search(line)
        ]

        # Avoid treating ordinary INFO-level failure wording alone
        # as an incident. Specific HTTP errors and exceptions remain visible.
        is_info_level = bool(
            re.search(
                r"\blevel\s*=\s*['\"]?info\b",
                line,
                re.IGNORECASE,
            )
        )

        if is_info_level:
            matched_categories = [
                category
                for category in matched_categories
                if category == "HTTP 5xx"
                or category == "HTTP 5xx JSON"
                or category == "Connection refused"
                or category == "Timeout"
                or category == "Exception"
            ]

        if matched_categories:
            findings.append({
                **entry,
                "categories": matched_categories,
            })

    return findings


def main():
    print("===== LOKI LOG CHECK =====")

    try:
        logs = get_recent_logs(minutes=15, limit=100)
        findings = analyze_logs(logs)

        print(f"Recent log entries: {len(logs)}")
        print(f"Potential error entries: {len(findings)}")

        if not logs:
            print("No logs returned for the selected time range.")

        for entry in findings[:20]:
            categories = ", ".join(entry["categories"])

            print(
                f"[{entry['timestamp']}] "
                f"container={entry['container']} "
                f"service={entry['service_name']} "
                f"categories={categories}"
            )
            print(f"  {entry['line'][:500]}")

        if len(findings) > 20:
            print(
                f"...and {len(findings) - 20} additional matches."
            )

        if not findings:
            print("No matching error patterns found in returned logs.")

        print(
            "\nNote: These are pattern matches, not confirmed incidents. "
            "Review the log context before taking action."
        )

    except (
        requests.RequestException,
        ValueError,
        RuntimeError,
    ) as exc:
        print(f"Loki query failed: {exc}")


if __name__ == "__main__":
    main()
