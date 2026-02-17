"""
Güvenlik Araçları - Firewall, ARP spoofing tespiti, güvenlik tarama, SSL sertifika.
"""
import os
import subprocess
import socket
import ssl
import re
import time
from datetime import datetime
from core.BaseModule import Tool, ToolParam

CATEGORY = "security"


def get_tools() -> list[Tool]:
    return [
        Tool("firewall_list_rules", "Firewall kurallarını listele.",
             [ToolParam("direction", "in veya out (gelen/giden)", "string", False, "in"),
              ToolParam("filter_name", "Kural adı filtresi", "string", False)],
             "safe", CATEGORY),
        Tool("firewall_block_ip", "Belirli bir IP adresini engelle.",
             [ToolParam("ip_address", "Engellenecek IP", "string"),
              ToolParam("rule_name", "Kural adı", "string", False, "SmartTerminal_Block")],
             "dangerous", CATEGORY),
        Tool("firewall_allow_port", "Belirli bir portu aç.",
             [ToolParam("port", "Port numarası", "number"),
              ToolParam("protocol", "TCP veya UDP", "string", False, "TCP"),
              ToolParam("rule_name", "Kural adı", "string", False, "SmartTerminal_Allow")],
             "dangerous", CATEGORY),
        Tool("firewall_remove_rule", "Firewall kuralını sil.",
             [ToolParam("rule_name", "Silinecek kural adı", "string")],
             "dangerous", CATEGORY),
        Tool("arp_spoof_detect", "ARP spoofing saldırısı tespiti yap.",
             [], "safe", CATEGORY),
        Tool("ssl_certificate_check", "Bir domain'in SSL sertifika bilgilerini göster.",
             [ToolParam("domain", "Domain adı", "string"),
              ToolParam("port", "Port", "number", False, 443)],
             "safe", CATEGORY),
        Tool("security_port_audit",
             "Kapsamlı port güvenlik denetimi: açık portlar, risk analizi, gizli port/backdoor tespiti.",
             [ToolParam("host", "Hedef IP (boş=bu bilgisayar)", "string", False, "")],
             "safe", CATEGORY),

        Tool("detect_rogue_dhcp", "Ağda sahte DHCP sunucusu olup olmadığını kontrol et.",
             [], "safe", CATEGORY),
        Tool("network_security_audit", "Kapsamlı ağ güvenliği denetimi çalıştır.",
             [], "safe", CATEGORY),
        Tool("list_certificates", "Sistemde yüklü SSL sertifikalarını listele.",
             [], "safe", CATEGORY),
        Tool("check_ssl_expiry_bulk", "Birden fazla sitenin sertifika bitiş tarihini kontrol et.",
             [ToolParam("domains", "Virgülle ayrılmış domain listesi", "string")],
             "safe", CATEGORY),
    ]


def _run(cmd, timeout=15):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True,
                                shell=True, timeout=timeout, encoding="utf-8",
                                errors="replace")
        return {"stdout": result.stdout.strip(), "stderr": result.stderr.strip(),
                "returncode": result.returncode}
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "Zaman aşımı", "returncode": -1}


def firewall_list_rules(direction: str = "in", filter_name: str = None) -> dict:
    cmd = f'netsh advfirewall firewall show rule name=all dir={direction}'
    r = _run(cmd, timeout=30)
    if r["returncode"] != 0:
        return {"success": False, "error": r["stderr"] or "Yönetici yetkisi gerekli"}

    rules = []
    current = {}
    for line in r["stdout"].splitlines():
        if "Rule Name:" in line or "Kural Adı:" in line:
            if current:
                rules.append(current)
            current = {"name": line.split(":", 1)[-1].strip()}
        elif "Enabled:" in line or "Etkin:" in line:
            current["enabled"] = line.split(":", 1)[-1].strip()
        elif "Action:" in line or "Eylem:" in line:
            current["action"] = line.split(":", 1)[-1].strip()
        elif "Direction:" in line or "Yön:" in line:
            current["direction"] = line.split(":", 1)[-1].strip()

    if current:
        rules.append(current)

    if filter_name:
        rules = [r for r in rules if filter_name.lower() in r.get("name", "").lower()]

    return {"success": True, "data": rules[:50], "count": len(rules),
            "message": f"{len(rules)} firewall kuralı ({direction})"}


