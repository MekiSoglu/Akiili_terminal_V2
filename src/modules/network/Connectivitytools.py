"""
Tüm araçlar Windows subprocess komutları kullanır farklı işletim sistemlerine uygun değildir
Kullanım dili cp857 ile türkçedir farklı dillerde hata verebilir
Metotlar Command Injection a açıktır !!
Bağlantı Test Araçları - Ping, traceroute, port tarama, hız testi.
"""

import subprocess
import socket
import time
import re
from core.BaseModule import Tool, ToolParam
from modules.network.Basictools import get_public_ip

import concurrent.futures

CATEGORY = "connectivity"


def get_tools() -> list[Tool]:
    return [
        Tool("ping", "Hedefe ping at.",
             [ToolParam("host", "Hedef IP veya domain", "string"),
              ToolParam("count", "Kaç paket", "number", False, 4)],
             "safe", CATEGORY),
        Tool("traceroute", "Hedefe paket rotasını göster.",
             [ToolParam("host", "Hedef IP veya domain", "string")],
             "safe", CATEGORY),
        Tool("visual_traceroute", "Hedefe giden yolun haritasını çıkar - her atlama noktasının konum bilgisiyle.",
             [ToolParam("host", "Hedef IP veya domain", "string")],
             "safe", CATEGORY),
        Tool("check_port_usage", "Belirli bir portu kullanan uygulamayı bul.",
             [ToolParam("port", "Port numarası", "number")],
             "safe", CATEGORY),
        Tool("list_active_connections", "Aktif ağ bağlantılarını listele.",
             [ToolParam("state", "Filtre: ESTABLISHED, LISTENING, TIME_WAIT", "string", False)],
             "safe", CATEGORY),
        Tool("speed_test", "İnternet hızını ölç (indirme hızı tahmini).",
             [], "safe", CATEGORY),
        Tool("connection_quality_test", "Bağlantı kalitesini ölç (gecikme, paket kaybı, jitter).",
             [ToolParam("host", "Hedef", "string", False, "8.8.8.8"),
              ToolParam("count", "Paket sayısı", "number", False, 20)],
             "safe", CATEGORY),
        Tool("check_website_status", "Web sitesinin erişilebilir olup olmadığını kontrol et.",
             [ToolParam("url", "Site URL'si", "string")],
             "safe", CATEGORY),
        Tool("measure_response_time", "Web sitesinin yanıt süresini ölç.",
             [ToolParam("url", "Site URL'si", "string"),
              ToolParam("count", "Kaç kez ölçüm", "number", False, 3)],
             "safe", CATEGORY),

        Tool("download_speed_test", "Belirli bir URL'den indirme hızını ölç.",
             [ToolParam("url", "İndirilecek dosya URL'si", "string")],
             "safe", CATEGORY),
    ]


def _run(cmd, timeout=30):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True,
                                shell=True, timeout=timeout, encoding="utf-8",
                                errors="replace")
        return {"stdout": result.stdout.strip(), "stderr": result.stderr.strip(),
                "returncode": result.returncode}
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "Zaman aşımı", "returncode": -1}


def ping(host: str, count: int = 4) -> dict:
    r = _run(f"ping -n {count} {host}")
    if r["returncode"] != 0 and "istatistik" not in r["stdout"].lower() and "statistics" not in r["stdout"].lower():
        return {"success": False, "error": f"Ping başarısız: {host}"}

    stats = {}
    for line in r["stdout"].splitlines():
        if "ortalama" in line.lower() or "average" in line.lower():
            nums = re.findall(r"(\d+)ms", line)
            if len(nums) >= 3:
                stats = {"min_ms": int(nums[0]), "max_ms": int(nums[1]), "avg_ms": int(nums[2])}
        if "kayıp" in line.lower() or "lost" in line.lower():
            loss = re.search(r"\((\d+)%", line)
            if loss:
                stats["packet_loss"] = int(loss.group(1))

    return {"success": True, "data": stats, "raw": r["stdout"],
            "message": f"Ping {host}: ortalama {stats.get('avg_ms', '?')}ms, kayıp %{stats.get('packet_loss', '?')}"}


