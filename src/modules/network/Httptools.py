"""
HTTP/API Test Araçları - HTTP istek, site durum, WHOIS, SSL kontrol.
"""

import subprocess
import socket
import ssl
import time
import re
import json as json_lib
from datetime import datetime
from core.BaseModule import Tool, ToolParam

CATEGORY = "http_tools"


def get_tools() -> list[Tool]:
    return [
        Tool("http_request", "HTTP isteği gönder (GET/POST).",
             [ToolParam("url", "URL adresi", "string"),
              ToolParam("method", "GET veya POST", "string", False, "GET"),
              ToolParam("headers", "Ek header'lar (JSON formatında)", "string", False, ""),
              ToolParam("body", "İstek gövdesi (POST için)", "string", False, "")],
             "safe", CATEGORY),
        Tool("whois_lookup", "Domain WHOIS bilgilerini sorgula.",
             [ToolParam("domain", "Domain adı", "string")],
             "safe", CATEGORY),
        Tool("http_headers", "Bir sitenin HTTP yanıt başlıklarını göster.",
             [ToolParam("url", "URL adresi", "string")],
             "safe", CATEGORY),
        Tool("check_website_technologies", "Web sitesinin kullandığı teknolojileri tespit et.",
             [ToolParam("url", "Site URL'si", "string")],
             "safe", CATEGORY),
    ]


def http_request(url: str, method: str = "GET", headers: str = "", body: str = "") -> dict:
    if not url.startswith("http"):
        url = f"https://{url}"

    try:
        import urllib.request
        req = urllib.request.Request(url, method=method.upper())

        if headers:
            try:
                h = json_lib.loads(headers)
                for k, v in h.items():
                    req.add_header(k, v)
            except Exception:
                pass

        if body and method.upper() == "POST":
            req.data = body.encode("utf-8")

        start = time.time()
        resp = urllib.request.urlopen(req, timeout=15)
        elapsed = round(time.time() - start, 2)
        content = resp.read().decode("utf-8", errors="replace")

        return {
            "success": True,
            "data": {
                "status_code": resp.getcode(),
                "response_time": elapsed,
                "content_length": len(content),
                "headers": dict(resp.headers),
                "body_preview": content[:500],
            },
            "message": f"{method} {url}: HTTP {resp.getcode()} ({elapsed}s, {len(content)} bytes)"
        }
    except Exception as e:
        return {"success": False, "error": f"HTTP hatası: {str(e)}"}


def whois_lookup(domain: str) -> dict:
    try:
        import urllib.request
        response = urllib.request.urlopen(f"https://rdap.org/domain/{domain}", timeout=10)
        data = json_lib.loads(response.read().decode())

        info = {
            "domain": domain,
            "status": data.get("status", []),
            "nameservers": [ns.get("ldhName", "") for ns in data.get("nameservers", [])],
        }

        for event in data.get("events", []):
            if event.get("eventAction") == "registration":
                info["registered"] = event.get("eventDate", "?")[:10]
            elif event.get("eventAction") == "expiration":
                info["expires"] = event.get("eventDate", "?")[:10]
            elif event.get("eventAction") == "last changed":
                info["updated"] = event.get("eventDate", "?")[:10]

        for entity in data.get("entities", []):
            roles = entity.get("roles", [])
            if "registrar" in roles:
                vcards = entity.get("vcardArray", [None, []])
                for vcard in vcards[1] if len(vcards) > 1 else []:
                    if vcard[0] == "fn":
                        info["registrar"] = vcard[3]

        return {
            "success": True, "data": info,
            "message": f"{domain}: Kayıt: {info.get('registered', '?')}, Bitiş: {info.get('expires', '?')}"
        }
    except Exception as e:
        # Fallback: nslookup
        r = subprocess.run(f"nslookup -type=any {domain}", capture_output=True, text=True,
                           shell=True, timeout=10, encoding="utf-8", errors="replace")
        return {
            "success": True,
            "data": {"domain": domain, "raw": r.stdout[:1000]},
            "message": f"WHOIS API hatası, nslookup sonucu gösteriliyor"
        }


def check_ssl_expiry(domain: str) -> dict:
    try:
        ctx = ssl.create_default_context()
        with ctx.wrap_socket(socket.socket(), server_hostname=domain) as s:
            s.settimeout(10)
            s.connect((domain, 443))
            cert = s.getpeercert()

        not_after = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z")
        days_left = (not_after - datetime.now()).days
        subject = dict(x[0] for x in cert["subject"])
        issuer = dict(x[0] for x in cert["issuer"])

        return {
            "success": True,
            "data": {
                "domain": domain,
                "issuer": issuer.get("organizationName", "?"),
                "common_name": subject.get("commonName", "?"),
                "valid_until": not_after.strftime("%Y-%m-%d"),
                "days_remaining": days_left,
            },
            "message": f"{domain}: SSL geçerli, {days_left} gün kaldı (issuer: {issuer.get('organizationName', '?')})"
        }
    except Exception as e:
        return {"success": False, "error": f"SSL kontrol hatası: {str(e)}"}

# domain adı verip kullanılan teknolojileri öğrenme
def http_headers(url: str) -> dict:
    if not url.startswith("http"):
        url = f"https://{url}"
    try:
        import urllib.request
        resp = urllib.request.urlopen(url, timeout=10)
        headers = dict(resp.headers)
        return {
            "success": True,
            "data": {"url": url, "headers": headers},
            "message": f"{url}: {len(headers)} header"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def check_website_technologies(url: str) -> dict:
    if not url.startswith("http"):
        url = f"https://{url}"
    try:
        import urllib.request
        resp = urllib.request.urlopen(url, timeout=10)
        headers = dict(resp.headers)
        body = resp.read().decode("utf-8", errors="replace")[:5000]

        techs = []
        server = headers.get("Server", "")
        if server:
            techs.append({"name": "Server", "value": server})
        powered_by = headers.get("X-Powered-By", "")
        if powered_by:
            techs.append({"name": "Powered By", "value": powered_by})

        tech_patterns = {
            "React": r"react|__next",
            "Vue.js": r"vue\.js|__vue",
            "Angular": r"ng-version|angular",
            "jQuery": r"jquery",
            "Bootstrap": r"bootstrap",
            "WordPress": r"wp-content|wordpress",
            "Tailwind": r"tailwind",
            "Next.js": r"__next|next\.js",
        }
        for name, pattern in tech_patterns.items():
            if re.search(pattern, body, re.I):
                techs.append({"name": name, "value": "Tespit edildi"})

        return {
            "success": True, "data": {"url": url, "technologies": techs},
            "message": f"{url}: {len(techs)} teknoloji tespit edildi"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}