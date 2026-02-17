"""
Temel Ağ Araçları - IP bilgileri, adaptör yönetimi, ARP tablosu.
Tüm araçlar Windows subprocess komutları kullanır farklı işletim sistemlerine uygun değildir
Kullanım dili cp857 ile türkçedir farklı dillerde hata verebilir
Metotlar Command Injection a açıktır !!
"""

import socket
import uuid
from core.BaseModule import Tool, ToolParam
from typing import Any
import concurrent.futures
import subprocess
import re

from src.modules.network.common import _enrich_ip_info

CATEGORY = "basic"


def get_tools() -> list[Tool]:
    return [
        Tool("get_network_info", "Tüm ağ bilgilerini göster (IP, MAC, gateway, DNS).",
             [], "safe", CATEGORY),
        Tool("get_public_ip", "Dış IP adresini göster veya belirtilen IP'lerin konum bilgisini getir.",
             [ToolParam("ip_addresses", "Virgülle ayrılmış IP listesi (boş=kendi IP'n)", "string", False, "")],
             "safe", CATEGORY),
        Tool("list_network_adapters", "Ağ adaptörlerini listele (WiFi, Ethernet vs.).",
             [], "safe", CATEGORY),
        Tool("toggle_network_adapter", "Ağ adaptörünü aç veya kapat.",
             [ToolParam("adapter_name", "Adaptör adı", "string"),
              ToolParam("action", "enable veya disable", "string")],
             "confirm", CATEGORY),
        Tool("set_static_ip", "Statik IP adresi ayarla.",
             [ToolParam("adapter_name", "Adaptör adı", "string"),
              ToolParam("ip_address", "IP adresi", "string"),
              ToolParam("subnet_mask", "Alt ağ maskesi", "string", False, "255.255.255.0"),
              ToolParam("gateway", "Varsayılan ağ geçidi", "string", False)],
             "confirm", CATEGORY),
        Tool("set_dhcp", "DHCP moduna geç (otomatik IP al).",
             [ToolParam("adapter_name", "Adaptör adı", "string")],
             "confirm", CATEGORY),
        Tool("subnet_calculator", "Alt ağ hesapla (kaç cihaz alır, ağ adresi vs.).",
             [ToolParam("cidr", "CIDR notasyonu (ör: 192.168.1.0/24)", "string")],
             "safe", CATEGORY),
        Tool("list_arp_table", "ARP tablosunu göster (ağdaki cihaz-MAC eşleşmeleri).",
             [], "safe", CATEGORY),
        Tool("wake_on_lan", "Uzak cihazı ağ üzerinden aç (Wake on LAN).",
             [ToolParam("mac_address", "Hedef MAC adresi", "string")],
             "confirm", CATEGORY),
        Tool("ip_full_info", "Bir IP adresi hakkında tüm bilgileri topla.",
             [ToolParam("ip_address", "IP adresi", "string")],
             "safe", CATEGORY),
        Tool("scan_all_devices",
             "Ağdaki TÜM cihazları detaylı tara: IP, MAC, hostname, üretici, açık portlar, cihaz tipi, ping süresi.",
             [ToolParam("network_range", "Ağ aralığı (ör: 192.168.1)", "string", False)],
             "safe", CATEGORY),
    ]

def _run(cmd, shell=True, timeout=15):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True,
                                shell=shell, timeout=timeout, encoding="cp857",
                                errors="replace")
        return {"stdout": result.stdout.strip(), "stderr": result.stderr.strip(),
                "returncode": result.returncode}
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "Zaman aşımı", "returncode": -1}
    except Exception as e:
        return {"stdout": "", "stderr": str(e), "returncode": -1}

def get_network_info() -> dict:
    r = _run("ipconfig /all")
    if r["returncode"] != 0:
        return {"success": False, "error": r["stderr"]}

    info: dict[str, Any] = {"adapters": []}
    current = None

    for line in r["stdout"].splitlines():
        line = line.rstrip()
        if not line.startswith(" ") and ":" in line and "adapter" in line.lower():
            if current:
                info["adapters"].append(current)
            current = {"name": line.split("adapter")[-1].strip().rstrip(":"), "details": {}}
        elif current and (". :" in line or ". :" in line):
            parts = line.split(":", 1)
            if len(parts) == 2:
                key = parts[0].strip().strip(".")
                val = parts[1].strip()
                current["details"][key] = val

    if current:
        info["adapters"].append(current)

    hostname = socket.gethostname()
    mac = ":".join(f"{uuid.getnode():012x}"[i:i+2] for i in range(0, 12, 2))
    info["hostname"] = hostname
    info["mac_address"] = mac


    return {"success": True, "data": info, "message": f"Ağ bilgileri alındı ({len(info['adapters'])} adaptör)"}


