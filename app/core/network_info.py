"""Informazioni di rete: IP pubblico, locale, hostname."""

import socket
import urllib.request


def get_public_ip() -> str | None:
    """Ottiene l'IP pubblico tramite servizi esterni."""
    services = [
        "https://api.ipify.org",
        "https://ifconfig.me/ip",
        "https://icanhazip.com",
    ]
    for url in services:
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                return resp.read().decode().strip()
        except Exception:
            continue
    return None


def get_local_ip() -> str:
    """Ottiene l'IP locale principale."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def get_hostname() -> str:
    return socket.gethostname()