def firewall_block_ip(ip_address: str, rule_name: str = "SmartTerminal_Block") -> dict:
    name = f"{rule_name}_{ip_address.replace('.', '_')}"
    cmd = f'netsh advfirewall firewall add rule name="{name}" dir=in action=block remoteip={ip_address}'
    r = _run(cmd)
    if r["returncode"] != 0:
        return {"success": False, "error": r["stderr"] or "Yönetici yetkisi gerekli"}
    return {"success": True, "message": f"IP engellendi: {ip_address} (kural: {name})"}


def firewall_allow_port(port: int, protocol: str = "TCP", rule_name: str = "SmartTerminal_Allow") -> dict:
    name = f"{rule_name}_{protocol}_{int(port)}"
    cmd = f'netsh advfirewall firewall add rule name="{name}" dir=in action=allow protocol={protocol} localport={int(port)}'
    r = _run(cmd)
    if r["returncode"] != 0:
        return {"success": False, "error": r["stderr"] or "Yönetici yetkisi gerekli"}
    return {"success": True, "message": f"Port açıldı: {port}/{protocol} (kural: {name})"}


def firewall_remove_rule(rule_name: str) -> dict:
    r = _run(f'netsh advfirewall firewall delete rule name="{rule_name}"')
    if r["returncode"] != 0:
        return {"success": False, "error": r["stderr"] or "Kural bulunamadı veya yetki yok"}
    return {"success": True, "message": f"Firewall kuralı silindi: {rule_name}"}


def arp_spoof_detect() -> dict:
    r = _run("arp -a")

    mac_to_ips = {}
    for line in r["stdout"].splitlines():
        match = re.search(r"(\d+\.\d+\.\d+\.\d+)\s+([0-9a-f-]+)\s+(\w+)", line, re.I)
        if match:
            ip = match.group(1)
            mac = match.group(2).lower()
            entry_type = match.group(3)

            # Filtrele: multicast, broadcast, boş, statik
            if mac in ("ff-ff-ff-ff-ff-ff", "---", "00-00-00-00-00-00"):
                continue
            if mac.startswith("01-00-5e"):  # multicast
                continue
            if mac.startswith("33-33"):  # IPv6 multicast
                continue
            if entry_type.lower() == "static":
                continue
            if ip.startswith("224.") or ip.startswith("239.") or ip.startswith("255."):
                continue

            if mac not in mac_to_ips:
                mac_to_ips[mac] = set()
            mac_to_ips[mac].add(ip)

    # Aynı MAC birden fazla IP'de = şüpheli
    suspicious = {}
    for mac, ips in mac_to_ips.items():
        if len(ips) > 1:
            suspicious[mac] = list(ips)

    if suspicious:
        return {
            "success": True,
            "data": {"safe": False, "suspicious": suspicious, "total_devices": len(mac_to_ips)},
            "message": f"!! {len(suspicious)} şüpheli MAC tespit edildi"
        }
    else:
        return {
            "success": True,
            "data": {"safe": True, "suspicious": {}, "total_devices": len(mac_to_ips)},
            "message": f" ARP tablosu güvenli ({len(mac_to_ips)} cihaz tarandı)"
        }


def ssl_certificate_check(domain: str, port: int = 443) -> dict:
    try:
        ctx = ssl.create_default_context()
        with ctx.wrap_socket(socket.socket(), server_hostname=domain) as s:
            s.settimeout(10)
            s.connect((domain, int(port)))
            cert = s.getpeercert()

        not_after = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z")
        not_before = datetime.strptime(cert["notBefore"], "%b %d %H:%M:%S %Y %Z")
        days_left = (not_after - datetime.now()).days

        subject = dict(x[0] for x in cert["subject"])
        issuer = dict(x[0] for x in cert["issuer"])

        return {
            "success": True,
            "data": {
                "domain": domain,
                "issuer": issuer.get("organizationName", "?"),
                "subject": subject.get("commonName", "?"),
                "valid_from": not_before.strftime("%Y-%m-%d"),
                "valid_until": not_after.strftime("%Y-%m-%d"),
                "days_remaining": days_left,
                "serial": cert.get("serialNumber", "?"),
            },
            "message": f"{domain}: Sertifika geçerli, {days_left} gün kaldı"
        }
    except Exception as e:
        return {"success": False, "error": f"SSL kontrol hatası: {str(e)}"}


