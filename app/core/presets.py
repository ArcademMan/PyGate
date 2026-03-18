"""Preset DNS predefiniti."""

PRESETS = {
    "Google": {
        "primary": "8.8.8.8",
        "secondary": "8.8.4.4",
        "description": "Google Public DNS",
    },
    "Cloudflare": {
        "primary": "1.1.1.1",
        "secondary": "1.0.0.1",
        "description": "Cloudflare DNS — fast & private",
    },
    "Cloudflare Family": {
        "primary": "1.1.1.3",
        "secondary": "1.0.0.3",
        "description": "Cloudflare DNS — blocks malware & adult content",
    },
    "Quad9": {
        "primary": "9.9.9.9",
        "secondary": "149.112.112.112",
        "description": "Quad9 — security focused",
    },
    "OpenDNS": {
        "primary": "208.67.222.222",
        "secondary": "208.67.220.220",
        "description": "Cisco OpenDNS",
    },
    "OpenDNS Family": {
        "primary": "208.67.222.123",
        "secondary": "208.67.220.123",
        "description": "OpenDNS FamilyShield — blocks adult content",
    },
    "AdGuard": {
        "primary": "94.140.14.14",
        "secondary": "94.140.15.15",
        "description": "AdGuard DNS — blocks ads & trackers",
    },
    "Comodo": {
        "primary": "8.26.56.26",
        "secondary": "8.20.247.20",
        "description": "Comodo Secure DNS",
    },
}
