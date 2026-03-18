"""Gestione del file hosts di Windows."""

import os
import re

HOSTS_PATH = os.path.join(os.environ.get("SYSTEMROOT", r"C:\Windows"),
                          "System32", "drivers", "etc", "hosts")


def read_hosts() -> list[dict]:
    """Legge il file hosts e restituisce le entry parsate.

    Returns:
        Lista di dict con chiavi: ip, hostname, comment, enabled, line_num, raw
    """
    entries = []
    try:
        with open(HOSTS_PATH, encoding="utf-8") as f:
            lines = f.readlines()
    except Exception:
        return entries

    for i, raw in enumerate(lines):
        stripped = raw.strip()

        # Riga vuota
        if not stripped:
            continue

        # Riga di solo commento (no entry disabilitata)
        if stripped.startswith("#"):
            # Controlla se e' una entry disabilitata: # ip hostname
            match = re.match(r"^#\s*(\d+\.\d+\.\d+\.\d+)\s+(\S+)(.*)", stripped)
            if match:
                entries.append({
                    "ip": match.group(1),
                    "hostname": match.group(2),
                    "comment": match.group(3).strip().lstrip("#").strip(),
                    "enabled": False,
                    "line_num": i,
                    "raw": raw,
                })
            continue

        # Entry attiva: ip hostname [# commento]
        match = re.match(r"^(\d+\.\d+\.\d+\.\d+)\s+(\S+)(.*)", stripped)
        if match:
            comment_part = match.group(3).strip()
            if comment_part.startswith("#"):
                comment_part = comment_part[1:].strip()
            else:
                comment_part = ""

            entries.append({
                "ip": match.group(1),
                "hostname": match.group(2),
                "comment": comment_part,
                "enabled": True,
                "line_num": i,
                "raw": raw,
            })

    return entries


def write_hosts(entries: list[dict]) -> tuple[bool, str]:
    """Riscrive il file hosts preservando commenti e righe originali.

    Returns:
        (successo, messaggio)
    """
    try:
        with open(HOSTS_PATH, encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        return False, str(e)

    # Aggiorna le righe modificate
    modified_lines = set()
    for entry in entries:
        line_num = entry.get("line_num")
        if line_num is not None and 0 <= line_num < len(lines):
            new_line = _format_entry(entry)
            lines[line_num] = new_line + "\n"
            modified_lines.add(line_num)

    try:
        with open(HOSTS_PATH, "w", encoding="utf-8") as f:
            f.writelines(lines)
        return True, "Hosts file saved"
    except PermissionError:
        return False, "Access denied — run as Administrator"
    except Exception as e:
        return False, str(e)


def add_entry(ip: str, hostname: str, comment: str = "") -> tuple[bool, str]:
    """Aggiunge una nuova entry al file hosts."""
    from shared.validation import is_valid_ipv4, is_valid_hostname
    if not is_valid_ipv4(ip):
        return False, f"Invalid IP address: {ip}"
    if not is_valid_hostname(hostname):
        return False, f"Invalid hostname: {hostname}"

    line = _format_entry({"ip": ip, "hostname": hostname,
                          "comment": comment, "enabled": True})
    try:
        with open(HOSTS_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        return True, f"Added: {ip} {hostname}"
    except PermissionError:
        return False, "Access denied — run as Administrator"
    except Exception as e:
        return False, str(e)


def remove_entry(line_num: int) -> tuple[bool, str]:
    """Rimuove una entry dal file hosts per numero di riga."""
    try:
        with open(HOSTS_PATH, encoding="utf-8") as f:
            lines = f.readlines()

        if 0 <= line_num < len(lines):
            del lines[line_num]

        with open(HOSTS_PATH, "w", encoding="utf-8") as f:
            f.writelines(lines)
        return True, "Entry removed"
    except PermissionError:
        return False, "Access denied — run as Administrator"
    except Exception as e:
        return False, str(e)


def toggle_entry(line_num: int) -> tuple[bool, str]:
    """Abilita/disabilita una entry commentandola/scommentandola."""
    try:
        with open(HOSTS_PATH, encoding="utf-8") as f:
            lines = f.readlines()

        if 0 <= line_num < len(lines):
            line = lines[line_num].strip()
            if line.startswith("#"):
                lines[line_num] = line.lstrip("#").strip() + "\n"
            else:
                lines[line_num] = "# " + line + "\n"

        with open(HOSTS_PATH, "w", encoding="utf-8") as f:
            f.writelines(lines)
        return True, "Entry toggled"
    except PermissionError:
        return False, "Access denied — run as Administrator"
    except Exception as e:
        return False, str(e)


def _format_entry(entry: dict) -> str:
    """Formatta una entry come riga del file hosts."""
    line = f"{entry['ip']}\t{entry['hostname']}"
    if entry.get("comment"):
        line += f"\t# {entry['comment']}"
    if not entry.get("enabled", True):
        line = "# " + line
    return line