PORT_SECURITY_DB = {
    21: {"service": "FTP", "risk": "Yüksek", "info": "Şifresiz dosya transferi. SFTP kullanın."},
    22: {"service": "SSH", "risk": "Orta", "info": "Güçlü şifre ve key-based auth kullanın."},
    23: {"service": "Telnet", "risk": "Kritik", "info": "Şifresiz bağlantı. SSH ile değiştirin."},
    25: {"service": "SMTP", "risk": "Yüksek", "info": "Spam relay riski. Sadece lokalde açık olmalı."},
    80: {"service": "HTTP", "risk": "Orta", "info": "Şifresiz web. HTTPS kullanın."},
    135: {"service": "RPC", "risk": "Yüksek", "info": "Windows RPC. İnternete kapalı olmalı. BlueKeep saldırılarına açık."},
    139: {"service": "NetBIOS", "risk": "Yüksek", "info": "Dosya paylaşımı. İnternete kapalı olmalı."},
    443: {"service": "HTTPS", "risk": "Düşük", "info": "Şifreli web trafiği. Güncel tutun."},
    445: {"service": "SMB", "risk": "Kritik", "info": "WannaCry/EternalBlue hedefi. İNTERNETE ASLA AÇIK OLMAMALI."},
    1433: {"service": "MSSQL", "risk": "Kritik", "info": "Veritabanı. İnternete kapalı olmalı."},
    1434: {"service": "MSSQL Browser", "risk": "Yüksek", "info": "SQL keşif servisi. Kapatın."},
    3306: {"service": "MySQL", "risk": "Kritik", "info": "Veritabanı. İnternete kapalı olmalı."},
    3389: {"service": "RDP", "risk": "Kritik", "info": "Uzak masaüstü. Brute-force hedefi. VPN arkasına alın."},
    5432: {"service": "PostgreSQL", "risk": "Kritik", "info": "Veritabanı. İnternete kapalı olmalı."},
    5900: {"service": "VNC", "risk": "Kritik", "info": "Uzak masaüstü. Şifresiz olabilir. VPN arkasına alın."},
    6379: {"service": "Redis", "risk": "Kritik", "info": "Varsayılan şifresiz. İnternete kapalı olmalı."},
    8080: {"service": "HTTP Proxy", "risk": "Orta", "info": "Alternatif web portu. Gereksizse kapatın."},
    8443: {"service": "HTTPS Alt", "risk": "Düşük", "info": "Alternatif HTTPS portu."},
    27017: {"service": "MongoDB", "risk": "Kritik", "info": "Varsayılan şifresiz. İnternete kapalı olmalı."},
}