"""
ipinfo.io kullanılıyor .api anakatarı olamadan günlük istek limitleri vardır 
"""
def get_public_ip(ip_addresses: str = "") -> dict:
    import urllib.request
    import json

    def _fetch_ip_info(ip: str = "") -> dict:
        try:
            url = f"https://ipinfo.io/{ip}/json" if ip else "https://ipinfo.io/json"
            response = urllib.request.urlopen(url, timeout=10)
            data = json.loads(response.read().decode())
            return {
                "ip": data.get("ip", "?"),
                "city": data.get("city", "?"),
                "region": data.get("region", "?"),
                "country": data.get("country", "?"),
                "org": data.get("org", "?"),
                "timezone": data.get("timezone", "?"),
                "loc": data.get("loc", "?"),
            }
        except Exception as e:
            return {"ip": ip or "?", "error": str(e)}

    if not ip_addresses:
        info = _fetch_ip_info()
        return {
            "success": True,
            "data": info,
            "message": f"Dış IP: {info.get('ip', '?')} ({info.get('city', '?')}, {info.get('country', '?')})"
        }

    # Birden fazla IP
    ip_list = [ip.strip() for ip in ip_addresses.split(",") if ip.strip()]
    results = []
    for ip in ip_list:
        results.append(_fetch_ip_info(ip))

    return {
        "success": True,
        "data": results,
        "message": f"{len(results)} IP sorgulandı"
    }

def list_network_adapters() -> dict:
    r = _run('netsh interface show interface')
    if r["returncode"] != 0:
        return {"success": False, "error": r["stderr"]}

    adapters = []
    for line in r["stdout"].splitlines()[3:]:
        parts = line.split()
        if len(parts) >= 4:
            adapters.append({
                "admin_state": parts[0],
                "state": parts[1],
                "type": parts[2],
                "name": " ".join(parts[3:]),
            })

    return {"success": True, "data": adapters, "count": len(adapters),
            "message": f"{len(adapters)} ağ adaptörü bulundu"}

def toggle_network_adapter(adapter_name: str, action: str) -> dict:
    if action not in ("enable", "disable"):
        return {"success": False, "error": "action: 'enable' veya 'disable' olmalı"}
    r = _run(f'netsh interface set interface "{adapter_name}" {action}')
    if r["returncode"] != 0:
        return {"success": False, "error": r["stderr"] or "Yönetici yetkisi gerekli olabilir"}
    return {"success": True, "message": f"Adaptör {adapter_name}: {action} yapıldı"}


def set_static_ip(adapter_name: str, ip_address: str,
                  subnet_mask: str = "255.255.255.0", gateway: str = None) -> dict:
    cmd = f'netsh interface ip set address "{adapter_name}" static {ip_address} {subnet_mask}'
    if gateway:
        cmd += f" {gateway}"
    r = _run(cmd)
    if r["returncode"] != 0:
        return {"success": False, "error": r["stderr"] or "Yönetici yetkisi gerekli"}
    return {"success": True, "message": f"Statik IP ayarlandı: {ip_address}"}


def set_dhcp(adapter_name: str) -> dict:
    r = _run(f'netsh interface ip set address "{adapter_name}" dhcp')
    if r["returncode"] != 0:
        return {"success": False, "error": r["stderr"] or "Yönetici yetkisi gerekli"}
    return {"success": True, "message": f"DHCP moduna geçildi: {adapter_name}"}



def subnet_calculator(cidr: str) -> dict:
    try:
        import ipaddress
        network = ipaddress.ip_network(cidr, strict=False)
        return {
            "success": True,
            "data": {
                "network_address": str(network.network_address),
                "broadcast_address": str(network.broadcast_address),
                "subnet_mask": str(network.netmask),
                "total_hosts": network.num_addresses - 2,
                "first_host": str(network.network_address + 1),
                "last_host": str(network.broadcast_address - 1),
                "prefix_length": network.prefixlen,
            },
            "message": f"{cidr}: {network.num_addresses - 2} kullanılabilir adres"
        }
    except Exception as e:
        return {"success": False, "error": f"Geçersiz CIDR: {str(e)}"}


