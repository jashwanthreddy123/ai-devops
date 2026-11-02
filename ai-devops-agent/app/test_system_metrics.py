from prometheus_client import (
    get_cpu_usage,
    get_memory_usage,
    get_disk_usage,
    get_load_average,
)


cpu = get_cpu_usage()
memory = get_memory_usage()
disk = get_disk_usage()
load = get_load_average()


print("\n===== SERVER METRICS =====\n")

if cpu is not None:
    print(f"CPU Usage:    {cpu:.2f}%")
else:
    print("CPU Usage:    Not available")

if memory is not None:
    print(f"Memory Usage: {memory:.2f}%")
else:
    print("Memory Usage: Not available")

if disk is not None:
    print(f"Disk Usage:   {disk:.2f}%")
else:
    print("Disk Usage:   Not available")

if load is not None:
    print(f"Load Average: {load:.2f}")
else:
    print("Load Average: Not available")
