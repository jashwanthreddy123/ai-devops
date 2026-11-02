import unittest
from loki_client import analyze_logs


def make_log(line):
    return {
        "timestamp": "2026-10-27T09:00:00+00:00",
        "container": "test-app",
        "service_name": "test-app",
        "stream": "stdout",
        "line": line,
    }


class TestLokiDetection(unittest.TestCase):

    def test_normal_info_log_is_ignored(self):
        self.assertEqual(
            analyze_logs([make_log("level=info request completed successfully")]),
            [],
        )

    def test_generic_failure_in_info_log_is_ignored(self):
        logs = [make_log('level=info msg="Error or failure check completed"')]
        self.assertEqual(analyze_logs(logs), [])

    def test_http_502_is_detected(self):
        findings = analyze_logs([make_log("HTTP/1.1 502 Bad Gateway")])
        self.assertTrue(any("HTTP 5xx" in x["categories"] for x in findings))

    def test_http_500_json_status_is_detected(self):
        logs = [make_log('{"status": 500, "message": "request failed"}')]
        findings = analyze_logs(logs)
        self.assertTrue(any("HTTP 5xx" in x["categories"] for x in findings))

    def test_connection_refused_is_detected(self):
        findings = analyze_logs([make_log("connection refused while connecting")])
        self.assertTrue(any("Connection refused" in x["categories"] for x in findings))

    def test_timeout_is_detected(self):
        findings = analyze_logs([make_log("upstream request timed out")])
        self.assertTrue(any("Timeout" in x["categories"] for x in findings))

    def test_exception_is_detected(self):
        findings = analyze_logs([make_log("RuntimeError: unexpected response")])
        self.assertTrue(any("Exception" in x["categories"] for x in findings))

    def test_error_level_is_detected(self):
        findings = analyze_logs([make_log('level=error msg="request failed"')])
        self.assertTrue(any("Error or failure" in x["categories"] for x in findings))


if __name__ == "__main__":
    unittest.main(verbosity=2)
