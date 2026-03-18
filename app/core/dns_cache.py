"""Parsing e gestione della cache DNS di Windows."""

import re
from shared.subprocess import run as _run


def get_dns_cache() -> list[dict]:
    """Legge la cache DNS di Windows e restituisce una lista di record.

    Returns:
        Lista di dict con chiavi: name, type, ttl, data
    """
    result = _run(
        ["ipconfig", "/displaydns"],
    )

    entries = []
    current: dict | None = None

    for line in result.stdout.splitlines():
        line = line.strip()

        if not line:
            continue

        # Nuova sezione (riga con ---)
        if line.startswith("---"):
            if current and current.get("name"):
                entries.append(current)
            current = {}
            continue

        if current is None:
            continue

        # Parsing chiave : valore
        if ":" not in line and "." not in line:
            continue

        # Nome record
        if "Nome record" in line or "Record Name" in line:
            current["name"] = line.split(":", 1)[1].strip()
        # Tipo record
        elif "Tipo record" in line or "Record Type" in line:
            val = line.split(":", 1)[1].strip()
            current["type_code"] = int(val) if val.isdigit() else 0
            current["type"] = _record_type_name(current["type_code"])
        # TTL
        elif "TTL" in line or "Durata" in line:
            val = line.split(":", 1)[1].strip()
            current["ttl"] = int(val) if val.isdigit() else 0
        # Record A
        elif "Record A" in line and "AAAA" not in line:
            current["data"] = line.split(":", 1)[1].strip()
        # Record AAAA
        elif "Record AAAA" in line:
            current["data"] = line.split(":", 1)[1].strip()
        # Record CNAME
        elif "CNAME" in line:
            current["data"] = line.split(":", 1)[1].strip()
        # Record PTR
        elif "PTR" in line:
            current["data"] = line.split(":", 1)[1].strip()

    # Ultimo record
    if current and current.get("name"):
        entries.append(current)

    return entries


def get_cache_stats(entries: list[dict]) -> dict:
    """Statistiche sulla cache DNS.

    Returns:
        dict con chiavi: total, unique_domains, by_type
    """
    domains = set()
    by_type: dict[str, int] = {}

    for e in entries:
        domains.add(e.get("name", ""))
        rtype = e.get("type", "?")
        by_type[rtype] = by_type.get(rtype, 0) + 1

    return {
        "total": len(entries),
        "unique_domains": len(domains),
        "by_type": by_type,
    }


def _record_type_name(code: int) -> str:
    return {
        1: "A",
        5: "CNAME",
        12: "PTR",
        28: "AAAA",
        33: "SRV",
    }.get(code, str(code))
