#  Akkıl Terminal v2

**Lokal LLM'lerle çalışan, DAG tabanlı akıllı terminal asistanı.**

Doğal dilde verilen komutları anlayıp, birden fazla aracı zincirleme çalıştırabilen, tamamen offline çalışan bir terminal asistanı. Bulut API'ye ihtiyaç duymaz — tüm zeka lokal LLM'lerden gelir.

---

## Ne İşe Yarar?

Tek bir cümleyle karmaşık işlemler yapabilirsiniz:

```
>>> ggs.txt dosyasını oku, içindeki domainlerin DNS kayıtlarını sorgula ve sonuçları dns_rapor.txt'ye yaz
```

Sistem otomatik olarak:
1. Dosyayı okur
2. İçindeki domain adreslerini ayıklar (find_in_text)
3. Her domain için DNS sorgusu yapar (foreach)
4. Sonuçları dosyaya yazar

Kullanıcı sadece sonucu görür — planlama, tip dönüşümü, hata yönetimi arka planda halledilir.

---

## Mimari

```
┌─────────────────────────────────────────────────────────┐
│                    Kullanıcı Girişi                      │
│            "dosyayı oku ve domainlere ping at"           │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│              Karmaşıklık Skorlama                       │
│         Kelime (W) + Yapısal (S) Analiz                 │
│    ≤4 → medium (7b)  ≤7 → hard (8b)  >7 → complex (12b)│
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│              ChromaDB Araç Seçimi                       │
│     106 araç · multilingual-e5-base embedding           │
│     Kullanıcı ifadesine en uygun araçları seçer         │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│           LLM DAG Planlama (Ollama)                     │
│                                                         │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐             │
│   │  7b      │  │  8b      │  │  12b     │             │
│   │  Qwen    │  │ DeepSeek │  │  Gemma   │             │
│   │  Coder   │  │  R1      │  │  3       │             │
│   │  ────    │  │  ────    │  │  ────    │             │
│   │ Basit    │  │ Çapraz   │  │ Karmaşık │             │
│   │ görevler │  │ modül    │  │ foreach  │             │
│   └──────────┘  └──────────┘  └──────────┘             │
│                                                         │
│   Çıktı: JSON DAG planı (adımlar + bağımlılıklar)      │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│              DAG Executor (Motor)                       │
│                                                         │
│   • Adımları bağımlılık sırasına göre çalıştırır       │
│   • Paralel adımları eşzamanlı çalıştırır              │
│   • foreach ile liste üzerinde iterasyon               │
│   • Otomatik tip dönüşümü (_coerce_param_types)        │
│   • $tN.output referans çözümleme                      │
│   • Path parametrelerine content gelirse düzeltme       │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│                    Modüller                              │
│                                                         │
│   📁 file_operations (29 araç)                          │
│      Dosya arama, okuma, yazma, kopyalama, taşıma,     │
│      karşılaştırma, boyut hesaplama, uzantı             │
│      istatistikleri, dosya dönüştürme (convert_file)    │
│                                                         │
│   🌐 network_operations (77 araç)                       │
│      Ping, DNS, traceroute, whois, port tarama,         │
│      ağ bilgisi, public IP, hız testi                   │
└─────────────────────────────────────────────────────────┘
```

---

## Temel Özellikler

###  DAG Tabanlı Görev Planlama
LLM, kullanıcının isteğini bir Yönlendirilmiş Döngüsüz Çizge (DAG) olarak planlar. Adımlar arası bağımlılıklar belirlenir, paralel çalışabilecek adımlar eşzamanlı çalıştırılır.

###  3 Katmanlı Model Mimarisi
Görevin karmaşıklığına göre farklı LLM seçilir:

| Karmaşıklık | Model | Boyut | Kullanım |
|---|---|---|---|
| Basit | Qwen 2.5 Coder | 7B | Tek/iki adım, aynı modül |
| Orta | DeepSeek R1 | 8B | Çapraz modül, foreach |
| Karmaşık | Gemma 3 | 12B | İç içe foreach, 4+ adım |

