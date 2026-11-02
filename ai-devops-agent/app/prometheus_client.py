import requests


PROMETHEUS_URL = "http://localhost:9090/api/v1/query"


def query_prometheus(query):
    response = requests.get(
        PROMETHEUS_URL,
        params={"query": query},
        timeout=10
    )

    response.raise_for_status()

    data = response.json()

    if data["status"] != "success":
        raise RuntimeError(f"Prometheus query failed: {data}")

    return data["data"]["result"]


# ==================================================
# HOST METRICS
# ==================================================

def get_cpu_usage():
    query = """
    100 - (
        avg by(instance) (
            rate(node_cpu_seconds_total{mode="idle"}[5m])
        ) * 100
    )
    """

    results = query_prometheus(query)

    if not results:
        return None

    return float(results[0]["value"][1])


def get_memory_usage():
    query = """
    100 * (
        1 -
        node_memory_MemAvailable_bytes /
        node_memory_MemTotal_bytes
    )
    """

    results = query_prometheus(query)

    if not results:
        return None

    return float(results[0]["value"][1])


def get_total_memory_bytes():
    query = """
    node_memory_MemTotal_bytes
    """

    results = query_prometheus(query)

    if not results:
        return None

    return float(results[0]["value"][1])


def get_disk_usage():
    query = """
    100 * (
        1 -
        node_filesystem_avail_bytes{
            mountpoint="/",
            fstype!~"tmpfs|overlay"
        }
        /
        node_filesystem_size_bytes{
            mountpoint="/",
            fstype!~"tmpfs|overlay"
        }
    )
    """

    results = query_prometheus(query)

    if not results:
        return None

    return float(results[0]["value"][1])


def get_load_average():
    query = """
    node_load1
    """

    results = query_prometheus(query)

    if not results:
        return None

    return float(results[0]["value"][1])


# ==================================================
# CONTAINER METRICS
# ==================================================

def get_container_cpu_usage():
    query = """
    100 * sum by(name) (
        rate(
            container_cpu_usage_seconds_total{
                name!=""
            }[5m]
        )
    )
    """

    results = query_prometheus(query)

    containers = {}

    for result in results:
        name = result["metric"].get("name")

        if not name:
            continue

        cpu = float(result["value"][1])

        containers[name] = cpu

    return containers


def get_container_memory_usage():
    query = """
    sum by(name) (
        container_memory_usage_bytes{
            name!=""
        }
    )
    """

    results = query_prometheus(query)

    containers = {}

    for result in results:
        name = result["metric"].get("name")

        if not name:
            continue

        memory = float(result["value"][1])

        containers[name] = memory

    return containers
