"""
DNS Araçları - DNS sorgulama, sunucu değiştirme, hosts dosyası.
"""

import subprocess
import socket
import re
from pathlib import Path
from core.BaseModule import Tool, ToolParam

from src.modules.network.common import get_active_adapter

CATEGORY = "dns"
HOSTS_PATH = r"C:\Windows\System32\drivers\etc\hosts"


def get_tools() -> list[Tool]:
    return [
        Tool("dns_lookup", "Domain adından IP adresini çöz.",
             [ToolParam("domain", "Domain adı", "string")],
             "safe", CATEGORY),
        Tool("dns_reverse", "IP adresinden domain adını çöz.",
             [ToolParam("ip_address", "IP adresi", "string")],
             "safe", CATEGORY),
        Tool("change_dns", "DNS sunucusunu değiştir. Preset: google, cloudflare, opendns, quad9, adguard",
             [ToolParam("adapter_name", "Adaptör adı (boş=aktif adaptör)", "string", False, ""),
              ToolParam("primary_dns", "Birincil DNS IP", "string", False, ""),
              ToolParam("secondary_dns", "İkincil DNS IP", "string", False, ""),
              ToolParam("preset", "Hazır DNS: google, cloudflare, opendns, quad9, adguard", "string", False, "")],
             "confirm", CATEGORY),
        Tool("reset_dns", "DNS ayarlarını otomatik (DHCP) moduna döndür.",
             [ToolParam("adapter_name", "Adaptör adı (boş=aktif adaptör)", "string", False, "")],
             "confirm", CATEGORY),

        Tool("dns_bypass_test", "Engelli siteye farklı DNS sunucularıyla erişim dene.",
             [ToolParam("url", "Erişilecek site adresi", "string"),
              ToolParam("auto_switch", "Çalışan DNS'e otomatik geç", "boolean", False, False)],
             "confirm", CATEGORY),
        Tool("flush_dns", "DNS önbelleğini temizle.",
             [], "safe", CATEGORY),
        Tool("show_dns_cache", "DNS önbelleğini göster.",
             [], "safe", CATEGORY),
        Tool("list_hosts", "Hosts dosyasındaki kayıtları listele.",
             [], "safe", CATEGORY),
        Tool("add_host_entry", "Hosts dosyasına kayıt ekle.",
             [ToolParam("ip_address", "IP adresi", "string"),
              ToolParam("domain", "Domain adı", "string")],
             "confirm", CATEGORY),
        Tool("remove_host_entry", "Hosts dosyasından kayıt sil.",
             [ToolParam("domain", "Silinecek domain", "string")],
             "confirm", CATEGORY),

        Tool("dns_propagation_check", "DNS kayıtlarının yayılım durumunu kontrol et.",
             [ToolParam("domain", "Domain adı", "string")],
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


def dns_lookup(domain: str) -> dict:
    try:
        ips = socket.getaddrinfo(domain, None)
        unique_ips = list(set(addr[4][0] for addr in ips))
        return {
            "success": True,
            "data": {"domain": domain, "ip_addresses": unique_ips},
            "message": f"{domain} -> {', '.join(unique_ips)}"
        }
    except socket.gaierror as e:
        return {"success": False, "error": f"DNS çözümleme başarısız: {domain} ({str(e)})"}


def dns_reverse(ip_address: str) -> dict:
    import urllib.request
    import json as json_lib

    hostname = None
    method = ""

    # 1. socket ile dene
    try:
        result = socket.gethostbyaddr(ip_address)
        hostname = result[0]
        method = "PTR"
    except:
        pass

    # 2. nslookup ile dene
    if not hostname:
        try:
            r = _run(f"nslookup {ip_address}", timeout=10)
            match = re.search(r"Name:\s+(.+)", r["stdout"])
            if match:
                hostname = match.group(1).strip()
                method = "nslookup"
        except:
            pass

    # 3. Bulunamazsa ipinfo.io'dan bilgi al
    try:
        response = urllib.request.urlopen(f"https://ipinfo.io/{ip_address}/json", timeout=5)
        geo = json_lib.loads(response.read().decode())
        org = geo.get("org", "-")
        city = geo.get("city", "?")
        country = geo.get("country", "?")
        ipinfo_hostname = geo.get("hostname", "")
        if not hostname and ipinfo_hostname:
            hostname = ipinfo_hostname
            method = "ipinfo"
    except:
        org = "-"
        city = "?"
        country = "?"

    if hostname:
        return {
            "success": True,
            "data": {
                "ip": ip_address,
                "hostname": hostname,
                "method": method,
                "org": org,
                "location": f"{city}, {country}",
            },
            "message": f"{ip_address} → {hostname} ({org})"
        }
    else:
        return {
            "success": True,
            "data": {
                "ip": ip_address,
                "hostname": "-",
                "org": org,
                "location": f"{city}, {country}",
                "note": "PTR kaydı yok ama IP bilgisi mevcut"
            },
            "message": f"{ip_address}: PTR kaydı yok | {org} | {city}, {country}"
        }


DNS_PRESETS = {
    "google": {"primary": "8.8.8.8", "secondary": "8.8.4.4"},
    "cloudflare": {"primary": "1.1.1.1", "secondary": "1.0.0.1"},
    "opendns": {"primary": "208.67.222.222", "secondary": "208.67.220.220"},
    "quad9": {"primary": "9.9.9.9", "secondary": "149.112.112.112"},
    "adguard": {"primary": "94.140.14.14", "secondary": "94.140.15.15"},
    "yandex": {"primary": "77.88.8.8", "secondary": "77.88.8.1"},
}

def change_dns(adapter_name: str = "", primary_dns: str = "", secondary_dns: str = "", preset: str = "") -> dict:
    # Preset varsa IP'leri otomatik doldur
    if preset:
        preset_lower = preset.lower()
        for name, ips in DNS_PRESETS.items():
            if name in preset_lower:
                primary_dns = ips["primary"]
                secondary_dns = ips["secondary"]
                break

    if not primary_dns:
        return {"success": False, "error": "DNS adresi belirtilmedi. Kullanılabilir: google, cloudflare, opendns, quad9, adguard"}

    if not adapter_name:
        r = _run("netsh interface show interface")
        best = None
        for line in r["stdout"].splitlines():
            if "Connected" in line and "Dedicated" in line:
                parts = line.split()
                name = " ".join(parts[3:])
                if any(v in name.lower() for v in ["virtual", "vethernet", "vmware", "hyper-v", "loopback"]):
                    continue
                if not best:
                    best = name
                if "wi-fi" in name.lower() or "wifi" in name.lower():
                    best = name
                    break
        adapter_name = best or ""

    if not adapter_name:
        return {"success": False, "error": "Aktif adaptör bulunamadı"}

    r1 = _run(f'netsh interface ip set dns "{adapter_name}" static {primary_dns}')
    if secondary_dns:
        _run(f'netsh interface ip add dns "{adapter_name}" {secondary_dns} index=2')

    return {
        "success": r1["returncode"] == 0,
        "data": {"adapter": adapter_name, "primary": primary_dns, "secondary": secondary_dns},
        "message": f"DNS değiştirildi: {primary_dns}, {secondary_dns} ({adapter_name})"
    }


def reset_dns(adapter_name: str = "") -> dict:
    if not adapter_name:
        adapter_name = get_active_adapter()
    if not adapter_name:
        return {"success": False, "error": "Aktif adaptör bulunamadı"}

    r = _run(f'netsh interface ip set dns "{adapter_name}" dhcp')
    return {
        "success": r["returncode"] == 0,
        "data": {"adapter": adapter_name},
        "message": f"DNS otomatik moda döndürüldü: {adapter_name}"
    }


def dns_bypass_test(url: str, auto_switch: bool = False) -> dict:
    import urllib.request

    if not url.startswith("http"):
        domain = url.replace("https://", "").replace("http://", "").split("/")[0]
    else:
        domain = url.replace("https://", "").replace("http://", "").split("/")[0]

    test_url = f"https://{domain}"

    DNS_SERVERS = {
        "Mevcut DNS": None,
        "Google": {"primary": "8.8.8.8", "secondary": "8.8.4.4"},
        "Cloudflare": {"primary": "1.1.1.1", "secondary": "1.0.0.1"},
        "Quad9": {"primary": "9.9.9.9", "secondary": "149.112.112.112"},
        "OpenDNS": {"primary": "208.67.222.222", "secondary": "208.67.220.220"},
        "AdGuard": {"primary": "94.140.14.14", "secondary": "94.140.15.15"},
        "Level3": {"primary": "4.2.2.1", "secondary": "4.2.2.2"},
        "Comodo": {"primary": "8.26.56.26", "secondary": "8.20.247.20"},
        "Control D": {"primary": "76.76.2.0", "secondary": "76.76.10.0"},
        "CleanBrowsing": {"primary": "185.228.168.9", "secondary": "185.228.169.9"},
        "Mullvad": {"primary": "194.242.2.2", "secondary": "194.242.2.3"}
    }
    adapter = get_active_adapter()
    if not adapter:
        return {"success": False, "error": "Aktif adaptör bulunamadı"}

    original_dns = _run(f'netsh interface ip show dns "{adapter}"')

    results = []
    working_dns = None
    total = len(DNS_SERVERS)

    print(f"\n  🔍 DNS erişim testi: {domain}")

    for i, (name, dns) in enumerate(DNS_SERVERS.items()):
        pct = int((i + 1) / total * 40)
        bar = "█" * pct + "░" * (40 - pct)
        print(f"\r  [{bar}] {name} deneniyor...              ", end="", flush=True)

        # DNS değiştir (Mevcut hariç)
        if dns:
            _run(f'netsh interface ip set dns "{adapter}" static {dns["primary"]}')
            if dns.get("secondary"):
                _run(f'netsh interface ip add dns "{adapter}" {dns["secondary"]} index=2')
            _run("ipconfig /flushdns")
            import time
            time.sleep(1)

        # Erişim dene
        try:
            req = urllib.request.Request(test_url)
            req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            start = time.time()
            resp = urllib.request.urlopen(req, timeout=8)
            elapsed = round((time.time() - start) * 1000)
            status = resp.getcode()
            accessible = True
        except urllib.request.HTTPError as e:
            elapsed = round((time.time() - start) * 1000)
            status = e.code
            accessible = status < 500  # 403 bile olsa site yanıt veriyor
        except Exception as e:
            elapsed = -1
            status = 0
            accessible = False

        result = {
            "dns_name": name,
            "dns_ip": dns["primary"] if dns else "Mevcut",
            "accessible": accessible,
            "status_code": status,
            "response_ms": elapsed,
        }
        results.append(result)

        if accessible and not working_dns and dns:
            working_dns = {"name": name, "dns": dns}

    # DNS'i geri al (otomatik geçiş istenmemişse veya çalışan yoksa)
    if auto_switch and working_dns:
        dns = working_dns["dns"]
        _run(f'netsh interface ip set dns "{adapter}" static {dns["primary"]}')
        if dns.get("secondary"):
            _run(f'netsh interface ip add dns "{adapter}" {dns["secondary"]} index=2')
        _run("ipconfig /flushdns")
        switched_to = working_dns["name"]
    else:
        # Orijinal DNS'e dön
        _run(f'netsh interface ip set dns "{adapter}" dhcp')
        _run("ipconfig /flushdns")
        switched_to = None

    print(f"\r  [{'█' * 40}] Tamamlandı.                              ")

    accessible_count = sum(1 for r in results if r["accessible"])

    return {
        "success": True,
        "data": {
            "domain": domain,
            "results": results,
            "working_dns": working_dns["name"] if working_dns else None,
            "switched_to": switched_to,
            "accessible_count": accessible_count,
        },
        "message": f"{domain}: {accessible_count}/{total} DNS ile erişilebilir"
                   + (f" | {switched_to} DNS'e geçildi" if switched_to else "")
    }


def flush_dns() -> dict:
    r = _run("ipconfig /flushdns")
    return {"success": True, "message": "DNS önbelleği temizlendi"}


def show_dns_cache() -> dict:
    r = _run("ipconfig /displaydns")
    entries = []
    current = {}
    for line in r["stdout"].splitlines():
        if "Record Name" in line or "Kayıt Adı" in line:
            if current:
                entries.append(current)
            current = {"name": line.split(":", 1)[-1].strip()}
        elif "Record Type" in line or "Kayıt Türü" in line:
            current["type"] = line.split(":", 1)[-1].strip()
        elif ("A (Host)" in line or "Bölüm" in line) and ":" in line:
            val = line.split(":", 1)[-1].strip()
            if re.match(r"\d+\.\d+\.\d+\.\d+", val):
                current["ip"] = val

    if current:
        entries.append(current)

    return {"success": True, "data": entries[:50], "count": len(entries),
            "message": f"DNS önbelleğinde {len(entries)} kayıt"}


def list_hosts() -> dict:
    try:
        content = Path(HOSTS_PATH).read_text(encoding="utf-8", errors="replace")
        entries = []
        for line in content.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                parts = line.split()
                if len(parts) >= 2:
                    entries.append({"ip": parts[0], "domain": parts[1]})

        return {"success": True, "data": entries, "count": len(entries),
                "message": f"Hosts dosyasında {len(entries)} kayıt"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def add_host_entry(ip_address: str, domain: str) -> dict:
    try:
        with open(HOSTS_PATH, "a", encoding="utf-8") as f:
            f.write(f"\n{ip_address}\t{domain}")
        return {"success": True, "message": f"Hosts'a eklendi: {ip_address} -> {domain}"}
    except PermissionError:
        return {"success": False, "error": "Yönetici yetkisi gerekli"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def remove_host_entry(domain: str) -> dict:
    try:
        content = Path(HOSTS_PATH).read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()
        new_lines = [l for l in lines if domain not in l]

        if len(lines) == len(new_lines):
            return {"success": False, "error": f"Kayıt bulunamadı: {domain}"}

        Path(HOSTS_PATH).write_text("\n".join(new_lines), encoding="utf-8")
        removed = len(lines) - len(new_lines)
        return {"success": True, "message": f"{removed} kayıt silindi: {domain}"}
    except PermissionError:
        return {"success": False, "error": "Yönetici yetkisi gerekli"}
    except Exception as e:
        return {"success": False, "error": str(e)}


import subprocess
import re


def dns_propagation_check(domain: str) -> dict:
    dns_servers = {
        "Google": "8.8.8.8",
        "Cloudflare": "1.1.1.1",
        "OpenDNS": "208.67.222.222",
        "Quad9": "9.9.9.9",
    }

    results = []
    for name, server_ip in dns_servers.items():
        try:
            r = subprocess.run(
                f"nslookup {domain} {server_ip}",
                capture_output=True, text=True, shell=True, timeout=10
            )

            all_ips = re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", r.stdout)


            target_ips = [ip for ip in all_ips if ip != server_ip]

            unique_ips = list(set(target_ips))

            results.append({
                "dns_server": name,
                "server_ip": server_ip,
                "resolved_ips": unique_ips
            })

        except Exception as e:
            results.append({"dns_server": name, "server_ip": server_ip, "error": str(e)})

    return {
        "success": True,
        "data": results,
        "message": f"{domain} kontrol edildi."
    }


