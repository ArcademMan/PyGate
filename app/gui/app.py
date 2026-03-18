"""Interfaccia GUI per PyGate con PySide6."""

import ctypes
import os
import platform
import sys
import threading

from PySide6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QComboBox, QScrollArea, QRadioButton, QButtonGroup,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QCheckBox, QDialog, QDialogButtonBox, QFormLayout,
)
from PySide6.QtCore import Qt, Signal, QObject, QTimer
from PySide6.QtGui import QColor

from shared.theme import ToolWindow, COLORS, font, FONT_SIZE, FONT_SIZE_SMALL, FONT_SIZE_TITLE
from shared.widgets import Sidebar, LatencyBar
from shared.i18n import t
from core import (
    get_dns, set_dns, reset_dns, flush_cache, is_dhcp, is_admin,
    list_active_interfaces, benchmark_all, PRESETS,
    get_public_ip, get_local_ip, get_hostname,
    get_dns_cache, get_cache_stats,
    get_ipv4_config, set_static_ip, set_dhcp,
    read_hosts, add_entry, remove_entry, toggle_entry, HOSTS_PATH,
    scan_ports, parse_ports, get_local_listeners, PORT_PRESETS,
    get_connections,
    get_wifi_networks, get_current_wifi, suggest_channel,
)

SECTIONS = ["Home", "DNS", "IPv4", "Hosts", "Port Scan", "Monitor", "WiFi"]

# Stylesheet condiviso per tutte le tabelle
_TABLE_STYLE = f"""
    QTableWidget {{
        background-color: {COLORS['bg_light']};
        border: none;
        border-radius: 8px;
        gridline-color: {COLORS['accent']};
    }}
    QTableWidget::item {{
        padding: 4px 8px;
    }}
    QTableWidget::item:alternate {{
        background-color: {COLORS['bg']};
    }}
    QHeaderView::section {{
        background-color: {COLORS['accent']};
        color: {COLORS['text_dim']};
        border: none;
        padding: 6px 8px;
        font-weight: bold;
    }}
"""


def _make_table(columns: list[str], min_height: int = 300) -> QTableWidget:
    """Crea una QTableWidget stilizzata."""
    table = QTableWidget(0, len(columns))
    table.setHorizontalHeaderLabels(columns)
    table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectRows)
    table.setAlternatingRowColors(True)
    table.verticalHeader().setVisible(False)
    table.setMinimumHeight(min_height)
    table.setStyleSheet(_TABLE_STYLE)
    return table


def _make_scroll_page(container) -> tuple[QScrollArea, QVBoxLayout]:
    """Crea una pagina scrollabile con layout allineato in alto."""
    scroll = QScrollArea(container)
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.NoFrame)

    outer = QWidget()
    outer_lay = QVBoxLayout(outer)
    outer_lay.setContentsMargins(0, 0, 0, 0)
    outer_lay.setSpacing(0)

    page = QWidget()
    lay = QVBoxLayout(page)
    lay.setContentsMargins(24, 24, 24, 24)
    lay.setSpacing(12)

    outer_lay.addWidget(page)
    outer_lay.addStretch()
    scroll.setWidget(outer)
    scroll.hide()

    return scroll, lay


def _page_header(lay: QVBoxLayout, title: str, subtitle_key: str):
    """Aggiunge titolo e sottotitolo a una pagina."""
    lbl = QLabel(title)
    lbl.setFont(font(FONT_SIZE_TITLE, bold=True))
    lbl.setStyleSheet(f"color: {COLORS['primary']};")
    lay.addWidget(lbl)

    sub = QLabel(t(subtitle_key))
    sub.setFont(font(FONT_SIZE))
    sub.setStyleSheet(f"color: {COLORS['text_dim']};")
    lay.addWidget(sub)


class _Signals(QObject):
    """Segnali per comunicazione thread -> GUI."""
    status = Signal(str)
    refresh_dns = Signal()
    show_benchmark = Signal(list)
    public_ip = Signal(str)
    show_cache = Signal(list)
    refresh_ipv4 = Signal()
    scan_result = Signal(dict)
    scan_done = Signal(list)
    public_ip_scan = Signal(str)


