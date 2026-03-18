from core.dns import get_dns, set_dns, reset_dns, flush_cache, is_dhcp, is_admin
from core.interfaces import list_interfaces, list_active_interfaces
from core.presets import PRESETS
from core.benchmark import ping_dns, benchmark_all
from core.network_info import get_public_ip, get_local_ip, get_hostname
from core.dns_cache import get_dns_cache, get_cache_stats
from core.ipv4 import get_ipv4_config, set_static_ip, set_dhcp
from core.hosts import read_hosts, add_entry, remove_entry, toggle_entry, HOSTS_PATH
from core.portscan import scan_ports, parse_ports, get_local_listeners, PRESETS as PORT_PRESETS
from core.monitor import get_connections
from core.wifi import get_wifi_networks, get_current_wifi, suggest_channel