def security_port_audit(host: str = "") -> dict:
    import concurrent.futures

    is_local_scan = False
    if not host or host in ("localhost", "127.0.0.1"):
        is_local_scan = True
        r = _run("ipconfig")
        match = re.search(r"Default Gateway.*?:\s*(\d+\.\d+\.\d+\.\d+)", r["stdout"])
        if match:
            gw = match.group(1)
            prefix = gw.rsplit(".", 1)[0]
            ip_match = re.search(rf"IPv4.*?:\s*({prefix}\.\d+)", r["stdout"])
            if ip_match:
                host = ip_match.group(1)
        if not host:
            host = "127.0.0.1"
            is_local_scan = True

    print(f"\n Güvenlik port denetimi: {host}")

    # 1. Netstat ile sistem bilinen açık portlar
    print(f"  [{'░' * 40}] Netstat analizi...", end="", flush=True)
    netstat_ports = set()
    netstat_details = {}
    r = _run('netstat -ano | findstr LISTENING')
    for line in r["stdout"].splitlines():
        parts = line.split()
        if len(parts) >= 5:
            match = re.search(r":(\d+)\s", line)
            if match:
                port = int(match.group(1))
                netstat_ports.add(port)
                pid = parts[-1]
                # PID'den uygulama adı
                if pid not in ("0",):
                    pr = _run(f'tasklist /FI "PID eq {pid}" /FO CSV /NH')
                    proc_name = pr["stdout"].split(",")[0].strip('"') if pr["stdout"] else "?"
                else:
                    proc_name = "System"
                netstat_details[port] = {"pid": pid, "process": proc_name}

    print(f"\r  [{'█' * 13}{'░' * 27}] Soket tarama...                ", end="", flush=True)

    # 2. Socket ile gerçek port tarama (1-1024 + bilinen riskli portlar)
    scan_ports = set(range(1, 1025))
    scan_ports.update(PORT_SECURITY_DB.keys())
    scan_ports.update([8443, 8888, 9090, 9100, 27017, 5432, 6379, 11211])
    scan_ports = sorted(scan_ports)

    socket_ports = set()
    scanned = {"count": 0}
    total = len(scan_ports)

    def _scan(port):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.3)
            if sock.connect_ex((host, port)) == 0:
                socket_ports.add(port)
            sock.close()
        except:
            pass
        finally:
            scanned["count"] += 1
            if scanned["count"] % 100 == 0 or scanned["count"] == total:
                pct = 33 + int(scanned["count"] / total * 34)
                bar_filled = int(pct / 100 * 40)
                bar = "█" * bar_filled + "░" * (40 - bar_filled)
                print(f"\r  [{bar}] {pct}% - Soket tarama...          ", end="", flush=True)

    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
        executor.map(_scan, scan_ports)

    # 3. Gizli port tespiti (socket'te var, netstat'ta yok)
    print(f"\r  [{'█' * 28}{'░' * 12}] Gizli port analizi...          ", end="", flush=True)
    hidden_ports = socket_ports - netstat_ports if is_local_scan else set()

    # 4. Tüm açık portları birleştir ve analiz et
    all_open = sorted(socket_ports | (netstat_ports if is_local_scan else set()))

    port_results = []
    critical_count = 0
    high_count = 0

    for port in all_open:
        entry = {"port": port}

        # Servis adı
        try:
            entry["service"] = socket.getservbyport(port)
        except:
            entry["service"] = ""

        if port in PORT_SECURITY_DB:
            sec = PORT_SECURITY_DB[port]
            entry["risk"] = sec["risk"]
            entry["security_info"] = sec["info"]
            if not entry["service"]:
                entry["service"] = sec["service"]
            if sec["risk"] == "Kritik":
                critical_count += 1
            elif sec["risk"] == "Yüksek":
                high_count += 1
        else:
            entry["risk"] = "Bilinmiyor"
            entry["security_info"] = ""

        # Netstat bilgisi
        if port in netstat_details:
            entry["process"] = netstat_details[port]["process"]
            entry["pid"] = netstat_details[port]["pid"]
        else:
            entry["process"] = "-"
            entry["pid"] = "-"

        # Tespit yöntemi
        in_netstat = port in netstat_ports
        in_socket = port in socket_ports
        if in_socket and not in_netstat and is_local_scan:
            entry["detection"] = "!! GİZLİ"
            entry["risk"] = "Kritik"
            entry["security_info"] = "Netstat'ta görünmüyor! Olası backdoor/rootkit."
            critical_count += 1
        elif in_netstat and in_socket:
            entry["detection"] = "Normal"
        elif in_netstat and not in_socket:
            entry["detection"] = "Sadece netstat"
        else:
            entry["detection"] = "Sadece soket"

        port_results.append(entry)

    # Risk özeti
    is_local = host.startswith(("192.168.", "10.", "172.16.", "127."))
    if hidden_ports:
        risk_summary = "!! KRİTİK - Gizli portlar tespit edildi! Sistem tehlikede olabilir."
    elif critical_count > 0 and not is_local:
        risk_summary = "!! KRİTİK - İnternete açık tehlikeli portlar var!"
    elif critical_count > 0:
        risk_summary = "! Kritik portlar açık. İnternete kapalı olduğundan emin olun."
    elif high_count > 0:
        risk_summary = "!️ Yüksek riskli portlar açık. Gereksiz olanları kapatın."
    else:
        risk_summary = " Ciddi risk tespit edilmedi."

    print(f"\r  [{'█' * 40}] 100% - Tamamlandı.                      ")

    return {
        "success": True,
        "data": {
            "ports": port_results,
            "host": host,
            "is_local": is_local,
            "is_local_scan": is_local_scan,
            "critical_count": critical_count,
            "high_count": high_count,
            "hidden_ports": sorted(hidden_ports),
            "netstat_count": len(netstat_ports),
            "socket_count": len(socket_ports),
            "risk_summary": risk_summary,
        },
        "message": f"{host}: {len(port_results)} açık port, {critical_count} kritik, {len(hidden_ports)} gizli"
    }

