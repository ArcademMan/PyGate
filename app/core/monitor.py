"""Monitor connessioni di rete attive."""

import psutil

from core.portscan import COMMON_PORTS


def get_connections() -> list[dict]:
    """Restituisce le connessioni TCP attive.

    Returns:
        Lista di dict con chiavi: pid, process, local_addr, local_port,
        remote_addr, remote_port, status, service
    """
    connections = []

    for conn in psutil.net_connections(kind="tcp"):
        if not conn.laddr:
            continue

        # Nome processo
        process = ""
        try:
            if conn.pid:
                process = psutil.Process(conn.pid).name()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

        local_port = conn.laddr.port
        remote_addr = conn.raddr.ip if conn.raddr else ""
        remote_port = conn.raddr.port if conn.raddr else 0

        connections.append({
            "pid": conn.pid or 0,
            "process": process,
            "local_addr": conn.laddr.ip,
            "local_port": local_port,
            "remote_addr": remote_addr,
            "remote_port": remote_port,
            "status": conn.status,
            "service": COMMON_PORTS.get(local_port, "") or COMMON_PORTS.get(remote_port, ""),
        })

    connections.sort(key=lambda c: (c["status"] != "ESTABLISHED", c["process"], c["local_port"]))
    return connections