"""
Bilgisayarın son zamanlarda iletişim kurduğu tüm cihazların fiziksel adres defterini çıkarır.
"""
def list_arp_table() -> dict:
    r = _run("arp -a")
    if r["returncode"] != 0:
        return {"success": False, "error": r["stderr"]}

    entries = []
    for line in r["stdout"].splitlines():
        match = re.search(r"(\d+\.\d+\.\d+\.\d+)\s+([0-9a-f-]+)\s+(\w+)", line, re.I)
        if match:
            entries.append({
                "ip": match.group(1),
                "mac": match.group(2),
                "type": match.group(3),
            })

    return {"success": True, "data": entries, "count": len(entries),

            "message": f"ARP tablosu: {len(entries)} kayıt"}

def wake_on_lan(mac_address: str) -> dict:
    try:
        mac_bytes = bytes.fromhex(mac_address.replace(":", "").replace("-", ""))
        magic_packet = b'\xff' * 6 + mac_bytes * 16
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.sendto(magic_packet, ('<broadcast>', 9))
        sock.close()
        return {"success": True, "message": f"Wake-on-LAN paketi gönderildi: {mac_address}"}
    except Exception as e:
        return {"success": False, "error": f"WoL hatası: {str(e)}"}


def ip_full_info(ip_address: str) -> dict:
    info = _enrich_ip_info(ip_address)

    # Ping
    try:
        pr = subprocess.run(f"ping -n 2 {ip_address}", capture_output=True, text=True,
                           shell=True, timeout=10, encoding="cp857", errors="replace")
        avg = re.search(r"[=<](\d+)ms", pr.stdout)
        info["ping_ms"] = int(avg.group(1)) if avg else -1
        info["reachable"] = "unreachable" not in pr.stdout.lower()
    except:
        info["ping_ms"] = -1
        info["reachable"] = False

    try:
        r = subprocess.run("arp -a", capture_output=True, text=True, shell=True,
                          timeout=5, encoding="cp857", errors="replace")
        mac = "-"
        for line in r.stdout.splitlines():
            if ip_address in line:
                match = re.search(r"([0-9a-f-]{17})", line, re.I)
                if match:
                    mac = match.group(1)
        info["mac"] = mac
    except:
        info["mac"] = "-"

    return {
        "success": True,
        "data": info,
        "message": f"{ip_address}: {info.get('tag', '?')} | {info.get('city', '?')}, {info.get('country', '?')} | {'Erişilebilir' if info.get('reachable') else 'Erişilemez'}"
    }

