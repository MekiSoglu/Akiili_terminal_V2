"""
Ağ İzleme Araçları - Bant genişliği, ağ topolojisi, paylaşılan kaynaklar.
"""
import socket
import subprocess
import re
import time
from core.BaseModule import Tool, ToolParam

from src.modules.network.common import _enrich_ips_bulk

CATEGORY = "monitoring"


def get_tools() -> list[Tool]:
    return [
        Tool("bandwidth_monitor", "Anlık ağ trafiği ve bant genişliği kullanımını göster.",
             [ToolParam("duration_sec", "İzleme süresi (saniye)", "number", False, 5)],
             "safe", CATEGORY),
        Tool("bandwidth_by_process", "Hangi uygulama ne kadar ağ trafiği kullanıyor.",
             [], "safe", CATEGORY),
        Tool("network_topology_map", "Ağ topolojisini haritalandır.",
             [], "safe", CATEGORY),
        Tool("packet_capture", "Ağ paketlerini yakala ve analiz et.",
             [ToolParam("duration_sec", "Yakalama süresi (saniye)", "number", False, 10),
              ToolParam("filter_ip", "IP filtresi", "string", False)],
             "confirm", CATEGORY),
        Tool("netbios_scan", "Ağdaki NetBIOS isimlerini tara.",
             [], "safe", CATEGORY),
        Tool("discover_shared_folders", "Ağdaki paylaşılan klasörleri bul.",
             [ToolParam("target_ip", "Hedef IP (boş=tüm ağ)", "string", False)],
             "safe", CATEGORY),
        Tool("list_routes", "Yönlendirme tablosunu göster.",
             [], "safe", CATEGORY),
        Tool("add_route", "Yönlendirme tablosuna kayıt ekle.",
             [ToolParam("destination", "Hedef ağ", "string"),
              ToolParam("mask", "Alt ağ maskesi", "string"),
              ToolParam("gateway", "Ağ geçidi", "string")],
             "dangerous", CATEGORY),
        Tool("delete_route", "Yönlendirme tablosundan kayıt sil.",
             [ToolParam("destination", "Hedef ağ", "string")],
             "dangerous", CATEGORY),
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


def bandwidth_monitor(duration_sec: int = 5) -> dict:
    import time
    try:
        import psutil
        has_psutil = True
    except ImportError:
        has_psutil = False

    r1 = _run("netstat -e")
    start_bytes = _parse_netstat_bytes(r1["stdout"])

    app_start = {}
    if has_psutil:
        for conn in psutil.net_connections(kind="inet"):
            if conn.pid and conn.pid > 0:
                try:
                    proc = psutil.Process(conn.pid)
                    io = proc.io_counters()
                    if conn.pid not in app_start:
                        app_start[conn.pid] = {
                            "name": proc.name(),
                            "read": io.read_bytes,
                            "write": io.write_bytes,
                        }
                except:
                    pass

    print(f"\n  Ağ trafiği izleniyor ({duration_sec} saniye)...")
    for i in range(duration_sec):
        pct = int((i + 1) / duration_sec * 40)
        bar = "█" * pct + "░" * (40 - pct)
        print(f"\r  [{bar}] {i+1}/{duration_sec}s", end="", flush=True)
        time.sleep(1)

    r2 = _run("netstat -e")
    end_bytes = _parse_netstat_bytes(r2["stdout"])
    elapsed = max(duration_sec, 1)

    sent_bytes = end_bytes["sent"] - start_bytes["sent"]
    recv_bytes = end_bytes["recv"] - start_bytes["recv"]

    conn_r = _run("netstat -no")
    destinations = {}
    for line in conn_r["stdout"].splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[0] == "TCP" and parts[3] == "ESTABLISHED":
            remote = parts[2]
            ip = remote.split(":")[0]
            port = remote.split(":")[-1] if ":" in remote else ""
            if ip in ("0.0.0.0", "127.0.0.1", "::"):
                continue

            port_services = {
                "443": "HTTPS", "80": "HTTP", "53": "DNS",
                "22": "SSH", "3389": "RDP", "8080": "Proxy",
                "5222": "XMPP", "3478": "STUN", "8443": "HTTPS",
            }
            service = port_services.get(port, f"Port {port}")

            if ip not in destinations:
                hostname = ip
                try:
                    hostname = socket.gethostbyaddr(ip)[0]
                except:
                    pass
                destinations[ip] = {"hostname": hostname, "service": service, "count": 0}
            destinations[ip]["count"] += 1

    unresolved = [ip for ip, d in destinations.items()
                  if d["hostname"] == ip and not ip.startswith(("192.168.", "10.", "127."))]

    if unresolved:
        print(f"\r  Hedefler çözümleniyor...                    ", end="", flush=True)
        try:
            enriched = _enrich_ips_bulk(unresolved)
            for ip, info in enriched.items():
                if ip in destinations:
                    destinations[ip]["hostname"] = info.get("hostname", ip)
                    destinations[ip]["tag"] = info.get("tag", "-")
                    destinations[ip]["provider"] = info.get("provider", "-")
                    destinations[ip]["location"] = f"{info.get('city', '?')}, {info.get('country', '?')}"
        except:
            pass

    print(f"\r  [{'█' * 40}] Tamamlandı.                              ")

    top_destinations = sorted(destinations.values(), key=lambda x: x["count"], reverse=True)[:10]

    return {
        "success": True,
        "data": {
            "duration_sec": elapsed,
            "sent_kb_s": round(sent_bytes / 1024 / elapsed, 1),
            "recv_kb_s": round(recv_bytes / 1024 / elapsed, 1),
            "sent_during": _format_bytes(sent_bytes),
            "recv_during": _format_bytes(recv_bytes),
            "sent_total_mb": round(end_bytes["sent"] / 1024 / 1024, 1),
            "recv_total_mb": round(end_bytes["recv"] / 1024 / 1024, 1),
            "destinations": top_destinations,
        },
        "message": f"↑ {round(sent_bytes/1024/elapsed, 1)} KB/s ↓ {round(recv_bytes/1024/elapsed, 1)} KB/s"
    }


def _parse_netstat_bytes(output):
    sent = recv = 0
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] == "Bytes":
            recv = int(parts[1])
            sent = int(parts[2]) if len(parts) > 2 else 0
    return {"sent": sent, "recv": recv}


