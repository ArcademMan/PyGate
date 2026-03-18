"""Rilevamento interfacce di rete Windows."""

import subprocess


def list_interfaces() -> list[dict]:
    """Restituisce le interfacce di rete con nome e stato.

    Returns:
        Lista di dict con chiavi: admin_state, status, type, name
    """
    result = subprocess.run(
        ["netsh", "interface", "show", "interface"],
        capture_output=True, text=True, encoding="cp850",
    )

    lines = result.stdout.strip().splitlines()
    if len(lines) < 3:
        return []

    interfaces = []
    for line in lines[2:]:  # Salta header + separatore
        if not line.strip():
            continue
        # Le colonne sono separate da 2+ spazi
        parts = [p.strip() for p in line.split("  ") if p.strip()]
        if len(parts) >= 4:
            interfaces.append({
                "admin_state": parts[0],
                "status": parts[1],
                "type": parts[2],
                "name": parts[3],
            })

    return interfaces


# Parole che indicano "connesso" in varie lingue di Windows
_CONNECTED_WORDS = {"connected", "connesso", "connessione", "verbunden", "conectado", "connecté"}


def list_active_interfaces() -> list[str]:
    """Restituisce i nomi delle interfacce di rete connesse."""
    return [
        iface["name"]
        for iface in list_interfaces()
        if iface["status"].lower() in _CONNECTED_WORDS
    ]
