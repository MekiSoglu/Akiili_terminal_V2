def _fmt_get_network_info(self, data):
    print(f"\n  Hostname: {data.get('hostname', '?')}")
    print(f"  MAC: {data.get('mac_address', '?')}")

    for adapter in data.get("adapters", []):
        name = adapter.get("name", "?")
        details = adapter.get("details", {})

        # Bağlı mı?
        media = details.get("Media State . . . . . . . . . . ", "")
        if "disconnected" in media.lower():
            status = "Bağlı değil"
        else:
            status = "Bağlı"

        ip = details.get("IPv4 Address. . . . . . . . . . ", "-")
        mac = details.get("Physical Address. . . . . . . . ", "-")
        gateway = details.get("Default Gateway . . . . . . . . ", "-")
        dns = details.get("DNS Servers . . . . . . . . . . ", "-")
        dhcp = details.get("DHCP Enabled. . . . . . . . . . ", "-")
        desc = details.get("Description . . . . . . . . . . ", "-")

        print(f"\n  📡 {name} ({status})")
        print(f"     Açıklama:  {desc}")
        print(f"     IP:        {ip}")
        print(f"     MAC:       {mac}")
        print(f"     Gateway:   {gateway}")
        print(f"     DNS:       {dns}")
        print(f"     DHCP:      {dhcp}")