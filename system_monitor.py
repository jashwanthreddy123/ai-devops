import subprocess
import shutil


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


print("===== SYSTEM INFORMATION =====")

print("\nHOSTNAME:")
print(run_command("hostname"))

print("\nCPU:")
print(run_command("nproc"))

print("\nMEMORY:")
print(run_command("free -h"))

print("\nDISK:")
print(run_command("df -h /"))

print("\nDOCKER:")
if shutil.which("docker"):
    print(run_command("docker ps"))
else:
    print("Docker not installed")
