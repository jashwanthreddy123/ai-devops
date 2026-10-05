import subprocess


def run_command(command):
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=10
        )

        return result.stdout.strip() or result.stderr.strip()

    except Exception as e:
        return str(e)


print("\n===== DOCKER STATUS =====")
print(run_command("docker ps -a"))

print("\n===== LISTENING PORTS =====")
print(run_command("ss -lntp"))

print("\n===== NGINX STATUS =====")
print(run_command("systemctl is-active nginx"))

print("\n===== NGINX ERROR LOG =====")
print(
    run_command(
        "journalctl -u nginx -n 30 --no-pager"
    )
)

print("\n===== SYSTEM LOAD =====")
print(run_command("uptime"))
