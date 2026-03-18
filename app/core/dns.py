"""Gestione DNS su Windows via netsh."""

import ctypes
from shared.subprocess import run as _run


def is_admin() -> bool:
    """Controlla se lo script gira come Amministratore."""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def get_dns(interface: str) -> list[str]:
    """Restituisce i DNS configurati per un'interfaccia.

    Returns:
        Lista di IP DNS (vuota se DHCP/automatico).
    """
    result = _run(
        ["netsh", "interface", "ip", "show", "dns", interface],
    )

    servers = []
    for line in result.stdout.splitlines():
        line = line.strip()
        # Le righe con IP DNS contengono indirizzi tipo "8.8.8.8"
        parts = line.split()
        for part in parts:
            if _is_ipv4(part):
                servers.append(part)

    return servers


def is_dhcp(interface: str) -> bool:
    """Controlla se il DNS dell'interfaccia e' configurato via DHCP."""
    result = _run(
        ["netsh", "interface", "ip", "show", "dns", interface],
    )
    text = result.stdout.lower()
    return "dhcp" in text or "automaticamente" in text or "automatically" in text


def set_dns(interface: str, primary: str, secondary: str | None = None) -> tuple[bool, str]:
    """Imposta DNS statici su un'interfaccia.

    Returns:
        (successo, messaggio)
    """
    from shared.validation import is_valid_ipv4, is_valid_interface_name
    if not is_valid_interface_name(interface):
        return False, "Invalid interface name"
    if not is_valid_ipv4(primary):
        return False, f"Invalid primary DNS: {primary}"
    if secondary and not is_valid_ipv4(secondary):
        return False, f"Invalid secondary DNS: {secondary}"

    # Imposta DNS primario
    result = _run(
        ["netsh", "interface", "ip", "set", "dns", interface, "static", primary],
    )
    if result.returncode != 0:
        return False, result.stderr.strip() or result.stdout.strip()

    # Imposta DNS secondario
    if secondary:
        result = _run(
            ["netsh", "interface", "ip", "add", "dns", interface, secondary, "index=2"],
        )
        if result.returncode != 0:
            return False, result.stderr.strip() or result.stdout.strip()

    return True, f"DNS set: {primary}" + (f", {secondary}" if secondary else "")


def reset_dns(interface: str) -> tuple[bool, str]:
    """Ripristina il DNS a DHCP (automatico).

    Returns:
        (successo, messaggio)
    """
    result = _run(
        ["netsh", "interface", "ip", "set", "dns", interface, "dhcp"],
    )
    if result.returncode != 0:
        return False, result.stderr.strip() or result.stdout.strip()
    return True, "DNS reset to DHCP"


def flush_cache() -> tuple[bool, str]:
    """Svuota la cache DNS di Windows.

    Returns:
        (successo, messaggio)
    """
    result = _run(
        ["ipconfig", "/flushdns"],
    )
    if result.returncode != 0:
        return False, result.stderr.strip() or result.stdout.strip()
    return True, "DNS cache flushed"


def _is_ipv4(text: str) -> bool:
    parts = text.split(".")
    if len(parts) != 4:
        return False
    return all(p.isdigit() and 0 <= int(p) <= 255 for p in parts)