Küçük modeller hızlı çalışır, büyük modeller sadece gerektiğinde devreye girer.

###  Otomatik Tip Dönüşümü
DAG Executor, araçlar arası veri akışında otomatik tip dönüşümü yapar:
- `List[Dict]` → parametre adına göre uygun alan çıkarma (full_path, ip, domain vb.)
- Path parametresine dosya içeriği gelirse → orijinal sonuçtan file_path çıkarma
- String → satırlara bölme (foreach için)
- Dict → data/files/items alanlarını çıkarma

###  Akıllı Dosya Sistemi İndeksleme
SQLite + FTS5 tabanlı dosya indeksleme:
- Watchdog ile gerçek zamanlı dosya değişikliği izleme
- Tam eşleşme öncelikli arama (FTS5 fuzzy arama son çare)
- Otomatik blacklist (venv, node_modules, site-packages vb.)

###  Dosya Dönüştürme (convert_file)
48 format çifti destekleyen tek giriş noktalı dönüştürücü:

| Kategori | Desteklenen |
|---|---|
| Doküman | txt↔pdf, txt↔docx, txt↔html, md↔pdf, md↔html, csv↔xlsx, docx↔pdf |
| Görsel | png↔jpg, webp→png, bmp→png, png→gif, png→webp |
| Ses | wav↔mp3, ogg→mp3, flac→mp3, m4a→mp3 |
| Video | mp4→mp3, mp4→wav, mkv→mp4, avi→mp4, mp4→gif |

Orijinal dosyaya dokunmaz, güvenli kopya üzerinde çalışır.

###  Ağ İşlemleri
Ping, DNS sorgu, traceroute, whois, port tarama, ağ bilgisi, public IP tespiti ve daha fazlası.

###  Zincirleme İşlemler
Araçları birbirine bağlayarak karmaşık iş akışları:

```
>>> projeler klasöründeki .txt dosyalarını bul, her birini oku ve birlesik.txt'ye yaz

  t1: list_directory_contents(path: "projeler", extension: ".txt")
  t2: read_file [foreach] ← items=$t1.output
  t3: write_file(content: $t2.output)
```

---

## Kurulum

### Gereksinimler
- Python 3.10+
- Ollama (lokal LLM çalıştırmak için)
- CUDA destekli GPU (önerilen, 8GB+ VRAM)

### 1. Projeyi Klonla
```bash
git clone https://github.com/kullanici/akkil-terminal-v2.git
cd akkil-terminal-v2
```

### 2. Python Bağımlılıklarını Kur
```bash
pip install -r requirements.txt
```

Temel bağımlılıklar:
```
sentence-transformers
chromadb
ollama
watchdog
reportlab
Pillow
openpyxl
python-docx
markdown
```

### 3. Ollama Modellerini İndir
```bash
ollama pull qwen2.5-coder:7b
ollama pull deepseek-r1:8b
ollama pull gemma3:12b
```

### 4. FFmpeg Kur (Ses/Video dönüştürme için opsiyonel)
```bash
# Windows — https://ffmpeg.org/download.html adresinden indir
# veya winget ile:
winget install ffmpeg
```

### 5. config.json Ayarla
```json
{
  "indexing": {
    "watch_path": "C:\\Users\\KULLANICI\\Desktop",
    "allowed_extensions": [".txt", ".py", ".json", ".csv", ".xlsx", ".png", ".jpg", ".wav", ".mp3"],
    "blacklist_dirs": ["venv", ".venv", "node_modules", "__pycache__", ".git", "site-packages"]
  }
}
```

### 6. İlk İndeksleme
```bash
python reindex.py
```

### 7. Çalıştır
```bash
python run.py run
```

---

## Kullanım Örnekleri

### Dosya İşlemleri
```
>>> projeler klasöründeki .py dosyalarını bul
>>> config.txt dosyasını oku
>>> rapor.txt dosyasını PDF'e dönüştür
>>> test_resim.png dosyasını jpg formatına çevir
>>> projeler klasörünün boyutunu hesapla
```

### Ağ İşlemleri
```
>>> google.com'a ping at
>>> cloudflare.com'un DNS kaydını sorgula
>>> ağ bilgilerimi göster
>>> public IP'mi bul
```

