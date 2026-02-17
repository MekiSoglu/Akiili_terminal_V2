"""
Çıktı Formatlayıcı - Terminal sonuçlarını okunabilir formatta gösterir.
Her araç tipi için özel format tanımlanabilir.
"""

import logging

logger = logging.getLogger(__name__)


class OutputFormatter:

    def display(self, result):
        if result.success:
            print(f"\n✓ {result.message}")
            for step in result.steps:
                self._format_step(step)
        else:
            print(f"\n✗ {result.message}")
            for step in result.steps:
                if not step.success:
                    print(f"  Adım {step.step_number}: {step.error}")

    def _format_step(self, step):
        r = step.result
        data = r.get("data", None)
        content = r.get("content", None)
        message = r.get("message", "")

        # Araç adına göre özel formatlayıcı varsa kullan
        formatter = getattr(self, f"_fmt_{step.tool_name}", None)
        if formatter and data is not None:
            formatter(data)
            return

        # Dosya içeriği
        if content:
            print(f"\n--- {message} ---")
            print(content)
            print("---")
            return

        # Liste sonuçları
        if isinstance(data, list) and data:
            self._fmt_list(data, step.tool_name)
            return

        # Dict içinde subdirs/files varsa
        if isinstance(data, dict):
            if "subdirs" in data or "files" in data:
                self._fmt_directory_contents(data)
                return
            # Genel dict bilgisi
            self._fmt_dict(data)
            return

        if message:
            print(f"  ✓ {message}")

    # ============================================================
    # ARAÇ BAZLI FORMATLAR
    # ============================================================

    def _fmt_get_directory_size(self, data):
        print(f"\n  📁 {data.get('directory', '')}")
        print(f"     Dosya sayısı:  {data.get('file_count', 0)}")
        print(f"     Toplam boyut:  {data.get('total_size_mb', 0)} MB ({data.get('total_size_gb', 0)} GB)")

    def _fmt_get_file_info(self, data):
        print(f"\n  📄 {data.get('name', '')}")
        print(f"     Yol:           {data.get('full_path', '')}")
        print(f"     Boyut:         {data.get('size_human', '')}")
        print(f"     Oluşturulma:   {data.get('created', '')}")
        print(f"     Değiştirilme:  {data.get('modified', '')}")

    def _fmt_search_directories(self, data):
        if isinstance(data, list):
            for d in data:
                print(f"\n  📁 {d.get('name', '')}")
                print(f"     Yol:           {d.get('full_path', '')}")
                print(f"     Dosya sayısı:  {d.get('file_count', 0)}")
                print(f"     Alt klasör:    {d.get('subdir_count', 0)}")

    # ============================================================
    # GENEL FORMATLAR
    # ============================================================

    def _fmt_list(self, data, tool_name):
        print(f"\n  {tool_name} ({len(data)} sonuç):")
        for item in data[:15]:
            name = f"{item.get('name', '')}{item.get('extension', '')}"
            size = item.get('size_human', '')
            path = item.get('full_path', '')
            print(f"    {name:<30} {size:<10} {path}")
        if len(data) > 15:
            print(f"    ... ve {len(data) - 15} sonuç daha")

    def _fmt_directory_contents(self, data):
        subdirs = data.get("subdirs", [])
        files = data.get("files", [])
        if subdirs:
            print(f"\n  Klasörler ({len(subdirs)}):")
            for d in subdirs:
                print(f"    📁 {d['name']:<25} ({d.get('file_count', 0)} dosya)")
        if files:
            print(f"\n  Dosyalar ({len(files)}):")
            for f in files[:15]:
                name = f"{f.get('name', '')}{f.get('extension', '')}"
                print(f"    📄 {name:<25} {f.get('size_human', '')}")

    def _fmt_dict(self, data):
        for key, value in data.items():
            print(f"     {key:<15} {value}")

    def _fmt_find_largest_files(self, data):
        if isinstance(data, list):
            print(f"\n  En büyük dosyalar ({len(data)} sonuç):")
            for item in data:
                name = f"{item.get('name', '')}{item.get('extension', '')}"
                print(f"\n    📄 {name}")
                print(f"       Yol:           {item.get('full_path', '')}")
                print(f"       Boyut:         {item.get('size_human', '')}")
                print(f"       Dizin:         {item.get('dir_path', '')}")
                print(f"       Değiştirilme:  {item.get('modified_at_human', '')}")
                print(f"       Oluşturulma:   {item.get('created_at_human', '')}")

    def _fmt_search_in_files(self, data):
        if isinstance(data, list):
            print(f"\n  Dosya içi arama ({len(data)} dosyada eşleşme):")
            for item in data:
                print(f"\n    📄 {item['name']} ({item['total_matches']} eşleşme)")
                for m in item['matches']:
                    print(f"       Satır {m['line']}: {m['text'][:80]}")

    def _fmt_count_lines_words(self, data):
        print(f"\n    📄 {data.get('file', '')}")
        print(f"       Satır:     {data.get('lines', 0)}")
        print(f"       Kelime:    {data.get('words', 0)}")
        print(f"       Karakter:  {data.get('characters', 0)}")

    def _fmt_get_extension_stats(self, data):
        if isinstance(data, list):
            print(f"\n  Uzantı İstatistikleri ({len(data)} uzantı):")
            print(f"    {'Uzantı':<15} {'Dosya':<10} {'Toplam':<12} {'Ortalama':<10}")
            print(f"    {'-' * 47}")
            for item in data[:20]:
                print(
                    f"    {item['extension']:<15} {item['file_count']:<10} {item['total_size_mb']:<12} {item['avg_size_mb']:<10}")

    def _fmt_find_duplicate_names(self, data):
        if isinstance(data, list):
            print(f"\n  Tekrar Eden Dosyalar ({len(data)} grup):")
            for item in data:
                print(f"\n    📄 {item['name']}{item['extension']} (x{item['count']})")
                for p in item['paths']:
                    print(f"       {p}")

    def _fmt_compare_files(self, data):
        print(f"\n    Sonuç: {data.get('reason', '')}")
        if data.get('hash_1'):
            print(f"    Hash 1: {data['hash_1']}")
            print(f"    Hash 2: {data['hash_2']}")

    def _fmt_find_empty_files(self, data):
        if isinstance(data, list):
            print(f"\n  Boş Dosyalar ({len(data)} adet):")
            for item in data:
                print(f"    📄 {item.get('name', '')}{item.get('extension', '')}  {item.get('full_path', '')}")

    def _fmt_find_empty_directories(self, data):
        if isinstance(data, list):
            print(f"\n  Boş Klasörler ({len(data)} adet):")
            for item in data:
                print(f"    📁 {item.get('name', '')}  {item.get('full_path', '')}")

    def _fmt_get_directory_tree(self, data):
        self._print_tree(data, "")

    def _print_tree(self, node, indent):
        icon = "📁" if node.get("children") is not None else "📄"
        fc = f" ({node.get('file_count', 0)} dosya)" if node.get('file_count', 0) > 0 else ""
        print(f"{indent}{icon} {node.get('name', '')}{fc}")
        for child in node.get("children", []):
            self._print_tree(child, indent + "    ")

    # ═══════════════════════════════════════════
    #  BASIC TOOLS
    # ═══════════════════════════════════════════

    def _fmt_get_network_info(self, data):
        if not isinstance(data, dict):
            return
        print(f"\n  Hostname: {data.get('hostname', '?')}")
        print(f"  MAC: {data.get('mac_address', '?')}")

        for adapter in data.get("adapters", []):
            name = adapter.get("name", "?")
            details = adapter.get("details", {})

            media = details.get("Media State", "")
            status = "Bağlı değil" if "disconnected" in media.lower() else "Bağlı"

            ip = details.get("IPv4 Address", "-").replace("(Preferred)", "").strip()
            mac = details.get("Physical Address", "-")
            gateway = details.get("Default Gateway", "-")
            dns = details.get("DNS Servers", "-")
            dhcp = details.get("DHCP Enabled", "-")
            desc = details.get("Description", "-")

            print(f"\n  📡 {name} ({status})")
            print(f"     Açıklama:  {desc}")
            print(f"     IP:        {ip}")
            print(f"     MAC:       {mac}")
            print(f"     Gateway:   {gateway}")
            print(f"     DNS:       {dns}")
            print(f"     DHCP:      {dhcp}")

    def _fmt_get_public_ip(self, data):
        if isinstance(data, list):
            print(f"\n  🌍 IP Konum Bilgileri ({len(data)} adet):")
            for info in data:
                if info.get('error'):
                    print(f"\n    ❌ {info.get('ip', '?')}: {info['error']}")
                else:
                    print(f"\n    🌐 {info.get('ip', '?')}")
                    print(f"       Şehir:     {info.get('city', '?')}")
                    print(f"       Bölge:     {info.get('region', '?')}")
                    print(f"       Ülke:      {info.get('country', '?')}")
                    print(f"       ISP:       {info.get('org', '?')}")
                    print(f"       Koordinat: {info.get('loc', '?')}")
        elif isinstance(data, dict):
            print(f"\n  🌍 Dış IP Bilgileri:")
            print(f"     IP:        {data.get('ip', '?')}")
            print(f"     Şehir:     {data.get('city', '?')}")
            print(f"     Bölge:     {data.get('region', '?')}")
            print(f"     Ülke:      {data.get('country', '?')}")
            print(f"     ISP:       {data.get('org', '?')}")
            print(f"     Koordinat: {data.get('loc', '?')}")
            print(f"     Saat Dil.: {data.get('timezone', '?')}")

    def _fmt_list_network_adapters(self, data):
        if isinstance(data, list):
            print(f"\n  Ağ Adaptörleri ({len(data)} adet):")
            print(f"    {'Ad':<30} {'Durum':<12} {'Tür':<12} {'Yönetim'}")
            print(f"    {'-'*65}")
            for a in data:
                name = a.get('name', '?')
                state = a.get('state', '?')
                atype = a.get('type', '?')
                admin = a.get('admin_state', '?')
                icon = "🟢" if state == "Connected" else "🔴"
                print(f"    {icon} {name:<28} {state:<12} {atype:<12} {admin}")

    def _fmt_list_arp_table(self, data):
        if isinstance(data, list):
            print(f"\n  ARP Tablosu ({len(data)} kayıt):")
            print(f"    {'IP Adresi':<20} {'MAC Adresi':<20} {'Tür':<10}")
            print(f"    {'-'*50}")
            for item in data:
                print(f"    {item.get('ip',''):<20} {item.get('mac',''):<20} {item.get('type',''):<10}")

    def _fmt_ip_conflict_check(self, data):
        if isinstance(data, dict):
            conflicts = data.get('conflicts', [])
            total = data.get('total_entries', 0)
            if conflicts:
                print(f"\n  ⚠️  IP Çakışması Tespit Edildi!")
                for c in conflicts:
                    print(f"     {c['ip']}: {c['mac1']} ↔ {c['mac2']}")
            else:
                print(f"\n  ✅ IP çakışması yok ({total} cihaz tarandı)")

    def _fmt_subnet_calculator(self, data):
        if isinstance(data, dict):
            print(f"\n  🧮 Subnet Hesaplama:")
            print(f"     Ağ Adresi:     {data.get('network_address', '?')}")
            print(f"     Broadcast:     {data.get('broadcast_address', '?')}")
            print(f"     Subnet Mask:   {data.get('subnet_mask', '?')}")
            print(f"     Prefix:        /{data.get('prefix_length', '?')}")
            print(f"     İlk Host:      {data.get('first_host', '?')}")
            print(f"     Son Host:      {data.get('last_host', '?')}")
            print(f"     Toplam Host:   {data.get('total_hosts', '?')}")

    def _fmt_ip_full_info(self, data):
        if isinstance(data, dict):
            tag = data.get('tag', '-')
            provider = data.get('provider', '')
            tag_line = f"{tag} ({provider})" if provider and provider != tag else tag

            print(f"\n  🌐 {data.get('ip', '?')}")
            print(f"     Servis:       {tag_line}")
            print(f"     Hostname:     {data.get('hostname', '-')}")
            print(f"     MAC:          {data.get('mac', '-')}")
            print(f"     Konum:        {data.get('city', '?')}, {data.get('region', '?')}, {data.get('country', '?')}")
            print(f"     ISP:          {data.get('org', '-')}")
            print(f"     Koordinat:    {data.get('loc', '-')}")
            print(f"     Ping:         {data.get('ping_ms', -1)}ms")
            print(f"     Erişilebilir: {'Evet ✅' if data.get('reachable') else 'Hayır ❌'}")

    def _fmt_scan_all_devices(self, data):
        if isinstance(data, list):
            print(f"\n  Ağdaki Cihazlar ({len(data)} adet):")
            for d in data:
                status = "✅ Aktif" if d.get("active") else "❌ Pasif"
                ping = f"{d.get('ping_ms', -1)}ms" if d.get('ping_ms', -1) > 0 else "-"
                ports = ", ".join(str(p) for p in d.get("open_ports", []))

                print(f"\n    🖥 {d.get('ip','')}")
                print(f"       Hostname:    {d.get('hostname', '-')}")
                print(f"       MAC:         {d.get('mac', '-')}")
                print(f"       Üretici:     {d.get('vendor', '-')}")
                print(f"       Cihaz Tipi:  {d.get('device_type', '-')}")
                print(f"       Açık Portlar:{ports or '-'}")
                print(f"       Ping:        {ping}")
                print(f"       Durum:       {status}")

    # ═══════════════════════════════════════════
    #  CONNECTIVITY TOOLS
    # ═══════════════════════════════════════════

    def _fmt_ping(self, data):
        if isinstance(data, dict):
            print(f"\n  Ping Sonuçları:")
            print(f"     Minimum:     {data.get('min_ms', '?')} ms")
            print(f"     Maksimum:    {data.get('max_ms', '?')} ms")
            print(f"     Ortalama:    {data.get('avg_ms', '?')} ms")
            loss = data.get('packet_loss', 0)
            icon = "✅" if loss == 0 else "⚠️" if loss < 50 else "❌"
            print(f"     Paket Kaybı: %{loss} {icon}")

    def _fmt_traceroute(self, data):
        if isinstance(data, list):
            print(f"\n    Traceroute ({len(data)} atlama):")
            print(f"    {'#':<4} {'IP Adresi':<20} {'Süre'}")
            print(f"    {'-'*50}")
            for hop in data:
                print(f"    {hop.get('hop','?'):<4} {hop.get('ip','?'):<20} {hop.get('times','?')}")

    def _fmt_visual_traceroute(self, data):
        if isinstance(data, list):
            print(f"\n  🗺️  Rota Haritası ({len(data)} atlama):")
            print(f"    {'#':<4} {'IP Adresi':<18} {'Süre':<22} {'Konum':<25} {'ISP'}")
            print(f"    {'-' * 95}")

            prev_country = ""
            for hop in data:
                num = hop.get('hop', '?')
                ip = hop.get('ip', '?')
                times = hop.get('times', '?')
                city = hop.get('city', '?')
                country = hop.get('country', '?')
                org = hop.get('org', '?')

                location = f"{city}, {country}" if city not in ("?", "Yerel Ağ") else country

                if country != prev_country and prev_country:
                    print(f"    {'─' * 95}")
                prev_country = country

                if num == 1:
                    icon = "🏠"
                elif hop == data[-1]:
                    icon = "🎯"
                elif country == "LAN":
                    icon = "🔒"
                else:
                    icon = "🌐"

                org_short = (org[:28] + "..") if len(str(org)) > 30 else org
                print(f"    {icon} {num:<3} {ip:<18} {times:<22} {location:<25} {org_short}")

            countries = list(dict.fromkeys(
                h.get('country', '?') for h in data if h.get('country') not in ('?', 'LAN')
            ))
            if countries:
                print(f"\n    📍 Rota: {' → '.join(countries)}")

    def _fmt_port_scan(self, data):
        if isinstance(data, dict) and "ports" in data:
            host = data.get("host", "?")
            is_local = data.get("is_local", True)
            scope = "Yerel Ağ" if is_local else "İNTERNET"
            ports = data.get("ports", [])

            print(f"\n  🔍 Port Tarama: {host} ({scope})")
            print(f"  {data.get('risk_summary', '')}")

            if not ports:
                print(f"\n  🔒 Açık port bulunamadı.")
                return

            print(f"\n    {'Port':<7} {'Servis':<18} {'Risk':<10} {'Bilgi'}")
            print(f"    {'-' * 85}")
            for p in ports:
                risk = p.get('risk', '?')
                icon = {"Kritik": "🔴", "Yüksek": "🟠", "Orta": "🟡", "Düşük": "🟢"}.get(risk, "⚪")
                print(
                    f"    {icon} {p.get('port', '?'):<5} {p.get('service', '-') or '-':<18} {risk:<10} {p.get('security_info', '')[:45]}")

            if data.get("critical_count", 0) > 0 and not is_local:
                print(f"\n  🚨 ÖNERİ: Kritik portları modem ayarlarından internete kapatın!")
            elif data.get("critical_count", 0) > 0:
                print(f"\n  💡 ÖNERİ: Bu portlar yerel ağda açık. Modemden internete")
                print(f"     yönlendirilmediğinden emin olun.")
        elif isinstance(data, list):
            if not data:
                print(f"\n  🔒 Açık port bulunamadı.")
                return
            print(f"\n  🔓 Açık Portlar ({len(data)} adet):")
            for p in data:
                print(f"    {p.get('port', '?'):<8} {p.get('service', '-') or '-'}")

    def _fmt_check_port_usage(self, data):
        if isinstance(data, list):
            if not data:
                print(f"\n  Bu portu kullanan işlem yok.")
                return
            print(f"\n  🔍 Port Kullanımı ({len(data)} bağlantı):")
            print(f"    {'Prt':<6} {'Yerel Adres':<24} {'Uzak Adres':<24} {'Durum':<14} {'İşlem'}")
            print(f"    {'-'*80}")
            for e in data:
                process = e.get('process', f"PID:{e.get('pid', '?')}")
                print(f"    {e.get('protocol','?'):<6} {e.get('local_address','?'):<24} {e.get('foreign_address','?'):<24} {e.get('state','-'):<14} {process}")

    def _fmt_list_active_connections(self, data):
        if isinstance(data, list):
            states = {}
            for c in data:
                s = c.get('state', 'OTHER')
                states[s] = states.get(s, 0) + 1

            print(f"\n  🌐 Aktif Bağlantılar ({len(data)} adet):")
            if states:
                parts = [f"{s}: {c}" for s, c in sorted(states.items(), key=lambda x: x[1], reverse=True)]
                print(f"     Özet: {', '.join(parts)}")

            print(f"\n    {'Prt':<5} {'Yerel Adres':<24} {'Uzak Adres':<24} {'Durum':<14} {'Uygulama'}")
            print(f"    {'-' * 80}")
            for c in data[:70]:
                process = c.get('process', f"PID:{c.get('pid', '?')}")
                print(
                    f"    {c.get('protocol', '?'):<5} {c.get('local', '?'):<24} {c.get('remote', '?'):<24} {c.get('state', '-'):<14} {process}")
            if len(data) > 70:
                print(f"    ... ve {len(data) - 30} bağlantı daha")

    def _fmt_speed_test(self, data):
        if isinstance(data, dict):
            speed = data.get('download_mbps', 0)
            elapsed = data.get('elapsed_sec', 0)

            if speed > 50:
                icon, quality = "🚀", "Hızlı"
            elif speed > 10:
                icon, quality = "✅", "İyi"
            elif speed > 5:
                icon, quality = "⚠️", "Orta"
            else:
                icon, quality = "❌", "Yavaş"

            print(f"\n  {icon} Hız Testi Sonucu:")
            print(f"     İndirme Hızı: {speed} Mbps ({quality})")
            print(f"     Süre:         {elapsed} saniye")

            bar_len = min(int(speed), 50)
            bar = "█" * bar_len + "░" * (50 - bar_len)
            print(f"     [{bar}] {speed} Mbps")

    def _fmt_connection_quality_test(self, data):
        if isinstance(data, dict):
            quality = data.get('quality', '?')
            icons = {"Mükemmel": "🟢", "İyi": "🟡", "Orta": "🟠", "Kötü": "🔴"}
            icon = icons.get(quality, "⚪")

            print(f"\n  {icon} Bağlantı Kalitesi: {quality}")
            print(f"     Ortalama:    {data.get('avg_ms', '?')} ms")
            print(f"     Minimum:     {data.get('min_ms', '?')} ms")
            print(f"     Maksimum:    {data.get('max_ms', '?')} ms")
            print(f"     Jitter:      {data.get('jitter_ms', '?')} ms")
            loss = data.get('packet_loss', 0)
            loss_icon = "✅" if loss == 0 else "⚠️" if loss < 10 else "❌"
            print(f"     Paket Kaybı: %{loss} {loss_icon}")

    def _fmt_check_website_status(self, data):
        if isinstance(data, dict):
            url = data.get('url', '?')
            status = data.get('status_code', 0)
            resp_time = data.get('response_time_sec', 0)
            error = data.get('error', '')
            note = data.get('note', '')

            if 200 <= status < 400:
                icon, status_text = "✅", f"Erişilebilir (HTTP {status})"
            elif 400 <= status < 500:
                icon, status_text = "⚠️", f"Yanıt veriyor ama kısıtlı (HTTP {status})"
            elif status >= 500:
                icon, status_text = "❌", f"Sunucu hatası (HTTP {status})"
            else:
                icon, status_text = "❌", "Erişilemiyor"

            print(f"\n  {icon} {url}")
            print(f"     Durum:        {status_text}")
            if resp_time:
                print(f"     Yanıt Süresi: {resp_time}s")
            if note:
                print(f"     Not:          {note}")
            if error:
                print(f"     Hata:         {error}")
    def _fmt_measure_response_time(self, data):
        if isinstance(data, dict):
            url = data.get('url', '?')
            times = data.get('times_ms', [])
            avg = data.get('avg_ms', -1)
            min_ms = data.get('min_ms', -1)

            print(f"\n  ⏱️  Yanıt Süresi: {url}")
            print(f"     Ortalama: {avg} ms")
            print(f"     En Hızlı: {min_ms} ms")
            print(f"     Ölçümler:")
            for i, t in enumerate(times):
                icon = "✅" if t > 0 else "❌"
                val = f"{t}ms" if t > 0 else "Başarısız"
                print(f"       [{i+1}] {val} {icon}")

    # ═══════════════════════════════════════════
    #  WIFI TOOLS
    # ═══════════════════════════════════════════

    def _fmt_wifi_list(self, data):
        if isinstance(data, list):
            print(f"\n  📶 WiFi Ağları ({len(data)} adet):")
            print(f"    {'Ağ Adı':<28} {'Sinyal':<10} {'Güvenlik':<16} {'Kanal'}")
            print(f"    {'-'*65}")
            for net in data:
                ssid = net.get('ssid', '?')
                signal = net.get('signal', 0)
                auth = net.get('auth', '?')
                channel = net.get('channel', '?')
                bars = "█" * (signal // 20) + "░" * (5 - signal // 20)
                print(f"    {ssid:<28} {bars} {signal}%  {auth:<16} {channel}")

    def _fmt_wifi_saved_networks(self, data):
        if isinstance(data, list):
            print(f"\n  💾 Kayıtlı WiFi Ağları ({len(data)} adet):")
            for i, net in enumerate(data, 1):
                print(f"    {i}. {net.get('name', '?')}")

    def _fmt_wifi_saved_passwords(self, data):
        if isinstance(data, dict):
            print(f"\n  🔑 WiFi Şifresi:")
            print(f"     Ağ:    {data.get('network', '?')}")
            print(f"     Şifre: {data.get('password', '?')}")

    # ═══════════════════════════════════════════
    #  DNS TOOLS
    # ═══════════════════════════════════════════

    def _fmt_dns_lookup(self, data):
        if isinstance(data, dict):
            domain = data.get('domain', '?')
            ips = data.get('ip_addresses', [])
            print(f"\n  🔍 DNS Çözümleme: {domain}")
            for ip in ips:
                print(f"     → {ip}")

    def _fmt_dns_reverse(self, data):
        if isinstance(data, dict):
            hostname = data.get('hostname', '-')
            ip = data.get('ip', '?')

            icon = "✅" if hostname != "-" else "⚠️"
            print(f"\n  {icon} Reverse DNS: {ip}")
            print(f"     Hostname: {hostname}")
            if data.get('method'):
                print(f"     Yöntem:   {data.get('method')}")
            if data.get('org'):
                print(f"     ISP:      {data.get('org')}")
            if data.get('location'):
                print(f"     Konum:    {data.get('location')}")
            if data.get('note'):
                print(f"     Not:      {data.get('note')}")

    def _fmt_dns_bypass_test(self, data):
        if isinstance(data, dict):
            domain = data.get("domain", "?")
            results = data.get("results", [])
            switched = data.get("switched_to")

            print(f"\n  🔓 DNS Erişim Testi: {domain}")
            print(f"    {'DNS':<15} {'IP':<18} {'Durum':<14} {'HTTP':<7} {'Süre'}")
            print(f"    {'-' * 65}")
            for r in results:
                if r["accessible"]:
                    icon = "✅"
                    status = "Erişilebilir"
                else:
                    icon = "❌"
                    status = "Engelli"
                ms = f"{r['response_ms']}ms" if r['response_ms'] > 0 else "-"
                http = f"{r['status_code']}" if r['status_code'] > 0 else "-"
                print(f"    {icon} {r['dns_name']:<13} {r['dns_ip']:<18} {status:<14} {http:<7} {ms}")

            if switched:
                print(f"\n  🔄 DNS otomatik olarak {switched} ile değiştirildi.")
            elif data.get("working_dns"):
                print(f"\n  💡 Erişim için şunu deneyin: DNS'i {data['working_dns']} olarak değiştir")
            else:
                print(f"\n  ⚠️  Hiçbir DNS ile erişim sağlanamadı. Site tamamen engellenmiş olabilir.")



    def _fmt_list_hosts(self, data):
        if isinstance(data, list):
            print(f"\n  📋 Hosts Dosyası ({len(data)} kayıt):")
            print(f"    {'IP Adresi':<20} {'Domain'}")
            print(f"    {'-'*45}")
            for entry in data:
                print(f"    {entry.get('ip',''):<20} {entry.get('domain','')}")

    def _fmt_show_dns_cache(self, data):
        if isinstance(data, list):
            print(f"\n  📋 DNS Önbelleği ({len(data)} kayıt):")
            print(f"    {'Domain':<35} {'IP':<18} {'Tür'}")
            print(f"    {'-'*60}")
            for entry in data[:30]:
                print(f"    {entry.get('name','?'):<35} {entry.get('ip','-'):<18} {entry.get('type','-')}")
            if len(data) > 30:
                print(f"    ... ve {len(data) - 30} kayıt daha")

    # ═══════════════════════════════════════════
    #  SECURITY TOOLS
    # ═══════════════════════════════════════════

    def _fmt_firewall_list_rules(self, data):
        if isinstance(data, list):
            # Okunamaz kuralları filtrele ve temizle
            clean_rules = []
            seen = set()
            for r in data:
                name = r.get('name', '?')

                # ms-resource ve @{Microsoft... gibi okunamaz isimleri atla
                if name.startswith(("ms-resource:", "@{", "ms-appx:")):
                    continue

                # Kural adını kısalt
                if len(name) > 40:
                    name = name[:38] + ".."

                # Tekrarları birleştir
                key = f"{name}|{r.get('action', '')}|{r.get('direction', '')}"
                if key in seen:
                    continue
                seen.add(key)

                enabled = r.get('enabled', '?')
                action = r.get('action', '?')
                direction = r.get('direction', '?')

                # İkonlar
                action_icon = "✅" if action == "Allow" else "🚫"
                dir_icon = "⬇️" if direction == "In" else "⬆️" if direction == "Out" else "↔️"
                status_icon = "🟢" if enabled == "Yes" else "⚪"

                clean_rules.append({
                    "name": name,
                    "action_icon": action_icon,
                    "action": "İzin" if action == "Allow" else "Engel",
                    "dir_icon": dir_icon,
                    "direction": "Gelen" if direction == "In" else "Giden",
                    "status_icon": status_icon,
                    "enabled": "Aktif" if enabled == "Yes" else "Pasif",
                })

            print(
                f"\n  🛡️ Firewall Kuralları ({len(clean_rules)} adet, {len(data) - len(clean_rules)} sistem kuralı gizlendi):")
            print(f"    {'Kural Adı':<40} {'Durum':<10} {'Eylem':<10} {'Yön'}")
            print(f"    {'-' * 70}")
            for r in clean_rules[:30]:
                print(
                    f"    {r['status_icon']} {r['name']:<38} {r['enabled']:<10} {r['action_icon']} {r['action']:<7} {r['dir_icon']} {r['direction']}")
            if len(clean_rules) > 30:
                print(f"    ... ve {len(clean_rules) - 30} kural daha")

    def _fmt_arp_spoof_detect(self, data):
        if isinstance(data, dict):
            if data.get('safe'):
                print(f"\n  ✅ ARP Tablosu Güvenli")
                print(f"     {data.get('total_devices', 0)} cihaz tarandı, saldırı tespit edilmedi.")
            else:
                print(f"\n  🚨 ARP Spoofing Şüphesi!")
                for mac, ips in data.get('suspicious', {}).items():
                    print(f"     MAC {mac} → {', '.join(ips)}")

    def _fmt_ssl_certificate_check(self, data):
        if isinstance(data, dict):
            days = data.get('days_remaining', 0)
            if days > 30:
                icon = "✅"
            elif days > 7:
                icon = "⚠️"
            else:
                icon = "🚨"

            print(f"\n  {icon} SSL Sertifika: {data.get('domain', '?')}")
            print(f"     Veren:       {data.get('issuer', '?')}")
            print(f"     Konu:        {data.get('subject', data.get('common_name', '?'))}")
            print(f"     Geçerlilik:  {data.get('valid_from', '?')} → {data.get('valid_until', '?')}")
            print(f"     Kalan Gün:   {days}")

    def _fmt_security_port_audit(self, data):
        if isinstance(data, dict):
            host = data.get("host", "?")
            is_local = data.get("is_local_scan", False)
            scope = "Bu Bilgisayar" if is_local else host
            hidden = data.get("hidden_ports", [])
            ports = data.get("ports", [])

            print(f"\n  🛡️ Port Güvenlik Denetimi: {scope}")
            print(f"  {data.get('risk_summary', '')}")
            print(f"     Netstat portları: {data.get('netstat_count', 0)}")
            print(f"     Soket tarama:     {data.get('socket_count', 0)}")

            if hidden:
                print(f"\n  🚨 GİZLİ PORTLAR (netstat'ta görünmüyor!):")
                for p in hidden:
                    print(f"     🚨 Port {p} — Olası backdoor/rootkit!")

            if ports:
                print(f"\n    {'Port':<7} {'Servis':<16} {'Risk':<10} {'Uygulama':<20} {'Tespit':<12} {'Bilgi'}")
                print(f"    {'-' * 95}")
                for p in ports:
                    risk = p.get('risk', '?')
                    icon = {"Kritik": "🔴", "Yüksek": "🟠", "Orta": "🟡", "Düşük": "🟢"}.get(risk, "⚪")
                    detection = p.get('detection', '')
                    det_icon = "🚨" if "GİZLİ" in detection else ""
                    info = p.get('security_info', '')
                    print(
                        f"    {icon} {p.get('port', '?'):<5} {p.get('service', '-') or '-':<16} {risk:<10} {p.get('process', '-'):<20} {det_icon}{detection:<10} {info[:30]}")
                    if info and len(info) > 30:
                        print(f"                                                                    {info[30:]}")

            if data.get("critical_count", 0) > 0 and not data.get("is_local", True):
                print(f"\n  🚨 ÖNERİ: Kritik portları modem ayarlarından internete kapatın!")
            elif data.get("critical_count", 0) > 0:
                print(f"\n  💡 ÖNERİ: Kritik portlar yerel ağda açık. Modemden internete")
                print(f"     yönlendirilmediğinden emin olun.")

    def _fmt_detect_rogue_dhcp(self, data):
        if isinstance(data, dict):
            safe = data.get("safe", True)
            method = data.get("method", "?")
            gateway = data.get("gateway", "?")
            total = data.get("total_servers", 0)

            icon = "✅" if safe else "🚨"
            method_text = "Aktif (DHCP DISCOVER)" if method == "active" else "Pasif (ipconfig)"

            print(f"\n  {icon} DHCP Güvenlik Kontrolü ({method_text}):")
            print(f"     Gateway:          {gateway}")
            print(f"     Yanıt Veren:      {total} sunucu")

            legitimate = data.get("legitimate", [])
            if legitimate:
                print(f"\n     ✅ Meşru Sunucular:")
                for s in legitimate:
                    print(f"       {s.get('server_ip', '?')}")
                    if s.get("offered_ip"):
                        print(f"         Teklif IP:  {s['offered_ip']}")
                    if s.get("router"):
                        print(f"         Router:     {s['router']}")
                    if s.get("source_mac"):
                        print(f"         MAC:        {s['source_mac']}")

            suspicious = data.get("suspicious", [])
            if suspicious:
                print(f"\n     🚨 Şüpheli Sunucular:")
                for s in suspicious:
                    print(f"       ⚠️  {s.get('server_ip', '?')} — {s.get('status', '?')}")
                    if s.get("offered_ip"):
                        print(f"           Teklif IP:  {s['offered_ip']}")
                    if s.get("source_mac"):
                        print(f"           MAC:        {s['source_mac']}")
                    if s.get("adapter"):
                        print(f"           Adaptör:    {s['adapter']}")

            virtual = data.get("virtual_ignored", {})
            if virtual:
                print(f"\n     ⚪ Sanal Adaptörler (güvenli, göz ardı edildi):")
                for a, s in virtual.items():
                    print(f"       {a}: {s}")

            note = data.get("note", "")
            if note:
                print(f"\n  ℹ️  {note}")

    def _fmt_network_security_audit(self, data):
        if isinstance(data, dict):
            score = data.get("score", "?")
            issues = data.get("issues", [])
            results = data.get("results", {})

            icons = {"İYİ": "🟢", "RİSKLİ": "🟠", "KRİTİK": "🔴"}
            icon = icons.get(score, "⚪")

            print(f"\n  {'═' * 60}")
            print(f"  {icon} AĞ GÜVENLİK DENETİMİ: {score}")
            print(f"  {'═' * 60}")

            # Sorunlar
            if issues:
                print(f"\n  ⚠️  Tespit Edilen Sorunlar ({len(issues)}):")
                for i, issue in enumerate(issues, 1):
                    print(f"     {i}. {issue}")
            else:
                print(f"\n  ✅ Sorun tespit edilmedi. Ağınız güvenli görünüyor.")

            # Port detayları
            port_data = results.get("port_audit", {})
            if port_data:
                print(f"\n  {'─' * 60}")
                print(f"  🔍 PORT DENETİMİ")
                print(f"     Toplam açık port: {port_data.get('socket_count', 0)}")
                print(f"     Kritik:           {port_data.get('critical_count', 0)}")
                print(f"     Yüksek risk:      {port_data.get('high_count', 0)}")

                hidden = port_data.get("hidden_ports", [])
                if hidden:
                    print(f"\n     🚨 GİZLİ PORTLAR (netstat'ta görünmüyor!):")
                    for p in hidden:
                        print(f"        Port {p} — Olası backdoor/rootkit!")

                ports = port_data.get("ports", [])
                risky = [p for p in ports if p.get("risk") in ("Kritik", "Yüksek")]
                if risky:
                    print(f"\n     Riskli Portlar:")
                    for p in risky:
                        risk = p.get("risk", "?")
                        r_icon = "🔴" if risk == "Kritik" else "🟠"
                        info = p.get("security_info", "")
                        print(
                            f"        {r_icon} Port {p.get('port', '?'):<6} {p.get('service', '-'):<16} {p.get('process', '-')}")
                        if info:
                            print(f"           💬 {info}")

            # ARP detayları
            arp_data = results.get("arp_spoofing", {})
            if arp_data:
                arp_safe = arp_data.get("safe", True)
                print(f"\n  {'─' * 60}")
                print(f"  🛡️ ARP GÜVENLİK")
                print(f"     {'✅ Güvenli' if arp_safe else '🚨 Şüpheli aktivite tespit edildi'}")
                print(f"     Taranan cihaz: {arp_data.get('total_devices', 0)}")
                suspicious = arp_data.get("suspicious", {})
                if suspicious:
                    for mac, ips in suspicious.items():
                        print(f"     ⚠️  MAC {mac}")
                        print(f"        Kullandığı IP'ler: {', '.join(ips)}")
                        print(f"        Aynı MAC birden fazla IP'de — olası ARP spoofing!")

            # DHCP detayları
            dhcp_data = results.get("rogue_dhcp", {})
            if dhcp_data:
                dhcp_safe = dhcp_data.get("safe", True)
                method = "Aktif" if dhcp_data.get("method") == "active" else "Pasif"
                print(f"\n  {'─' * 60}")
                print(f"  📡 DHCP GÜVENLİK ({method})")
                print(f"     {'✅ Güvenli' if dhcp_safe else '🚨 Sahte DHCP tespit edildi'}")
                print(f"     Gateway: {dhcp_data.get('gateway', '?')}")
                suspicious = dhcp_data.get("suspicious", [])
                if suspicious:
                    for s in suspicious:
                        print(f"     ⚠️  Sunucu: {s.get('server_ip', '?')} — {s.get('status', '?')}")
                        if s.get("offered_ip"):
                            print(f"        Teklif IP: {s['offered_ip']}")
                        if s.get("source_mac"):
                            print(f"        MAC:       {s['source_mac']}")

            # Proxy kontrolü
            proxy_data = results.get("proxy", {})
            if proxy_data:
                proxy_enabled = proxy_data.get("enabled", False)
                print(f"\n  {'─' * 60}")
                print(f"  🔀 PROXY KONTROLÜ")
                if proxy_enabled:
                    proxy_addr = proxy_data.get("proxy_address", "?")
                    print(f"     🚨 Proxy AKTİF: {proxy_addr}")
                    print(f"        Bu ayarı siz yapmadıysanız sisteminizde adware veya")
                    print(f"        casus yazılım olabilir!")
                else:
                    print(f"     ✅ Proxy devre dışı")

            # Öneriler
            if score != "İYİ":
                print(f"\n  {'─' * 60}")
                print(f"  💡 ÖNERİLER:")

                if port_data.get("critical_count", 0) > 0:
                    print(f"     • Kritik portları kapatın veya modemden internete")
                    print(f"       yönlendirilmediğinden emin olun")
                if port_data.get("hidden_ports"):
                    print(f"     • Gizli portlar tespit edildi — tam antivirüs taraması yapın")
                    print(f"       ve şüpheli işlemleri kontrol edin")
                if not arp_data.get("safe", True):
                    print(f"     • ARP tablosunu temizleyin: arp -d *")
                    print(f"       ve ağdaki bilinmeyen cihazları kontrol edin")
                if not dhcp_data.get("safe", True):
                    print(f"     • Ağdaki bilinmeyen cihazları kontrol edin")
                    print(f"       ve modeminizin DHCP ayarlarını doğrulayın")
                if proxy_data.get("enabled", False):
                    print(f"     • Proxy ayarını kontrol edin — tanımadığınız bir adresse kaldırın")
                    print(f"     • Antivirüs taraması yapın (adware/casus yazılım kontrolü)")

            print(f"\n  {'═' * 60}")

    def _fmt_check_ssl_expiry_bulk(self, data):
        if isinstance(data, list):
            print(f"\n  🔐 SSL Sertifika Durumları ({len(data)} site):")
            print(f"    {'Domain':<30} {'Kalan Gün':<12} {'Bitiş Tarihi'}")
            print(f"    {'-'*55}")
            for cert in data:
                days = cert.get('days_remaining', -1)
                icon = "" if days > 30 else "⚠️" if days > 7 else "🚨" if days > 0 else "❌"
                domain = cert.get('domain', '?')
                expires = cert.get('valid_until', cert.get('error', '?'))
                print(f"    {icon} {domain:<28} {days:<12} {expires}")

    # ═══════════════════════════════════════════
    #  VPN / PROXY TOOLS
    # ═══════════════════════════════════════════
    def _fmt_vpn_create(self, data):
        if isinstance(data, dict):
            name = data.get("name", "?")
            connected = data.get("connected", False)
            tried = data.get("tried_count", 0)
            country = data.get("server", {}).get("country", data.get("country", "?"))

            if connected:
                server = data.get("server", {})
                creds = data.get("credentials", {})
                print(f"\n  ✅ VPN Bağlandı: {name}")
                print(f"     Sunucu:     {server.get('ip', '?')} ({country})")
                print(f"     Hız:        {server.get('speed_mbps', '?')} Mb/s")
                print(f"     Ping:       {server.get('ping', '?')} ms")
                print(f"     Protokol:   L2TP/IPsec")
                print(f"     Deneme:     {tried}. sunucuda başarılı")
                print(f"     Kullanıcı:  {creds.get('username', 'vpn')}")
                print(f"     Şifre:      {creds.get('password', 'vpn')}")
                print(f"     PSK:        {creds.get('psk', 'vpn')}")
            else:
                print(f"\n  ⚠️ VPN Bağlantısı Başarısız: {name}")
                print(f"     Ülke:       {country}")
                print(f"     Denenen:    {tried} sunucu")
                print(f"\n  💡 Öneriler:")
                print(f"     • L2TP portu (UDP 500/4500) engellenmiş olabilir")
                print(f"     • Farklı ülke deneyin")
                print(f"     • IKEv2 veya SSTP protokolü deneyin")
                print(f"     • Modem/firewall ayarlarını kontrol edin")


    def _fmt_vpn_status(self, data):
        if isinstance(data, dict):
            connected = data.get('connected', False)
            if connected:
                profiles = data.get('profiles', [])
                print(f"\n  🔒 VPN Bağlı: {', '.join(profiles)}")
            else:
                print(f"\n  🔓 VPN bağlantısı yok")

    def _fmt_vpn_list_profiles(self, data):
        if isinstance(data, list):
            print(f"\n  📋 VPN Profilleri ({len(data)} adet):")
            for p in data:
                if isinstance(p, dict):
                    print(f"    🔑 {p.get('Name', '?')} → {p.get('ServerAddress', '?')} ({p.get('TunnelType', '?')})")
                else:
                    print(f"    🔑 {p}")

    def _fmt_proxy_status(self, data):
        if isinstance(data, dict):
            enabled = data.get('enabled', False)
            addr = data.get('proxy_address', '')
            if enabled:
                print(f"\n  🔀 Proxy Aktif: {addr}")
            else:
                print(f"\n  ⭕ Proxy devre dışı")

    def _fmt_proxy_test(self, data):
        if isinstance(data, dict):
            print(f"\n  🔀 Proxy Test:")
            print(f"     Proxy:      {data.get('proxy', '?')}")
            print(f"     Yanıt Süresi: {data.get('response_time', '?')}s")

    # ═══════════════════════════════════════════
    #  MONITORING TOOLS
    # ═══════════════════════════════════════════

    def _fmt_bandwidth_monitor(self, data):
        if isinstance(data, dict):
            print(f"\n  📊 Bant Genişliği ({data.get('duration_sec', '?')}s izleme):")
            print(f"     ↑ Gönderme:    {data.get('sent_kb_s', 0)} KB/s ({data.get('sent_during', '?')})")
            print(f"     ↓ Alma:        {data.get('recv_kb_s', 0)} KB/s ({data.get('recv_during', '?')})")
            print(f"     Toplam Giden:  {data.get('sent_total_mb', 0)} MB")
            print(f"     Toplam Gelen:  {data.get('recv_total_mb', 0)} MB")

            apps = data.get("app_usage", [])

            dests = data.get("destinations", [])
            if dests:
                print(f"\n     🌐 Aktif Hedefler:")
                print(f"       {'Hedef':<30} {'Sağlayıcı':<22} {'Servis':<8} {'Bağ.':<5} {'Konum'}")
                print(f"       {'-' * 80}")
                for d in dests:
                    tag = d.get('tag', '') or d.get('hostname', '?')
                    provider = d.get('provider', '')
                    if len(tag) > 28:
                        tag = tag[:26] + ".."
                    if len(provider) > 20:
                        provider = provider[:18] + ".."
                    loc = d.get('location', '')
                    print(f"       {tag:<30} {provider:<22} {d.get('service', '?'):<8} {d.get('count', 0):<5} {loc}")


    def _fmt_bandwidth_by_process(self, data):
        if isinstance(data, list):
            print(f"\n   Ağ Kullanan Uygulamalar ({len(data)} adet):")
            print(f"    {'Uygulama':<25} {'Bağlantı':<12} {'PID'}")
            print(f"    {'-'*45}")
            for p in data[:15]:
                print(f"    {p.get('name','?'):<25} {p.get('connections',0):<12} {p.get('pid','?')}")

    def _fmt_network_topology_map(self, data):
        if isinstance(data, dict):
            this = data.get('this_device', {})
            gw = data.get('gateway', '?')
            devices = data.get('devices', [])

            print(f"\n  🗺️  Ağ Topolojisi:")
            print(f"     Bu Cihaz: {this.get('hostname', '?')} ({this.get('ip', '?')})")
            print(f"     Gateway:  {gw}")
            print(f"     Cihazlar: {len(devices)} adet")
            print(f"\n    {'IP Adresi':<20} {'MAC Adresi':<20} {'Tür'}")
            print(f"    {'-'*50}")
            for d in devices:
                print(f"    {d.get('ip',''):<20} {d.get('mac',''):<20} {d.get('type','')}")

    def _fmt_list_routes(self, data):
        if isinstance(data, list):
            print(f"\n  🛤  Yönlendirme Tablosu ({len(data)} kayıt):")
            print(f"    {'Hedef':<18} {'Maske':<18} {'Gateway':<18} {'Metrik'}")
            print(f"    {'-'*65}")
            for r in data:
                print(f"    {r.get('destination',''):<18} {r.get('netmask',''):<18} {r.get('gateway',''):<18} {r.get('metric','')}")

    def _fmt_packet_capture(self, data):
        if isinstance(data, dict):
            print(f"\n  📡 Paket Yakalama Sonuçları ({data.get('duration_sec', '?')}s):")
            print(f"     Gönderilen:  {data.get('total_sent', '?')} ({data.get('packets_sent', 0)} paket)")
            print(f"     Alınan:      {data.get('total_recv', '?')} ({data.get('packets_recv', 0)} paket)")
            print(f"     Benzersiz IP: {data.get('unique_ips', 0)}")
            print(f"     Uygulamalar:  {data.get('unique_processes', 0)}")

            conns = data.get("connections", [])
            if conns:
                print(f"\n     Bağlantı Detayları:")
                print(f"       {'Uygulama':<20} {'Uzak IP:Port':<28} {'Görülme':<10} {'Süre'}")
                print(f"       {'-' * 70}")
                for c in conns:
                    remote = f"{c.get('remote_ip', '?')}:{c.get('remote_port', '?')}"
                    proc = c.get('process', '?')
                    count = c.get('count', 0)
                    first = c.get('first_seen', 0)
                    last = c.get('last_seen', 0)
                    duration = f"{last - first}s" if last > first else "anlık"
                    print(f"       {proc:<20} {remote:<28} {count:<10} {duration}")
    def _fmt_discover_shared_folders(self, data):
        if isinstance(data, list):
            print(f"\n  📂 Paylaşılan Kaynaklar ({len(data)} adet):")
            for s in data:
                icon = "📁" if s.get('type') == 'Disk' else "🖨️"
                print(f"    {icon} {s.get('name', '?')} ({s.get('type', '?')})")


    # ═══════════════════════════════════════════
    #  HTTP TOOLS
    # ═══════════════════════════════════════════

    def _fmt_http_request(self, data):
        if isinstance(data, dict):
            status = data.get('status_code', 0)
            icon = "" if 200 <= status < 400 else "⚠️"
            print(f"\n  {icon} HTTP Yanıt:")
            print(f"     Durum:     HTTP {status}")
            print(f"     Süre:      {data.get('response_time', '?')}s")
            print(f"     Boyut:     {data.get('content_length', '?')} byte")
            body = data.get('body_preview', '')
            if body:
                print(f"     Önizleme:  {body[:150]}...")

    def _fmt_whois_lookup(self, data):
        if isinstance(data, dict):
            print(f"\n   WHOIS: {data.get('domain', '?')}")
            print(f"     Kayıt Tarihi: {data.get('registered', '?')}")
            print(f"     Bitiş Tarihi: {data.get('expires', '?')}")
            print(f"     Güncellenme:  {data.get('updated', '?')}")
            print(f"     Registrar:    {data.get('registrar', '?')}")
            ns = data.get('nameservers', [])
            if ns:
                print(f"     NS:           {', '.join(ns[:3])}")

    def _fmt_check_ssl_expiry(self, data):
        return self._fmt_ssl_certificate_check(data)

    def _fmt_http_headers(self, data):
        if isinstance(data, dict):
            headers = data.get('headers', {})
            print(f"\n   HTTP Headers: {data.get('url', '?')} ({len(headers)} adet)")
            print(f"    {'-'*55}")
            for k, v in headers.items():
                print(f"    {k:<25} {v[:50]}")

    def _fmt_ip_geolocation(self, data):
        if isinstance(data, dict):
            print(f"\n  📍 IP Konum: {data.get('ip', '?')}")
            print(f"     Şehir:     {data.get('city', '?')}")
            print(f"     Bölge:     {data.get('region', '?')}")
            print(f"     Ülke:      {data.get('country', '?')}")
            print(f"     ISP:       {data.get('org', '?')}")
            print(f"     Koordinat: {data.get('loc', '?')}")

    def _fmt_dns_propagation_check(self, data):
        if isinstance(data, list):
            print(f"\n  🌐 DNS Yayılım Durumu ({len(data)} sunucu):")
            print(f"    {'DNS Sunucu':<15} {'IP':<18} {'Sonuç'}")
            print(f"    {'-'*55}")
            for r in data:
                ips = ", ".join(r.get('resolved_ips', []))
                print(f"    {r.get('dns_server','?'):<15} {r.get('server_ip','?'):<18} {ips or '-'}")

    def _fmt_check_website_technologies(self, data):
        if isinstance(data, dict):
            techs = data.get('technologies', [])
            print(f"\n  🔧 Site Teknolojileri: {data.get('url', '?')}")
            if techs:
                for t in techs:
                    print(f"    ⚙️  {t.get('name', '?')}: {t.get('value', '?')}")
            else:
                print(f"    Tespit edilen teknoloji yok.")