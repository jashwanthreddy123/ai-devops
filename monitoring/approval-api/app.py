import hmac
import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

DB_PATH = os.environ.get(
    "APPROVAL_DB", "/data/approvals.db"
)
API_TOKEN = os.environ.get("APPROVAL_API_TOKEN", "")
HOST = "0.0.0.0"
PORT = 8089

# These are identifiers, not shell commands. No action is executed here.
ALLOWED_ACTIONS = {
    "collect_diagnostics",
    "restart_container",
    "rollback_deployment",
}
ALLOWED_SEVERITIES = {"info", "low", "medium", "high", "critical"}


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def connect_db():
    con = sqlite3.connect(DB_PATH, timeout=5)
    con.row_factory = sqlite3.Row
    return con


def initialize_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with connect_db() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS approvals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_ref TEXT NOT NULL,
                severity TEXT NOT NULL,
                title TEXT NOT NULL,
                action TEXT NOT NULL,
                action_params TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK(status IN ('pending','approved','rejected')),
                requested_by TEXT NOT NULL,
                reviewer TEXT,
                reason TEXT,
                created_at TEXT NOT NULL,
                decided_at TEXT
            )
        """)
        con.execute("""
            CREATE INDEX IF NOT EXISTS idx_approvals_status
            ON approvals(status, id)
        """)


def public_record(row):
    item = dict(row)
    item["action_params"] = json.loads(item["action_params"])
    return item


class Handler(BaseHTTPRequestHandler):
    def send_json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def authorized(self):
        header = self.headers.get("Authorization", "")
        expected = "Bearer " + API_TOKEN
        return bool(API_TOKEN) and hmac.compare_digest(header, expected)

    def read_json(self):
        raw_length = self.headers.get("Content-Length", "")
        if not raw_length.isdigit():
            raise ValueError("invalid_content_length")
        length = int(raw_length)
        if length < 1 or length > 16384:
            raise ValueError("invalid_body_size")
        data = json.loads(self.rfile.read(length))
        if not isinstance(data, dict):
            raise ValueError("json_object_required")
        return data

    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/health":
            try:
                with connect_db() as con:
                    con.execute("SELECT 1").fetchone()
                self.send_json(200, {
                    "status": "ok",
                    "service": "approval-api",
                    "execution_enabled": False
                })
            except (sqlite3.Error, OSError):
                self.send_json(503, {"status": "unavailable"})
            return

        if not self.authorized():
            self.send_json(401, {"error": "unauthorized"})
            return

        if path != "/api/approvals":
            self.send_json(404, {"error": "endpoint_not_found"})
            return

        try:
            with connect_db() as con:
                rows = con.execute("""
                    SELECT * FROM approvals ORDER BY id DESC LIMIT 200
                """).fetchall()
            self.send_json(200, [public_record(r) for r in rows])
        except (sqlite3.Error, ValueError):
            self.send_json(500, {"error": "request_failed"})

    def do_POST(self):
        path = urlparse(self.path).path

        if not self.authorized():
            self.send_json(401, {"error": "unauthorized"})
            return

        try:
            data = self.read_json()
        except (ValueError, json.JSONDecodeError):
            self.send_json(400, {"error": "invalid_json"})
            return

        if path == "/api/approvals":
            incident_ref = data.get("incident_ref")
            severity = data.get("severity")
            title = data.get("title")
            action = data.get("action")
            requested_by = data.get("requested_by")
            params = data.get("action_params", {})

            if not all(isinstance(x, str) and x.strip()
                       for x in (incident_ref, severity, title,
                                 action, requested_by)):
                self.send_json(400, {"error": "required_fields_missing"})
                return

            if severity.lower() not in ALLOWED_SEVERITIES:
                self.send_json(400, {"error": "invalid_severity"})
                return

            if action not in ALLOWED_ACTIONS:
                self.send_json(400, {"error": "action_not_allowlisted"})
                return

            if not isinstance(params, dict):
                self.send_json(400, {"error": "action_params_must_be_object"})
                return

            if any(len(x) > limit for x, limit in (
                (incident_ref, 200), (title, 500), (requested_by, 120)
            )):
                self.send_json(400, {"error": "field_too_long"})
                return

            try:
                with connect_db() as con:
                    cur = con.execute("""
                        INSERT INTO approvals (
                            incident_ref, severity, title, action,
                            action_params, requested_by, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        incident_ref.strip(), severity.lower(),
                        title.strip(), action,
                        json.dumps(params), requested_by.strip(), utc_now()
                    ))
                    row = con.execute(
                        "SELECT * FROM approvals WHERE id = ?",
                        (cur.lastrowid,)
                    ).fetchone()
                self.send_json(201, public_record(row))
            except sqlite3.Error:
                self.send_json(500, {"error": "storage_failed"})
            return

        match = re.fullmatch(r"/api/approvals/([0-9]+)/decision", path)
        if not match:
            self.send_json(404, {"error": "endpoint_not_found"})
            return

        approval_id = int(match.group(1))
        decision = data.get("decision")
        reviewer = data.get("reviewer")
        reason = data.get("reason", "")

        if decision not in ("approved", "rejected"):
            self.send_json(400, {
                "error": "decision_must_be_approved_or_rejected"
            })
            return

        if not isinstance(reviewer, str) or not reviewer.strip():
            self.send_json(400, {"error": "reviewer_required"})
            return

        if not isinstance(reason, str) or len(reason) > 2000:
            self.send_json(400, {"error": "invalid_reason"})
            return

        try:
            with connect_db() as con:
                cur = con.execute("""
                    UPDATE approvals
                    SET status = ?, reviewer = ?, reason = ?, decided_at = ?
                    WHERE id = ? AND status = 'pending'
                """, (
                    decision, reviewer.strip(), reason, utc_now(), approval_id
                ))

                if cur.rowcount != 1:
                    exists = con.execute(
                        "SELECT status FROM approvals WHERE id = ?",
                        (approval_id,)
                    ).fetchone()
                    if exists is None:
                        self.send_json(404, {"error": "approval_not_found"})
                    else:
                        self.send_json(409, {
                            "error": "decision_already_recorded",
                            "status": exists["status"]
                        })
                    return

                row = con.execute(
                    "SELECT * FROM approvals WHERE id = ?",
                    (approval_id,)
                ).fetchone()

            self.send_json(200, {
                "approval": public_record(row),
                "execution_enabled": False
            })
        except sqlite3.Error:
            self.send_json(500, {"error": "storage_failed"})

    def do_PUT(self):
        self.send_json(405, {"error": "method_not_allowed"})

    def do_DELETE(self):
        self.send_json(405, {"error": "method_not_allowed"})

    def log_message(self, fmt, *args):
        print(
            f"{self.address_string()} - {fmt % args}",
            flush=True
        )


if __name__ == "__main__":
    if not API_TOKEN or len(API_TOKEN) < 32:
        raise SystemExit("APPROVAL_API_TOKEN must contain at least 32 characters")

    initialize_db()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(
        f"Approval API listening on {HOST}:{PORT}; "
        "remediation execution disabled",
        flush=True
    )
    server.serve_forever()
