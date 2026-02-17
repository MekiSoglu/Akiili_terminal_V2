

import sys
import os
import importlib.util

_this_dir = os.path.dirname(os.path.abspath(__file__))
_src_dir = os.path.dirname(os.path.dirname(_this_dir))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from core.BaseModule import BaseModule, ModuleMetadata, Tool, Subcategory


def _load_tool_module(name):
    path = os.path.join(_this_dir, f"{name}.py")
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod



BasicTools = _load_tool_module("Basictools")
ConnectivityTools = _load_tool_module("Connectivitytools")
WifiTools = _load_tool_module("Wifitools")
DnsTools = _load_tool_module("Dnstools")
SecurityTools = _load_tool_module("Securitytools")
VpnProxyTools = _load_tool_module("Vpnproxytools")
MonitoringTools = _load_tool_module("Monitoringtools")
HttpTools = _load_tool_module("Httptools")

CATEGORY_MODULES = {
    "basic": BasicTools,
    "connectivity": ConnectivityTools,
    "wifi": WifiTools,
    "dns": DnsTools,
    "security": SecurityTools,
    "vpn_proxy": VpnProxyTools,
    "monitoring": MonitoringTools,
    "http_tools": HttpTools,
}





class NetworkOperationsModule(BaseModule):

    @property
    def metadata(self) -> ModuleMetadata:
        return ModuleMetadata(
            name="network_operations",
            description="Ağ işlemleri: bilgi, bağlantı testi, WiFi, DNS, güvenlik, VPN, izleme, HTTP araçları",
            version="1.0.0",
        )

    @property
    def subcategories(self) -> list[Subcategory]:
        return [
            Subcategory("basic", "Temel ağ bilgileri, adaptör yönetimi, IP ayarları, ARP, Wake-on-LAN"),
            Subcategory("connectivity", "Ping, traceroute, port tarama, hız testi, bağlantı kalitesi"),
            Subcategory("wifi", "WiFi ağları listeleme, bağlanma, hotspot, kayıtlı şifreler"),
            Subcategory("dns", "DNS sorgulama, sunucu değiştirme, hosts dosyası yönetimi"),
            Subcategory("security", "Firewall, ARP saldırı tespiti, güvenlik tarama, SSL sertifika"),
            Subcategory("vpn_proxy", "VPN bağlantı yönetimi, proxy ayarları"),
            Subcategory("monitoring", "Bant genişliği izleme, ağ topolojisi, paket yakalama, route yönetimi"),
            Subcategory("http_tools", "HTTP istek, WHOIS, SSL kontrol, site teknoloji tespiti"),
        ]

    @property
    def tools(self) -> list[Tool]:
        """Tüm kategorilerdeki araçları birleştir."""
        all_tools = []
        for module in CATEGORY_MODULES.values():
            all_tools.extend(module.get_tools())
        return all_tools



    KEYWORD_MAP = {
        "scan_all_devices": ["ağ tara", "cihaz tara", "cihaz bul", "ip tara",
                             "ağdaki cihaz", "ağdaki ip", "bilgi topla", "detaylı tara",
                             "scan", "ağı tara", "cihazları listele", "cihazları bul"],
        "get_network_info": ["ağ bilgi", "network info", "ip bilgi", "adaptör bilgi"],
        "get_public_ip": ["dış ip", "public ip", "dış adres", "internet ip"],
        "list_network_adapters": ["adaptör listele", "adaptörler"],
        "list_arp_table": ["arp tablo", "arp göster"],
        "ip_conflict_check": ["ip çakışma", "conflict"],
        "subnet_calculator": ["subnet", "alt ağ hesapla", "cidr"],
        "wake_on_lan": ["wake on lan", "uzaktan aç", "wol"],
        "ip_full_info": ["ip hakkında", "ip bilgi topla"],
    }

    def match_tool_by_keywords(self, user_input: str) -> str | None:
        user_lower = user_input.lower()
        for tool_name, keywords in self.KEYWORD_MAP.items():
            for kw in keywords:
                if kw in user_lower:
                    return tool_name
        return None


    def execute(self, tool_name: str, params: dict) -> dict:
        tool = self.get_tool(tool_name)
        if not tool:
            return {"success": False, "error": f"Araç bulunamadı: {tool_name}"}

        actual_name = tool.name
        category = tool.category

        module = CATEGORY_MODULES.get(category)
        if not module:
            return {"success": False, "error": f"Kategori bulunamadı: {category}"}

        func = getattr(module, actual_name, None)
        if not func or not callable(func):
            return {"success": False, "error": f"Fonksiyon bulunamadı: {actual_name}"}

        try:
            return func(**params)
        except TypeError as e:
            return {"success": False, "error": f"Parametre hatası: {str(e)}"}
        except Exception as e:
            return {"success": False, "error": f"Çalışma hatası: {str(e)}"}



