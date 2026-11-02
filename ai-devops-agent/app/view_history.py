import sqlite3
from incident_history import DB_PATH


def main():
    with sqlite3.connect(DB_PATH) as connection:
        runs = connection.execute("""
            SELECT id, timestamp, overall_health,
                   incident_count, rca_status
            FROM monitoring_runs
            ORDER BY id DESC
            LIMIT 10
        """).fetchall()

        print("\n===== RECENT MONITORING HISTORY =====")

        if not runs:
            print("No monitoring history available.")
            return

        for run in runs:
            print(
                f"\nRun ID: {run[0]}\n"
                f"Timestamp: {run[1]}\n"
                f"Health: {run[2]}\n"
                f"Incidents: {run[3]}\n"
                f"RCA: {run[4]}"
            )

        incidents = connection.execute("""
            SELECT i.run_id, i.severity, i.source,
                   i.title, i.details, i.occurrences
            FROM incidents i
            ORDER BY i.id DESC
            LIMIT 20
        """).fetchall()

        print("\n===== RECENT INCIDENTS =====")

        if not incidents:
            print("No incidents have been recorded.")
        else:
            for incident in incidents:
                print(
                    f"\nRun ID: {incident[0]}\n"
                    f"Severity: {incident[1]}\n"
                    f"Source: {incident[2]}\n"
                    f"Title: {incident[3]}\n"
                    f"Details: {incident[4]}\n"
                    f"Occurrences: {incident[5]}"
                )


if __name__ == "__main__":
    main()
