import json
import os
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

DB_PATH = os.environ.get("DB_PATH", "/data/incident_history.db")
HOST = "0.0.0.0"
PORT = 8088


def query_db(sql, params=()):
    # The database is opened read-only; writes are prohibited.
    uri = "file:" + DB_PATH + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True, timeout=5)
    connection.row_factory = sqlite3.Row

    try:
        connection.execute("PRAGMA query_only = ON")
        return [dict(row) for row in connection.execute(sql, params).fetchall()]
    finally:
        connection.close()


class Handler(BaseHTTPRequestHandler):
    def send_json(self, status, payload):
        body = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        try:
            if path == "/health":
                rows = query_db("SELECT COUNT(*) AS count FROM monitoring_runs")
                self.send_json(200, {
                    "status": "ok",
                    "database": "read-only",
                    "monitoring_runs": rows[0]["count"]
                })
                return

            if path == "/api/rca/status-counts":
                rows = query_db("""
                    SELECT rca_status AS status, COUNT(*) AS count
                    FROM monitoring_runs
                    GROUP BY rca_status
                    ORDER BY count DESC
                """)
                self.send_json(200, rows)
                return

            if path == "/api/health/counts":
                rows = query_db("""
                    SELECT overall_health AS health, COUNT(*) AS count
                    FROM monitoring_runs
                    GROUP BY overall_health
                    ORDER BY count DESC
                """)
                self.send_json(200, rows)
                return

            if path == "/api/incidents/severity-counts":
                rows = query_db("""
                    SELECT severity, COUNT(*) AS count
                    FROM incidents
                    GROUP BY severity
                    ORDER BY count DESC
                """)
                self.send_json(200, rows)
                return

            if path == "/api/runs":
                limit = int(params.get("limit", ["50"])[0])
                limit = max(1, min(limit, 200))
                rows = query_db("""
                    SELECT id, timestamp, overall_health, incident_count,
                           rca_status, rca_analysis
                    FROM monitoring_runs
                    ORDER BY id DESC
                    LIMIT ?
                """, (limit,))
                self.send_json(200, rows)
                return

            if path == "/api/incidents":
                limit = int(params.get("limit", ["50"])[0])
                limit = max(1, min(limit, 200))
                rows = query_db("""
                    SELECT id, run_id, source, severity, title, details,
                           occurrences, first_timestamp, last_timestamp
                    FROM incidents
                    ORDER BY id DESC
                    LIMIT ?
                """, (limit,))
                self.send_json(200, rows)
                return

            self.send_json(404, {"error": "endpoint_not_found"})
        except (ValueError, sqlite3.Error, OSError) as exc:
            # Do not expose database paths or internal exception details.
            print(f"Request failed for {path}: {type(exc).__name__}", flush=True)
            self.send_json(500, {"error": "request_failed"})

    def do_POST(self):
        self.send_json(405, {"error": "method_not_allowed"})

    def do_PUT(self):
        self.send_json(405, {"error": "method_not_allowed"})

    def do_DELETE(self):
        self.send_json(405, {"error": "method_not_allowed"})

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args), flush=True)


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Read-only incident history API listening on {HOST}:{PORT}", flush=True)
    server.serve_forever()
