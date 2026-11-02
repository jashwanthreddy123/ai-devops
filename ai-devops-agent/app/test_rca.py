
from rca_engine import analyze_root_cause

incidents = [{
    "title": "High CPU Usage",
    "severity": "CRITICAL",
    "source": "synthetic_test",
    "details": "Synthetic CPU usage reached 92%, above the critical threshold.",
    "occurrences": 1,
}]

host_metrics = [
    {"name": "cpu_usage_percent", "value": 92.0, "status": "CRITICAL"},
    {"name": "memory_usage_percent", "value": 45.0, "status": "NORMAL"},
    {"name": "disk_usage_percent", "value": 35.0, "status": "NORMAL"},
    {"name": "load_average", "value": 2.5, "status": "INFO"},
]

if __name__ == "__main__":
    print("Running synthetic RCA test...")
    try:
        result = analyze_root_cause(incidents, host_metrics, [], [])
        print("\nRCA STATUS:", result.get("status", "UNKNOWN"))
        print("\nANALYSIS:\n", result.get("analysis", "No analysis"))
        print("\nRECOMMENDATIONS:\n", result.get("recommendations", []))
    except Exception as exc:
        print("RCA TEST FAILED:", type(exc).__name__, str(exc))

    print("\nNo remediation commands were executed.")
    print("No email was triggered by this test.")
