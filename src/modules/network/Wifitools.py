"""
WiFi Araçları - Ağ listeleme, bağlanma, hotspot, kayıtlı şifreler.
"""

import subprocess
import re
from core.BaseModule import Tool, ToolParam

CATEGORY = "wifi"


def get_tools() -> list[Tool]:
    return [
        Tool("wifi_list", "Çevredeki WiFi ağlarını listele.",
             [], "safe", CATEGORY),
        Tool("wifi_saved_networks", "Daha önce bağlanılan WiFi ağlarını listele.",
             [], "safe", CATEGORY),
        Tool("wifi_saved_passwords", "Kayıtlı WiFi şifresini göster.",
             [ToolParam("network_name", "WiFi ağ adı", "string")],
             "confirm", CATEGORY),
        Tool("wifi_connect", "Bir WiFi ağına bağlan.",
             [ToolParam("network_name", "WiFi ağ adı", "string"),
              ToolParam("password", "Şifre (açık ağ ise boş bırak)", "string", False, "")],
             "confirm", CATEGORY),
        Tool("wifi_disconnect", "WiFi bağlantısını kes.",
             [], "safe", CATEGORY),
        Tool("enable_hotspot", "Mobil hotspot'u aç.",
             [ToolParam("ssid", "Hotspot adı", "string", False, "SmartTerminal"),
              ToolParam("password", "Hotspot şifresi", "string", False, "12345678")],
             "confirm", CATEGORY),
        Tool("disable_hotspot", "Mobil hotspot'u kapat.",
             [], "safe", CATEGORY),
        Tool("hotspot_status", "Hotspot durumunu göster.",
             [], "safe", CATEGORY),
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


def wifi_list() -> dict:
    r = _run("netsh wlan show networks mode=bssid")
    if r["returncode"] != 0:
        return {"success": False, "error": r["stderr"]}

    networks = []
    current = {}
    for line in r["stdout"].splitlines():
        if "SSID" in line and "BSSID" not in line:
            if current and current.get("ssid"):
                networks.append(current)
            current = {"ssid": line.split(":", 1)[-1].strip()}
        elif "Signal" in line or "Sinyal" in line:
            match = re.search(r"(\d+)%", line)
            if match:
                current["signal"] = int(match.group(1))
        elif "Authentication" in line or "Kimlik" in line:
            current["auth"] = line.split(":", 1)[-1].strip()
        elif "Encryption" in line or "Şifreleme" in line or "ifreleme" in line:
            current["encryption"] = line.split(":", 1)[-1].strip()
        elif "Channel" in line or "Kanal" in line:
            match = re.search(r"(\d+)", line.split(":", 1)[-1])
            if match:
                current["channel"] = int(match.group(1))

    if current and current.get("ssid"):
        networks.append(current)

    networks.sort(key=lambda x: x.get("signal", 0), reverse=True)

    return {"success": True, "data": networks, "count": len(networks),
            "message": f"{len(networks)} WiFi ağı bulundu"}


def wifi_saved_networks() -> dict:
    r = _run("netsh wlan show profiles")
    if r["returncode"] != 0:
        return {"success": False, "error": r["stderr"]}

    profiles = []
    for line in r["stdout"].splitlines():
        if ":" in line and ("profil" in line.lower() or "profile" in line.lower()):
            name = line.split(":", 1)[-1].strip()
            if name:
                profiles.append({"name": name})

    return {"success": True, "data": profiles, "count": len(profiles),
            "message": f"{len(profiles)} kayıtlı WiFi ağı"}


def wifi_saved_passwords(network_name: str) -> dict:
    r = _run(f'netsh wlan show profile name="{network_name}" key=clear')
    if r["returncode"] != 0:
        return {"success": False, "error": f"Profil bulunamadı: {network_name}"}

    password = ""
    for line in r["stdout"].splitlines():
        if "Key Content" in line or "Anahtar" in line:
            password = line.split(":", 1)[-1].strip()

    return {
        "success": True,
        "data": {"network": network_name, "password": password or "(şifre yok veya gösterilemiyor)"},
        "message": f"{network_name} şifresi: {password or '(bulunamadı)'}"
    }


def wifi_connect(network_name: str, password: str = "") -> dict:
    # Önce profil var mı kontrol et
    r = _run(f'netsh wlan connect name="{network_name}"')
    if r["returncode"] == 0:
        return {"success": True, "message": f"WiFi'a bağlanıldı: {network_name}"}

    # Profil yoksa yeni profil oluştur
    if password:
        xml = f"""<?xml version="1.0"?>
<WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">
    <name>{network_name}</name>
    <SSIDConfig><SSID><name>{network_name}</name></SSID></SSIDConfig>
    <connectionType>ESS</connectionType>
    <connectionMode>auto</connectionMode>
    <MSM><security>
        <authEncryption><authentication>WPA2PSK</authentication>
        <encryption>AES</encryption><useOneX>false</useOneX></authEncryption>
        <sharedKey><keyType>passPhrase</keyType><protected>false</protected>
        <keyMaterial>{password}</keyMaterial></sharedKey>
    </security></MSM>
</WLANProfile>"""
        import tempfile, os
        tmp = os.path.join(tempfile.gettempdir(), f"{network_name}.xml")
        with open(tmp, "w") as f:
            f.write(xml)
        _run(f'netsh wlan add profile filename="{tmp}"')
        os.remove(tmp)
        r = _run(f'netsh wlan connect name="{network_name}"')
        if r["returncode"] == 0:
            return {"success": True, "message": f"WiFi'a bağlanıldı: {network_name}"}

    return {"success": False, "error": f"Bağlanılamadı: {network_name}"}


def wifi_disconnect() -> dict:
    r = _run("netsh wlan disconnect")
    return {"success": True, "message": "WiFi bağlantısı kesildi"}


def enable_hotspot(ssid: str = "SmartTerminal", password: str = "12345678") -> dict:
    _run(f'netsh wlan set hostednetwork mode=allow ssid="{ssid}" key="{password}"')
    r = _run("netsh wlan start hostednetwork")
    if r["returncode"] != 0:
        return {"success": False, "error": r["stderr"] or "Hotspot başlatılamadı"}
    return {"success": True, "message": f"Hotspot açıldı: {ssid}"}


def disable_hotspot() -> dict:
    r = _run("netsh wlan stop hostednetwork")
    return {"success": True, "message": "Hotspot kapatıldı"}


def hotspot_status() -> dict:
    r = _run("netsh wlan show hostednetwork")
    return {"success": True, "data": {"raw": r["stdout"]}, "message": r["stdout"][:200]}