def _format_bytes(b):
    if b < 1024:
        return f"{b} B"
    elif b < 1024 * 1024:
        return f"{round(b / 1024, 1)} KB"
    else:
        return f"{round(b / 1024 / 1024, 1)} MB"

def _parse_netstat_bytes(output):
    sent = recv = 0
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] == "Bytes":
            recv = int(parts[1])
            sent = int(parts[2]) if len(parts) > 2 else 0
    return {"sent": sent, "recv": recv}


def _format_bytes(b):
    if b < 1024:
        return f"{b} B"
    elif b < 1024 * 1024:
        return f"{round(b/1024, 1)} KB"
    else:
        return f"{round(b/1024/1024, 1)} MB"


def bandwidth_by_process() -> dict:
    try:
        import psutil
        connections = psutil.net_connections(kind="inet")
        proc_data = {}
        for conn in connections:
            if conn.pid:
                try:
                    proc = psutil.Process(conn.pid)
                    name = proc.name()
                    if name not in proc_data:
                        proc_data[name] = {"pid": conn.pid, "connections": 0, "name": name}
                    proc_data[name]["connections"] += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

        result = sorted(proc_data.values(), key=lambda x: x["connections"], reverse=True)
        return {"success": True, "data": result[:20], "count": len(result),
                "message": f"{len(result)} uygulama ağ kullanıyor"}
    except ImportError:
        r = _run('netstat -b -n', timeout=30)
        return {"success": True, "data": {"raw": r["stdout"][:2000]},
                "message": "psutil yüklü değil, ham netstat verisi döndürüldü"}

def network_topology_map() -> dict:
    # ARP tablosu + gateway bilgisi ile basit topoloji
    r = _run("arp -a")
    devices = []
    for line in r["stdout"].splitlines():
        match = re.search(r"(\d+\.\d+\.\d+\.\d+)\s+([0-9a-f-]+)\s+(\w+)", line, re.I)
        if match and match.group(2) != "ff-ff-ff-ff-ff-ff":
            devices.append({"ip": match.group(1), "mac": match.group(2), "type": match.group(3)})

    # Gateway bul
    gw = _run("ipconfig")
    gateway = ""
    match = re.search(r"Default Gateway.*?:\s*(\d+\.\d+\.\d+\.\d+)", gw["stdout"])
    if match:
        gateway = match.group(1)

    # Hostname bul
    import socket
    hostname = socket.gethostname()
    local_ip = ""
    match = re.search(r"IPv4.*?:\s*(\d+\.\d+\.\d+\.\d+)", gw["stdout"])
    if match:
        local_ip = match.group(1)

    topology = {
        "this_device": {"hostname": hostname, "ip": local_ip},
        "gateway": gateway,
        "devices": devices,
        "total_devices": len(devices),
    }

    return {"success": True, "data": topology,
            "message": f"Ağ topolojisi: {len(devices)} cihaz, gateway: {gateway}"}