#Man-in-the-Middle saldırısı için nccap ve  scapy kullanır.

def detect_rogue_dhcp(timeout: int = 5) -> dict:
    """Gerçek DHCP DISCOVER paketi göndererek tüm DHCP sunucularını tespit et."""

    gateway = None
    r = _run("ipconfig /all")
    gw_match = re.search(r"Default Gateway.*?:\s*(\d+\.\d+\.\d+\.\d+)", r["stdout"])
    if gw_match:
        gateway = gw_match.group(1)

    # Scapy ile DHCP keşif
    dhcp_offers = []
    try:
        from scapy.all import (
            Ether, IP, UDP, BOOTP, DHCP,
            srp, conf, get_if_hwaddr, RandInt
        )
        import random

        conf.checkIPsrc = False

        # Aktif adaptörün MAC adresini al
        mac_raw = get_if_hwaddr(conf.iface)

        # DHCP DISCOVER paketi oluştur
        transaction_id = random.randint(1, 0xFFFFFFFF)

        discover = (
                Ether(dst="ff:ff:ff:ff:ff:ff") /
                IP(src="0.0.0.0", dst="255.255.255.255") /
                UDP(sport=68, dport=67) /
                BOOTP(chaddr=bytes.fromhex(mac_raw.replace(":", "")), xid=transaction_id) /
                DHCP(options=[("message-type", "discover"), "end"])
        )

        print(f"\n  DHCP DISCOVER gönderiliyor ({timeout}s dinleme)...")
        print(f"  [{'░' * 40}] Yanıtlar bekleniyor...", end="", flush=True)

        # Gönder ve yanıtları topla
        answered, _ = srp(discover, timeout=timeout, verbose=0, multi=True)

        for sent, received in answered:
            if received.haslayer(DHCP):
                options = {}
                for opt in received[DHCP].options:
                    if isinstance(opt, tuple) and len(opt) >= 2:
                        options[opt[0]] = opt[1]

                if options.get("message-type") in (2, 5):  # OFFER veya ACK
                    server_ip = received[IP].src
                    offered_ip = received[BOOTP].yiaddr
                    server_id = options.get("server_id", server_ip)
                    lease_time = options.get("lease_time", "?")
                    subnet = options.get("subnet_mask", "?")
                    router = options.get("router", "?")
                    dns = options.get("name_server", "?")

                    dhcp_offers.append({
                        "server_ip": str(server_id),
                        "offered_ip": str(offered_ip),
                        "lease_time": str(lease_time),
                        "subnet": str(subnet),
                        "router": str(router),
                        "dns": str(dns),
                        "source_mac": received[Ether].src,
                    })

        print(f"\r  [{'█' * 40}] {len(dhcp_offers)} DHCP sunucu yanıt verdi.          ")

    except ImportError:
        print(f"\r  !️ scapy yüklü değil, pasif moda geçiliyor...                    ")
        return _detect_rogue_dhcp_passive(gateway)
    except Exception as e:
        print(f"\r  !️ Aktif tarama başarısız ({e}), pasif moda geçiliyor...          ")
        return _detect_rogue_dhcp_passive(gateway)

    # Analiz
    suspicious = []
    legitimate = []

    for offer in dhcp_offers:
        server = offer["server_ip"]
        is_gateway = (server == gateway)
        # Gateway aralığında mı kontrol
        if gateway:
            gw_prefix = gateway.rsplit(".", 1)[0]
            is_local_range = server.startswith(gw_prefix)
        else:
            is_local_range = True

        if is_gateway:
            offer["status"] = " Meşru (Gateway)"
            legitimate.append(offer)
        elif not is_local_range:
            offer["status"] = "! Şüpheli (Farklı ağ)"
            suspicious.append(offer)
        else:
            offer["status"] = "!️ Bilinmeyen"
            suspicious.append(offer)

    safe = len(suspicious) == 0

    return {
        "success": True,
        "data": {
            "safe": safe,
            "method": "active",
            "gateway": gateway,
            "total_servers": len(dhcp_offers),
            "legitimate": legitimate,
            "suspicious": suspicious,
            "all_offers": dhcp_offers,
        },
        "message": f"{'! Sahte DHCP tespit edildi!' if suspicious else ' DHCP güvenli'} ({len(dhcp_offers)} sunucu yanıt verdi, gateway: {gateway})"
    }


