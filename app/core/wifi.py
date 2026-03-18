"""Analisi reti WiFi su Windows."""

import re

from shared.subprocess import run as _run


def get_wifi_networks() -> list[dict]:
    """Scansiona le reti WiFi disponibili.

    Returns:
        Lista di dict con chiavi: ssid, signal, channel, auth, encryption, bssid
    """
    result = _run(
        ["netsh", "wlan", "show", "networks", "mode=bssid"],
    )

    networks = []
    current: dict | None = None

    for line in result.stdout.splitlines():
        line = line.strip()

        # SSID
        if line.startswith("SSID") and "BSSID" not in line:
            if current and current.get("ssid"):
                networks.append(current)
            ssid = line.split(":", 1)[1].strip() if ":" in line else ""
            current = {"ssid": ssid, "signal": 0, "channel": 0,
                       "auth": "", "encryption": "", "bssid": ""}

        if current is None:
            continue

        # BSSID
        if "BSSID" in line and ":" in line:
            parts = line.split(":", 1)
            if len(parts) > 1:
                current["bssid"] = parts[1].strip()

        # Signal / Segnale
        if any(k in line.lower() for k in ["signal", "segnale"]):
            match = re.search(r"(\d+)%", line)
            if match:
                current["signal"] = int(match.group(1))

        # Channel / Canale
        if any(k in line.lower() for k in ["channel", "canale"]):
            match = re.search(r":\s*(\d+)", line)
            if match:
                current["channel"] = int(match.group(1))

        # Auth / Autenticazione
        if any(k in line.lower() for k in ["authentication", "autenticazione"]):
            if ":" in line:
                current["auth"] = line.split(":", 1)[1].strip()

        # Encryption / Crittografia
        if any(k in line.lower() for k in ["cipher", "crittografia", "encryption"]):
            if ":" in line:
                current["encryption"] = line.split(":", 1)[1].strip()

    if current and current.get("ssid"):
        networks.append(current)

    networks.sort(key=lambda n: -n["signal"])
    return networks


def get_current_wifi() -> dict | None:
    """Restituisce informazioni sulla connessione WiFi attuale.

    Returns:
        dict con chiavi: ssid, bssid, signal, channel, speed, auth
        oppure None se non connesso al WiFi
    """
    result = _run(
        ["netsh", "wlan", "show", "interfaces"],
    )

    info = {}
    for line in result.stdout.splitlines():
        line = line.strip()
        if ":" not in line:
            continue

        key, _, val = line.partition(":")
        key = key.strip().lower()
        val = val.strip()

        if "ssid" in key and "bssid" not in key:
            info["ssid"] = val
        elif "bssid" in key:
            info["bssid"] = val
        elif any(k in key for k in ["signal", "segnale"]):
            match = re.search(r"(\d+)", val)
            if match:
                info["signal"] = int(match.group(1))
        elif any(k in key for k in ["channel", "canale"]):
            match = re.search(r"(\d+)", val)
            if match:
                info["channel"] = int(match.group(1))
        elif any(k in key for k in ["speed", "velocità", "receive rate"]):
            info["speed"] = val
        elif any(k in key for k in ["authentication", "autenticazione"]):
            info["auth"] = val

    return info if info.get("ssid") else None


def suggest_channel(networks: list[dict]) -> dict:
    """Suggerisce il canale meno congestionato.

    Returns:
        dict con chiavi: channel_2g, channel_5g, reason
    """
    channels_2g = {i: 0 for i in range(1, 14)}
    channels_5g = {i: 0 for i in [36, 40, 44, 48, 52, 56, 60, 64,
                                    100, 104, 108, 112, 116, 120, 124, 128,
                                    132, 136, 140, 149, 153, 157, 161, 165]}

    for net in networks:
        ch = net["channel"]
        if 1 <= ch <= 13:
            # 2.4GHz — ogni rete occupa ±2 canali
            for c in range(max(1, ch - 2), min(14, ch + 3)):
                if c in channels_2g:
                    channels_2g[c] += net["signal"]
        elif ch in channels_5g:
            channels_5g[ch] += net["signal"]

    best_2g = min(channels_2g, key=channels_2g.get) if channels_2g else 1
    best_5g = min(channels_5g, key=channels_5g.get) if channels_5g else 36

    return {"channel_2g": best_2g, "channel_5g": best_5g}