### Zincirleme İşlemler
```
>>> ggs.txt dosyasını oku, içindeki domainlerin DNS kayıtlarını sorgula ve sonuçları dns_rapor.txt'ye yaz
>>> google.com ve cloudflare.com'a ping at, sonuçları rapor.txt'ye yaz
>>> projeler klasöründeki en büyük 3 dosyayı bul ve bilgilerini rapor.txt'ye yaz
```

### Dosya Dönüştürme
```
>>> test.txt dosyasını PDF yap
>>> resim.png dosyasını jpg'ye çevir kalite 95 olsun
>>> ses.wav dosyasını 320 bitrate mp3 yap
>>> tablo.xlsx dosyasını CSV'ye çevir
```

---

## Proje Yapısı

```
akkil_teminal_v2/
├── config.json                  # Yapılandırma
├── run.py                       # Ana giriş noktası
├── reindex.py                   # DB sıfırlama ve yeniden indeksleme
│
├── src/
│   ├── core/
│   │   ├── BaseModule.py        # Modül temel sınıfı
│   │   └── Dagexecutor.py       # DAG çalıştırma motoru
│   │
│   ├── llm/
│   │   ├── Brain.py             # Ana beyin — LLM yönetimi
│   │   ├── LLMClient.py         # Ollama API istemcisi
│   │   └── prompts.py           # Seviyeye göre DAG prompt şablonları
│   │
│   ├── tools/
│   │   ├── Tool_registry.py     # 106 araç tanımı (ChromaDB için)
│   │   └── tool_selector.py     # Karmaşıklık skorlama + araç seçimi
│   │
│   ├── modules/
│   │   ├── file/
│   │   │   └── FileOperations.py    # 29 dosya aracı + convert_file
│   │   └── network/
│   │       └── NetworkOperations.py # 77 ağ aracı
│   │
│   └── indexing/
│       ├── Database.py          # SQLite + FTS5 veritabanı
│       ├── FileIndexer.py       # Dosya tarama ve indeksleme
│       ├── FileQueryEngine.py   # Dosya sorgu motoru
│       └── FileWatcher.py       # Watchdog dosya izleyici
│
└── tests/
    └── test_convert.py          # Dosya dönüştürme testleri
```

---

## Neden Bulut API Değil?

| | Akkıl Terminal | Bulut API Çözümleri |
|---|---|---|
| Gizlilik | Tüm veriler lokalde kalır | Veriler sunucuya gönderilir |
| Maliyet | Ücretsiz (Ollama + açık modeller) | API kullanım ücreti |
| Hız | Ağ gecikmesi yok | Her istek ağ round-trip |
| Çevrimdışı | Tam çalışır | İnternet gerekli |
| Özelleştirme | Prompt, model, araç tamamen değiştirilebilir | Sınırlı |

---

## Neden OpenClaw/Benzeri Agent'lar Değil?

| | Akkıl Terminal | Genel Agent Frameworkleri |
|---|---|---|
| Min. Model | 7B (basit görevler) | 32B+ (güvenilir tool-calling) |
| Min. VRAM | 8GB | 24-32GB |
| Görev Planlama | Motor destekli (DAG + tip dönüşümü) | LLM'e bağımlı |
| Hata Yönetimi | Motor seviyesinde coercion/fallback | Model halüsinasyonuna bağlı |
| Hız | Plan bir kere, motor çalıştırır | Her adımda LLM düşünür |
| Türkçe | Native Türkçe prompt desteği | İngilizce odaklı |

---



---



## Yol Haritası

- [x] DAG tabanlı görev planlama
- [x] 3 katmanlı model mimarisi (7B/8B/12B)
- [x] 106 araç (dosya + ağ)
- [x] Otomatik tip dönüşümü
- [x] Dosya dönüştürme (48 format çifti)
- [x] FTS5 tam eşleşme öncelikli arama
- [ ] Güvenli ağ modülü (Docker + Tor izole ortam)
- [ ] Sesli komut desteği
- [ ] Web arayüzü