def _detect_rogue_dhcp_passive(gateway) -> dict:
    """Scapy yoksa pasif DHCP kontrolü."""
    r = _run("ipconfig /all")

    dhcp_servers = {}
    current_adapter = ""
    current_dhcp_enabled = False

    for line in r["stdout"].splitlines():
        if "adapter" in line.lower() or "adaptör" in line.lower():
            current_adapter = line.split(":")[-1].strip() if ":" in line else line.strip()
            current_dhcp_enabled = False
            continue
        if "DHCP" in line and ("Yes" in line or "Evet" in line):
            current_dhcp_enabled = True
        dhcp_match = re.search(r"DHCP Server.*?:\s*(\d+\.\d+\.\d+\.\d+)", line)
        if dhcp_match and current_dhcp_enabled:
            dhcp_servers[current_adapter] = dhcp_match.group(1)

    VIRTUAL_KEYWORDS = ["virtual", "vmware", "virtualbox", "hyper-v", "vethernet", "loopback", "bluetooth"]

    real_dhcp = {}
    virtual_dhcp = {}
    for adapter, server in dhcp_servers.items():
        if any(v in adapter.lower() for v in VIRTUAL_KEYWORDS):
            virtual_dhcp[adapter] = server
        else:
            real_dhcp[adapter] = server

    suspicious = []
    for adapter, server in real_dhcp.items():
        if gateway and server != gateway:
            suspicious.append({
                "server_ip": server,
                "adapter": adapter,
                "expected": gateway,
                "status": "! Gateway ile uyuşmuyor"
            })

    return {
        "success": True,
        "data": {
            "safe": len(suspicious) == 0,
            "method": "passive",
            "gateway": gateway,
            "total_servers": len(real_dhcp),
            "legitimate": [{"server_ip": s, "adapter": a, "status": " Meşru"} for a, s in real_dhcp.items() if
                           s == gateway],
            "suspicious": suspicious,
            "virtual_ignored": virtual_dhcp,
            "note": "Pasif tespit: scapy yükleyerek aktif DHCP tarama yapabilirsiniz."
        },
        "message": f"{'! Şüpheli DHCP!' if suspicious else ' DHCP güvenli'} (Pasif mod, gateway: {gateway})"
    }