def traceroute(host: str) -> dict:
    r = _run(f"tracert -d -w 2000 {host}", timeout=60)
    hops = []
    for line in r["stdout"].splitlines():
        match = re.search(r"^\s*(\d+)\s+(.+?)\s+(\d+\.\d+\.\d+\.\d+|[*])", line)
        if match:
            hops.append({
                "hop": int(match.group(1)),
                "ip": match.group(3),
                "times": match.group(2).strip(),
            })

    return {"success": True, "data": hops, "count": len(hops),
            "message": f"Traceroute {host}: {len(hops)} atlama"}


def visual_traceroute(host: str) -> dict:

    # 1. Traceroute
    print(f"\n  Rota analizi: {host}")
    print(f"  [{'░' * 40}] 0% - Traceroute...", end="", flush=True)

    r = _run(f"tracert -d -w 2000 {host}", timeout=120)
    hops = []
    for line in r["stdout"].splitlines():
        match = re.search(r"^\s*(\d+)\s+(.+?)\s+(\d+\.\d+\.\d+\.\d+|[*])", line)
        if match:
            ip = match.group(3)
            if ip != "*":
                hops.append({
                    "hop": int(match.group(1)),
                    "ip": ip,
                    "times": match.group(2).strip(),
                })

    print(f"\r  [{'█' * 20}{'░' * 20}] 50% - {len(hops)} atlama, konum sorgulanıyor...    ", flush=True)

    public_ips = [h["ip"] for h in hops
                  if not h["ip"].startswith(("192.168.", "10.", "172.16."))]

    if public_ips:
        geo_result = get_public_ip(ip_addresses=",".join(public_ips))
        geo_map = {}
        if geo_result["success"]:
            geo_data = geo_result["data"]
            if isinstance(geo_data, list):
                for info in geo_data:
                    geo_map[info.get("ip", "")] = info
            elif isinstance(geo_data, dict):
                geo_map[geo_data.get("ip", "")] = geo_data

    for hop in hops:
        ip = hop["ip"]
        if ip.startswith(("192.168.", "10.", "172.16.")):
            hop.update({"city": "Yerel Ağ", "country": "LAN", "org": "-", "loc": "-"})
        elif ip in geo_map:
            info = geo_map[ip]
            hop.update({
                "city": info.get("city", "?"),
                "region": info.get("region", "?"),
                "country": info.get("country", "?"),
                "org": info.get("org", "?"),
                "loc": info.get("loc", "?"),
            })
        else:
            hop.update({"city": "?", "country": "?", "org": "?", "loc": "?"})

    print(f"\r  [{'█' * 40}] 100% - Tamamlandı.                              ")

    countries = list(dict.fromkeys(
        h.get("country", "?") for h in hops if h.get("country") not in ("?", "LAN")
    ))

    return {
        "success": True,
        "data": hops,
        "count": len(hops),
        "countries": countries,
        "message": f"{host}: {len(hops)} atlama, {len(countries)} ülke ({' → '.join(countries)})"
    }



