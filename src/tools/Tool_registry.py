"""
ChromaDB Araç Veritabanı — Tüm modüllerdeki araçlar
Her aracın zengin açıklaması ve kullanıcı ifade kalıpları var.
intfloat/multilingual-e5-base embedding modeli ile kullanılır.
"""

TOOL_REGISTRY = [
    # ╔══════════════════════════════════════════════════════════════════╗
    # ║  DOSYA İŞLEMLERİ (file_operations) — v2 Dinamik                 ║
    # ║  Her ID = FileOperations.py'deki gerçek metot adı               ║
    # ╚══════════════════════════════════════════════════════════════════╝
    # ── ARAMA ──
    {
        "id": "search_files",
        "name": "Dosya Ara",
        "module": "file_operations",
        "params": "name, extension, directory, limit",
        "desc": "Bilgisayardaki dosyaları isim, uzantı veya dizin bazında arar ve bulur.",
        "output": "data: [{name, extension, full_path, size_bytes}]",
        "rich_info": (
            "search_files: Dosya arar, her dosyanın TÜM bilgilerini döner.\n"
            "Çıktıda zaten VAR: name, extension, full_path, size_bytes, modified_at\n"
            "ÖNEMLİ: Boyut (size_bytes) zaten sonuçta var — ayrı boyut hesaplama GEREKMEZ.\n"
            "ÖNEMLİ: extension filtresi yapar, name boş bırakılabilir.\n"
            "ÖNEMLİ: Alt klasörleri de tarar (recursive).\n"
            "ÖRNEK: '.py dosyalarını bul ve boyutlarını listele'\n"
            "→ TEK ADIM: search_files(directory: 'projeler', extension: '.py')\n"
            "  Boyut zaten size_bytes alanında döner, ikinci adıma gerek yok."
        ),
        "keywords": (
            "dosya ara, dosya bul, dosyayı bul, dosya nerede, dosyayı ara, "
            "config.json bul, test.txt ara, .py dosyalarını bul, "
            "klasördeki dosyaları ara, dizinde ara, dosya konumunu bul, "
            "bu dosyayı bul, nerede bu dosya, dosya var mı, "
            "bul dosyayı, dosya ismiyle ara, uzantıya göre ara"
        ),
    },
    {
        "id": "search_directories",
        "name": "Klasör Ara",
        "module": "file_operations",
        "params": "name, limit",
        "desc": "Bilgisayardaki klasörleri isimlerine göre arar ve bulur.",
        "keywords": (
            "klasör ara, klasör bul, dizin ara, dizin bul, "
            "klasör nerede, bu klasörü bul, dizini bul, "
            "folder ara, folder bul, klasör yolunu bul"
        ),
    },
    # ── OKUMA / YAZMA ──
    {
        "id": "read_file",
        "name": "Dosya Oku",
        "module": "file_operations",
        "params": "path",
        "desc": "Dosyanın içeriğini okur ve gösterir. Tam yol veya sadece dosya adı verilebilir (ör: test.txt).",
        "output": "content: dosya içeriği (string)",
        "rich_info": (
            "read_file: Dosya içeriğini string olarak döner.\n"
            "Çıktı: content alanında dosyanın tüm metni.\n"
            "ÖNEMLİ: Çıktıyı find_in_text ile filtreleyebilirsin.\n"
            "ÖRNEK: 'config.txt oku URL bul'\n"
            "→ t1: read_file(path: 'config.txt')\n"
            "→ t2: find_in_text(text: '$t1.output', pattern: 'url')"
        ),
        "keywords": (
            "dosya oku, dosya aç, metin oku, içerik oku, dosya göster, "
            "dosyasındaki, dosyadan, dosyadaki, içindeki, "
            "config.txt oku, servers.txt oku, log.txt oku, "
            "dosya içeriğini al, dosyayı aç ve oku, dosya içeriğini göster, "
            "dosyayı oku, bu dosyayı oku, içeriğini göster"
        ),
    },
    {
        "id": "write_file",
        "name": "Dosyaya Yaz",
        "module": "file_operations",
        "params": "path, content",
        "desc": "Dosyaya metin yazar. Dosya varsa üzerine yazar, yoksa oluşturur.",
        "keywords": (
            "dosya yaz, dosyaya yaz, kaydet, metin yaz, üzerine yaz, "
            "sonucu yaz, sonucu kaydet, çıktıyı yaz, raporu kaydet, "
            "log.txt'ye yaz, result.txt'ye yaz, dosyaya kaydet, "
            "sonuçları dosyaya yaz, çıktıyı kaydet, metin kaydet"
        ),
    },
    {
        "id": "create_file",
        "name": "Dosya Oluştur",
        "module": "file_operations",
        "params": "path, content",
        "desc": "Yeni bir dosya oluşturur ve opsiyonel olarak içerik yazar. Dosya zaten varsa hata verir.",
        "keywords": (
            "dosya oluştur, yeni dosya, yeni dosya oluştur, "
            "dosya yarat, boş dosya oluştur"
        ),
    },
    {
        "id": "append_to_file",
        "name": "Dosyaya Ekle",
        "module": "file_operations",
        "params": "path, content",
        "desc": "Mevcut dosyanın sonuna içerik ekler (var olan içeriği silmez).",
        "keywords": (
            "dosyaya ekle, sonuna ekle, ek yaz, dosya sonuna, "
            "append, ekle, içerik ekle, satır ekle, dosyanın sonuna yaz"
        ),
    },
    # ── İÇERİK İŞLEMLERİ ──
    {
        "id": "find_in_text",
        "name": "Metin İçinde Ara",
        "module": "file_operations",
        "params": "text, pattern",
        "desc": "Metin içinde adres (IP veya domain), URL, e-posta veya özel kalıp arar.",
        "output": "data: [bulunan_adresler] (string listesi)",
        "rich_info": (
            "find_in_text: Metin içinde belirli türde veri bulur.\n"
            "pattern değerleri: ip, domain, address, url, email veya custom regex\n"
            "Çıktı: data alanında bulunan öğelerin listesi (string[])\n"
            "'address' → hem IP hem domain otomatik aranır.\n"
            "ÖNEMLİ: text parametresine $tN.output verilebilir (read_file çıktısı).\n"
            "ÖNEMLİ: Geçersiz satırları (selam, naber gibi) otomatik filtreler.\n"
            "ÖRNEK: 'dosyadaki IP adresleri'\n"
            "→ find_in_text(text: '$t1.output', pattern: 'ip')"
        ),
        "keywords": (
            "metin ara, bul, filtrele, pattern, kelime ara, içinde bul, ayıkla, çıkar, "
            "URL bul, URL ayıkla, IP bul, IP ayıkla, adres bul, "
            "içinden çıkar, içindeki URL, dosyadaki IP, "
            "metin içinde ara, regex, eşleşme bul, "
            "dosyasındaki URL, dosyasındaki IP, linkleri bul, linkleri ayıkla, "
            "metinden URL çıkar, metinden IP çıkar, "
            "txt içindeki URL, config içindeki adres, "
            "olanları bul, varsa bul, içinde ara, içinde varsa, "
            "metin filtrele, kelime bul, satır bul, pattern ara, "
            "e-posta bul, email bul, domain bul, adres ara, "
            "içindeki adres, içindeki adrese, sunucu bul, host bul, site bul"
        ),
    },
    {
        "id": "search_in_files",
        "name": "Dosyalarda Metin Ara",
        "module": "file_operations",
        "params": "query, directory",
        "desc": "Birden fazla dosyanın içinde belirtilen metni arar, grep benzeri arama yapar.",
        "keywords": (
            "dosyalarda ara, dosya içinde ara, grep, metin tara, "
            "içerik ara, dosyalarda kelime bul, dosya içinde bul, "
            "tüm dosyalarda ara, hata ara, kod içinde ara"
        ),
    },
    {
        "id": "replace_text",
        "name": "Metin Bul ve Değiştir",
        "module": "file_operations",
        "params": "path, old_text, new_text",
        "desc": "Dosya içindeki bir metni bulup başka bir metinle değiştirir.",
        "keywords": (
            "bul değiştir, metin değiştir, replace, find replace, "
            "değiştir, yerine yaz, güncelle, metni değiştir, "
            "find and replace, metin bul değiştir"
        ),
    },
    # ── KOPYALAMA / TAŞIMA ──
    {
        "id": "copy_file",
        "name": "Dosya Kopyala",
        "module": "file_operations",
        "params": "source, destination",
        "desc": "Dosyayı kopyalar. Kaynak olarak dosya adı yeterli, otomatik bulur.",
        "keywords": (
            "dosya kopyala, kopyala, yedekle, çoğalt, "
            "dosyayı kopyala, buraya kopyala, şuraya kopyala, "
            "dosya yedeği al, kopya oluştur"
        ),
    },
    {
        "id": "move_file",
        "name": "Dosya Taşı",
        "module": "file_operations",
        "params": "source, destination",
        "desc": "Dosyayı taşır. Kaynak olarak dosya adı yeterli, otomatik bulur.",
        "keywords": (
            "dosya taşı, taşı, aktar, dosyayı taşı, "
            "buraya taşı, şuraya taşı, dosyayı aktar"
        ),
    },
    # ── SİLME ──
    {
        "id": "delete_file",
        "name": "Dosya Sil",
        "module": "file_operations",
        "params": "path",
        "desc": "Dosyayı kalıcı olarak siler. Dosya adı veya tam yol verilebilir.",
        "keywords": (
            "dosya sil, sil, kaldır, dosyayı sil, bu dosyayı sil, dosya kaldır, temizle"
        ),
    },
    {
        "id": "delete_directory",
        "name": "Klasör Sil",
        "module": "file_operations",
        "params": "path",
        "desc": "Klasör ve tüm içeriğini kalıcı olarak siler.",
        "keywords": (
            "klasör sil, dizin sil, klasörü sil, dizini sil, "
            "klasör kaldır, klasörü temizle, rmdir"
        ),
    },
    # ── OLUŞTURMA ──
    {
        "id": "create_directory",
        "name": "Klasör Oluştur",
        "module": "file_operations",
        "params": "path",
        "desc": "Yeni klasör/dizin oluşturur.",
        "keywords": (
            "klasör oluştur, dizin oluştur, yeni klasör, yeni dizin, "
            "klasör yap, folder oluştur, mkdir"
        ),
    },
    # ── YENİDEN ADLANDIRMA ──
    {
        "id": "rename",
        "name": "Yeniden Adlandır",
        "module": "file_operations",
        "params": "path, new_name",
        "desc": "Dosya veya klasörü yeniden adlandırır.",
        "keywords": (
            "yeniden adlandır, ad değiştir, isim değiştir, rename, "
            "dosya adını değiştir, klasör adını değiştir, "
            "ismini değiştir, adını değiştir"
        ),
    },
    # ── BİLGİ ──
    {
        "id": "get_file_info",
        "name": "Dosya Bilgisi",
        "module": "file_operations",
        "params": "path",
        "desc": "Dosya hakkında detaylı bilgi gösterir: boyut, tarih, yol, uzantı.",
        "rich_info": (
            "get_file_info: TEK dosyanın detaylı bilgisini döner.\n"
            "Çıktı: {name, extension, full_path, size_bytes, modified_at, created_at}\n"
            "FARK: search_files birden çok dosya arar, bu metot TEK dosyanın bilgisini verir.\n"
            "ÖRNEK: 'rapor.txt dosya bilgilerini getir'\n"
            "→ TEK ADIM: get_file_info(path: 'rapor.txt')"
        ),
        "keywords": (
            "dosya bilgisi, dosya detayı, dosya boyutu, ne zaman oluşturuldu, "
            "dosya özellikleri, dosya bilgi, dosya nitelik, "
            "dosya hakkında, boyutu ne, ne kadar"
        ),
    },
    {
        "id": "find_directory_size",
        "name": "Klasör Boyutu",
        "module": "file_operations",
        "params": "path",
        "desc": "Bir klasörün toplam boyutunu ve dosya sayısını hesaplar.",
        "keywords": (
            "klasör boyutu, dizin boyutu, ne kadar yer kaplıyor, "
            "toplam boyut, folder boyut, klasör ne kadar"
        ),
    },
    {
        "id": "count_lines_words",
        "name": "Satır ve Kelime Say",
        "module": "file_operations",
        "params": "path",
        "desc": "Dosyadaki satır, kelime ve karakter sayısını gösterir.",
        "keywords": (
            "satır sayısı, kelime sayısı, kaç satır, kaç kelime, "
            "dosya istatistik, wc, satır say, kelime say"
        ),
    },
    # ── LİSTELEME / AĞAÇ ──
    {
        "id": "list_directory_contents",
        "name": "Klasör İçeriği Listele",
        "module": "file_operations",
        "params": "path, extension",
        "desc": "Klasördeki dosya ve alt dizinleri listeler. extension ile uzantıya göre filtrele (.py, .txt).",
        "output": "data: {directory: yol, files: [{name, extension, full_path, size_bytes}], subdirs: [{name, file_count}]}",
        "rich_info": (
            "list_directory_contents: Sadece belirtilen klasörü listeler (alt klasörlere inmez).\n"
            "Çıktı: {directory: yol, files: [...], subdirs: [...]}\n"
            "extension parametresi: '.py' verilirse sadece .py dosyalarını döner.\n"
            "Her dosyada VAR: name, extension, full_path, size_bytes\n"
            "FARK: search_files alt klasörlere de iner, bu metot sadece o dizini listeler.\n"
            "ÖRNEK: 'projeler klasörünü listele'\n"
            "→ list_directory_contents(path: 'projeler')\n"
            "ÖRNEK: 'projeler klasöründeki .txt dosyalarını listele'\n"
            "→ list_directory_contents(path: 'projeler', extension: '.txt')"
        ),
        "keywords": (
            "dosya listele, klasör göster, dizin listele, dosyaları göster, "
            "klasördeki dosyalar, dizindeki dosyalar, içindekileri göster, "
            "klasör içeriği, ne var bu klasörde, dosyaları listele, ls, "
            "uzantılı dosyalar, .py dosyaları, .txt dosyaları, filtrele"
        ),
    },
    {
        "id": "get_directory_tree",
        "name": "Dizin Ağacı",
        "module": "file_operations",
        "params": "path, max_depth",
        "desc": "Klasör yapısını ağaç şeklinde gösterir (alt klasörler dahil).",
        "keywords": (
            "dizin ağacı, klasör ağacı, tree, klasör yapısı, "
            "alt klasörler, dizin yapısı, klasör hiyerarşisi"
        ),
    },
    # ── DOSYA BULMA ──
    {
        "id": "find_recently_modified",
        "name": "Son Değiştirilen Dosyalar",
        "module": "file_operations",
        "params": "days, extension",
        "desc": "Son belirtilen gün içinde değiştirilen dosyaları bulur.",
        "keywords": (
            "son değiştirilen, son değişen, yeni dosyalar, "
            "son 3 günde değişen, son bir haftada, yakın zamanda değişen, "
            "en son değiştirilen dosyalar, recent files"
        ),
    },
    {
        "id": "find_empty_files",
        "name": "Boş Dosyaları Bul",
        "module": "file_operations",
        "params": "directory",
        "desc": "İçeriği boş olan (0 byte) dosyaları bulur.",
        "keywords": (
            "boş dosya, boş dosyaları bul, 0 byte, içi boş, "
            "boş olan dosyalar, hiçbir şey yazılmamış"
        ),
    },
    {
        "id": "find_empty_directories",
        "name": "Boş Klasörleri Bul",
        "module": "file_operations",
        "params": "",
        "desc": "Hiçbir dosya veya alt klasör içermeyen boş klasörleri bulur.",
        "keywords": (
            "boş klasör, boş dizin, boş klasörleri bul, "
            "içi boş klasörler, gereksiz klasörler"
        ),
    },
    {
        "id": "find_largest_files",
        "name": "En Büyük Dosyalar",
        "module": "file_operations",
        "params": "directory, min_size_mb, limit",
        "desc": "En büyük dosyaları boyutlarına göre sıralayarak bulur.",
        "keywords": (
            "büyük dosya, en büyük, 1GB üstü, yer kaplayan, "
            "büyük dosyaları bul, ağır dosyalar, disk dolduran"
        ),
    },
    {
        "id": "find_small_files",
        "name": "Küçük Dosyaları Bul",
        "module": "file_operations",
        "params": "max_size_mb",
        "desc": "Boyutu belirtilen MB değerinin altında kalan dosyaları bulur. Sadece boyut filtresi için kullanılır.",
        "keywords": (
            "küçük dosya, küçük dosyaları bul, 1MB altı, ufak dosyalar, "
            "az yer kaplayan, boyutu küçük, boyut altı, MB altı, "
            "küçük boyutlu dosyalar, en küçük dosyalar"
        ),
    },
    {
        "id": "find_duplicate_names",
        "name": "Aynı İsimli Dosyaları Bul",
        "module": "file_operations",
        "params": "name, extension",
        "desc": "Aynı isme sahip birden fazla konumda olan dosyaları bulur.",
        "keywords": (
            "aynı isim, duplicate, kopya dosya, tekrar eden, "
            "birden fazla, çift dosya, aynı dosya"
        ),
    },
    {
        "id": "compare_files",
        "name": "Dosyaları Karşılaştır",
        "module": "file_operations",
        "params": "file_path_1, file_path_2",
        "desc": "İki dosyayı karşılaştırır: aynı mı farklı mı kontrol eder.",
        "keywords": (
            "dosya karşılaştır, karşılaştır, fark, diff, aynı mı, "
            "iki dosya, dosyalar aynı mı, dosya farkı"
        ),
    },
    {
        "id": "get_extension_stats",
        "name": "Uzantı İstatistikleri",
        "module": "file_operations",
        "params": "directory",
        "desc": "Klasördeki dosyaları uzantılarına göre gruplar ve istatistik gösterir.",
        "keywords": (
            "uzantı istatistik, dosya türleri, kaç tane py, "
            "dosya dağılımı, uzantı raporu, uzantı sayısı"
        ),
    },
    # ╔══════════════════════════════════════════════════════════════════╗
    # ║  AĞ İŞLEMLERİ — TEMEL (network_operations/basic)               ║
    # ╚══════════════════════════════════════════════════════════════════╝
    {
        "id": "get_network_info",
        "name": "Ağ Bilgisi",
        "module": "network_operations",
        "params": "",
        "desc": "Bilgisayarın ağ bilgilerini gösterir: IP adresi, ağ maskesi, gateway, DNS.",
        "keywords": (
            "ağ bilgisi, ağ bilgilerimi göster, network info, "
            "IP adresim, ağ ayarlarım, ipconfig, ağ durumu, "
            "bağlantı bilgileri, ağ yapılandırması"
        ),
    },
    {
        "id": "get_public_ip",
        "name": "Dış IP Adresi",
        "module": "network_operations",
        "params": "",
        "desc": "Bilgisayarın internetteki dış (public) IP adresini gösterir.",
        "keywords": (
            "dış IP, public IP, internet IP, gerçek IP, "
            "dış IP adresim ne, WAN IP, IP adresim nedir"
        ),
    },
    {
        "id": "list_network_adapters",
        "name": "Ağ Adaptörleri Listele",
        "module": "network_operations",
        "params": "",
        "desc": "Bilgisayardaki tüm ağ adaptörlerini (WiFi, Ethernet, VPN) listeler.",
        "keywords": (
            "ağ adaptörleri, network adapter, NIC, "
            "adaptör listele, ağ kartları, ağ arayüzleri"
        ),
    },
    {
        "id": "toggle_network_adapter",
        "name": "Adaptör Aç/Kapat",
        "module": "network_operations",
        "params": "adapter_name, action",
        "desc": "Ağ adaptörünü etkinleştirir veya devre dışı bırakır.",
        "keywords": (
            "adaptör kapat, adaptör aç, WiFi kapat, WiFi aç, "
            "ethernet kapat, ağ kartını kapat, disable adapter"
        ),
    },
    {
        "id": "set_static_ip",
        "name": "Statik IP Ayarla",
        "module": "network_operations",
        "params": "adapter_name, ip_address, subnet_mask, gateway",
        "desc": "Ağ adaptörüne sabit (statik) IP adresi atar.",
        "keywords": (
            "statik IP, sabit IP, IP ayarla, IP değiştir, "
            "manual IP, elle IP ver, IP adresi ayarla"
        ),
    },
    {
        "id": "set_dhcp",
        "name": "DHCP Moduna Geç",
        "module": "network_operations",
        "params": "adapter_name",
        "desc": "Ağ adaptörünü otomatik IP alma (DHCP) moduna geçirir.",
        "keywords": (
            "DHCP, otomatik IP, DHCP modu, dinamik IP, "
            "IP otomatik al, DHCP aç, IP sıfırla"
        ),
    },
    {
        "id": "ip_conflict_check",
        "name": "IP Çakışması Kontrol",
        "module": "network_operations",
        "params": "",
        "desc": "Ağda IP adresi çakışması olup olmadığını kontrol eder.",
        "keywords": (
            "IP çakışması, IP conflict, aynı IP, çakışma var mı, "
            "duplicate IP, IP sorunu"
        ),
    },
    {
        "id": "subnet_calculator",
        "name": "Subnet Hesaplayıcı",
        "module": "network_operations",
        "params": "cidr",
        "desc": "Alt ağ hesaplaması yapar: kullanılabilir IP sayısı, ağ adresi, yayın adresi.",
        "keywords": (
            "subnet, alt ağ, CIDR, subnet mask, kaç IP, ağ hesapla, subnet calculator"
        ),
    },
    {
        "id": "list_arp_table",
        "name": "ARP Tablosu",
        "module": "network_operations",
        "params": "",
        "desc": "ARP tablosunu gösterir: IP-MAC adres eşleştirmeleri.",
        "keywords": (
            "ARP tablosu, ARP, IP-MAC, MAC adresleri, arp -a, ARP cache, ARP listesi"
        ),
    },
    {
        "id": "list_network_devices",
        "name": "Ağdaki Cihazları Listele",
        "module": "network_operations",
        "params": "",
        "desc": "Ağdaki aktif cihazların IP ve MAC adreslerini listeler.",
        "keywords": (
            "ağdaki cihazlar, cihaz listele, bağlı cihazlar, "
            "ağa kim bağlı, ağdaki IP'ler, ağdaki MAC'ler"
        ),
    },
    {
        "id": "wake_on_lan",
        "name": "Wake on LAN",
        "module": "network_operations",
        "params": "mac_address",
        "desc": "MAC adresi ile kapalı bir bilgisayarı uzaktan açar (Wake on LAN).",
        "keywords": (
            "wake on lan, WOL, uzaktan aç, bilgisayarı aç, PC'yi uyandır, magic packet"
        ),
    },
    {
        "id": "scan_all_devices",
        "name": "Ağ Tarama",
        "module": "network_operations",
        "params": "",
        "desc": "Ağdaki tüm cihazları tarar: IP, MAC, hostname, açık portlar, üretici bilgisi.",
        "keywords": (
            "ağ tara, ağı tara, network scan, cihaz tara, "
            "ağdaki cihazları tara, IP tara, detaylı tarama, "
            "ağ keşfi, ağ haritası, kim bağlı"
        ),
    },
    # ╔══════════════════════════════════════════════════════════════════╗
    # ║  AĞ İŞLEMLERİ — BAĞLANTI (network_operations/connectivity)     ║
    # ╚══════════════════════════════════════════════════════════════════╝
    {
        "id": "ping",
        "name": "Ping At",
        "module": "network_operations",
        "params": "host, count",
        "desc": "Hedef IP veya domain adresine ping atarak erişilebilirliği ve gecikmeyi test eder.",
        "output": "data: {min_ms, max_ms, avg_ms, packet_loss}",
        "keywords": (
            "ping, ping at, erişim testi, gecikme, latency, ulaşılabilirlik, "
            "ayakta mı, çalışıyor mu, erişilebilir mi, cevap veriyor mu, "
            "sunucu kontrol, bağlantı testi, yanıt veriyor mu, "
            "ping gönder, paket gönder, sunucu erişimi"
        ),
    },
    {
        "id": "traceroute",
        "name": "Traceroute",
        "module": "network_operations",
        "params": "host",
        "desc": "Hedefe giden ağ yolunu ve her atlama noktasını gösterir.",
        "keywords": (
            "traceroute, tracert, yol izle, ağ yolu, hop, atlama, "
            "rota izle, hangi yoldan gidiyor, ağ rotası"
        ),
    },
    {
        "id": "visual_traceroute",
        "name": "Görsel Traceroute",
        "module": "network_operations",
        "params": "host",
        "desc": "Hedefe giden ağ yolunu harita üzerinde görselleştirir, ülke bazlı rota gösterir.",
        "keywords": (
            "görsel traceroute, harita, rota haritası, "
            "hangi ülkelerden geçiyor, yol haritası, rota analizi, "
            "coğrafi rota, visual traceroute"
        ),
    },
    {
        "id": "port_scan",
        "name": "Port Tara (Uzak)",
        "module": "network_operations",
        "params": "host, ports",
        "desc": "Uzak hedef IP üzerindeki açık portları tarar.",
        "keywords": (
            "port tara, port scan, açık port, portları tara, "
            "hedef port, uzak port tarama, nmap benzeri"
        ),
    },
    {
        "id": "check_port_usage",
        "name": "Port Kullanım Sorgula",
        "module": "network_operations",
        "params": "port",
        "desc": "Belirtilen portu hangi uygulamanın kullandığını gösterir.",
        "keywords": (
            "port kullanım, portu kim kullanıyor, port sorgula, "
            "8080 portu, port meşgul, port kimin"
        ),
    },
    {
        "id": "list_active_connections",
        "name": "Aktif Bağlantılar",
        "module": "network_operations",
        "params": "state",
        "desc": "Aktif ağ bağlantılarını ve dinlemedeki portları listeler.",
        "keywords": (
            "aktif bağlantılar, açık bağlantılar, netstat, "
            "dinlemedeki portlar, listening, bağlantı listesi, "
            "aktif oturumlar, ağ bağlantıları"
        ),
    },
    {
        "id": "speed_test",
        "name": "İnternet Hız Testi",
        "module": "network_operations",
        "params": "",
        "desc": "İnternet indirme ve yükleme hızını ölçer.",
        "keywords": (
            "hız testi, internet hızı, speed test, indirme hızı, "
            "yükleme hızı, bant genişliği testi, ne kadar hızlı"
        ),
    },
    {
        "id": "connection_quality_test",
        "name": "Bağlantı Kalitesi Testi",
        "module": "network_operations",
        "params": "",
        "desc": "İnternet bağlantısının kalitesini test eder: gecikme, jitter, paket kaybı.",
        "keywords": (
            "bağlantı kalitesi, bağlantı testi, jitter, paket kaybı, "
            "bağlantı stabilitesi, internet kalitesi, lag testi"
        ),
    },
    {
        "id": "check_website_status",
        "name": "Site Durumu Kontrol",
        "module": "network_operations",
        "params": "url",
        "desc": "Web sitesinin çalışıp çalışmadığını HTTP durum kodu ile kontrol eder.",
        "keywords": (
            "site durumu, çalışıyor mu, ayakta mı, erişilebilir mi, "
            "http durum, status code, site açık mı, site kapalı mı, "
            "web sitesi kontrol, erişim kontrolü"
        ),
    },
    {
        "id": "measure_response_time",
        "name": "Yanıt Süresi Ölç",
        "module": "network_operations",
        "params": "url",
        "desc": "Web sitesinin yanıt süresini milisaniye cinsinden ölçer.",
        "keywords": (
            "yanıt süresi, hız testi, response time, site hızı, "
            "gecikme ölç, ne kadar hızlı, sayfa yüklenme süresi"
        ),
    },
    # ╔══════════════════════════════════════════════════════════════════╗
    # ║  AĞ İŞLEMLERİ — DNS (network_operations/dns)                   ║
    # ╚══════════════════════════════════════════════════════════════════╝
    {
        "id": "dns_lookup",
        "name": "DNS Sorgula",
        "module": "network_operations",
        "params": "domain",
        "desc": "Domain adının IP adresini çözümler, DNS kayıtlarını sorgular.",
        "output": "data: {ip, records: [...]}",
        "keywords": (
            "dns, dns sorgula, IP adresi bul, domain çözümle, "
            "nslookup, dns kaydı, A kaydı, domain IP"
        ),
    },
    {
        "id": "dns_reverse",
        "name": "Ters DNS Sorgula",
        "module": "network_operations",
        "params": "ip_address",
        "desc": "IP adresinden domain adını bulur (reverse DNS).",
        "keywords": (
            "ters dns, reverse dns, IP'den domain, kime ait, IP sahibi, IP kimin"
        ),
    },
    {
        "id": "change_dns",
        "name": "DNS Değiştir",
        "module": "network_operations",
        "params": "preset, primary_dns, secondary_dns",
        "desc": "Ağ adaptörünün DNS sunucusunu değiştirir. Google, Cloudflare gibi hazır ayarlar var.",
        "keywords": (
            "dns değiştir, dns ayarla, google dns, cloudflare dns, "
            "DNS'i değiştir, DNS sunucu değiştir, 1.1.1.1, 8.8.8.8"
        ),
    },
    {
        "id": "reset_dns",
        "name": "DNS Sıfırla",
        "module": "network_operations",
        "params": "",
        "desc": "DNS ayarlarını varsayılana (DHCP) döndürür.",
        "keywords": (
            "dns sıfırla, dns reset, varsayılan dns, dns geri al, orijinal dns"
        ),
    },
    {
        "id": "flush_dns",
        "name": "DNS Önbellek Temizle",
        "module": "network_operations",
        "params": "",
        "desc": "DNS önbelleğini (cache) temizler.",
        "keywords": (
            "dns temizle, dns cache temizle, dns flush, "
            "dns önbellek, flushdns, dns cache sil"
        ),
    },
    {
        "id": "show_dns_cache",
        "name": "DNS Önbellek Göster",
        "module": "network_operations",
        "params": "",
        "desc": "DNS önbelleğindeki kayıtları gösterir.",
        "keywords": (
            "dns cache göster, dns önbellek listele, dns kayıtları, cache listesi"
        ),
    },
    {
        "id": "list_hosts",
        "name": "Hosts Dosyası Göster",
        "module": "network_operations",
        "params": "",
        "desc": "Windows hosts dosyasının içeriğini gösterir.",
        "keywords": (
            "hosts dosyası, hosts göster, hosts listele, engellenen siteler, hosts file"
        ),
    },
    {
        "id": "add_host_entry",
        "name": "Hosts Kaydı Ekle",
        "module": "network_operations",
        "params": "ip_address, domain",
        "desc": "Hosts dosyasına yeni bir domain-IP eşleştirmesi ekler. Site engelleme için kullanılır.",
        "keywords": (
            "hosts ekle, site engelle, domain engelle, "
            "site blokla, siteyi kapat, erişim engelle"
        ),
    },
    {
        "id": "remove_host_entry",
        "name": "Hosts Kaydı Sil",
        "module": "network_operations",
        "params": "domain",
        "desc": "Hosts dosyasından domain kaydını siler. Site engelini kaldırır.",
        "keywords": (
            "hosts sil, engel kaldır, site aç, "
            "engeli kaldır, bloğu kaldır, site engeli sil"
        ),
    },
    {
        "id": "dns_bypass_test",
        "name": "DNS Bypass Testi",
        "module": "network_operations",
        "params": "url, auto_switch",
        "desc": "Engelli siteye farklı DNS sunucularıyla erişmeyi dener.",
        "keywords": (
            "dns bypass, engelli site, erişilemiyor, site açılmıyor, "
            "farklı dns dene, engel aş, yasak site, siteye erişemiyorum"
        ),
    },
    {
        "id": "dns_propagation_check",
        "name": "DNS Yayılım Kontrolü",
        "module": "network_operations",
        "params": "domain",
        "desc": "Domain'in DNS kayıtlarının dünya genelindeki yayılım durumunu kontrol eder.",
        "keywords": (
            "dns yayılım, propagation, dns propagation, "
            "dns güncellenmiş mi, dns yayıldı mı"
        ),
    },
    # ╔══════════════════════════════════════════════════════════════════╗
    # ║  AĞ İŞLEMLERİ — HTTP (network_operations/http_tools)           ║
    # ╚══════════════════════════════════════════════════════════════════╝
    {
        "id": "http_request",
        "name": "HTTP İstek Gönder",
        "module": "network_operations",
        "params": "url, method, body, headers",
        "desc": "URL'ye HTTP GET/POST/PUT/DELETE isteği gönderir ve yanıtı döndürür.",
        "keywords": (
            "http get, http post, http istek, api çağır, "
            "web istek, url aç, sayfa çek, istek at, istek gönder, "
            "REST API, endpoint çağır, GET isteği, POST gönder"
        ),
    },
    {
        "id": "whois_lookup",
        "name": "WHOIS Sorgula",
        "module": "network_operations",
        "params": "domain",
        "desc": "Domain'in WHOIS bilgilerini sorgular: kayıt tarihi, sahibi, sunucu.",
        "keywords": (
            "whois, domain bilgi, alan adı sahibi, "
            "domain kimin, kayıt tarihi, whois sorgula"
        ),
    },
    {
        "id": "http_headers",
        "name": "HTTP Header Göster",
        "module": "network_operations",
        "params": "url",
        "desc": "Web sitesinin HTTP yanıt başlıklarını (headers) gösterir.",
        "keywords": (
            "http header, yanıt başlıkları, response headers, "
            "server header, header bilgisi"
        ),
    },
    {
        "id": "download_speed_test",
        "name": "İndirme Hız Testi",
        "module": "network_operations",
        "params": "url",
        "desc": "Belirtilen URL'den dosya indirerek indirme hızını ölçer.",
        "keywords": (
            "indirme hızı, download speed, dosya indirme hızı, indirme testi, hız ölç"
        ),
    },
    {
        "id": "check_website_technologies",
        "name": "Site Teknoloji Tespiti",
        "module": "network_operations",
        "params": "url",
        "desc": "Web sitesinin kullandığı teknolojileri tespit eder: sunucu, framework, CMS.",
        "keywords": (
            "teknoloji tespit, hangi teknoloji, site altyapısı, "
            "framework, CMS, sunucu yazılımı, wappalyzer"
        ),
    },
    {
        "id": "check_ssl_expiry",
        "name": "SSL Sertifika Kontrolü",
        "module": "network_operations",
        "params": "domain",
        "desc": "Web sitesinin SSL/TLS sertifikasının geçerlilik süresini kontrol eder.",
        "keywords": (
            "ssl sertifika, https sertifika, sertifika süresi, "
            "ssl kontrol, sertifika ne zaman bitiyor, TLS"
        ),
    },
    # ╔══════════════════════════════════════════════════════════════════╗
    # ║  AĞ İŞLEMLERİ — İZLEME (network_operations/monitoring)         ║
    # ╚══════════════════════════════════════════════════════════════════╝
    {
        "id": "bandwidth_monitor",
        "name": "Bant Genişliği İzle",
        "module": "network_operations",
        "params": "duration_sec",
        "desc": "Ağ bant genişliğini ve aktif bağlantıları gerçek zamanlı izler.",
        "keywords": (
            "bant genişliği, bandwidth, ağ izle, trafik izle, "
            "internet kullanımı, ağ trafiği, gerçek zamanlı izleme"
        ),
    },
    {
        "id": "bandwidth_by_process",
        "name": "Uygulama Bazlı Bant Genişliği",
        "module": "network_operations",
        "params": "",
        "desc": "Hangi uygulamaların ne kadar internet bant genişliği kullandığını gösterir.",
        "keywords": (
            "uygulama internet, hangi program, interneti kim kullanıyor, "
            "process bandwidth, uygulama trafik"
        ),
    },
    {
        "id": "top_bandwidth_consumers",
        "name": "En Çok İnternet Kullanan Uygulamalar",
        "module": "network_operations",
        "params": "limit",
        "desc": "En çok internet bant genişliği tüketen uygulamaları sıralar.",
        "keywords": (
            "en çok kullanan, top bandwidth, internet yiyen, "
            "en çok trafik, bant genişliği sıralama"
        ),
    },
    {
        "id": "network_topology_map",
        "name": "Ağ Topoloji Haritası",
        "module": "network_operations",
        "params": "",
        "desc": "Ağın topoloji haritasını çıkarır: cihazlar, bağlantılar, yapı.",
        "keywords": (
            "ağ haritası, topoloji, network map, ağ yapısı, ağ diyagramı, ağ şeması"
        ),
    },
    {
        "id": "packet_capture",
        "name": "Paket Yakalama",
        "module": "network_operations",
        "params": "duration_sec, filter_ip",
        "desc": "Ağ trafiğini yakalar ve paketleri analiz eder.",
        "keywords": (
            "paket yakala, packet capture, trafik yakala, sniff, "
            "ağ trafiği yakala, tcpdump, wireshark benzeri"
        ),
    },
    {
        "id": "netbios_scan",
        "name": "NetBIOS Tarama",
        "module": "network_operations",
        "params": "",
        "desc": "Ağdaki cihazların NetBIOS isimlerini tarar.",
        "keywords": (
            "netbios, bilgisayar isimleri, hostname tara, "
            "ağdaki isimler, bilgisayar adları"
        ),
    },
    {
        "id": "discover_shared_folders",
        "name": "Paylaşılan Klasörleri Bul",
        "module": "network_operations",
        "params": "target_ip",
        "desc": "Ağdaki paylaşılan klasörleri ve dosya paylaşımlarını keşfeder.",
        "keywords": (
            "paylaşılan klasör, shared folder, ağ paylaşımı, "
            "SMB paylaşım, dosya paylaşımı, paylaşımlar"
        ),
    },
    {
        "id": "list_routes",
        "name": "Yönlendirme Tablosu",
        "module": "network_operations",
        "params": "",
        "desc": "Yönlendirme tablosunu (routing table) gösterir.",
        "keywords": (
            "route tablosu, yönlendirme, routing table, route listele, ağ yönlendirme"
        ),
    },
    {
        "id": "add_route",
        "name": "Rota Ekle",
        "module": "network_operations",
        "params": "destination, mask, gateway",
        "desc": "Yönlendirme tablosuna yeni bir rota ekler.",
        "keywords": ("rota ekle, route add, yönlendirme ekle, statik rota, yeni rota"),
    },
    {
        "id": "delete_route",
        "name": "Rota Sil",
        "module": "network_operations",
        "params": "destination",
        "desc": "Yönlendirme tablosundan bir rotayı siler.",
        "keywords": ("rota sil, route delete, yönlendirme sil, rotayı kaldır"),
    },
    # ╔══════════════════════════════════════════════════════════════════╗
    # ║  AĞ İŞLEMLERİ — GÜVENLİK (network_operations/security)        ║
    # ╚══════════════════════════════════════════════════════════════════╝
    {
        "id": "firewall_list_rules",
        "name": "Firewall Kuralları Listele",
        "module": "network_operations",
        "params": "direction",
        "desc": "Windows Güvenlik Duvarı kurallarını listeler.",
        "keywords": (
            "firewall kuralları, güvenlik duvarı, firewall listele, "
            "gelen kurallar, giden kurallar, firewall rules"
        ),
    },
    {
        "id": "firewall_block_ip",
        "name": "IP Engelle (Firewall)",
        "module": "network_operations",
        "params": "ip_address",
        "desc": "Belirtilen IP adresini güvenlik duvarında engeller.",
        "keywords": (
            "IP engelle, IP blokla, firewall block, IP'yi engelle, erişimi engelle"
        ),
    },
    {
        "id": "firewall_allow_port",
        "name": "Port Aç (Firewall)",
        "module": "network_operations",
        "params": "port, protocol",
        "desc": "Windows Güvenlik Duvarında belirli bir port numarasına gelen/giden trafiğe izin verir.",
        "keywords": (
            "port aç, firewall port aç, port izin ver, portu aç, "
            "firewall'da port aç, port allow, güvenlik duvarı port, "
            "TCP port aç, UDP port aç, gelen bağlantı izin"
        ),
    },
    {
        "id": "firewall_remove_rule",
        "name": "Firewall Kuralı Sil",
        "module": "network_operations",
        "params": "rule_name",
        "desc": "Güvenlik duvarından belirtilen kuralı siler.",
        "keywords": (
            "firewall sil, kural sil, firewall kaldır, kuralı sil, rule delete"
        ),
    },
    {
        "id": "arp_spoof_detect",
        "name": "ARP Saldırı Tespiti",
        "module": "network_operations",
        "params": "",
        "desc": "Ağda ARP spoofing/poisoning saldırısı olup olmadığını tespit eder.",
        "keywords": (
            "ARP saldırı, ARP spoof, ARP poisoning, "
            "ağ saldırısı, MITM, ortadaki adam saldırısı"
        ),
    },
    {
        "id": "security_port_audit",
        "name": "Port Güvenlik Denetimi",
        "module": "network_operations",
        "desc": "Bilgisayardaki açık portları tarar, risk seviyesini analiz eder, gizli backdoor ve rootkit tespiti yapar.",
        "keywords": (
            "port denetimi, port güvenlik denetimi, güvenlik taraması, "
            "açık port tara, backdoor tespiti, rootkit tespiti, gizli port, "
            "tehlikeli port bul, port risk analizi, port kontrol, "
            "güvenlik açığı tara, açık port güvenlik kontrolü, "
            "bilgisayarım güvenli mi, portlarımı tara, "
            "zararlı yazılım port, şüpheli port"
        ),
    },
    {
        "id": "detect_rogue_dhcp",
        "name": "Sahte DHCP Tespiti",
        "module": "network_operations",
        "params": "",
        "desc": "Ağda sahte (rogue) DHCP sunucusu olup olmadığını tespit eder.",
        "keywords": (
            "sahte DHCP, rogue DHCP, DHCP saldırı, DHCP güvenlik, DHCP kontrol"
        ),
    },
    {
        "id": "network_security_audit",
        "name": "Kapsamlı Güvenlik Denetimi",
        "module": "network_operations",
        "params": "",
        "desc": "Tüm ağ güvenliğini kapsamlı denetler: port tarama, ARP saldırı tespiti, sahte DHCP kontrolü, proxy kontrolü.",
        "keywords": (
            "güvenlik denetimi, kapsamlı güvenlik, security audit, "
            "ağ güvenliği tara, tüm güvenlik kontrol, güvenlik raporu, "
            "ağ denetimi, güvenlik açığı, güvenlik testi, "
            "ağımdaki güvenlik açıkları, ağ güvenlik taraması, "
            "saldırı tespiti, ağ risk analizi, güvenlik kontrolü yap, "
            "ağımı tara, ağımı denetle, ağ güvenli mi"
        ),
    },
    {
        "id": "list_certificates",
        "name": "Sistem Sertifikaları Listele",
        "module": "network_operations",
        "params": "",
        "desc": "Bilgisayardaki yüklü SSL/TLS sertifikalarını listeler.",
        "keywords": (
            "sertifika listele, sistem sertifikaları, "
            "yüklü sertifikalar, certificate store"
        ),
    },
    {
        "id": "check_ssl_expiry_bulk",
        "name": "Toplu SSL Kontrol",
        "module": "network_operations",
        "params": "domains",
        "desc": "Birden fazla domain'in SSL sertifikalarını toplu kontrol eder.",
        "keywords": (
            "toplu ssl, çoklu sertifika, birden fazla ssl, "
            "ssl toplu kontrol, sertifika toplu"
        ),
    },
    # ╔══════════════════════════════════════════════════════════════════╗
    # ║  AĞ İŞLEMLERİ — VPN/PROXY (network_operations/vpn_proxy)       ║
    # ╚══════════════════════════════════════════════════════════════════╝
    {
        "id": "vpn_status",
        "name": "VPN Durumu",
        "module": "network_operations",
        "params": "",
        "desc": "Aktif VPN bağlantısının durumunu gösterir.",
        "keywords": ("vpn durumu, vpn bağlı mı, vpn kontrol, vpn status, VPN açık mı"),
    },
    {
        "id": "vpn_list_profiles",
        "name": "VPN Profilleri Listele",
        "module": "network_operations",
        "params": "",
        "desc": "Kayıtlı VPN profillerini listeler.",
        "keywords": (
            "vpn profilleri, vpn listele, kayıtlı VPN, VPN'lerim, VPN bağlantılarım"
        ),
    },
    {
        "id": "vpn_connect",
        "name": "VPN Bağlan",
        "module": "network_operations",
        "params": "profile_name",
        "desc": "Belirtilen VPN profiline bağlanır.",
        "keywords": ("vpn bağlan, vpn aç, vpn'e bağlan, VPN aktifleştir, VPN başlat"),
    },
    {
        "id": "vpn_disconnect",
        "name": "VPN Bağlantısını Kes",
        "module": "network_operations",
        "params": "profile_name",
        "desc": "Aktif VPN bağlantısını keser.",
        "keywords": (
            "vpn kes, vpn kapat, vpn bağlantı kes, VPN'i kapat, VPN devre dışı"
        ),
    },
    {
        "id": "vpn_create",
        "name": "VPN Oluştur",
        "module": "network_operations",
        "params": "name, country",
        "desc": "Ücretsiz VPN sunucularından VPN bağlantısı oluşturur ve bağlanır.",
        "keywords": (
            "vpn oluştur, vpn kur, vpn bağlantı oluştur, ücretsiz vpn, "
            "vpn bağlan, yeni vpn, free vpn, VPN kuruluş"
        ),
    },
    {
        "id": "proxy_status",
        "name": "Proxy Durumu",
        "module": "network_operations",
        "params": "",
        "desc": "Sistemdeki proxy ayarlarını gösterir.",
        "keywords": (
            "proxy durumu, proxy ayarları, proxy kontrol, proxy açık mı, proxy status"
        ),
    },
    {
        "id": "proxy_set",
        "name": "Proxy Ayarla",
        "module": "network_operations",
        "params": "proxy_address",
        "desc": "Windows sistem proxy sunucusu adresini ayarlar. Sadece proxy yapılandırması içindir.",
        "keywords": (
            "proxy ayarla, proxy kur, proxy ekle, proxy set, "
            "proxy sunucu ayarla, proxy adresi gir, "
            "proxy yapılandır, sistem proxy"
        ),
    },
    {
        "id": "proxy_remove",
        "name": "Proxy Kaldır",
        "module": "network_operations",
        "params": "",
        "desc": "Sistemdeki proxy ayarını kaldırır.",
        "keywords": (
            "proxy kaldır, proxy sil, proxy kapat, proxy remove, proxy devre dışı"
        ),
    },
    {
        "id": "proxy_test",
        "name": "Proxy Test Et",
        "module": "network_operations",
        "params": "proxy_address",
        "desc": "Belirtilen proxy sunucusunun çalışıp çalışmadığını test eder.",
        "keywords": (
            "proxy test, proxy çalışıyor mu, proxy kontrol, proxy dene, proxy doğrula"
        ),
    },
    # ╔══════════════════════════════════════════════════════════════════╗
    # ║  AĞ İŞLEMLERİ — WiFi (network_operations/wifi)                 ║
    # ╚══════════════════════════════════════════════════════════════════╝
    {
        "id": "wifi_list",
        "name": "WiFi Ağları Listele",
        "module": "network_operations",
        "params": "",
        "desc": "Çevredeki kablosuz ağları (WiFi) tarar ve listeler.",
        "keywords": (
            "wifi listele, wifi tara, kablosuz ağlar, "
            "wifi ağları, çevredeki wifi, SSID listele"
        ),
    },
    {
        "id": "wifi_saved_networks",
        "name": "Kayıtlı WiFi Ağları",
        "module": "network_operations",
        "params": "",
        "desc": "Bilgisayarda kayıtlı olan WiFi ağlarını listeler.",
        "keywords": (
            "kayıtlı wifi, bilinen ağlar, saved wifi, wifi profillerim, kayıtlı ağlarım"
        ),
    },
    {
        "id": "wifi_saved_passwords",
        "name": "WiFi Şifreleri Göster",
        "module": "network_operations",
        "params": "network_name",
        "desc": "Kayıtlı WiFi ağının şifresini gösterir.",
        "keywords": (
            "wifi şifre, wifi password, şifre göster, wifi şifresi ne, ağ şifresi"
        ),
    },
    {
        "id": "wifi_connect",
        "name": "WiFi Bağlan",
        "module": "network_operations",
        "params": "network_name, password",
        "desc": "Belirtilen WiFi ağına bağlanır.",
        "keywords": (
            "wifi bağlan, wifi'ye bağlan, ağa bağlan, kablosuz bağlan, wifi connect"
        ),
    },
    {
        "id": "wifi_disconnect",
        "name": "WiFi Bağlantısını Kes",
        "module": "network_operations",
        "params": "",
        "desc": "WiFi bağlantısını keser.",
        "keywords": (
            "wifi kes, wifi kapat, wifi bağlantı kes, kablosuz kes, wifi disconnect"
        ),
    },
    {
        "id": "enable_hotspot",
        "name": "Hotspot Aç",
        "module": "network_operations",
        "params": "ssid, password",
        "desc": "Bilgisayarı mobil erişim noktası (hotspot) olarak açar.",
        "keywords": (
            "hotspot aç, hotspot başlat, erişim noktası, "
            "internet paylaş, mobil hotspot, tethering"
        ),
    },
    {
        "id": "disable_hotspot",
        "name": "Hotspot Kapat",
        "module": "network_operations",
        "params": "",
        "desc": "Açık olan hotspot'u kapatır.",
        "keywords": ("hotspot kapat, hotspot durdur, erişim noktası kapat"),
    },
    {
        "id": "hotspot_status",
        "name": "Hotspot Durumu",
        "module": "network_operations",
        "params": "",
        "desc": "Hotspot'un açık/kapalı durumunu ve bağlı cihazları gösterir.",
        "keywords": (
            "hotspot durumu, hotspot açık mı, hotspot status, "
            "hotspot bilgi, bağlı cihazlar"
        ),
    },
    # ╔══════════════════════════════════════════════════════════════════╗
    # ║  ÖZEL YAPILAR (DAG Executor tarafından işlenir)                 ║
    # ╚══════════════════════════════════════════════════════════════════╝
    {
        "id": "foreach",
        "name": "Döngü (Foreach)",
        "module": "_internal",
        "params": "items, tool, params",
        "desc": "Bir liste üzerinde aynı işlemi tekrarlar. items ile listeyi alır, her öğe için belirtilen aracı çalıştırır.",
        "keywords": (
            "her bir, her birine, hepsine, tümüne, teker teker, "
            "her birini, hepsini, tümünü, sırayla, "
            "listedeki her, bulunan her, döngü, tekrarla, "
            "herbir öğe için, her IP için, her dosya için, "
            "her URL için, her satır için, toplu işlem"
        ),
    },
]

# Araç sayısı
TOTAL_TOOLS = len(TOOL_REGISTRY)