"""
50 thrat aynı anda sorgulama yaptığı router güvenlik duvarına takılabilir !!
"""
def scan_all_devices(network_range: str = None) -> dict:
    import concurrent.futures
    import socket
    import threading

    if not network_range or not re.match(r"\d+\.\d+\.\d+", str(network_range)):
        r = subprocess.run("ipconfig", capture_output=True, text=True,
                           shell=True, timeout=15, encoding="cp857", errors="replace")
        gateway_match = re.search(r"Default Gateway.*?:\s*(\d+\.\d+\.\d+)\.\d+", r.stdout)
        if gateway_match:
            network_range = gateway_match.group(1)
        else:
            ip_match = re.search(r"IPv4.*?:\s*(\d+\.\d+\.\d+)\.\d+", r.stdout)
            if ip_match:
                network_range = ip_match.group(1)
            else:
                return {"success": False, "error": "Ağ aralığı belirlenemedi"}

    print(f"\n Ağ taranıyor: {network_range}.*")

    progress = {"done": 0, "total": 254}
    lock = threading.Lock()

    def _ping(ip):
        subprocess.run(f"ping -n 1 -w 150 {ip}", shell=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        with lock:
            progress["done"] += 1
            pct = int(progress["done"] / progress["total"] * 40)
            bar = "█" * pct + "░" * (40 - pct)
            percent = int(progress["done"] / progress["total"] * 100)
            print(f"\r  [{bar}] {percent}% - Ping tarama...", end="", flush=True)

    ips = [f"{network_range}.{i}" for i in range(1, 255)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        executor.map(_ping, ips)

    print(f"\r  [{'█' * 40}] 100% - Ping tarama tamamlandı.    ")

    arp_result = subprocess.run("arp -a", capture_output=True, text=True,
                                shell=True, timeout=15, encoding="cp857", errors="replace")

    raw_devices = []
    for line in arp_result.stdout.splitlines():
        match = re.search(r"(\d+\.\d+\.\d+\.\d+)\s+([0-9a-f-]+)\s+(\w+)", line, re.I)
        if match:
            ip = match.group(1)
            mac = match.group(2)
            if ip.startswith(network_range) and mac != "ff-ff-ff-ff-ff-ff":
                raw_devices.append({"ip": ip, "mac": mac, "type": match.group(3)})

    devices = []
    total = len(raw_devices)

    for i, dev in enumerate(raw_devices):
        ip = dev["ip"]
        mac = dev["mac"]
        device = {"ip": ip, "mac": mac, "type": dev["type"]}

        pct = int((i + 1) / total * 40) if total > 0 else 40
        bar = "█" * pct + "░" * (40 - pct)
        percent = int((i + 1) / total * 100) if total > 0 else 100
        print(f"\r  [{bar}] {percent}% - Analiz: {ip}...          ", end="", flush=True)

        try:
            device["hostname"] = socket.gethostbyaddr(ip)[0]
        except:
            try:
                nr = subprocess.run(f"nbtstat -A {ip}", capture_output=True, text=True,
                                    shell=True, timeout=3, encoding="cp857", errors="replace")
                nb_match = re.search(r"(\S+)\s+<00>\s+UNIQUE", nr.stdout)
                device["hostname"] = nb_match.group(1) if nb_match else "-"
            except:
                device["hostname"] = "-"

        try:
            pr = subprocess.run(f"ping -n 1 -w 500 {ip}", capture_output=True, text=True,
                                shell=True, timeout=5, encoding="cp857", errors="replace")
            avg = re.search(r"[=<](\d+)ms", pr.stdout)
            device["ping_ms"] = int(avg.group(1)) if avg else -1
            device["active"] = pr.returncode == 0
        except:
            device["ping_ms"] = -1
            device["active"] = False

        # Port tarama
        try:
            open_ports = []
            for port in [80, 443, 22, 23, 8080, 554, 9100, 3389, 5900, 21]:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(0.3)
                if sock.connect_ex((ip, port)) == 0:
                    open_ports.append(port)
                sock.close()
            device["open_ports"] = open_ports

            if 9100 in open_ports:
                device["device_type"] = " Yazıcı"
            elif 554 in open_ports:
                device["device_type"] = " IP Kamera"
            elif ip.endswith(".1"):
                device["device_type"] = " Router/Modem"
            elif 3389 in open_ports:
                device["device_type"] = " Windows PC"
            elif 22 in open_ports:
                device["device_type"] = " Linux/Sunucu"
            elif 5900 in open_ports:
                device["device_type"] = "🖥 VNC Cihaz"
            elif 80 in open_ports or 443 in open_ports:
                device["device_type"] = " Akıllı Cihaz"
            elif 8080 in open_ports:
                device["device_type"] = " Servis/Proxy"
            else:
                device["device_type"] = " Bilinmiyor"
        except:
            device["open_ports"] = []
            device["device_type"] = " Bilinmiyor"

        try:
            mac_prefix = mac[:8].upper()
            KNOWN_VENDORS = {
                "08-26-97": "MitraStar Technology",
                "C4-3D-1A": "Intel Corporation",
                "00-15-5D": "Microsoft (Hyper-V)",
                "0A-00-27": "Oracle VirtualBox",
                "DE-37-69": "Apple (Randomized)",
                "F6-06-71": "Android (Randomized)",
                "66-48-3A": "Android (Randomized)",
            }
            device["vendor"] = KNOWN_VENDORS.get(mac_prefix, "-")
        except:
            device["vendor"] = "-"

        devices.append(device)

    print(f"\r  [{'█' * 40}] 100% - Analiz tamamlandı.              ")

    devices.sort(key=lambda x: (not x.get("active"), x.get("ping_ms", 999)))

    return {
        "success": True,
        "data": devices,
        "count": len(devices),
        "network": f"{network_range}.*",
        "message": f"Ağda {len(devices)} cihaz bulundu ({network_range}.*)"
    }