def port_scan(host: str, start_port: int = 1, end_port: int = 1024) -> dict:
    if not host:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                host = s.getsockname()[0]
        except Exception:
            r = _run("ipconfig")
            match = re.search(r"Default Gateway.*?:\s*(\d+\.\d+\.\d+\.\d+)", r["stdout"])
            if match:
                gw = match.group(1)
                prefix = gw.rsplit(".", 1)[0]
                ip_match = re.search(rf"IPv4.*?:\s*({prefix}\.\d+)", r["stdout"])
                if ip_match:
                    host = ip_match.group(1)
            else:
                host = "127.0.0.1"

    # Tekil Port Tarama
    def scan_single_port(target_host, port):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(0.5)  # Her thread için kısa zaman aşımı
                if sock.connect_ex((target_host, port)) == 0:
                    service = ""
                    try:
                        service = socket.getservbyport(port)
                    except OSError:
                        service = "unknown"
                    return {"port": port, "service": service}
        except Exception:
            pass
        return None

    open_ports = []
    start = int(start_port)
    end = int(end_port)

    # Dinamik threat
    worker_count = min(100, end - start + 1)

    # Thread Havuzu ile Paralel Tarama
    with concurrent.futures.ThreadPoolExecutor(max_workers=worker_count) as executor:

        future_to_port = {
            executor.submit(scan_single_port, host, port): port
            for port in range(start, end + 1)
        }

        for future in concurrent.futures.as_completed(future_to_port):
            result = future.result()
            if result:
                open_ports.append(result)

    open_ports.sort(key=lambda x: x["port"])

    return {
        "success": True,
        "data": open_ports,
        "count": len(open_ports),
        "message": f"{host}: {len(open_ports)} açık port ({start}-{end})"
    }


# lokal uygulamalar için uygundur . web sunucusu olarak çalışan bir bilgisyar için optimize edilmelidir O(n^2).
def check_port_usage(port: int) -> dict:
    r = _run(f'netstat -ano | findstr :{int(port)}')
    entries = []
    for line in r["stdout"].splitlines():
        parts = line.split()
        if len(parts) >= 5:
            entries.append({
                "protocol": parts[0],
                "local_address": parts[1],
                "foreign_address": parts[2],
                "state": parts[3],
                "pid": parts[4],
            })

    for entry in entries:
        pid = entry["pid"]
        pr = _run(f'tasklist /FI "PID eq {pid}" /FO CSV /NH')
        if pr["stdout"]:
            entry["process"] = pr["stdout"].split(",")[0].strip('"')

    return {"success": True, "data": entries, "count": len(entries),
            "message": f"Port {port}: {len(entries)} bağlantı"}


def list_active_connections(state: str = None) -> dict:
    cmd = "netstat -ano"
    if state:
        cmd += f' | findstr {state}'
    r = _run(cmd)

    connections = []
    for line in r["stdout"].splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[0] in ("TCP", "UDP"):
            connections.append({
                "protocol": parts[0],
                "local": parts[1],
                "remote": parts[2] if len(parts) > 2 else "",
                "state": parts[3] if parts[0] == "TCP" else "",
                "pid": parts[-1],
            })

    # PID -> uygulama adı eşleşmesi (tek seferde tüm işlemleri al)
    pr = _run('tasklist /FO CSV /NH')
    pid_map = {}
    for line in pr["stdout"].splitlines():
        parts = line.split('","')
        if len(parts) >= 2:
            name = parts[0].strip('"')
            pid = parts[1].strip('"')
            pid_map[pid] = name

    for conn in connections:
        conn["process"] = pid_map.get(conn["pid"], "?")

    return {"success": True, "data": connections[:100], "count": len(connections),
            "message": f"{len(connections)} aktif bağlantı"}
# kullanılan sunucada yavaşlama olabilir . net sonuç vermeyebilir
def speed_test() -> dict:
    import urllib.request
    import time

    test_urls = [
        "https://speed.cloudflare.com/__down?bytes=1048576",
        "http://speedtest.tele2.net/1MB.zip",
        "http://cachefly.cachefly.net/1mb.test",
        "http://ipv4.download.thinkbroadband.com/1MB.zip"
    ]

    last_error = ""

    for url in test_urls:
        try:
            start = time.time()
            with urllib.request.urlopen(url, timeout=10) as response:
                data = response.read()

            elapsed = time.time() - start
            size_mb = len(data) / 1048576
            size_mbits = size_mb * 8

            speed_mbps = round(size_mbits / elapsed, 2)

            return {
                "success": True,
                "data": {
                    "download_mbps": speed_mbps,
                    "elapsed_sec": round(elapsed, 2),
                    "server_used": url.split('/')[2]
                },
                "message": f"İndirme hızı: ~{speed_mbps} Mbps (Sunucu: {url.split('/')[2]})"
            }

        except Exception as e:
            last_error = str(e)
            continue

    return {"success": False, "error": f"Tüm sunucular denendi, başarısız. Son hata: {last_error}"}


