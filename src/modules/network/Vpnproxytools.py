"""
VPN ve Proxy Araçları - VPN bağlantı yönetimi, proxy ayarları.
"""

import subprocess
import re
from core.BaseModule import Tool, ToolParam

from src.modules.network.common import get_active_adapter

CATEGORY = "vpn_proxy"

PRESET_DNS = {
    "google": ("8.8.8.8", "8.8.4.4"),
    "cloudflare": ("1.1.1.1", "1.0.0.1"),
    "opendns": ("208.67.222.222", "208.67.220.220"),
    "quad9": ("9.9.9.9", "149.112.112.112"),
}


def get_tools() -> list[Tool]:
    return [
        Tool("vpn_create", "Ücretsiz VPN bağlantısı oluştur. VPN Gate'den sunucu listesi alır.",
             [ToolParam("name", "VPN bağlantı adı (boş=kullanıcıya sor)", "string", False, ""),
              ToolParam("country", "Ülke filtresi: Japan, Korea, US vb. (boş=liste göster)", "string", False, "")],
             "confirm", CATEGORY),
        Tool("vpn_status", "VPN bağlantı durumunu göster.",
             [], "safe", CATEGORY),
             Tool("vpn_connect", "Kayıtlı VPN profiline bağlan.",
             [ToolParam("profile_name", "VPN profil adı", "string")],
             "confirm", CATEGORY),
        Tool("vpn_disconnect", "VPN bağlantısını kes.",
             [ToolParam("profile_name", "VPN profil adı (boş=tümü)", "string", False, "")],
             "safe", CATEGORY),
        Tool("vpn_list_profiles", "Kayıtlı VPN profillerini listele.",
             [], "safe", CATEGORY),
        Tool("proxy_status", "Mevcut proxy ayarlarını göster.",
             [], "safe", CATEGORY),
        Tool("proxy_set", "Sistem proxy ayarlarını yapılandır.",
             [ToolParam("proxy_address", "Proxy adresi (ör: 192.168.1.1:8080)", "string")],
             "confirm", CATEGORY),
        Tool("proxy_remove", "Proxy ayarlarını kaldır.",
             [], "confirm", CATEGORY),
        Tool("proxy_test", "Proxy bağlantısını test et.",
             [ToolParam("proxy_address", "Proxy adresi", "string"),
              ToolParam("test_url", "Test edilecek URL", "string", False, "https://httpbin.org/ip")],
             "safe", CATEGORY),

        Tool("stealth_mode_on", "Gizli mod aç: VPN, MAC spoofing, DNS şifreleme, kill switch, telemetri durdurma.",
             [ToolParam("country", "VPN ülkesi (boş=Japan)", "string", False, "")],
             "dangerous", CATEGORY),
        Tool("stealth_mode_off", "Gizli modu kapat, tüm ayarları geri yükle, izleri temizle.",
             [], "dangerous", CATEGORY),
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

def vpn_create(name: str = "", country: str = "") -> dict:
    """VPN Gate + ipspeed.info'dan ücretsiz VPN sunucu listesi alıp L2TP bağlantısı oluştur."""
    import urllib.request
    import csv
    import io

    print(f"\n  🔍 VPN sunucuları aranıyor...")
    servers = []

    # Kaynak 1: VPN Gate CSV API
    try:
        req = urllib.request.Request("https://www.vpngate.net/api/iphone/")
        req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
        response = urllib.request.urlopen(req, timeout=15)
        raw = response.read().decode("utf-8")

        lines = raw.splitlines()
        header_idx = -1
        for i, line in enumerate(lines):
            if "#HostName" in line:
                header_idx = i
                break

        if header_idx >= 0:
            header = lines[header_idx].lstrip("#")
            data_lines = [header]
            for line in lines[header_idx + 1:]:
                if line.startswith("*") or not line.strip():
                    continue
                data_lines.append(line)

            reader = csv.DictReader(io.StringIO("\n".join(data_lines)))
            for row in reader:
                try:
                    server_ip = row.get("IP", "")
                    if not server_ip:
                        continue
                    speed_raw = int(row.get("Speed", 0) or 0)
                    uptime_raw = int(row.get("Uptime", 0) or 0)
                    ping_raw = row.get("Ping", "-") or "-"
                    try:
                        ping_val = int(ping_raw)
                    except:
                        ping_val = 999

                    servers.append({
                        "hostname": row.get("HostName", ""),
                        "ip": server_ip,
                        "score": int(row.get("Score", 0) or 0),
                        "ping": ping_raw,
                        "ping_val": ping_val,
                        "speed": speed_raw,
                        "speed_mbps": round(speed_raw / 1_000_000, 1),
                        "country": row.get("CountryLong", "?"),
                        "country_code": row.get("CountryShort", "?"),
                        "sessions": row.get("NumVpnSessions", "0"),
                        "uptime": str(uptime_raw),
                        "uptime_hours": round(uptime_raw / 3_600_000, 1),
                        "operator": row.get("Operator", ""),
                        "source": "VPN Gate",
                    })
                except:
                    continue
        print(f"     VPN Gate: {len(servers)} sunucu")
    except Exception as e:
        print(f"     VPN Gate: Hata ({e})")

    # Kaynak 2: ipspeed.info
    ipspeed_count = 0
    try:
        req2 = urllib.request.Request("https://ipspeed.info/free-l2tpipsec.php")
        req2.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
        resp2 = urllib.request.urlopen(req2, timeout=15)
        html = resp2.read().decode("utf-8")

        rows = re.findall(
            r"<tr>\s*<td[^>]*>\s*(\d+)\s*</td>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>([\d.]+)</td>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>",
            html, re.DOTALL
        )
        existing_ips = set(s["ip"] for s in servers)
        for row in rows:
            num, raw_country, ip, uptime, ping = row
            ip = ip.strip()
            if ip in existing_ips:
                continue
            c = re.sub(r"<[^>]+>", "", raw_country).strip()
            p = re.sub(r"[^\d]", "", ping) or "-"
            try:
                ping_val = int(p)
            except:
                ping_val = 999

            servers.append({
                "hostname": ip,
                "ip": ip,
                "score": 0,
                "ping": p,
                "ping_val": ping_val,
                "speed": 0,
                "speed_mbps": 0,
                "country": c,
                "country_code": c[:2].upper(),
                "sessions": "?",
                "uptime": re.sub(r"<[^>]+>", "", uptime).strip(),
                "uptime_hours": 0,
                "operator": "",
                "source": "ipspeed.info",
            })
            ipspeed_count += 1
        print(f"     ipspeed.info: {ipspeed_count} sunucu")
    except Exception as e:
        print(f"     ipspeed.info: Hata ({e})")

    if not servers:
        return {"success": False, "error": "Hiç sunucu bulunamadı"}

    # Ülke gruplama
    countries = {}
    for s in servers:
        c = s["country"]
        if c not in countries:
            countries[c] = {"count": 0, "best_speed": 0, "best_ping": 999, "code": s["country_code"]}
        countries[c]["count"] += 1
        if s["speed_mbps"] > countries[c]["best_speed"]:
            countries[c]["best_speed"] = s["speed_mbps"]
        if s["ping_val"] < countries[c]["best_ping"]:
            countries[c]["best_ping"] = s["ping_val"]

    sorted_countries = sorted(countries.items(), key=lambda x: x[1]["count"], reverse=True)

    # Ülke seçimi
    if not country:
        print(f"\n  🌍 {len(sorted_countries)} ülkede {len(servers)} sunucu bulundu:")
        print(f"    {'#':<4} {'Ülke':<25} {'Kod':<6} {'Sunucu':<10} {'En Hızlı':<14} {'En İyi Ping'}")
        print(f"    {'-'*70}")
        for i, (name_c, info) in enumerate(sorted_countries, 1):
            ping_txt = f"{info['best_ping']}ms" if info['best_ping'] < 999 else "-"
            print(f"    {i:<4} {name_c:<25} {info['code']:<6} {info['count']:<10} {info['best_speed']} Mb/s{'':<4} {ping_txt}")

        try:
            choice = input(f"\n  Ülke numarası seçin (1-{len(sorted_countries)}): ").strip()
            idx = int(choice) - 1
            if idx < 0 or idx >= len(sorted_countries):
                return {"success": False, "error": "Geçersiz seçim"}
            country = sorted_countries[idx][0]
        except (ValueError, EOFError):
            return {"success": False, "error": "Geçersiz giriş"}

    # Ülke filtrele
    country_lower = country.lower()
    filtered = [s for s in servers if country_lower in s["country"].lower()
                or country_lower in s["country_code"].lower()]

    if not filtered:
        return {"success": False, "error": f"'{country}' için sunucu bulunamadı"}

    # En iyiden en kötüye sırala: hız yüksek + ping düşük
    filtered.sort(key=lambda x: (-x["speed_mbps"], x["ping_val"]))

    # VPN adı
    if not name:
        name = input("  VPN bağlantı adı (boş=otomatik): ").strip()
    if not name:
        code = filtered[0]["country_code"]
        name = f"VPNGate-{code}"

    # VPN oluştur
    first_ip = filtered[0]["ip"]
    print(f"\n  ⚙️ VPN oluşturuluyor: {name}")

    _run(f'powershell -Command "Remove-VpnConnection -Name \'{name}\' -Force -ErrorAction SilentlyContinue"')

    cmd = (
        f'powershell -Command "'
        f"Add-VpnConnection "
        f"-Name '{name}' "
        f"-ServerAddress '{first_ip}' "
        f"-TunnelType 'L2tp' "
        f"-L2tpPsk 'vpn' "
        f"-AuthenticationMethod 'Pap' "
        f"-EncryptionLevel 'Optional' "
        f"-RememberCredential "
        f'-Force"'
    )
    r = _run(cmd, timeout=15)

    if r["returncode"] != 0:
        return {"success": False, "error": f"VPN oluşturulamadı: {r['stderr']}"}

    # Sunucuları sırayla dene
    connected = False
    selected = None
    tried = 0
    max_try = min(len(filtered), 10)

    print(f"\n  📡 {country} — {max_try} sunucu denenecek (en hızlıdan yavaşa):")
    print(f"    {'#':<4} {'IP Adresi':<18} {'Hız':<12} {'Ping':<8} {'Durum'}")
    print(f"    {'-'*55}")

    for i, srv in enumerate(filtered[:max_try]):
        tried += 1

        if i > 0:
            _run(f'powershell -Command "Set-VpnConnection -Name \'{name}\' -ServerAddress \'{srv["ip"]}\' -Force"')

        rc = _run(f'rasdial "{name}" vpn vpn', timeout=15)
        connected = rc["returncode"] == 0

        speed_txt = f"{srv['speed_mbps']} Mb/s" if srv['speed_mbps'] > 0 else "-"
        ping_txt = f"{srv['ping']}ms" if srv['ping'] != "-" else "-"

        if connected:
            print(f"    ✅ {i+1:<2} {srv['ip']:<18} {speed_txt:<12} {ping_txt:<8} Bağlandı!")
            selected = srv
            break
        else:
            print(f"    ❌ {i+1:<2} {srv['ip']:<18} {speed_txt:<12} {ping_txt:<8} Başarısız")
            _run(f'rasdial "{name}" /disconnect', timeout=3)

    if not connected:
        _run(f'rasdial "{name}" /disconnect', timeout=3)
        _run(f'powershell -Command "Remove-VpnConnection -Name \'{name}\' -Force -ErrorAction SilentlyContinue"')

        return {
            "success": True,
            "data": {
                "name": name,
                "country": country,
                "connected": False,
                "tried_count": tried,
            },
            "message": f"⚠️ {country} — {tried} sunucu denendi, bağlanılamadı."
        }

    return {
        "success": True,
        "data": {
            "name": name,
            "server": selected,
            "credentials": {"username": "vpn", "password": "vpn", "psk": "vpn"},
            "connected": True,
            "tried_count": tried,
        },
        "message": f"✅ VPN '{name}' bağlandı! ({selected['ip']}, {country}) — {tried}. denemede"
    }


def vpn_status() -> dict:
    r = _run("rasdial")
    if "bağlantı yok" in r["stdout"].lower() or "no connections" in r["stdout"].lower():
        return {"success": True, "data": {"connected": False}, "message": "VPN bağlantısı yok"}

    connections = [l.strip() for l in r["stdout"].splitlines() if l.strip() and ":" not in l.lower()]
    return {
        "success": True,
        "data": {"connected": True, "profiles": connections},
        "message": f"Aktif VPN: {', '.join(connections)}"
    }


def vpn_connect(profile_name: str) -> dict:
    r = _run(f'rasdial "{profile_name}"', timeout=30)
    if r["returncode"] == 0:
        return {"success": True, "message": f"VPN bağlandı: {profile_name}"}
    return {"success": False, "error": r["stderr"] or r["stdout"] or "Bağlantı başarısız"}


def vpn_disconnect(profile_name: str = "") -> dict:
    if profile_name:
        r = _run(f'rasdial "{profile_name}" /disconnect')
    else:
        r = _run("rasdial /disconnect")
    return {"success": True, "message": "VPN bağlantısı kesildi"}


def vpn_list_profiles() -> dict:
    r = _run('rasphone -h')
    # Alternatif: PowerShell ile
    r2 = _run('powershell "Get-VpnConnection | Select-Object Name,ServerAddress,TunnelType | ConvertTo-Json"')

    profiles = []
    if r2["stdout"] and r2["stdout"].startswith("["):
        import json
        try:
            profiles = json.loads(r2["stdout"])
            if isinstance(profiles, dict):
                profiles = [profiles]
        except Exception:
            pass
    elif r2["stdout"] and r2["stdout"].startswith("{"):
        import json
        try:
            profiles = [json.loads(r2["stdout"])]
        except Exception:
            pass

    if not profiles:
        # rasphone çıktısından parse et
        r3 = _run("rasphone -h")
        return {"success": True, "data": [], "count": 0,
                "message": "Kayıtlı VPN profili bulunamadı"}

    return {"success": True, "data": profiles, "count": len(profiles),
            "message": f"{len(profiles)} VPN profili kayıtlı"}


def proxy_status() -> dict:
    r = _run('reg query "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings" /v ProxyEnable')
    enabled = "0x1" in r["stdout"]

    proxy_addr = ""
    if enabled:
        r2 = _run('reg query "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings" /v ProxyServer')
        match = re.search(r"ProxyServer\s+REG_SZ\s+(.+)", r2["stdout"])
        if match:
            proxy_addr = match.group(1).strip()

    return {
        "success": True,
        "data": {"enabled": enabled, "proxy_address": proxy_addr},
        "message": f"Proxy: {'Aktif -> ' + proxy_addr if enabled else 'Devre dışı'}"
    }


def proxy_set(proxy_address: str) -> dict:
    _run(f'reg add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings" /v ProxyEnable /t REG_DWORD /d 1 /f')
    r = _run(f'reg add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings" /v ProxyServer /t REG_SZ /d "{proxy_address}" /f')
    if r["returncode"] != 0:
        return {"success": False, "error": "Proxy ayarlanamadı"}
    return {"success": True, "message": f"Proxy ayarlandı: {proxy_address}"}


def proxy_remove() -> dict:
    _run('reg add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings" /v ProxyEnable /t REG_DWORD /d 0 /f')
    return {"success": True, "message": "Proxy kaldırıldı"}


def proxy_test(proxy_address: str, test_url: str = "https://httpbin.org/ip") -> dict:
    try:
        import urllib.request
        proxy_handler = urllib.request.ProxyHandler({
            "http": f"http://{proxy_address}",
            "https": f"http://{proxy_address}",
        })
        opener = urllib.request.build_opener(proxy_handler)
        import time
        start = time.time()
        response = opener.open(test_url, timeout=10)
        elapsed = round(time.time() - start, 2)
        data = response.read().decode()

        return {
            "success": True,
            "data": {"proxy": proxy_address, "response_time": elapsed, "response": data[:200]},
            "message": f"Proxy çalışıyor: {proxy_address} ({elapsed}s)"
        }
    except Exception as e:
        return {"success": False, "error": f"Proxy test başarısız: {str(e)}"}


import json
import random
import string
import os

STEALTH_STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".stealth_state.json")


def _save_stealth_state(state):
    with open(STEALTH_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def _load_stealth_state():
    try:
        with open(STEALTH_STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return None


def _random_mac():
    """Rastgele MAC adresi üret (ilk byte çift olmalı — unicast)."""
    first = random.randint(0, 255) & 0xFE  # Çift yap
    rest = [random.randint(0, 255) for _ in range(5)]
    return "-".join(f"{b:02X}" for b in [first] + rest)


def _random_hostname():
    """Rastgele bilgisayar adı üret."""
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"PC-{suffix}"