def network_security_audit() -> dict:
    """Kapsamlı ağ güvenlik denetimi: port, ARP, DHCP, proxy kontrolü. ! çok detaylı bir tarama işlemi değildir tam peroformans için optimize edilmelidir"""

    print(f"\n  Kapsamlı güvenlik denetimi başlatılıyor...")

    # 1. Port denetimi
    print(f"\r  [{'█' * 10}{'░' * 30}] Port denetimi...              ", end="", flush=True)
    results = {"port_audit": security_port_audit()["data"]}

    # 2. ARP kontrolü
    print(f"\r  [{'█' * 20}{'░' * 20}] ARP kontrolü...               ", end="", flush=True)
    results["arp_spoofing"] = arp_spoof_detect()["data"]

    # 3. DHCP kontrolü
    print(f"\r  [{'█' * 28}{'░' * 12}] DHCP kontrolü...              ", end="", flush=True)
    results["rogue_dhcp"] = detect_rogue_dhcp()["data"]

    # 4. Proxy kontrolü
    print(f"\r  [{'█' * 35}{'░' * 5}] Proxy kontrolü...             ", end="", flush=True)
    try:
        import importlib.util
        _dir = os.path.dirname(os.path.abspath(__file__))
        _spec = importlib.util.spec_from_file_location("VpnProxyTools", os.path.join(_dir, "VpnProxyTools.py"))
        _vp = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_vp)
        results["proxy"] = _vp.proxy_status()["data"]
    except:
        results["proxy"] = {"enabled": False, "error": "Proxy kontrolü yapılamadı"}

    print(f"\r  [{'█' * 40}] Tamamlandı.                              ")

    # 5. Sorunları topla
    issues = []

    # Port sorunları
    if results["port_audit"].get("critical_count", 0) > 0:
        critical_ports = [p for p in results["port_audit"].get("ports", []) if p.get("risk") == "Kritik"]
        port_names = ", ".join(f"{p['port']}/{p.get('service', '?')}" for p in critical_ports)
        issues.append(f"{results['port_audit']['critical_count']} kritik port açık ({port_names})")

    if results["port_audit"].get("hidden_ports"):
        hidden = results["port_audit"]["hidden_ports"]
        issues.append(f"{len(hidden)} gizli port tespit edildi ({', '.join(str(p) for p in hidden)})!")

    if results["port_audit"].get("high_count", 0) > 0:
        high_ports = [p for p in results["port_audit"].get("ports", []) if p.get("risk") == "Yüksek"]
        port_names = ", ".join(f"{p['port']}/{p.get('service', '?')}" for p in high_ports)
        issues.append(f"{results['port_audit']['high_count']} yüksek riskli port açık ({port_names})")

    # ARP sorunları
    if not results["arp_spoofing"].get("safe", True):
        suspicious = results["arp_spoofing"].get("suspicious", {})
        issues.append(f"ARP spoofing şüphesi ({len(suspicious)} şüpheli MAC)")

    # DHCP sorunları
    if not results["rogue_dhcp"].get("safe", True):
        suspicious = results["rogue_dhcp"].get("suspicious", [])
        rogue_ips = ", ".join(s.get("server_ip", "?") for s in suspicious)
        issues.append(f"Sahte DHCP sunucusu tespit edildi ({rogue_ips})")

    # Proxy sorunları
    if results["proxy"].get("enabled", False):
        proxy_addr = results["proxy"].get("proxy_address", "?")
        issues.append(f"Proxy aktif ({proxy_addr}) — Adware/casus yazılım olabilir!")

    # 6. Skor hesapla
    has_hidden = bool(results["port_audit"].get("hidden_ports"))
    has_proxy = results["proxy"].get("enabled", False)
    has_rogue = not results["rogue_dhcp"].get("safe", True)

    if has_hidden or (has_proxy and has_rogue):
        score = "KRİTİK"
    elif issues:
        score = "RİSKLİ"
    else:
        score = "İYİ"

    return {
        "success": True,
        "data": {"results": results, "issues": issues, "score": score},
        "message": f"Güvenlik skoru: {score}" + (f" — {', '.join(issues)}" if issues else "")
    }

def list_certificates() -> dict:
    r = _run('certutil -store -user My', timeout=30)
    certs = []
    current = {}
    for line in r["stdout"].splitlines():
        if "Subject:" in line:
            if current:
                certs.append(current)
            current = {"subject": line.split(":", 1)[-1].strip()}
        elif "NotAfter:" in line:
            current["expires"] = line.split(":", 1)[-1].strip()
        elif "Serial Number:" in line:
            current["serial"] = line.split(":", 1)[-1].strip()

    if current:
        certs.append(current)

    return {"success": True, "data": certs, "count": len(certs),
            "message": f"{len(certs)} sertifika yüklü"}


def check_ssl_expiry_bulk(domains: str) -> dict:
    domain_list = [d.strip() for d in domains.split(",")]
    results = []
    for domain in domain_list:
        r = ssl_certificate_check(domain)
        if r["success"]:
            results.append(r["data"])
        else:
            results.append({"domain": domain, "error": r["error"], "days_remaining": -1})

    results.sort(key=lambda x: x.get("days_remaining", 999))

    return {"success": True, "data": results, "count": len(results),
            "message": f"{len(results)} site kontrol edildi"}