class PyGateApp(ToolWindow):
    def __init__(self):
        super().__init__("PyGate", width=1000, height=680)
        self.setMinimumSize(900, 600)
        self._header.hide()

        # Icona finestra
        from PySide6.QtGui import QIcon
        icon_path = os.path.join(os.path.dirname(__file__), "..", "..", "pygate.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # Segnali thread -> GUI
        self._signals = _Signals()
        self._signals.status.connect(self._set_status)
        self._signals.refresh_dns.connect(self._refresh_dns_display)
        self._signals.show_benchmark.connect(self._show_benchmark)
        self._signals.public_ip.connect(
            lambda ip: self._public_ip_value.setText(ip) if hasattr(self, '_public_ip_value') else None
        )
        self._signals.show_cache.connect(self._show_cache_results)
        self._signals.refresh_ipv4.connect(
            lambda: self._refresh_ipv4_display() if hasattr(self, '_ipv4_iface_combo') else None
        )
        self._signals.scan_result.connect(self._on_scan_port_result)
        self._signals.scan_done.connect(self._on_scan_complete)
        self._signals.public_ip_scan.connect(self._start_public_scan)

        # Layout: sidebar + contenuto
        main_widget = QWidget()
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self._sidebar = Sidebar(items=SECTIONS, on_select=self._on_section_change, width=180)
        main_layout.addWidget(self._sidebar)

        sep = QFrame()
        sep.setFixedWidth(2)
        sep.setStyleSheet(f"background-color: {COLORS['accent']};")
        main_layout.addWidget(sep)

        self._page_container = QWidget()
        self._page_container_layout = QVBoxLayout(self._page_container)
        self._page_container_layout.setContentsMargins(0, 0, 0, 0)
        self._page_container_layout.setSpacing(0)
        main_layout.addWidget(self._page_container, stretch=1)

        self.add_widget(main_widget)
        self._layout.setStretch(self._layout.indexOf(main_widget), 1)

        # Status bar
        self._status_bar = QLabel("")
        self._status_bar.setFont(font(FONT_SIZE_SMALL))
        self._status_bar.setFixedHeight(28)
        self._status_bar.setStyleSheet(
            f"background-color: {COLORS['bg_light']}; color: {COLORS['text_dim']}; padding: 0 12px;"
        )
        self.add_widget(self._status_bar)

        if not is_admin():
            self._set_status(t("admin_warning"))

        # Pagine
        self._pages: dict[str, QWidget] = {}
        self._build_home_page()
        self._build_dns_page()
        self._build_ipv4_page()
        self._build_hosts_page()
        self._build_portscan_page()
        self._build_monitor_page()
        self._build_wifi_page()

        self._current_page: str | None = None
        self._show_page("Home")

    # ── Navigazione ──

    def _set_status(self, text: str):
        self._status_bar.setText(text)

    def _show_page(self, name: str):
        if self._current_page == name:
            return
        if self._current_page and self._current_page in self._pages:
            self._pages[self._current_page].hide()
        self._pages[name].show()
        self._current_page = name

    def _on_section_change(self, _index: int, name: str):
        self._show_page(name)

    def _add_page(self, name: str, widget: QWidget):
        """Registra e aggiunge una pagina al container."""
        self._page_container_layout.addWidget(widget)
        self._pages[name] = widget

    # ══════════════════════════════════════
    #  HOME
    # ══════════════════════════════════════

    def _build_home_page(self):
        page = QWidget(self._page_container)
        lay = QVBoxLayout(page)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(16)

        _page_header(lay, "PyGate", "pygate.home_subtitle")

        # Info cards — riga 1
        row1 = QHBoxLayout()
        row1.setSpacing(12)

        ip_card = self._make_info_card(t("pygate.home_public_ip"), t("pygate.home_fetching_ip"))
        self._public_ip_value = ip_card.findChild(QLabel, "card_value")
        row1.addWidget(ip_card)
        row1.addWidget(self._make_info_card(t("pygate.home_local_ip"), get_local_ip()))
        row1.addWidget(self._make_info_card(t("pygate.home_hostname"), get_hostname()))
        lay.addLayout(row1)

        # Info cards — riga 2
        row2 = QHBoxLayout()
        row2.setSpacing(12)

        row2.addWidget(self._make_info_card(
            t("pygate.home_os"), f"{platform.system()} {platform.release()}"
        ))

        admin_yes = is_admin()
        row2.addWidget(self._make_info_card(
            t("pygate.home_admin"),
            t("pygate.home_admin_yes") if admin_yes else t("pygate.home_admin_no"),
            value_color=COLORS["success"] if admin_yes else COLORS["warning"],
        ))

        row2.addWidget(self._make_info_card(
            t("pygate.home_interfaces"), str(len(list_active_interfaces()))
        ))
        lay.addLayout(row2)

        if not admin_yes:
            lay.addWidget(self.make_button(
                t("pygate.home_btn_admin"), command=self._restart_as_admin, primary=True
            ))

        lay.addStretch()
        page.hide()
        self._add_page("Home", page)

        threading.Thread(target=self._fetch_public_ip, daemon=True).start()

    def _make_info_card(self, label: str, value: str, value_color: str = None) -> QFrame:
        card = QFrame()
        card.setStyleSheet(f"background-color: {COLORS['bg_light']}; border-radius: 8px;")
        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(16, 12, 16, 12)
        card_lay.setSpacing(4)

        lbl = QLabel(label)
        lbl.setFont(font(FONT_SIZE_SMALL))
        lbl.setStyleSheet(f"color: {COLORS['text_dim']};")
        card_lay.addWidget(lbl)

        val = QLabel(value)
        val.setObjectName("card_value")
        val.setFont(font(FONT_SIZE_TITLE, bold=True))
        val.setStyleSheet(f"color: {value_color or COLORS['text']};")
        card_lay.addWidget(val)

        return card

    def _fetch_public_ip(self):
        ip = get_public_ip()
        self._signals.public_ip.emit(ip or t("pygate.home_ip_error"))

    def _restart_as_admin(self):
        script = os.path.abspath(sys.argv[0])
        params = " ".join(sys.argv[1:])
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, f'"{script}" {params}', None, 1
        )
        sys.exit(0)

    # ══════════════════════════════════════
    #  DNS
    # ══════════════════════════════════════

    def _build_dns_page(self):
        scroll, lay = _make_scroll_page(self._page_container)
        self._add_page("DNS", scroll)

        _page_header(lay, "DNS", "pygate.subtitle")

        # Selettore interfaccia
        iface_row = QHBoxLayout()
        iface_row.setSpacing(10)
        iface_lbl = QLabel(t("pygate.select_interface"))
        iface_lbl.setFont(font(FONT_SIZE, bold=True))
        iface_row.addWidget(iface_lbl)

        self._interfaces = list_active_interfaces()
        self._iface_combo = QComboBox()
        self._iface_combo.setFont(font(FONT_SIZE))
        self._iface_combo.setMinimumWidth(280)
        self._iface_combo.addItems(self._interfaces or ["—"])
        self._iface_combo.currentTextChanged.connect(lambda _: self._refresh_dns_display())
        iface_row.addWidget(self._iface_combo)
        iface_row.addStretch()
        lay.addLayout(iface_row)

        # DNS attuale
        dns_box = QFrame()
        dns_box.setStyleSheet(f"background-color: {COLORS['bg_light']}; border-radius: 8px;")
        dns_box_lay = QVBoxLayout(dns_box)
        dns_box_lay.setContentsMargins(16, 12, 16, 12)
        self._dns_info = QLabel("")
        self._dns_info.setFont(font(FONT_SIZE))
        dns_box_lay.addWidget(self._dns_info)
        lay.addWidget(dns_box)
        self._refresh_dns_display()

        # Preset DNS
        preset_lbl = QLabel(t("pygate.select_preset"))
        preset_lbl.setFont(font(FONT_SIZE, bold=True))
        lay.addWidget(preset_lbl)

        preset_scroll = QScrollArea()
        preset_scroll.setWidgetResizable(True)
        preset_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        preset_scroll.setFrameShape(QFrame.NoFrame)
        preset_scroll.setFixedHeight(180)
        preset_scroll.setStyleSheet(f"background-color: {COLORS['bg_light']}; border-radius: 8px;")

        preset_widget = QWidget()
        preset_lay = QVBoxLayout(preset_widget)
        preset_lay.setContentsMargins(12, 8, 12, 8)
        preset_lay.setSpacing(4)

        self._preset_group = QButtonGroup(self)
        self._preset_values: dict[int, str] = {}

        # DHCP come prima opzione
        row = QHBoxLayout()
        row.setSpacing(12)
        rb_dhcp = QRadioButton(t("pygate.dhcp"))
        rb_dhcp.setFont(font(FONT_SIZE))
        rb_dhcp.setChecked(True)
        self._preset_group.addButton(rb_dhcp, 0)
        self._preset_values[0] = "_dhcp"
        row.addWidget(rb_dhcp)
        row.addStretch()
        preset_lay.addLayout(row)

        for i, (name, p) in enumerate(PRESETS.items(), start=1):
            row = QHBoxLayout()
            row.setSpacing(12)
            rb = QRadioButton(name)
            rb.setFont(font(FONT_SIZE))
            self._preset_group.addButton(rb, i)
            self._preset_values[i] = name
            row.addWidget(rb)
            detail = QLabel(f"{p['primary']}, {p['secondary']}")
            detail.setFont(font(FONT_SIZE_SMALL))
            detail.setStyleSheet(f"color: {COLORS['text_dim']};")
            row.addWidget(detail)
            row.addStretch()
            preset_lay.addLayout(row)

        # Custom
        custom_idx = len(PRESETS) + 1
        row = QHBoxLayout()
        rb_custom = QRadioButton(t("pygate.custom"))
        rb_custom.setFont(font(FONT_SIZE))
        self._preset_group.addButton(rb_custom, custom_idx)
        self._preset_values[custom_idx] = "_custom"
        row.addWidget(rb_custom)
        row.addStretch()
        preset_lay.addLayout(row)

        self._preset_group.idToggled.connect(self._on_preset_toggled)
        preset_widget.setMinimumHeight(preset_lay.count() * 30 + 16)
        preset_scroll.setWidget(preset_widget)
        lay.addWidget(preset_scroll)

        # Custom DNS input
        self._custom_frame = QWidget()
        custom_lay = QHBoxLayout(self._custom_frame)
        custom_lay.setContentsMargins(0, 0, 0, 0)
        custom_lay.setSpacing(8)
        custom_lay.addWidget(QLabel(t("pygate.custom_primary")))
        self._custom_primary = QLineEdit()
        self._custom_primary.setFixedWidth(140)
        self._custom_primary.setPlaceholderText("1.1.1.1")
        custom_lay.addWidget(self._custom_primary)
        custom_lay.addWidget(QLabel(t("pygate.custom_secondary")))
        self._custom_secondary = QLineEdit()
        self._custom_secondary.setFixedWidth(140)
        self._custom_secondary.setPlaceholderText("1.0.0.1")
        custom_lay.addWidget(self._custom_secondary)
        custom_lay.addStretch()
        self._custom_frame.hide()
        lay.addWidget(self._custom_frame)

        # Bottoni
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        for label, cmd, primary in [
            (t("pygate.btn_apply"), self._on_apply, True),
            (t("pygate.btn_reset"), self._on_reset, False),
            (t("pygate.btn_flush"), self._on_flush, False),
            (t("pygate.btn_benchmark"), self._on_benchmark, False),
        ]:
            btn_row.addWidget(self.make_button(label, command=cmd, primary=primary))
        btn_row.addStretch()
        lay.addLayout(btn_row)

        # Cache DNS
        cache_header = QHBoxLayout()
        cache_header.setSpacing(8)
        cache_lbl = QLabel(t("pygate.cache_title"))
        cache_lbl.setFont(font(FONT_SIZE, bold=True))
        cache_header.addWidget(cache_lbl)
        self._cache_stats_lbl = QLabel("")
        self._cache_stats_lbl.setFont(font(FONT_SIZE_SMALL))
        self._cache_stats_lbl.setStyleSheet(f"color: {COLORS['text_dim']};")
        cache_header.addWidget(self._cache_stats_lbl)
        cache_header.addStretch()
        cache_header.addWidget(self.make_button(t("pygate.cache_btn_view"), command=self._on_view_cache, primary=False))
        cache_header.addWidget(self.make_button(t("pygate.cache_btn_flush"), command=self._on_flush, primary=False))
        lay.addLayout(cache_header)

        self._cache_table = _make_table([
            t("pygate.cache_col_name"), t("pygate.cache_col_type"),
            t("pygate.cache_col_data"), t("pygate.cache_col_ttl"),
        ])
        self._cache_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._cache_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._cache_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self._cache_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self._cache_table.hide()
        lay.addWidget(self._cache_table)

        # Benchmark
        self._bench_container = QWidget()
        self._bench_layout = QVBoxLayout(self._bench_container)
        self._bench_layout.setContentsMargins(0, 8, 0, 0)
        self._bench_layout.setSpacing(2)
        lay.addWidget(self._bench_container)

    # ── DNS Callbacks ──

    def _refresh_dns_display(self):
        iface = self._iface_combo.currentText()
        if not iface or iface == "—":
            self._dns_info.setText(t("pygate.no_interfaces"))
            return
        servers = get_dns(iface)
        dhcp = is_dhcp(iface)
        lines = []
        if servers:
            lines.append(f"{t('pygate.current_dns')}: {', '.join(servers)}")
        if dhcp:
            lines.append(t("pygate.dhcp"))
        elif not servers:
            lines.append(t("pygate.no_dns"))
        self._dns_info.setText("\n".join(lines))

    def _on_preset_toggled(self, btn_id: int, checked: bool):
        if not checked:
            return
        value = self._preset_values.get(btn_id, "")
        self._custom_frame.show() if value == "_custom" else self._custom_frame.hide()

    def _get_selected_dns(self) -> tuple[str, str | None] | None:
        btn_id = self._preset_group.checkedId()
        value = self._preset_values.get(btn_id, "")
        if value == "_custom":
            primary = self._custom_primary.text().strip()
            secondary = self._custom_secondary.text().strip() or None
            return (primary, secondary) if primary else None
        if value in PRESETS:
            p = PRESETS[value]
            return p["primary"], p["secondary"]
        return None

    def _current_iface(self) -> str | None:
        val = self._iface_combo.currentText()
        return val if val and val != "—" else None

    def _on_apply(self):
        iface = self._current_iface()
        if not iface:
            return
        btn_id = self._preset_group.checkedId()
        value = self._preset_values.get(btn_id, "")
        if value == "_dhcp":
            self._on_reset()
            return
        dns = self._get_selected_dns()
        if not dns:
            return
        primary, secondary = dns
        self._set_status(t("pygate.applying"))

        def _worker():
            success, msg = set_dns(iface, primary, secondary)
            text = t("pygate.applied", primary=primary, secondary=secondary or "-") if success \
                else t("pygate.apply_failed", error=msg)
            self._signals.status.emit(text)
            self._signals.refresh_dns.emit()
        threading.Thread(target=_worker, daemon=True).start()

    def _on_reset(self):
        iface = self._current_iface()
        if not iface:
            return
        self._set_status(t("pygate.resetting"))

        def _worker():
            success, msg = reset_dns(iface)
            text = t("pygate.reset_done") if success else t("pygate.reset_failed", error=msg)
            self._signals.status.emit(text)
            self._signals.refresh_dns.emit()
        threading.Thread(target=_worker, daemon=True).start()

    def _on_flush(self):
        self._set_status(t("pygate.flushing"))

        def _worker():
            success, msg = flush_cache()
            text = t("pygate.flush_done") if success else t("pygate.flush_failed", error=msg)
            self._signals.status.emit(text)
        threading.Thread(target=_worker, daemon=True).start()

    def _on_benchmark(self):
        self._set_status(t("pygate.benchmark_running"))
        self._clear_bench()
        lbl = QLabel(t("pygate.benchmark_running"))
        lbl.setFont(font(FONT_SIZE_SMALL))
        lbl.setStyleSheet(f"color: {COLORS['text_dim']};")
        self._bench_layout.addWidget(lbl)

        def _worker():
            results = benchmark_all()
            self._signals.show_benchmark.emit(results)
        threading.Thread(target=_worker, daemon=True).start()

    def _clear_bench(self):
        while self._bench_layout.count():
            item = self._bench_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _show_benchmark(self, results: list[dict]):
        self._clear_bench()
        max_ms = max((r["ms"] for r in results if r["ms"] is not None), default=200)
        for r in results:
            self._bench_layout.addWidget(
                LatencyBar(name=r["name"], ip=r["ip"], ms=r["ms"], max_ms=max_ms * 1.2)
            )
        best = next((r for r in results if r["ms"] is not None), None)
        if best:
            self._set_status(t("pygate.benchmark_best", name=best["name"], ms=f"{best['ms']:.0f}"))

    # ── Cache Callbacks ──

    def _on_view_cache(self):
        self._set_status(t("pygate.cache_loading"))
        self._cache_table.show()

        def _worker():
            entries = get_dns_cache()
            self._signals.show_cache.emit(entries)
        threading.Thread(target=_worker, daemon=True).start()

    def _show_cache_results(self, entries: list[dict]):
        stats = get_cache_stats(entries)
        self._cache_stats_lbl.setText(
            t("pygate.cache_records", total=stats["total"], domains=stats["unique_domains"])
        )
        self._cache_table.setRowCount(len(entries))
        for i, e in enumerate(entries):
            self._cache_table.setItem(i, 0, QTableWidgetItem(e.get("name", "")))
            self._cache_table.setItem(i, 1, QTableWidgetItem(e.get("type", "")))
            self._cache_table.setItem(i, 2, QTableWidgetItem(e.get("data", "")))
            self._cache_table.setItem(i, 3, QTableWidgetItem(str(e.get("ttl", ""))))
        self._set_status(
            t("pygate.cache_records", total=stats["total"], domains=stats["unique_domains"])
        )

    # ══════════════════════════════════════
    #  IPv4
    # ══════════════════════════════════════

    def _build_ipv4_page(self):
        scroll, lay = _make_scroll_page(self._page_container)
        self._add_page("IPv4", scroll)

        _page_header(lay, "IPv4", "pygate.ipv4_subtitle")

        # Selettore interfaccia
        iface_row = QHBoxLayout()
        iface_row.setSpacing(10)
        iface_lbl = QLabel(t("pygate.select_interface"))
        iface_lbl.setFont(font(FONT_SIZE, bold=True))
        iface_row.addWidget(iface_lbl)
        self._ipv4_iface_combo = QComboBox()
        self._ipv4_iface_combo.setFont(font(FONT_SIZE))
        self._ipv4_iface_combo.setMinimumWidth(280)
        self._ipv4_iface_combo.addItems(list_active_interfaces() or ["—"])
        self._ipv4_iface_combo.currentTextChanged.connect(lambda _: self._refresh_ipv4_display())
        iface_row.addWidget(self._ipv4_iface_combo)
        iface_row.addStretch()
        lay.addLayout(iface_row)

        # Config attuale
        current_lbl = QLabel(t("pygate.ipv4_current"))
        current_lbl.setFont(font(FONT_SIZE, bold=True))
        lay.addWidget(current_lbl)

        current_box = QFrame()
        current_box.setStyleSheet(f"background-color: {COLORS['bg_light']}; border-radius: 8px;")
        current_box_lay = QVBoxLayout(current_box)
        current_box_lay.setContentsMargins(16, 12, 16, 12)
        self._ipv4_current_info = QLabel("")
        self._ipv4_current_info.setFont(font(FONT_SIZE))
        current_box_lay.addWidget(self._ipv4_current_info)
        lay.addWidget(current_box)
        self._refresh_ipv4_display()

        # DHCP / Statico
        mode_lbl = QLabel(t("pygate.ipv4_mode"))
        mode_lbl.setFont(font(FONT_SIZE, bold=True))
        lay.addWidget(mode_lbl)

        mode_row = QHBoxLayout()
        mode_row.setSpacing(16)
        self._ipv4_mode_group = QButtonGroup(self)
        self._ipv4_rb_dhcp = QRadioButton(t("pygate.ipv4_dhcp"))
        self._ipv4_rb_dhcp.setFont(font(FONT_SIZE))
        self._ipv4_rb_dhcp.setChecked(True)
        self._ipv4_mode_group.addButton(self._ipv4_rb_dhcp, 0)
        mode_row.addWidget(self._ipv4_rb_dhcp)
        self._ipv4_rb_static = QRadioButton(t("pygate.ipv4_static"))
        self._ipv4_rb_static.setFont(font(FONT_SIZE))
        self._ipv4_mode_group.addButton(self._ipv4_rb_static, 1)
        mode_row.addWidget(self._ipv4_rb_static)
        mode_row.addStretch()
        lay.addLayout(mode_row)

        # Campi IP statico
        self._ipv4_fields_frame = QWidget()
        fields_lay = QVBoxLayout(self._ipv4_fields_frame)
        fields_lay.setContentsMargins(0, 0, 0, 0)
        fields_lay.setSpacing(8)
        for label_key, attr_name, placeholder in [
            ("pygate.ipv4_ip", "_ipv4_ip_input", "192.168.1.100"),
            ("pygate.ipv4_subnet", "_ipv4_subnet_input", "255.255.255.0"),
            ("pygate.ipv4_gateway", "_ipv4_gateway_input", "192.168.1.1"),
        ]:
            row = QHBoxLayout()
            row.setSpacing(8)
            lbl = QLabel(t(label_key))
            lbl.setFont(font(FONT_SIZE))
            lbl.setFixedWidth(150)
            row.addWidget(lbl)
            entry = QLineEdit()
            entry.setFont(font(FONT_SIZE))
            entry.setFixedWidth(200)
            entry.setPlaceholderText(placeholder)
            setattr(self, attr_name, entry)
            row.addWidget(entry)
            row.addStretch()
            fields_lay.addLayout(row)
        self._ipv4_fields_frame.hide()
        lay.addWidget(self._ipv4_fields_frame)
        self._ipv4_mode_group.idToggled.connect(self._on_ipv4_mode_change)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addWidget(self.make_button(t("pygate.ipv4_btn_apply"), command=self._on_ipv4_apply, primary=True))
        btn_row.addStretch()
        lay.addLayout(btn_row)

    # ── IPv4 Callbacks ──

    def _refresh_ipv4_display(self):
        iface = self._ipv4_iface_combo.currentText()
        if not iface or iface == "—":
            self._ipv4_current_info.setText(t("pygate.no_interfaces"))
            return
        config = get_ipv4_config(iface)
        mode = t("pygate.ipv4_dhcp") if config["dhcp"] else t("pygate.ipv4_static")
        self._ipv4_current_info.setText("\n".join([
            f"{t('pygate.ipv4_mode')} {mode}",
            f"{t('pygate.ipv4_ip')} {config['ip'] or '—'}",
            f"{t('pygate.ipv4_subnet')} {config['subnet'] or '—'}",
            f"{t('pygate.ipv4_gateway')} {config['gateway'] or '—'}",
        ]))

    def _on_ipv4_mode_change(self, btn_id: int, checked: bool):
        if checked:
            self._ipv4_fields_frame.show() if btn_id == 1 else self._ipv4_fields_frame.hide()

    def _on_ipv4_apply(self):
        iface = self._ipv4_iface_combo.currentText()
        if not iface or iface == "—":
            return
        self._set_status(t("pygate.ipv4_applying"))

        if self._ipv4_mode_group.checkedId() == 1:
            ip = self._ipv4_ip_input.text().strip()
            subnet = self._ipv4_subnet_input.text().strip()
            gateway = self._ipv4_gateway_input.text().strip()
            if not all([ip, subnet, gateway]):
                return

            def _worker():
                success, msg = set_static_ip(iface, ip, subnet, gateway)
                text = t("pygate.ipv4_applied", ip=ip, subnet=subnet, gateway=gateway) if success \
                    else t("pygate.ipv4_apply_failed", error=msg)
                self._signals.status.emit(text)
                self._signals.refresh_ipv4.emit()
            threading.Thread(target=_worker, daemon=True).start()
        else:
            def _worker():
                success, msg = set_dhcp(iface)
                text = t("pygate.ipv4_dhcp_done") if success else t("pygate.ipv4_dhcp_failed", error=msg)
                self._signals.status.emit(text)
                self._signals.refresh_ipv4.emit()
            threading.Thread(target=_worker, daemon=True).start()

    # ══════════════════════════════════════
    #  HOSTS
    # ══════════════════════════════════════

    def _build_hosts_page(self):
        scroll, lay = _make_scroll_page(self._page_container)
        self._add_page("Hosts", scroll)

        _page_header(lay, "Hosts", "pygate.hosts_subtitle")

        path_lbl = QLabel(t("pygate.hosts_path", path=HOSTS_PATH))
        path_lbl.setFont(font(FONT_SIZE_SMALL))
        path_lbl.setStyleSheet(f"color: {COLORS['text_dim']};")
        lay.addWidget(path_lbl)

        # Bottoni
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addWidget(self.make_button(t("pygate.hosts_btn_add"), command=self._on_hosts_add, primary=True))
        btn_row.addWidget(self.make_button(t("pygate.hosts_btn_toggle"), command=self._on_hosts_toggle, primary=False))
        btn_row.addWidget(self.make_button(t("pygate.hosts_btn_remove"), command=self._on_hosts_remove, primary=False))
        btn_row.addWidget(self.make_button(t("pygate.hosts_btn_refresh"), command=self._refresh_hosts, primary=False))
        btn_row.addStretch()
        self._hosts_count_lbl = QLabel("")
        self._hosts_count_lbl.setFont(font(FONT_SIZE_SMALL))
        self._hosts_count_lbl.setStyleSheet(f"color: {COLORS['text_dim']};")
        btn_row.addWidget(self._hosts_count_lbl)
        lay.addLayout(btn_row)

        # Tabella
        self._hosts_table = _make_table([
            t("pygate.hosts_col_enabled"), t("pygate.hosts_col_ip"),
            t("pygate.hosts_col_hostname"), t("pygate.hosts_col_comment"),
        ], min_height=350)
        self._hosts_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._hosts_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Interactive)
        self._hosts_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self._hosts_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self._hosts_table.setColumnWidth(1, 150)
        lay.addWidget(self._hosts_table)

        self._hosts_entries: list[dict] = []
        self._refresh_hosts()

    # ── Hosts Callbacks ──

    def _refresh_hosts(self):
        self._hosts_entries = read_hosts()
        self._hosts_table.setRowCount(len(self._hosts_entries))
        for i, entry in enumerate(self._hosts_entries):
            status = "✓" if entry["enabled"] else "✗"
            status_item = QTableWidgetItem(status)
            status_item.setTextAlignment(Qt.AlignCenter)
            status_item.setForeground(QColor(COLORS["success"] if entry["enabled"] else COLORS["text_dim"]))
            self._hosts_table.setItem(i, 0, status_item)

            for col, key in [(1, "ip"), (2, "hostname")]:
                item = QTableWidgetItem(entry[key])
                if not entry["enabled"]:
                    item.setForeground(QColor(COLORS["text_dim"]))
                self._hosts_table.setItem(i, col, item)

            comment_item = QTableWidgetItem(entry.get("comment", ""))
            comment_item.setForeground(QColor(COLORS["text_dim"]))
            self._hosts_table.setItem(i, 3, comment_item)
        self._hosts_count_lbl.setText(t("pygate.hosts_entries", count=len(self._hosts_entries)))

    def _on_hosts_add(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(t("pygate.hosts_add_title"))
        dialog.setMinimumWidth(400)
        dialog.setStyleSheet(f"background-color: {COLORS['bg']}; color: {COLORS['text']};")
        form = QFormLayout(dialog)
        form.setSpacing(12)
        form.setContentsMargins(16, 16, 16, 16)

        ip_input = QLineEdit()
        ip_input.setPlaceholderText("127.0.0.1")
        form.addRow(t("pygate.hosts_add_ip"), ip_input)
        hostname_input = QLineEdit()
        hostname_input.setPlaceholderText("example.local")
        form.addRow(t("pygate.hosts_add_hostname"), hostname_input)
        comment_input = QLineEdit()
        form.addRow(t("pygate.hosts_add_comment"), comment_input)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)

        if dialog.exec() == QDialog.Accepted:
            ip = ip_input.text().strip()
            hostname = hostname_input.text().strip()
            if ip and hostname:
                success, msg = add_entry(ip, hostname, comment_input.text().strip())
                self._set_status(t("pygate.hosts_saved") if success else t("pygate.hosts_error", error=msg))
                if success:
                    self._refresh_hosts()

    def _on_hosts_toggle(self):
        row = self._hosts_table.currentRow()
        if 0 <= row < len(self._hosts_entries):
            success, msg = toggle_entry(self._hosts_entries[row]["line_num"])
            self._set_status(t("pygate.hosts_saved") if success else t("pygate.hosts_error", error=msg))
            if success:
                self._refresh_hosts()

    def _on_hosts_remove(self):
        row = self._hosts_table.currentRow()
        if 0 <= row < len(self._hosts_entries):
            success, msg = remove_entry(self._hosts_entries[row]["line_num"])
            self._set_status(t("pygate.hosts_saved") if success else t("pygate.hosts_error", error=msg))
            if success:
                self._refresh_hosts()

    # ══════════════════════════════════════
    #  PORT SCAN
    # ══════════════════════════════════════

    def _build_portscan_page(self):
        scroll, lay = _make_scroll_page(self._page_container)
        self._add_page("Port Scan", scroll)

        _page_header(lay, "Port Scan", "pygate.scan_subtitle")

        # Input
        input_row = QHBoxLayout()
        input_row.setSpacing(8)
        input_row.addWidget(QLabel(t("pygate.scan_host")))
        self._scan_host = QLineEdit()
        self._scan_host.setFixedWidth(200)
        self._scan_host.setPlaceholderText("127.0.0.1")
        self._scan_host.setText("127.0.0.1")
        input_row.addWidget(self._scan_host)
        input_row.addWidget(QLabel(t("pygate.scan_ports")))
        self._scan_ports_input = QLineEdit()
        self._scan_ports_input.setFixedWidth(200)
        self._scan_ports_input.setPlaceholderText("80,443,8080 or 1-1024")
        input_row.addWidget(self._scan_ports_input)
        input_row.addWidget(QLabel(t("pygate.scan_preset")))
        self._scan_preset_combo = QComboBox()
        self._scan_preset_combo.addItems(["—"] + list(PORT_PRESETS.keys()))
        self._scan_preset_combo.currentTextChanged.connect(self._on_scan_preset_change)
        input_row.addWidget(self._scan_preset_combo)
        input_row.addStretch()
        lay.addLayout(input_row)

        # Bottoni
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self._scan_btn = self.make_button(t("pygate.scan_btn_scan"), command=self._on_scan_start, primary=True)
        btn_row.addWidget(self._scan_btn)
        btn_row.addWidget(self.make_button(t("pygate.scan_btn_local"), command=self._on_show_local, primary=False))
        btn_row.addWidget(self.make_button(t("pygate.scan_btn_public"), command=self._on_scan_public, primary=False))
        self._scan_open_only = QCheckBox(t("pygate.scan_show_open"))
        self._scan_open_only.setFont(font(FONT_SIZE))
        self._scan_open_only.setChecked(True)
        self._scan_open_only.toggled.connect(self._on_scan_filter_change)
        btn_row.addWidget(self._scan_open_only)
        btn_row.addStretch()
        self._scan_status_lbl = QLabel("")
        self._scan_status_lbl.setFont(font(FONT_SIZE_SMALL))
        self._scan_status_lbl.setStyleSheet(f"color: {COLORS['text_dim']};")
        btn_row.addWidget(self._scan_status_lbl)
        lay.addLayout(btn_row)

        # Tabella
        self._scan_table = _make_table([
            t("pygate.scan_col_port"), t("pygate.scan_col_status"), t("pygate.scan_col_service"),
        ], min_height=350)
        self._scan_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._scan_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._scan_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        lay.addWidget(self._scan_table)

        self._scan_results: list[dict] = []
        self._scan_running = False
        self._scan_done_count = 0
        self._scan_total_count = 0

    # ── Port Scan Callbacks ──

    def _on_scan_preset_change(self, preset: str):
        if preset in PORT_PRESETS:
            self._scan_ports_input.setText(",".join(str(p) for p in PORT_PRESETS[preset]))

    def _on_scan_start(self):
        if self._scan_running:
            return
        host = self._scan_host.text().strip()
        ports_text = self._scan_ports_input.text().strip()
        if not host or not ports_text:
            return
        ports = parse_ports(ports_text)
        if not ports:
            return

        self._scan_running = True
        self._scan_results = []
        self._scan_done_count = 0
        self._scan_total_count = len(ports)
        self._scan_table.setRowCount(0)
        self._scan_btn.setEnabled(False)
        self._set_status(t("pygate.scan_running", host=host, done=0, total=len(ports)))

        def _worker():
            def _on_result(result):
                self._scan_done_count += 1
                self._signals.scan_result.emit(result)
            scan_ports(host, ports, timeout=1.0, on_result=_on_result)
            self._signals.scan_done.emit(self._scan_results)
        threading.Thread(target=_worker, daemon=True).start()

    def _on_scan_port_result(self, result: dict):
        self._scan_results.append(result)
        self._set_status(t("pygate.scan_running",
                           host=self._scan_host.text().strip(),
                           done=self._scan_done_count, total=self._scan_total_count))
        if self._scan_open_only.isChecked() and not result["open"]:
            return
        row = self._scan_table.rowCount()
        self._scan_table.insertRow(row)
        self._scan_table.setItem(row, 0, QTableWidgetItem(str(result["port"])))
        status_text = t("pygate.scan_open") if result["open"] else t("pygate.scan_closed")
        status_item = QTableWidgetItem(status_text)
        status_item.setForeground(QColor(COLORS["success"] if result["open"] else COLORS["text_dim"]))
        self._scan_table.setItem(row, 1, status_item)
        self._scan_table.setItem(row, 2, QTableWidgetItem(result["service"]))

    def _on_scan_complete(self, results: list[dict]):
        self._scan_running = False
        self._scan_btn.setEnabled(True)
        self._scan_results = results
        open_count = sum(1 for r in results if r["open"])
        status = t("pygate.scan_done", open=open_count, total=len(results))
        self._set_status(status)
        self._scan_status_lbl.setText(status)

    def _on_scan_filter_change(self, checked: bool):
        self._scan_table.setRowCount(0)
        for result in sorted(self._scan_results, key=lambda r: r["port"]):
            if checked and not result["open"]:
                continue
            row = self._scan_table.rowCount()
            self._scan_table.insertRow(row)
            self._scan_table.setItem(row, 0, QTableWidgetItem(str(result["port"])))
            status_text = t("pygate.scan_open") if result["open"] else t("pygate.scan_closed")
            status_item = QTableWidgetItem(status_text)
            status_item.setForeground(QColor(COLORS["success"] if result["open"] else COLORS["text_dim"]))
            self._scan_table.setItem(row, 1, status_item)
            self._scan_table.setItem(row, 2, QTableWidgetItem(result["service"]))

    def _on_show_local(self):
        listeners = get_local_listeners()
        self._scan_results = [{"port": l["port"], "open": True, "service": l.get("service", "")} for l in listeners]
        self._scan_open_only.setChecked(True)
        self._scan_table.setRowCount(0)

        for l in listeners:
            row = self._scan_table.rowCount()
            self._scan_table.insertRow(row)

            bind = l.get("bind", "")
            self._scan_table.setItem(row, 0, QTableWidgetItem(f"{l['port']}  ({bind})" if bind else str(l["port"])))

            status_item = QTableWidgetItem(t("pygate.scan_open"))
            status_item.setForeground(QColor(COLORS["warning"] if bind == "0.0.0.0" else COLORS["success"]))
            self._scan_table.setItem(row, 1, status_item)

            parts = [p for p in [l.get("process"), l.get("service")] if p]
            parts.append(f"PID {l['pid']}")
            self._scan_table.setItem(row, 2, QTableWidgetItem(" — ".join(parts)))

        self._scan_status_lbl.setText(f"{t('pygate.scan_local_title')} — {len(listeners)}")
        self._set_status(t("pygate.scan_local_title"))

    def _on_scan_public(self):
        self._set_status(t("pygate.home_fetching_ip"))

        def _worker():
            ip = get_public_ip()
            if ip:
                self._signals.public_ip_scan.emit(ip)
        threading.Thread(target=_worker, daemon=True).start()

    def _start_public_scan(self, ip: str):
        self._scan_host.setText(ip)
        self._scan_preset_combo.setCurrentText("top100")
        self._on_scan_preset_change("top100")
        self._set_status(t("pygate.scan_loopback_warning"))
        self._on_scan_start()

    # ══════════════════════════════════════
    #  MONITOR
    # ══════════════════════════════════════

    def _build_monitor_page(self):
        scroll, lay = _make_scroll_page(self._page_container)
        self._add_page("Monitor", scroll)

        _page_header(lay, "Monitor", "pygate.monitor_subtitle")

        # Bottoni + filtro
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addWidget(self.make_button(t("pygate.monitor_btn_refresh"), command=self._refresh_monitor, primary=True))
        self._monitor_auto = QCheckBox(t("pygate.monitor_btn_auto"))
        self._monitor_auto.setFont(font(FONT_SIZE))
        self._monitor_auto.toggled.connect(self._on_monitor_auto_toggle)
        btn_row.addWidget(self._monitor_auto)
        btn_row.addWidget(QLabel(t("pygate.monitor_filter")))
        self._monitor_filter = QLineEdit()
        self._monitor_filter.setFixedWidth(200)
        self._monitor_filter.setPlaceholderText("process, ip, port...")
        self._monitor_filter.textChanged.connect(lambda _: self._apply_monitor_filter())
        btn_row.addWidget(self._monitor_filter)
        btn_row.addStretch()
        self._monitor_count_lbl = QLabel("")
        self._monitor_count_lbl.setFont(font(FONT_SIZE_SMALL))
        self._monitor_count_lbl.setStyleSheet(f"color: {COLORS['text_dim']};")
        btn_row.addWidget(self._monitor_count_lbl)
        lay.addLayout(btn_row)

        # Tabella
        self._monitor_table = _make_table([
            t("pygate.monitor_col_process"), t("pygate.monitor_col_local"),
            t("pygate.monitor_col_remote"), t("pygate.monitor_col_status"),
            t("pygate.monitor_col_pid"),
        ], min_height=400)
        self._monitor_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        self._monitor_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._monitor_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self._monitor_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self._monitor_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self._monitor_table.setColumnWidth(0, 160)
        lay.addWidget(self._monitor_table)

        self._monitor_data: list[dict] = []
        self._monitor_timer = QTimer(self)
        self._monitor_timer.timeout.connect(self._refresh_monitor)

    # ── Monitor Callbacks ──

    _STATUS_COLORS = {
        "ESTABLISHED": COLORS["success"],
        "LISTEN": COLORS["warning"],
        "TIME_WAIT": COLORS["text_dim"],
        "CLOSE_WAIT": COLORS["error"],
    }

    def _refresh_monitor(self):
        self._monitor_data = get_connections()
        self._apply_monitor_filter()

    def _apply_monitor_filter(self):
        query = self._monitor_filter.text().strip().lower()
        filtered = self._monitor_data
        if query:
            filtered = [c for c in filtered
                        if query in c["process"].lower()
                        or query in c["local_addr"] or query in str(c["local_port"])
                        or query in c["remote_addr"] or query in str(c["remote_port"])
                        or query in c["status"].lower()]

        self._monitor_table.setRowCount(len(filtered))
        for i, c in enumerate(filtered):
            self._monitor_table.setItem(i, 0, QTableWidgetItem(c["process"]))
            self._monitor_table.setItem(i, 1, QTableWidgetItem(f"{c['local_addr']}:{c['local_port']}"))
            remote = f"{c['remote_addr']}:{c['remote_port']}" if c['remote_addr'] else ""
            self._monitor_table.setItem(i, 2, QTableWidgetItem(remote))
            status_item = QTableWidgetItem(c["status"])
            status_item.setForeground(QColor(self._STATUS_COLORS.get(c["status"], COLORS["text"])))
            self._monitor_table.setItem(i, 3, status_item)
            self._monitor_table.setItem(i, 4, QTableWidgetItem(str(c["pid"])))
        self._monitor_count_lbl.setText(t("pygate.monitor_connections", count=len(filtered)))

    def _on_monitor_auto_toggle(self, checked: bool):
        if checked:
            self._monitor_timer.start(3000)
            self._refresh_monitor()
        else:
            self._monitor_timer.stop()

    # ══════════════════════════════════════
    #  WIFI
    # ══════════════════════════════════════

    def _build_wifi_page(self):
        scroll, lay = _make_scroll_page(self._page_container)
        self._add_page("WiFi", scroll)

        _page_header(lay, "WiFi", "pygate.wifi_subtitle")

        # Connessione attuale
        wifi_box = QFrame()
        wifi_box.setStyleSheet(f"background-color: {COLORS['bg_light']}; border-radius: 8px;")
        wifi_box_lay = QVBoxLayout(wifi_box)
        wifi_box_lay.setContentsMargins(16, 12, 16, 12)
        self._wifi_current_lbl = QLabel(t("pygate.wifi_not_connected"))
        self._wifi_current_lbl.setFont(font(FONT_SIZE))
        wifi_box_lay.addWidget(self._wifi_current_lbl)
        lay.addWidget(wifi_box)

        # Bottoni
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addWidget(self.make_button(t("pygate.wifi_btn_scan"), command=self._on_wifi_scan, primary=True))
        btn_row.addStretch()
        self._wifi_count_lbl = QLabel("")
        self._wifi_count_lbl.setFont(font(FONT_SIZE_SMALL))
        self._wifi_count_lbl.setStyleSheet(f"color: {COLORS['text_dim']};")
        btn_row.addWidget(self._wifi_count_lbl)
        lay.addLayout(btn_row)

        # Suggerimento canale
        self._wifi_channel_lbl = QLabel("")
        self._wifi_channel_lbl.setFont(font(FONT_SIZE))
        self._wifi_channel_lbl.setStyleSheet(f"color: {COLORS['success']};")
        lay.addWidget(self._wifi_channel_lbl)

        # Tabella
        self._wifi_table = _make_table([
            t("pygate.wifi_col_ssid"), t("pygate.wifi_col_signal"),
            t("pygate.wifi_col_channel"), t("pygate.wifi_col_auth"),
            t("pygate.wifi_col_bssid"),
        ])
        self._wifi_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._wifi_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._wifi_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._wifi_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Interactive)
        self._wifi_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Interactive)
        self._wifi_table.setColumnWidth(3, 150)
        self._wifi_table.setColumnWidth(4, 150)
        lay.addWidget(self._wifi_table)

    # ── WiFi Callbacks ──

    def _on_wifi_scan(self):
        self._set_status("Scanning WiFi...")

        current = get_current_wifi()
        if current:
            parts = [f"{t('pygate.wifi_current')}: {current.get('ssid', '?')}"]
            if current.get("signal"):
                parts.append(f"Signal: {current['signal']}%")
            if current.get("channel"):
                parts.append(f"Ch: {current['channel']}")
            if current.get("auth"):
                parts.append(current["auth"])
            self._wifi_current_lbl.setText("   |   ".join(parts))
        else:
            self._wifi_current_lbl.setText(t("pygate.wifi_not_connected"))

        networks = get_wifi_networks()
        self._wifi_table.setRowCount(len(networks))
        for i, net in enumerate(networks):
            self._wifi_table.setItem(i, 0, QTableWidgetItem(net["ssid"]))
            signal_item = QTableWidgetItem(f"{net['signal']}%")
            color = COLORS["success"] if net["signal"] >= 70 else \
                    COLORS["warning"] if net["signal"] >= 40 else COLORS["error"]
            signal_item.setForeground(QColor(color))
            self._wifi_table.setItem(i, 1, signal_item)
            self._wifi_table.setItem(i, 2, QTableWidgetItem(str(net["channel"])))
            self._wifi_table.setItem(i, 3, QTableWidgetItem(net["auth"]))
            self._wifi_table.setItem(i, 4, QTableWidgetItem(net["bssid"]))

        self._wifi_count_lbl.setText(t("pygate.wifi_networks", count=len(networks)))
        suggestion = suggest_channel(networks)
        self._wifi_channel_lbl.setText(
            t("pygate.wifi_best_channel", ch2g=suggestion["channel_2g"], ch5g=suggestion["channel_5g"])
        )
        self._set_status(t("pygate.wifi_networks", count=len(networks)))


def launch():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(sys.argv)
    window = PyGateApp()
    window.show()
    app.exec()
