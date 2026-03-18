"""Gestione indirizzo IPv4 su Windows via netsh."""

import re
import subprocess


def get_ipv4_config(interface: str) -> dict:
    """Ottiene la configurazione IPv4 di un'interfaccia.

    Returns:
        dict con chiavi: ip, subnet, gateway, dhcp
    """
    result = subprocess.run(
        ["netsh", "interface", "ip", "show", "config", interface],
        capture_output=True, text=True, encoding="cp850",
    )

    config = {"ip": "", "subnet": "", "gateway": "", "dhcp": False}

    for line in result.stdout.splitlines():
        line = line.strip()
        lower = line.lower()

        if "dhcp" in lower and ("si" in lower or "yes" in lower or "sì" in lower):
            config["dhcp"] = True

        # IP address
        if any(k in lower for k in ["indirizzo ip", "ip address"]):
            val = line.split(":", 1)
            if len(val) > 1:
                ip = val[1].strip()
                if _is_ipv4(ip):
                    config["ip"] = ip

        # Subnet — formato: "Prefisso subnet: 192.168.8.0/24 (maschera 255.255.255.0)"
        if any(k in lower for k in ["subnet", "prefisso"]):
            # Cerca la maschera tra parentesi
            match = re.search(r'(\d+\.\d+\.\d+\.\d+)\)', line)
            if match and _is_ipv4(match.group(1)):
                config["subnet"] = match.group(1)
            else:
                # Fallback: cerca qualsiasi IP nella riga
                val = line.split(":", 1)
                if len(val) > 1:
                    for word in val[1].split():
                        if _is_ipv4(word):
                            config["subnet"] = word
                            break

        # Gateway
        if "gateway" in lower:
            val = line.split(":", 1)
            if len(val) > 1:
                for word in val[1].split():
                    if _is_ipv4(word):
                        config["gateway"] = word
                        break

    return config


def set_static_ip(interface: str, ip: str, subnet: str, gateway: str) -> tuple[bool, str]:
    """Imposta un indirizzo IP statico.

    Returns:
        (successo, messaggio)
    """
    from shared.validation import is_valid_ipv4, is_valid_interface_name
    if not is_valid_interface_name(interface):
        return False, "Invalid interface name"
    for label, val in [("IP", ip), ("Subnet", subnet), ("Gateway", gateway)]:
        if not is_valid_ipv4(val):
            return False, f"Invalid {label}: {val}"

    result = subprocess.run(
        ["netsh", "interface", "ip", "set", "address",
         interface, "static", ip, subnet, gateway],
        capture_output=True, text=True, encoding="cp850",
    )
    if result.returncode != 0:
        return False, result.stderr.strip() or result.stdout.strip()
    return True, f"IP set: {ip}/{subnet} gw {gateway}"


def set_dhcp(interface: str) -> tuple[bool, str]:
    """Ripristina DHCP sull'interfaccia.

    Returns:
        (successo, messaggio)
    """
    result = subprocess.run(
        ["netsh", "interface", "ip", "set", "address", interface, "dhcp"],
        capture_output=True, text=True, encoding="cp850",
    )
    if result.returncode != 0:
        return False, result.stderr.strip() or result.stdout.strip()
    return True, "IP reset to DHCP"


def _is_ipv4(text: str) -> bool:
    parts = text.split(".")
    if len(parts) != 4:
        return False
    return all(p.isdigit() and 0 <= int(p) <= 255 for p in parts)
