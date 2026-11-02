import os
import sqlite3
from datetime import datetime, timezone

DB_DIR = "/var/lib/ai-devops-agent"
DB_PATH = os.path.join(DB_DIR, "incident_history.db")


def initialize_database(connection):
    connection.executescript("""
        CREATE TABLE IF NOT EXISTS monitoring_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            overall_health TEXT NOT NULL,
            incident_count INTEGER NOT NULL,
            rca_status TEXT,
            rca_analysis TEXT
        );

        CREATE TABLE IF NOT EXISTS incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            source TEXT,
            severity TEXT,
            title TEXT,
            details TEXT,
            occurrences INTEGER DEFAULT 1,
            first_timestamp TEXT,
            last_timestamp TEXT,
            FOREIGN KEY (run_id) REFERENCES monitoring_runs(id)
        );

        CREATE INDEX IF NOT EXISTS idx_runs_timestamp
        ON monitoring_runs(timestamp);

        CREATE INDEX IF NOT EXISTS idx_incidents_run_id
        ON incidents(run_id);
    """)


def record_run(overall_health, incidents, rca_result):
    """Persist one completed monitoring run and its detected incidents."""
    os.makedirs(DB_DIR, mode=0o700, exist_ok=True)
    os.chmod(DB_DIR, 0o700)

    with sqlite3.connect(DB_PATH, timeout=10) as connection:
        initialize_database(connection)

        cursor = connection.execute(
            """
            INSERT INTO monitoring_runs (
                timestamp, overall_health, incident_count,
                rca_status, rca_analysis
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(),
                str(overall_health),
                len(incidents),
                rca_result.get("status", "UNKNOWN"),
                rca_result.get("analysis", ""),
            ),
        )

        run_id = cursor.lastrowid

        for incident in incidents:
            connection.execute(
                """
                INSERT INTO incidents (
                    run_id, source, severity, title, details,
                    occurrences, first_timestamp, last_timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    incident.get("source", "UNKNOWN"),
                    incident.get("severity", "UNKNOWN"),
                    incident.get("title", "Unknown incident"),
                    incident.get("details", ""),
                    incident.get("occurrences", 1),
                    incident.get("first_timestamp"),
                    incident.get("last_timestamp"),
                ),
            )

    os.chmod(DB_PATH, 0o600)
    return run_id