#bilgisayarının ağ trafiğini saniyeler bazında izleyen ve hangi uygulamanın, hangi IP adresiyle, ne kadar süre boyunca konuştuğunun raporu
def packet_capture(duration_sec: int = 10, filter_ip: str = "") -> dict:
    import time
    try:
        import psutil
        has_psutil = True
    except:
        has_psutil = False

    print(f"\n  📡 Paket yakalama başladı ({duration_sec}s)...")

    if has_psutil:
        start = psutil.net_io_counters()

    all_connections = {}
    for i in range(duration_sec):
        pct = int((i + 1) / duration_sec * 40)
        bar = "█" * pct + "░" * (40 - pct)
        print(f"\r  [{bar}] {i + 1}/{duration_sec}s", end="", flush=True)

        if has_psutil:
            for conn in psutil.net_connections(kind="inet"):
                if conn.raddr and conn.status == "ESTABLISHED":
                    remote_ip = conn.raddr.ip
                    remote_port = conn.raddr.port
                    local_port = conn.laddr.port if conn.laddr else 0

                    if filter_ip and filter_ip not in remote_ip:
                        continue

                    key = f"{remote_ip}:{remote_port}"
                    if key not in all_connections:
                        proc_name = "?"
                        try:
                            proc_name = psutil.Process(conn.pid).name()
                        except:
                            pass
                        all_connections[key] = {
                            "remote_ip": remote_ip,
                            "remote_port": remote_port,
                            "local_port": local_port,
                            "process": proc_name,
                            "pid": conn.pid,
                            "first_seen": i,
                            "last_seen": i,
                            "count": 0,
                        }
                    all_connections[key]["last_seen"] = i
                    all_connections[key]["count"] += 1
        time.sleep(1)

    if has_psutil:
        end = psutil.net_io_counters()
        total_sent = end.bytes_sent - start.bytes_sent
        total_recv = end.bytes_recv - start.bytes_recv
        total_packets_sent = end.packets_sent - start.packets_sent
        total_packets_recv = end.packets_recv - start.packets_recv
    else:
        total_sent = total_recv = total_packets_sent = total_packets_recv = 0

    print(f"\r  [{'█' * 40}] Tamamlandı.                              ")

    connections = sorted(all_connections.values(), key=lambda x: x["count"], reverse=True)

    unique_ips = set(c["remote_ip"] for c in connections)
    unique_processes = set(c["process"] for c in connections)

    return {
        "success": True,
        "data": {
            "duration_sec": duration_sec,
            "total_sent": _format_bytes(total_sent),
            "total_recv": _format_bytes(total_recv),
            "packets_sent": total_packets_sent,
            "packets_recv": total_packets_recv,
            "unique_ips": len(unique_ips),
            "unique_processes": len(unique_processes),
            "connections": connections[:20],
        },
        "message": f"{duration_sec}s: {len(connections)} bağlantı, {len(unique_ips)} hedef, ↑{_format_bytes(total_sent)} ↓{_format_bytes(total_recv)}"
    }


def netbios_scan() -> dict:
    r = _run("nbtstat -n")
    r2 = _run("net view", timeout=15)

    devices = []
    for line in r2["stdout"].splitlines():
        if line.startswith("\\\\"):
            name = line.split()[0].replace("\\", "")
            devices.append({"name": name})

    return {"success": True, "data": devices, "count": len(devices),
            "message": f"NetBIOS tarama: {len(devices)} cihaz bulundu"}


def discover_shared_folders(target_ip: str = None) -> dict:
    if target_ip:
        r = _run(f'net view \\\\{target_ip}', timeout=15)
    else:
        r = _run("net view", timeout=15)

    shares = []
    for line in r["stdout"].splitlines():
        if "Disk" in line or "Print" in line:
            parts = line.split()
            if parts:
                shares.append({"name": parts[0], "type": "Disk" if "Disk" in line else "Print"})

    return {"success": True, "data": shares, "count": len(shares),
            "message": f"{len(shares)} paylaşılan kaynak bulundu"}

# Windows yönlendirme tablosunu  analiz ederek aktif ağ rotalarını listeleyen ve sözlük yapısında döndüren metot.
#ağ sorunlarını teşhis etmek için. Mesela internete çıkamıyorsan
def list_routes() -> dict:
    r = _run("route print")
    routes = []
    in_table = False
    for line in r["stdout"].splitlines():
        if "Network Destination" in line or "Ağ Hedefi" in line:
            in_table = True
            continue
        if in_table:
            parts = line.split()
            if len(parts) >= 4 and re.match(r"\d+\.\d+", parts[0]):
                routes.append({
                    "destination": parts[0], "netmask": parts[1],
                    "gateway": parts[2], "interface": parts[3],
                    "metric": parts[4] if len(parts) > 4 else "",
                })

    return {"success": True, "data": routes, "count": len(routes),
            "message": f"Yönlendirme tablosu: {len(routes)} kayıt"}


def add_route(destination: str, mask: str, gateway: str) -> dict:
    r = _run(f"route add {destination} mask {mask} {gateway}")
    if r["returncode"] != 0:
        return {"success": False, "error": r["stderr"] or "Yönetici yetkisi gerekli"}
    return {"success": True, "message": f"Route eklendi: {destination}/{mask} -> {gateway}"}


def delete_route(destination: str) -> dict:
    r = _run(f"route delete {destination}")
    if r["returncode"] != 0:
        return {"success": False, "error": r["stderr"] or "Route bulunamadı"}
    return {"success": True, "message": f"Route silindi: {destination}"}