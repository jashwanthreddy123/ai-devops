import subprocess
import requests


OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL = "qwen2.5:0.5b"


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


def get_server_data():

    hostname = run_command("hostname")

    cpu_cores = run_command("nproc")

    memory = run_command(
        "free -m | awk 'NR==2 {print $2, $3, $7}'"
    )

    disk = run_command(
        "df -P / | awk 'NR==2 {print $2, $3, $4, $5}'"
    )

    docker = run_command(
        "docker ps -a --format '{{.Names}} | {{.Status}}'"
    )

    nginx = run_command(
        "systemctl is-active nginx"
    )

    load = run_command(
        "awk '{print $1, $2, $3}' /proc/loadavg"
    )

    # Only show important listening ports
    ports = run_command(
        "ss -lnt | awk 'NR>1 {print $4}' | "
        "grep -E ':(22|80|443|8000|8080|11434)$' || true"
    )

    return {
        "hostname": hostname,
        "cpu_cores": cpu_cores,
        "memory_mb": memory,
        "disk": disk,
        "docker": docker if docker else "No containers",
        "nginx": nginx,
        "load_average": load,
        "important_ports": ports if ports else "None"
    }


server = get_server_data()

server_context = f"""
REAL SERVER INFORMATION

Hostname: {server["hostname"]}
CPU cores: {server["cpu_cores"]}

Memory:
total_mb={server["memory_mb"].split()[0]}
used_mb={server["memory_mb"].split()[1]}
available_mb={server["memory_mb"].split()[2]}

Disk:
{server["disk"]}

Docker:
{server["docker"]}

NGINX:
{server["nginx"]}

Load average:
{server["load_average"]}

Important listening ports:
{server["important_ports"]}
"""


prompt = f"""
You are a Linux DevOps incident analysis assistant.

Analyze ONLY the following real server information.

{server_context}

Rules:

- CPU cores are NOT CPU utilization.
- Memory size is NOT memory utilization percentage.
- Do not invent missing information.
- Do not assume an application exists when Docker shows no containers.
- If NGINX is inactive, clearly state that.
- If no backend port is listening, clearly state that.
- A 502 commonly occurs when a reverse proxy cannot reach its upstream.
- Do not recommend increasing CPU or RAM unless evidence shows resource exhaustion.
- Do not provide destructive commands.

Return exactly:

FACTS:
SERVER HEALTH:
502 ANALYSIS:
ROOT CAUSE:
NEXT CHECKS:
SAFE ACTION:
VERIFICATION:

Keep each section short.
"""


try:

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0,
                "num_predict": 250
            }
        },
        timeout=60
    )

    response.raise_for_status()

    result = response.json()

    print("\n===== SERVER DATA =====")
    print(server_context)

    print("\n===== AI DEVOPS ANALYSIS =====")
    print(result["response"])

except requests.exceptions.Timeout:
    print("\nERROR: Ollama took too long to respond.")

except requests.exceptions.RequestException as e:
    print(f"\nERROR communicating with Ollama: {e}")
