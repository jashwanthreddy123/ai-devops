from prometheus_client import get_cpu_usage


cpu = get_cpu_usage()

if cpu is None:
    print("CPU metric not found")
else:
    print(f"Current CPU usage: {cpu:.2f}%")
