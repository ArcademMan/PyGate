<p align="center">
  <img src="pygate.png" alt="PyGate" width="180">
</p>

<h1 align="center">PyGate</h1>

<p align="center">
  <strong>Network toolkit for Windows</strong><br>
  DNS manager, port scanner, IPv4 config, hosts editor, network monitor, WiFi analyzer.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/platform-Windows-blue" alt="Platform">
  <img src="https://img.shields.io/badge/python-3.12+-yellow" alt="Python">
  <img src="https://img.shields.io/badge/gui-PySide6-green" alt="GUI">
  <img src="https://img.shields.io/badge/license-MIT-lightgrey" alt="License">
</p>

---

## Features

| Page | Description |
|------|-------------|
| **Home** | Public/local IP, hostname, system info, admin status |
| **DNS** | Change DNS with presets (Cloudflare, Google, Quad9, ...), flush cache, view cache entries, benchmark all DNS servers |
| **IPv4** | View and configure static IP or DHCP on any network adapter |
| **Hosts** | View, add, remove, enable/disable entries in the system hosts file |
| **Port Scan** | Scan ports on any host, view local listeners with process names, scan your public IP |
| **Monitor** | Real-time view of all active TCP connections with process, remote IP, status, PID. Auto-refresh and filtering |
| **WiFi** | Scan nearby networks, view signal strength, channel, security. Suggests least congested channels |

## Installation

### From source

```bash
git clone https://github.com/arcademman/PyGate.git
cd PyGate
pip install -r requirements.txt
python pygate.py
```

### From release

1. Download `PyGate-win64.zip` from [Releases](https://github.com/arcademman/PyGate/releases)
2. Extract the zip
3. Run `pygate.exe`

> Some features (changing DNS, IP, editing hosts) require **Administrator privileges**. You can elevate from the Home page.

## Build

To compile as a standalone `.exe`:

```bash
pip install nuitka
python build.py
```

Output: `dist/PyGate-win64.zip`

## Localization

PyGate auto-detects your system language. Currently supported:
- English
- Italiano

You can change the language from **Settings > Language** in the menu bar.

To add a new language, create a JSON file in `app/locale/` following the structure of `en.json`.

## License

[MIT](LICENSE) - See [DISCLAIMER.md](DISCLAIMER.md) for usage guidelines.
