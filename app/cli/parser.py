"""Interfaccia CLI per PyGate."""

import sys

import argparse

from shared.i18n import t
from core import (
    get_dns, set_dns, reset_dns, flush_cache, is_dhcp,
    list_active_interfaces, benchmark_all, PRESETS,
)


def run_cli():
    parser = argparse.ArgumentParser(
        prog="pygate",
        description=t("pygate.description"),
    )

    sub = parser.add_subparsers(dest="command")

    # pygate show [interface]
    show_p = sub.add_parser("show", help=t("pygate.cli_show_help"))
    show_p.add_argument("interface", nargs="?", help=t("pygate.cli_interface_help"))

    # pygate set <dns> -i <interface>
    set_p = sub.add_parser("set", help=t("pygate.cli_set_help"))
    set_p.add_argument("dns", help="DNS preset name or IP (primary[,secondary])")
    set_p.add_argument("-i", "--interface", help=t("pygate.cli_interface_help"))

    # pygate reset [-i interface]
    reset_p = sub.add_parser("reset", help=t("pygate.cli_reset_help"))
    reset_p.add_argument("-i", "--interface", help=t("pygate.cli_interface_help"))

    # pygate flush
    sub.add_parser("flush", help=t("pygate.cli_flush_help"))

    # pygate benchmark
    sub.add_parser("benchmark", help=t("pygate.cli_benchmark_help"))

    # pygate --gui
    parser.add_argument("--gui", action="store_true", help=t("pygate.cli_gui_help"))

    args = parser.parse_args()

    if args.gui or not args.command:
        from gui.app import launch
        launch()
        return

    if args.command == "show":
        _cmd_show(args)
    elif args.command == "set":
        _cmd_set(args)
    elif args.command == "reset":
        _cmd_reset(args)
    elif args.command == "flush":
        _cmd_flush()
    elif args.command == "benchmark":
        _cmd_benchmark()


def _get_interface(args) -> str:
    """Restituisce l'interfaccia specificata o la prima attiva."""
    if hasattr(args, "interface") and args.interface:
        return args.interface
    active = list_active_interfaces()
    if not active:
        print(t("pygate.no_interfaces"))
        sys.exit(1)
    return active[0]


def _cmd_show(args):
    iface = _get_interface(args)
    servers = get_dns(iface)
    dhcp = is_dhcp(iface)

    print(f"[{iface}]")
    if dhcp and not servers:
        print(f"  {t('pygate.dhcp')}")
    elif servers:
        prefix = f"  {t('pygate.current_dns')}: "
        print(f"{prefix}{', '.join(servers)}")
        if dhcp:
            print(f"  ({t('pygate.dhcp')})")
    else:
        print(f"  {t('pygate.no_dns')}")


def _cmd_set(args):
    iface = _get_interface(args)

    # Controlla se è un nome preset
    if args.dns in PRESETS:
        preset = PRESETS[args.dns]
        primary, secondary = preset["primary"], preset["secondary"]
    else:
        parts = args.dns.split(",")
        primary = parts[0].strip()
        secondary = parts[1].strip() if len(parts) > 1 else None

    success, msg = set_dns(iface, primary, secondary)
    if success:
        print(t("pygate.applied", primary=primary, secondary=secondary or "-"))
    else:
        print(t("pygate.apply_failed", error=msg))
        sys.exit(1)


def _cmd_reset(args):
    iface = _get_interface(args)
    success, msg = reset_dns(iface)
    if success:
        print(t("pygate.reset_done"))
    else:
        print(t("pygate.reset_failed", error=msg))
        sys.exit(1)


def _cmd_flush():
    success, msg = flush_cache()
    if success:
        print(t("pygate.flush_done"))
    else:
        print(t("pygate.flush_failed", error=msg))
        sys.exit(1)


def _cmd_benchmark():
    print(t("pygate.benchmark_running"))
    print()
    results = benchmark_all()
    for r in results:
        if r["ms"] is not None:
            print(t("pygate.benchmark_result", name=r["name"], ip=r["ip"], ms=f"{r['ms']:.1f}"))
        else:
            print(t("pygate.benchmark_timeout", name=r["name"], ip=r["ip"]))

    best = next((r for r in results if r["ms"] is not None), None)
    if best:
        print(f"\n{t('pygate.benchmark_best', name=best['name'], ms=f'{best["ms"]:.1f}')}")
