import hashlib
import json
import os
import re
import tempfile
import time

STATE_DIR = "/var/lib/ai-devops-agent"
STATE_FILE = os.path.join(STATE_DIR, "alert_state.json")
COOLDOWN_SECONDS = 30 * 60


def fingerprint(incident):
    source = str(incident.get("source", "UNKNOWN"))
    title = str(incident.get("title", "Unknown incident"))
    severity = str(incident.get("severity", "UNKNOWN"))
    container = str(incident.get("container", ""))

    # Ignore changing values in Loki log messages.
    details = ""
    if source == "Loki":
        details = str(incident.get("details", "")).lower()
        details = re.sub(
            r"\b\d{4}-\d{2}-\d{2}[t ][\w:.+-]+",
            "<timestamp>",
            details,
        )
        details = re.sub(r"\b0x[0-9a-f]+\b", "<hex>", details)
        details = re.sub(r"\b\d+\b", "<number>", details)
        details = re.sub(r"\s+", " ", details).strip()

    identity = "|".join((source, title, severity, container, details))
    return hashlib.sha256(identity.encode()).hexdigest()


def load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as file:
            state = json.load(file)
        if not isinstance(state, dict):
            raise ValueError("Invalid alert state")
        return state
    except FileNotFoundError:
        return {"active": [], "last_sent": {}}


def save_state(state):
    os.makedirs(STATE_DIR, mode=0o700, exist_ok=True)
    os.chmod(STATE_DIR, 0o700)

    fd, temp_path = tempfile.mkstemp(dir=STATE_DIR, prefix=".alert-state-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(state, file, indent=2)
            file.write("\n")
        os.chmod(temp_path, 0o600)
        os.replace(temp_path, STATE_FILE)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def prepare_alerts(incidents):
    """Select new incidents and incidents whose cooldown has expired."""
    state = load_state()
    previous_active = set(state.get("active", []))
    last_sent = state.setdefault("last_sent", {})
    now = time.time()

    current = {}
    for incident in incidents:
        current[fingerprint(incident)] = incident

    eligible = []
    for key, incident in current.items():
        sent_at = last_sent.get(key)

        is_new = key not in previous_active
        cooldown_expired = (
            sent_at is not None
            and now - float(sent_at) >= COOLDOWN_SECONDS
        )

        if sent_at is None or is_new or cooldown_expired:
            eligible.append(incident)

    # Clearing an incident removes it from the active set.
    # If it returns later, it can alert immediately.
    state["active"] = list(current.keys())
    save_state(state)

    return eligible


def record_alert_success(incidents):
    """Record cooldown timestamps only after email succeeds."""
    state = load_state()
    last_sent = state.setdefault("last_sent", {})
    now = time.time()

    for incident in incidents:
        last_sent[fingerprint(incident)] = now

    save_state(state)