def connection_quality_test(host: str = "8.8.8.8", count: int = 20) -> dict:
    r = _run(f"ping -n {int(count)} {host}", timeout=60)
    times = [int(m) for m in re.findall(r"[=<](\d+)ms", r["stdout"])]

    if not times:
        return {"success": False, "error": "Bağlantı yanıtı alınamadı"}

    loss_match = re.search(r"\((\d+)%", r["stdout"])
    packet_loss = int(loss_match.group(1)) if loss_match else 0

    avg_ms = sum(times) / len(times)
    jitter = sum(abs(times[i] - times[i-1]) for i in range(1, len(times))) / (len(times) - 1) if len(times) > 1 else 0

    quality = "Mükemmel" if avg_ms < 20 and packet_loss == 0 else \
              "İyi" if avg_ms < 50 and packet_loss < 2 else \
              "Orta" if avg_ms < 100 else "Kötü"

    return {
        "success": True,
        "data": {
            "avg_ms": round(avg_ms, 1), "min_ms": min(times), "max_ms": max(times),
            "jitter_ms": round(jitter, 1), "packet_loss": packet_loss, "quality": quality,
        },
        "message": f"Bağlantı kalitesi: {quality} (ort: {round(avg_ms)}ms, jitter: {round(jitter)}ms, kayıp: %{packet_loss})"
    }


def check_website_status(url: str) -> dict:
    if not url.startswith("http"):
        url = f"https://{url}"
    try:
        import urllib.request
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        start = time.time()
        resp = urllib.request.urlopen(req, timeout=10)
        elapsed = round(time.time() - start, 2)
        return {
            "success": True,
            "data": {"url": url, "status_code": resp.getcode(), "response_time_sec": elapsed},
            "message": f"{url}: Erişilebilir (HTTP {resp.getcode()}, {elapsed}s)"
        }
    except urllib.request.HTTPError as e:
        return {
            "success": True,
            "data": {"url": url, "status_code": e.code, "response_time_sec": 0,
                     "note": "Site yanıt veriyor ama erişimi kısıtlıyor"},
            "message": f"{url}: Erişilebilir ama kısıtlı (HTTP {e.code})"
        }
    except Exception as e:
        return {
            "success": True,
            "data": {"url": url, "status_code": 0, "error": str(e)},
            "message": f"{url}: Erişilemiyor ({str(e)})"
        }


def measure_response_time(url: str, count: int = 3) -> dict:
    if not url.startswith("http"):
        url = f"https://{url}"
    times = []
    import urllib.request
    for _ in range(int(count)):
        try:
            req = urllib.request.Request(url)
            req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            start = time.time()
            urllib.request.urlopen(req, timeout=10)
            times.append(round((time.time() - start) * 1000))
        except urllib.request.HTTPError as e:
            # 403 vs. ama yanıt süresi ölçülebilir
            times.append(round((time.time() - start) * 1000))
        except Exception:
            times.append(-1)

    valid = [t for t in times if t > 0]
    avg = round(sum(valid) / len(valid)) if valid else -1

    return {
        "success": True,
        "data": {"url": url, "times_ms": times, "avg_ms": avg, "min_ms": min(valid) if valid else -1},
        "message": f"{url}: ortalama {avg}ms ({count} ölçüm)"
    }

def download_speed_test(url: str) -> dict:
    try:
        import urllib.request
        start = time.time()
        data = urllib.request.urlopen(url, timeout=30).read()
        elapsed = time.time() - start
        size_mb = len(data) / 1048576
        speed = round(size_mb * 8 / elapsed, 2)

        return {
            "success": True,
            "data": {"url": url, "size_mb": round(size_mb, 2), "elapsed_sec": round(elapsed, 2),
                     "speed_mbps": speed},
            "message": f"İndirme: {round(size_mb, 2)}MB, {round(elapsed, 1)}s, {speed} Mbps"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}