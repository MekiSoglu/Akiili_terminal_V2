import socket
import subprocess
import re



def _run(cmd, timeout=30):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True,
                                shell=True, timeout=timeout, encoding="cp857",
                                errors="replace")
        return {"stdout": result.stdout.strip(), "stderr": result.stderr.strip(),
                "returncode": result.returncode}
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "Zaman aşımı", "returncode": -1}

def get_active_adapter():
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
    return best or ""



def _resolve_service_tag(hostname, org):
    """Hostname ve org bilgisinden servis/domain adı çıkar."""
    # Org'dan AS numarasını temizle
    clean_org = re.sub(r"AS\d+\s*", "", org).strip() if org else ""

    # Hostname IP ise sadece org döndür
    if not hostname or hostname.replace(".", "").replace("-", "").isdigit():
        return clean_org or "-", ""

    # Hostname'den domain çıkar
    parts = hostname.split(".")
    if len(parts) >= 2:
        domain = ".".join(parts[-2:])
        return domain, clean_org
    else:
        return hostname, clean_org


def _enrich_ip_info(ip):
    """Tek bir IP hakkında zengin bilgi topla: hostname, org, konum, servis etiketi."""
    import urllib.request
    import json as json_lib

    info = {"ip": ip, "hostname": "-", "org": "-", "city": "?", "country": "?", "tag": "-", "provider": "-"}

    # Özel IP kontrolü
    if ip.startswith(("192.168.", "10.", "172.16.", "127.")):
        try:
            info["hostname"] = socket.gethostbyaddr(ip)[0]
        except:
            pass
        info["tag"] = "Yerel Ağ"
        return info

    # Reverse DNS
    try:
        info["hostname"] = socket.gethostbyaddr(ip)[0]
    except:
        pass

    # ipinfo.io
    try:
        resp = urllib.request.urlopen(f"https://ipinfo.io/{ip}/json", timeout=5)
        data = json_lib.loads(resp.read().decode())
        info["org"] = data.get("org", "-")
        info["city"] = data.get("city", "?")
        info["country"] = data.get("country", "?")
        info["region"] = data.get("region", "?")
        info["loc"] = data.get("loc", "?")
        if not info["hostname"] or info["hostname"] == "-":
            info["hostname"] = data.get("hostname", "-")
    except:
        pass

    # Servis etiketi
    tag, provider = _resolve_service_tag(info["hostname"], info["org"])
    info["tag"] = tag
    info["provider"] = provider

    return info


def _enrich_ips_bulk(ip_list):


    """Birden fazla IP'yi toplu zenginleştir."""
    from modules.network.Basictools import get_public_ip

    results = {}
    public_ips = [ip for ip in ip_list if not ip.startswith(("192.168.", "10.", "172.16.", "127."))]
    local_ips = [ip for ip in ip_list if ip.startswith(("192.168.", "10.", "172.16.", "127."))]

    # Yerel IP'ler
    for ip in local_ips:
        info = {"ip": ip, "hostname": "-", "org": "-", "city": "Yerel Ağ", "country": "LAN",
                "tag": "Yerel Ağ", "provider": "-"}
        try:
            info["hostname"] = socket.gethostbyaddr(ip)[0]
        except:
            pass
        results[ip] = info

    # Public IP'ler — toplu sorgu
    if public_ips:
        try:
            geo_result = get_public_ip(ip_addresses=",".join(public_ips[:15]))
            if geo_result.get("success") and isinstance(geo_result.get("data"), list):
                for data in geo_result["data"]:
                    ip = data.get("ip", "")
                    hostname = "-"
                    try:
                        hostname = socket.gethostbyaddr(ip)[0]
                    except:
                        pass

                    org = data.get("org", "-")
                    tag, provider = _resolve_service_tag(hostname, org)

                    results[ip] = {
                        "ip": ip,
                        "hostname": hostname,
                        "org": org,
                        "city": data.get("city", "?"),
                        "country": data.get("country", "?"),
                        "region": data.get("region", "?"),
                        "loc": data.get("loc", "?"),
                        "tag": tag,
                        "provider": provider,
                    }
        except:
            pass

    # Çözümlenemeyenler
    for ip in ip_list:
        if ip not in results:
            results[ip] = {"ip": ip, "hostname": "-", "org": "-", "city": "?",
                           "country": "?", "tag": "-", "provider": "-"}

    return results