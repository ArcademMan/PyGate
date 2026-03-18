"""Benchmark latenza DNS."""

import socket
import time

from core.presets import PRESETS

_TEST_DOMAINS = ["google.com", "github.com", "cloudflare.com"]


def ping_dns(dns_ip: str, timeout: float = 2.0) -> float | None:
    """Misura la latenza di una risoluzione DNS attraverso un server specifico.

    Returns:
        Latenza media in millisecondi, o None se fallisce.
    """
    import struct

    # Costruisci una query DNS raw per "google.com"
    # Header: ID=0x1234, flags=0x0100 (standard query), QDCOUNT=1
    query = b"\x12\x34\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00"
    # QNAME: google.com
    query += b"\x06google\x03com\x00"
    # QTYPE=A (1), QCLASS=IN (1)
    query += b"\x00\x01\x00\x01"

    times = []
    for _ in range(3):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(timeout)
            start = time.perf_counter()
            sock.sendto(query, (dns_ip, 53))
            sock.recvfrom(512)
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)
        except (socket.timeout, OSError):
            pass
        finally:
            sock.close()

    return sum(times) / len(times) if times else None


def benchmark_all() -> list[dict]:
    """Testa la latenza di tutti i preset DNS.

    Returns:
        Lista ordinata per latenza: [{"name": ..., "ip": ..., "ms": ..., "description": ...}]
    """
    results = []
    for name, preset in PRESETS.items():
        ms = ping_dns(preset["primary"])
        results.append({
            "name": name,
            "ip": preset["primary"],
            "ms": ms,
            "description": preset["description"],
        })

    results.sort(key=lambda r: r["ms"] if r["ms"] is not None else float("inf"))
    return results
