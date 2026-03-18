"""MAC address changer per Windows."""

import random
import re
import subprocess


def get_mac(interface: str) -> str | None:
    """Restituisce il MAC address attuale di un'interfaccia."""
    result = subprocess.run(
        ["getmac", "/v", "/fo", "csv"],
        capture_output=True, text=True, encoding="cp850",
    )

    for line in result.stdout.splitlines():
        if interface in line:
            # Formato CSV: "nome","transport","mac"
            parts = line.split(",")
            for part in parts:
                part = part.strip('"')
                if re.match(r"^[0-9A-Fa-f]{2}(-[0-9A-Fa-f]{2}){5}$", part):
                    return part.replace("-", ":")
    return None


def generate_random_mac() -> str:
    """Genera un MAC address casuale con bit localmente amministrato."""
    # Primo byte: bit 1 (multicast) = 0, bit 2 (locally administered) = 1
    first_byte = random.randint(0, 255) & 0xFC | 0x02
    rest = [random.randint(0, 255) for _ in range(5)]
    return ":".join(f"{b:02X}" for b in [first_byte] + rest)


def set_mac(interface: str, mac: str) -> tuple[bool, str]:
    """Cambia il MAC address di un'interfaccia via registro di Windows.

    Richiede permessi di Amministratore e un riavvio dell'interfaccia.

    Returns:
        (successo, messaggio)
    """
    mac_no_sep = mac.replace(":", "").replace("-", "")
    if len(mac_no_sep) != 12:
        return False, "Invalid MAC address"

    # Trova l'ID dell'interfaccia nel registro
    import winreg

    reg_path = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e972-e325-11ce-bfc1-08002be10318}"

    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path)
    except WindowsError:
        return False, "Cannot access network adapter registry"

    found = False
    for i in range(100):
        try:
            subkey_name = winreg.EnumKey(key, i)
            subkey = winreg.OpenKey(key, subkey_name, 0, winreg.KEY_ALL_ACCESS)
            try:
                desc, _ = winreg.QueryValueEx(subkey, "DriverDesc")
                if interface.lower() in desc.lower():
                    winreg.SetValueEx(subkey, "NetworkAddress", 0, winreg.REG_SZ, mac_no_sep)
                    found = True
                    winreg.CloseKey(subkey)
                    break
            except WindowsError:
                pass
            winreg.CloseKey(subkey)
        except WindowsError:
            break

    winreg.CloseKey(key)

    if not found:
        return False, f"Interface '{interface}' not found in registry"

    # Riavvia l'interfaccia per applicare
    ok, msg = _restart_interface(interface)
    if not ok:
        return False, f"MAC set in registry but failed to restart interface: {msg}"

    return True, f"MAC changed to {mac}"


def reset_mac(interface: str) -> tuple[bool, str]:
    """Ripristina il MAC address originale rimuovendo l'override dal registro.

    Returns:
        (successo, messaggio)
    """
    import winreg

    reg_path = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e972-e325-11ce-bfc1-08002be10318}"

    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path)
    except WindowsError:
        return False, "Cannot access network adapter registry"

    found = False
    for i in range(100):
        try:
            subkey_name = winreg.EnumKey(key, i)
            subkey = winreg.OpenKey(key, subkey_name, 0, winreg.KEY_ALL_ACCESS)
            try:
                desc, _ = winreg.QueryValueEx(subkey, "DriverDesc")
                if interface.lower() in desc.lower():
                    try:
                        winreg.DeleteValue(subkey, "NetworkAddress")
                    except WindowsError:
                        pass
                    found = True
                    winreg.CloseKey(subkey)
                    break
            except WindowsError:
                pass
            winreg.CloseKey(subkey)
        except WindowsError:
            break

    winreg.CloseKey(key)

    if not found:
        return False, f"Interface '{interface}' not found in registry"

    ok, msg = _restart_interface(interface)
    if not ok:
        return False, f"MAC reset in registry but failed to restart interface: {msg}"

    return True, "MAC address restored to factory default"


def _restart_interface(interface: str) -> tuple[bool, str]:
    """Disabilita e riabilita un'interfaccia di rete."""
    r1 = subprocess.run(
        ["netsh", "interface", "set", "interface", interface, "disable"],
        capture_output=True, text=True, encoding="cp850",
    )
    if r1.returncode != 0:
        return False, r1.stderr.strip() or r1.stdout.strip()

    import time
    time.sleep(2)

    r2 = subprocess.run(
        ["netsh", "interface", "set", "interface", interface, "enable"],
        capture_output=True, text=True, encoding="cp850",
    )
    if r2.returncode != 0:
        return False, r2.stderr.strip() or r2.stdout.strip()

    return True, "Interface restarted"
