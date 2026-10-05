import subprocess
import requests
import json
import os

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL = "qwen2.5:0.5b"


# ============================================================
# Helper Functions
# ============================================================

def run_command(command):
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=10
        )

        return result.stdout.strip()

    except Exception as e:
        return f"ERROR: {e}"


# ============================================================
# Server Diagnostics
# ============================================================

def get_server_facts():

    facts = []

    # --------------------------------------------------------
    # NGINX
    # --------------------------------------------------------

    nginx_status = run_command(
        "systemctl is-active nginx 2>/dev/null || true"
    )

    if nginx_status == "active":
        facts.append("NGINX is running.")
    else:
        facts.append("NGINX is not running.")

    # --------------------------------------------------------
    # Docker
    # --------------------------------------------------------

    docker_count = run_command(
        "docker ps -q 2>/dev/null | wc -l"
    )

    try:
        docker_count = int(docker_count)
    except ValueError:
        docker_count = 0

    if docker_count == 0:
        facts.append("No Docker containers are currently running.")
    else:
        facts.append(
            f"{docker_count} Docker container(s) are currently running."
        )

    # --------------------------------------------------------
    # Listening Ports
    # --------------------------------------------------------

    listening_ports = run_command(
        "ss -lnt 2>/dev/null"
    )

    common_ports = {
        "3000": "Node.js",
        "5000": "Application",
        "8000": "Backend",
        "8080": "Application"
    }

    application_ports = []

    for port, service in common_ports.items():

        if f":{port} " in listening_ports:
            application_ports.append(
                f"{service} application is listening on port {port}."
            )

    if application_ports:
        facts.extend(application_ports)
    else:
        facts.append(
            "No common backend application port is listening."
        )

    # --------------------------------------------------------
    # CPU / Load
    # --------------------------------------------------------

    load_average = run_command(
        "awk '{print $1}' /proc/loadavg"
    )

    facts.append(
        f"System load average: {load_average}"
    )

    # --------------------------------------------------------
    # Disk
    # --------------------------------------------------------

    disk_usage = run_command(
        "df -h / | awk 'NR==2 {print $5}'"
    )

    facts.append(
        f"Root filesystem usage: {disk_usage}"
    )

    return facts


# ============================================================
# Deterministic Root Cause
# ============================================================

def determine_root_cause(facts):

    root_cause = []

    nginx_down = any(
        "NGINX is not running" in fact
        for fact in facts
    )

    docker_down = any(
        "No Docker containers" in fact
        for fact in facts
    )

    backend_down = any(
        "No common backend application port" in fact
        for fact in facts
    )

    if nginx_down:
        root_cause.append(
            "NGINX is currently not running."
        )

    if docker_down:
        root_cause.append(
            "There are no running Docker containers."
        )

    if backend_down:
        root_cause.append(
            "No common backend application port is listening."
        )

    if not root_cause:
        root_cause.append(
            "No obvious service failure was detected by the deterministic checks."
        )

    return root_cause


# ============================================================
# Main
# ============================================================

def main():

    print("\n========================================")
    print("AI DEVOPS INCIDENT ANALYZER")
    print("========================================\n")

    # --------------------------------------------------------
    # Collect verified facts
    # --------------------------------------------------------

    facts = get_server_facts()

    print("VERIFIED SERVER FACTS:")
    for fact in facts:
        print(f"- {fact}")

    # --------------------------------------------------------
    # Determine root cause using deterministic rules
    # --------------------------------------------------------

    root_causes = determine_root_cause(facts)

    print("\nDETERMINISTIC ROOT CAUSE:")

    for cause in root_causes:
        print(f"- {cause}")

    # --------------------------------------------------------
    # Prepare evidence for Ollama
    # --------------------------------------------------------

    facts_text = "\n".join(
        f"- {fact}"
        for fact in facts
    )

    root_cause_text = "\n".join(
        f"- {cause}"
        for cause in root_causes
    )

    prompt = f"""
You are an AI DevOps incident assistant.

Use ONLY the verified evidence below.

VERIFIED SERVER FACTS:
{facts_text}

DETERMINISTIC ROOT CAUSE:
{root_cause_text}

Your job is ONLY to explain the incident.

Rules:

1. Do not invent services.
2. Do not invent errors.
3. Do not claim HTTP 502 unless the evidence supports it.
4. Do not recommend increasing CPU or RAM unless resource pressure is actually shown.
5. Do not contradict the deterministic root cause.
6. Do not repeat these instructions.
7. Do not repeat the verified evidence section.
8. Keep the answer short.
9. Do not provide shell commands.
10. Do not perform remediation.

Return exactly this format:

INCIDENT:
<one short sentence>

ROOT CAUSE:
<one short sentence>

IMPACT:
<one short sentence>

RECOMMENDATION:
<one short sentence>
"""

    # --------------------------------------------------------
    # Ask Ollama for explanation
    # --------------------------------------------------------

    try:

        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0,
                    "num_predict": 180
                }
            },
            timeout=60
        )

        response.raise_for_status()

        ai_result = response.json()["response"].strip()

        # ----------------------------------------------------
        # Remove accidental prompt leakage
        # ----------------------------------------------------

        if "STRICT RULES:" in ai_result:
            ai_result = ai_result.split(
                "STRICT RULES:"
            )[0].strip()

        if "VERIFIED SERVER EVIDENCE" in ai_result:
            ai_result = ai_result.split(
                "VERIFIED SERVER EVIDENCE"
            )[0].strip()

        if "DETERMINISTIC ROOT CAUSE:" in ai_result:
            ai_result = ai_result.split(
                "DETERMINISTIC ROOT CAUSE:"
            )[0].strip()

        # ----------------------------------------------------
        # Display AI result
        # ----------------------------------------------------

        print("\n========================================")
        print("AI INCIDENT ANALYSIS")
        print("========================================\n")

        print(ai_result)

    except requests.exceptions.Timeout:

        print("\nERROR:")
        print("Ollama request timed out.")

    except requests.exceptions.ConnectionError:

        print("\nERROR:")
        print("Cannot connect to Ollama.")

    except requests.exceptions.RequestException as e:

        print("\nERROR:")
        print(f"Ollama request failed: {e}")

    except Exception as e:

        print("\nERROR:")
        print(f"Unexpected error: {e}")


# ============================================================
# Entry Point
# ============================================================

if __name__ == "__main__":
    main()
