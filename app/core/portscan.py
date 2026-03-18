"""Port scanner per Windows."""

import socket
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

COMMON_PORTS = {
    21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP", 53: "DNS",
    80: "HTTP", 110: "POP3", 143: "IMAP", 443: "HTTPS", 445: "SMB",
    993: "IMAPS", 995: "POP3S", 1433: "MSSQL", 1521: "Oracle",
    3306: "MySQL", 3389: "RDP", 5432: "PostgreSQL", 5900: "VNC",
    6379: "Redis", 8080: "HTTP-Alt", 8443: "HTTPS-Alt", 27017: "MongoDB",
}

PRESETS = {
    "common": list(COMMON_PORTS.keys()),
    "all": list(range(1, 65536)),
    "top100": [
        1, 3, 7, 9, 13, 17, 19, 21, 22, 23, 25, 26, 37, 42, 49, 53, 67, 68, 69, 70,
        79, 80, 81, 88, 102, 110, 111, 113, 119, 123, 135, 137, 139, 143, 161, 162,
        175, 179, 199, 389, 443, 445, 465, 497, 500, 502, 512, 513, 514, 515, 520,
        523, 548, 554, 587, 593, 631, 636, 666, 771, 789, 873, 902, 993, 995,
        1025, 1080, 1099, 1194, 1433, 1521, 1723, 1883, 2049, 2082, 2083, 2086,
        2087, 2181, 2222, 2375, 2376, 3000, 3128, 3268, 3306, 3389, 4443, 4444,
        5000, 5432, 5555, 5900, 6379, 8000, 8080, 8443, 8888, 9090, 9200, 27017,
    ],
    "web": [80, 443, 8080, 8443, 3000, 4200, 5000, 5173, 8000, 8888],
    "database": [1433, 1521, 3306, 5432, 6379, 27017, 9200, 9300],
    "remote": [22, 23, 3389, 5900, 5938, 5939],
    "gaming": [25565, 27015, 27016, 7777, 7778, 19132, 25575],
}


def scan_port(host: str, port: int, timeout: float = 1.0) -> dict:
    """Scansiona una singola porta.

    Returns:
        dict con chiavi: port, open, service
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        is_open = result == 0
    except (socket.timeout, OSError):
        is_open = False

    return {
        "port": port,
        "open": is_open,
        "service": COMMON_PORTS.get(port, ""),
    }


def scan_ports(host: str, ports: list[int], timeout: float = 1.0,
               max_workers: int = 50, on_result=None) -> list[dict]:
    """Scansiona una lista di porte in parallelo.

    Args:
        host: IP o hostname da scansionare
        ports: lista di porte
        timeout: timeout per porta in secondi
        max_workers: thread paralleli
        on_result: callback(dict) chiamato per ogni porta completata

    Returns:
        Lista di risultati ordinata per porta
    """
    results = []

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(scan_port, host, p, timeout): p for p in ports}
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            if on_result:
                on_result(result)

    results.sort(key=lambda r: r["port"])
    return results


def parse_ports(text: str) -> list[int]:
    """Parsa una stringa di porte in una lista.

    Supporta: "80", "80,443", "80-100", "80,443,8000-8100"
    """
    ports = set()
    for part in text.split(","):
        part = part.strip()
        if "-" in part:
            try:
                start, end = part.split("-", 1)
                for p in range(int(start), int(end) + 1):
                    if 1 <= p <= 65535:
                        ports.add(p)
            except ValueError:
                continue
        elif part.isdigit():
            p = int(part)
            if 1 <= p <= 65535:
                ports.add(p)
    return sorted(ports)


def get_local_listeners() -> list[dict]:
    """Restituisce le porte in ascolto sulla macchina locale.

    Returns:
        Lista di dict con chiavi: port, pid, process, service
    """
    import subprocess
    import psutil

    result = subprocess.run(
        ["netstat", "-ano", "-p", "TCP"],
        capture_output=True, text=True, encoding="cp850",
    )

    listeners = []
    seen = set()

    for line in result.stdout.splitlines():
        if "LISTENING" not in line:
            continue
        parts = line.split()
        if len(parts) < 5:
            continue

        addr = parts[1]
        pid_str = parts[4]

        # Estrai porta
        if ":" in addr:
            port_str = addr.rsplit(":", 1)[1]
            if port_str.isdigit():
                port = int(port_str)
                if port not in seen:
                    seen.add(port)

                    # Nome processo
                    process_name = ""
                    try:
                        p = psutil.Process(int(pid_str))
                        process_name = p.name()
                    except (psutil.NoSuchProcess, psutil.AccessDenied, ValueError):
                        pass

                    # Indirizzo di binding
                    bind_addr = addr.rsplit(":", 1)[0]

                    listeners.append({
                        "port": port,
                        "bind": bind_addr,
                        "pid": pid_str,
                        "process": process_name,
                        "service": COMMON_PORTS.get(port, ""),
                    })

    listeners.sort(key=lambda r: r["port"])
    return listeners
