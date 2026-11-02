import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import alert_deduplicator as dedup
import incident_history as history


class TestAlertDeduplication(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.state_dir = self.temp_dir.name

        self.dir_patch = patch.object(dedup, "STATE_DIR", self.state_dir)
        self.file_patch = patch.object(
            dedup, "STATE_FILE",
            os.path.join(self.state_dir, "alert_state.json")
        )
        self.dir_patch.start()
        self.file_patch.start()

        self.incident = {
            "source": "Prometheus",
            "title": "High CPU Usage",
            "severity": "CRITICAL",
            "details": "CPU usage exceeded threshold",
        }

    def tearDown(self):
        self.file_patch.stop()
        self.dir_patch.stop()
        self.temp_dir.cleanup()

    def test_new_incident_is_eligible(self):
        result = dedup.prepare_alerts([self.incident])
        self.assertEqual(len(result), 1)

    def test_successful_alert_is_deduplicated(self):
        dedup.prepare_alerts([self.incident])
        dedup.record_alert_success([self.incident])

        result = dedup.prepare_alerts([self.incident])
        self.assertEqual(result, [])

    def test_cleared_incident_can_alert_again(self):
        dedup.prepare_alerts([self.incident])
        dedup.record_alert_success([self.incident])

        dedup.prepare_alerts([])
        result = dedup.prepare_alerts([self.incident])

        self.assertEqual(len(result), 1)

    def test_failed_email_can_be_retried(self):
        dedup.prepare_alerts([self.incident])
        # Deliberately do not record successful email delivery.

        result = dedup.prepare_alerts([self.incident])
        self.assertEqual(len(result), 1)

    def test_alert_is_eligible_after_cooldown(self):
        with patch.object(dedup.time, "time", return_value=1000):
            dedup.prepare_alerts([self.incident])
            dedup.record_alert_success([self.incident])

        with patch.object(
            dedup.time, "time",
            return_value=1000 + dedup.COOLDOWN_SECONDS
        ):
            result = dedup.prepare_alerts([self.incident])

        self.assertEqual(len(result), 1)


class TestIncidentHistory(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_dir = self.temp_dir.name
        self.db_path = os.path.join(self.db_dir, "test_history.db")

        self.dir_patch = patch.object(history, "DB_DIR", self.db_dir)
        self.path_patch = patch.object(history, "DB_PATH", self.db_path)
        self.dir_patch.start()
        self.path_patch.start()

    def tearDown(self):
        self.path_patch.stop()
        self.dir_patch.stop()
        self.temp_dir.cleanup()

    def test_monitoring_run_and_incident_are_persisted(self):
        incidents = [{
            "source": "Prometheus",
            "severity": "CRITICAL",
            "title": "High CPU Usage",
            "details": "CPU reached 95%",
            "occurrences": 1,
        }]
        rca = {
            "status": "SUCCESS",
            "analysis": "Investigate the processes consuming CPU.",
        }

        run_id = history.record_run("CRITICAL", incidents, rca)

        with sqlite3.connect(self.db_path) as connection:
            run = connection.execute(
                "SELECT overall_health, incident_count, rca_status "
                "FROM monitoring_runs WHERE id = ?",
                (run_id,),
            ).fetchone()

            incident = connection.execute(
                "SELECT source, severity, title, details "
                "FROM incidents WHERE run_id = ?",
                (run_id,),
            ).fetchone()

        self.assertEqual(run, ("CRITICAL", 1, "SUCCESS"))
        self.assertEqual(
            incident,
            (
                "Prometheus", "CRITICAL", "High CPU Usage",
                "CPU reached 95%",
            ),
        )

    def test_empty_run_is_recorded(self):
        run_id = history.record_run(
            "HEALTHY", [], {"status": "NO_INCIDENTS", "analysis": ""}
        )

        with sqlite3.connect(self.db_path) as connection:
            row = connection.execute(
                "SELECT incident_count, rca_status "
                "FROM monitoring_runs WHERE id = ?",
                (run_id,),
            ).fetchone()

        self.assertEqual(row, (0, "NO_INCIDENTS"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
