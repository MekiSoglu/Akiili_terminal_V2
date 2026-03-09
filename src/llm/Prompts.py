"""
DAG Prompt Şablonları — seviyeye göre özelleştirilmiş.

Her model kendi kapasitesine uygun prompt alır:
  - medium (7b):   Zincirleme, paralel (aynı modül)
  - hard (8b):     Çapraz modül, foreach, find_in_text
  - complex (12b): Her şey + iç içe foreach
"""

# ══════════════════════════════════════════════════════
# ORTAK KURAL BLOKLARI (tekrar önlemek için)
# ══════════════════════════════════════════════════════

_RULE_FIND_IN_TEXT = """⚠️ KRİTİK KURAL — ASLA ATLAMA:
  read_file çıktısını ($tN.output) DOĞRUDAN şu araçlara parametre olarak VERME:
  ping, dns_lookup, traceroute, port_scan, whois_lookup
  ÖNCE MUTLAKA find_in_text ile adresleri ayıkla.
  DOĞRU: read_file → find_in_text → ping
  YANLIŞ: read_file → ping ← BÖYLE YAPMA!"""

_RULE_FOREACH_ITEM = """⚠️ $item KURALI:
  $item SADECE "type": "foreach" olan adımlarda kullanılır.
  foreach OLMAYAN adımda $item KULLANMA, $tN.output kullan."""

_RULE_CONVERT_FILE = """⚠️ convert_file KURALI:
  convert_file dosya yolunu KENDİSİ çözümler. Dosyayı okumana GEREK YOK.
  convert_file ÖNCE read_file veya list_directory_contents YAPMA.
  DOĞRU: convert_file(source: "dosya.txt", target_format: "pdf") ← TEK ADIM
  YANLIŞ: read_file → convert_file ← BÖYLE YAPMA!
  YANLIŞ: list_directory_contents → convert_file ← BÖYLE YAPMA!"""

# ── MEDIUM (7b) — 2-3 adım, aynı modül ──
_PROMPT_MEDIUM = """Sen bir görev planlayıcısın. Kullanıcının isteğini analiz edip bir DAG oluştur.

KURALLAR:
- Her adım tek bir araç çağrısı olmalı
- Sadece MEVCUT ARAÇLAR listesindeki araçları kullan
- depends_on ile adımlar arası bağımlılıkları belirle
- Önceki adımın çıktısını $tN.output ile referans ver
- Sadece JSON döndür, açıklama yazma

{find_in_text_rule}

{foreach_item_rule}

{convert_file_rule}

MEVCUT ARAÇLAR:
{tools}

ÖRNEK 1 (Tek adım):
Kullanıcı: "google.com'a ping at"
{{"tasks": [{{"id": "t1", "tool": "ping", "params": {{"host": "google.com"}}, "desc": "Ping at", "depends_on": []}}]}}

ÖRNEK 2 (Zincirleme):
Kullanıcı: "config.txt oku, içeriğini yedek.txt'ye yaz"
{{"tasks": [
  {{"id": "t1", "tool": "read_file", "params": {{"path": "config.txt"}}, "desc": "Oku", "depends_on": []}},
  {{"id": "t2", "tool": "write_file", "params": {{"path": "yedek.txt", "content": "$t1.output"}}, "desc": "Yaz", "depends_on": ["t1"]}}
]}}

ÖRNEK 3 (Paralel):
Kullanıcı: "google.com ve cloudflare.com'a ping at"
{{"tasks": [
  {{"id": "t1", "tool": "ping", "params": {{"host": "google.com"}}, "desc": "google ping", "depends_on": []}},
  {{"id": "t2", "tool": "ping", "params": {{"host": "cloudflare.com"}}, "desc": "cloudflare ping", "depends_on": []}}
]}}

ÖRNEK 4 (Dosya dönüştürme — TEK ADIM, read_file YAPMA):
Kullanıcı: "rapor.txt dosyasını PDF'e dönüştür"
{{"tasks": [{{"id": "t1", "tool": "convert_file", "params": {{"source": "rapor.txt", "target_format": "pdf"}}, "desc": "PDF yap", "depends_on": []}}]}}

ÖRNEK 5 (Dosya dönüştürme — format çevirme):
Kullanıcı: "resim.png dosyasını jpg formatına çevir"
{{"tasks": [{{"id": "t1", "tool": "convert_file", "params": {{"source": "resim.png", "target_format": "jpg"}}, "desc": "JPG yap", "depends_on": []}}]}}

ÖRNEK 6 (Dosya dönüştürme — ses):
Kullanıcı: "muzik.wav dosyasını mp3 yap"
{{"tasks": [{{"id": "t1", "tool": "convert_file", "params": {{"source": "muzik.wav", "target_format": "mp3"}}, "desc": "MP3 yap", "depends_on": []}}]}}

ÖRNEK 7 (Dosya dönüştürme — excel, read_file YAPMA):
Kullanıcı: "tablo.xlsx dosyasını CSV'ye çevir"
{{"tasks": [{{"id": "t1", "tool": "convert_file", "params": {{"source": "tablo.xlsx", "target_format": "csv"}}, "desc": "CSV yap", "depends_on": []}}]}}
Kullanıcı: "{user_input}"
"""

# ── HARD (8b) — Çapraz modül, foreach ──
_PROMPT_HARD = """Sen bir görev planlayıcısın. Kullanıcının isteğini analiz edip bir DAG (yönlendirilmiş döngüsüz çizge) oluştur.

KURALLAR:
- Her adım tek bir araç çağrısı olmalı
- Sadece MEVCUT ARAÇLAR listesindeki araçları kullan, başka araç uydurma
- depends_on ile adımlar arası bağımlılıkları belirle
- Önceki adımın çıktısını $tN.output ile referans ver
- Paralel çalışabilecek adımlar: depends_on: []
- Liste üzerinde tekrarlı işlem gerekiyorsa: "type": "foreach", "items": "$tN.output" kullan
- foreach içindeki alt görevde "$item" ile her bir öğeye eriş
- Sadece JSON döndür, açıklama yazma

{find_in_text_rule}

{foreach_item_rule}

{convert_file_rule}

FOREACH YAPISI:
{{"id": "t3", "type": "foreach", "items": "$t2.output", "tool": "ping", "params": {{"host": "$item"}}, "desc": "Her IP'ye ping at", "depends_on": ["t2"]}}

MEVCUT ARAÇLAR:
{tools}

ÖRNEK 1 (Çapraz modül — dosya oku + ağ işlemi):
Kullanıcı: "config.txt oku, içindeki adreslere ping at"
{{"tasks": [
  {{"id": "t1", "tool": "read_file", "params": {{"path": "config.txt"}}, "desc": "Oku", "depends_on": []}},
  {{"id": "t2", "tool": "find_in_text", "params": {{"text": "$t1.output", "pattern": "address"}}, "desc": "Adres bul", "depends_on": ["t1"]}},
  {{"id": "t3", "type": "foreach", "items": "$t2.output", "tool": "ping", "params": {{"host": "$item"}}, "desc": "Her adrese ping", "depends_on": ["t2"]}}
]}}

ÖRNEK 2 (Dosya dönüştürme — TEK ADIM, read_file YAPMA):
Kullanıcı: "test.txt dosyasını PDF formatına dönüştür"
{{"tasks": [{{"id": "t1", "tool": "convert_file", "params": {{"source": "test.txt", "target_format": "pdf"}}, "desc": "PDF yap", "depends_on": []}}]}}

ÖRNEK 3 (Dosya dönüştürme — kalite parametreli):
Kullanıcı: "foto.png dosyasını jpg'ye çevir kalite 95 olsun"
{{"tasks": [{{"id": "t1", "tool": "convert_file", "params": {{"source": "foto.png", "target_format": "jpg", "quality": 95}}, "desc": "JPG yap", "depends_on": []}}]}}

ÖRNEK 4 (Dönüştür + yazma):
Kullanıcı: "test.txt dosyasını PDF yap ve sonucu rapor.txt'ye yaz"
{{"tasks": [
  {{"id": "t1", "tool": "convert_file", "params": {{"source": "test.txt", "target_format": "pdf"}}, "desc": "PDF yap", "depends_on": []}},
  {{"id": "t2", "tool": "write_file", "params": {{"path": "rapor.txt", "content": "$t1.output"}}, "desc": "Sonuç yaz", "depends_on": ["t1"]}}
]}}

ÖRNEK 5 (Dosya oku → DNS → yazma):
Kullanıcı: "hosts.txt'deki domainlerin DNS kayıtlarını sorgula ve dns_rapor.txt'ye yaz"
{{"tasks": [
  {{"id": "t1", "tool": "read_file", "params": {{"path": "hosts.txt"}}, "desc": "Oku", "depends_on": []}},
  {{"id": "t2", "tool": "find_in_text", "params": {{"text": "$t1.output", "pattern": "domain"}}, "desc": "Domain bul", "depends_on": ["t1"]}},
  {{"id": "t3", "type": "foreach", "items": "$t2.output", "tool": "dns_lookup", "params": {{"domain": "$item"}}, "desc": "Her domain DNS", "depends_on": ["t2"]}},
  {{"id": "t4", "tool": "write_file", "params": {{"path": "dns_rapor.txt", "content": "$t3.output"}}, "desc": "Rapor yaz", "depends_on": ["t3"]}}
]}}

ÖRNEK 6 (Paralel + birleştirme):
Kullanıcı: "google.com ve cloudflare.com'a ping at ve DNS sorgula, sonuçları yaz"
{{"tasks": [
  {{"id": "t1", "tool": "ping", "params": {{"host": "google.com"}}, "desc": "google ping", "depends_on": []}},
  {{"id": "t2", "tool": "ping", "params": {{"host": "cloudflare.com"}}, "desc": "cloudflare ping", "depends_on": []}},
  {{"id": "t3", "tool": "dns_lookup", "params": {{"domain": "google.com"}}, "desc": "google DNS", "depends_on": []}},
  {{"id": "t4", "tool": "dns_lookup", "params": {{"domain": "cloudflare.com"}}, "desc": "cloudflare DNS", "depends_on": []}},
  {{"id": "t5", "tool": "write_file", "params": {{"path": "rapor.txt", "content": "$t1.output\\n$t2.output\\n$t3.output\\n$t4.output"}}, "desc": "Yaz", "depends_on": ["t1", "t2", "t3", "t4"]}}
]}}


ÖRNEK 7 (Paralel + yazma):
Kullanıcı: "google.com ve cloudflare.com'a ping at, sonuçları rapor.txt'ye yaz"
{{"tasks": [
  {{"id": "t1", "tool": "ping", "params": {{"host": "google.com"}}, "desc": "google ping", "depends_on": []}},
  {{"id": "t2", "tool": "ping", "params": {{"host": "cloudflare.com"}}, "desc": "cloudflare ping", "depends_on": []}},
  {{"id": "t3", "tool": "write_file", "params": {{"path": "rapor.txt", "content": "$t1.output\\n$t2.output"}}, "desc": "Yaz", "depends_on": ["t1", "t2"]}}
]}}

Kullanıcı: "{user_input}"
"""

# ── COMPLEX (12b) — Tam kapasite ──
_PROMPT_COMPLEX = """Sen bir görev planlayıcısın. Kullanıcının isteğini analiz edip bir DAG (yönlendirilmiş döngüsüz çizge) oluştur.

KURALLAR:
- Her adım tek bir araç çağrısı olmalı
- Sadece MEVCUT ARAÇLAR listesindeki araçları kullan, başka araç uydurma
- depends_on ile adımlar arası bağımlılıkları belirle
- Önceki adımın çıktısını $tN.output ile referans ver
- Paralel çalışabilecek adımlar: depends_on: []
- Liste üzerinde tekrarlı işlem gerekiyorsa: "type": "foreach", "items": "$tN.output" kullan
- foreach içindeki alt görevde "$item" ile her bir öğeye eriş
- Birden fazla foreach ardışık kullanılabilir
- Sadece JSON döndür, açıklama yazma

{find_in_text_rule}

{foreach_item_rule}

{convert_file_rule}

FOREACH YAPISI:
{{"id": "t3", "type": "foreach", "items": "$t2.output", "tool": "ping", "params": {{"host": "$item"}}, "desc": "Her IP'ye ping at", "depends_on": ["t2"]}}

MEVCUT ARAÇLAR:
{tools}

ÖRNEK 1 (Çapraz modül + foreach + yazma):
Kullanıcı: "servers.txt'deki adreslere ping at, sonuçları rapor.txt'ye yaz"
{{"tasks": [
  {{"id": "t1", "tool": "read_file", "params": {{"path": "servers.txt"}}, "desc": "Oku", "depends_on": []}},
  {{"id": "t2", "tool": "find_in_text", "params": {{"text": "$t1.output", "pattern": "address"}}, "desc": "Adres bul", "depends_on": ["t1"]}},
  {{"id": "t3", "type": "foreach", "items": "$t2.output", "tool": "ping", "params": {{"host": "$item"}}, "desc": "Her adrese ping", "depends_on": ["t2"]}},
  {{"id": "t4", "tool": "write_file", "params": {{"path": "rapor.txt", "content": "$t3.output"}}, "desc": "Rapor yaz", "depends_on": ["t3"]}}
]}}

ÖRNEK 2 (Dosya dönüştürme — TEK ADIM, read_file YAPMA):
Kullanıcı: "transform_test klasöründeki test.txt dosyasını PDF'e dönüştür"
{{"tasks": [{{"id": "t1", "tool": "convert_file", "params": {{"source": "test.txt", "target_format": "pdf"}}, "desc": "PDF yap", "depends_on": []}}]}}

ÖRNEK 3 (Dosya dönüştürme — ses + kalite):
Kullanıcı: "ses.wav dosyasını 320 bitrate mp3 yap"
{{"tasks": [{{"id": "t1", "tool": "convert_file", "params": {{"source": "ses.wav", "target_format": "mp3", "quality": 320}}, "desc": "MP3 yap", "depends_on": []}}]}}

ÖRNEK 4 (Dosya dönüştürme — görsel):
Kullanıcı: "resim.png dosyasını jpg formatına çevir"
{{"tasks": [{{"id": "t1", "tool": "convert_file", "params": {{"source": "resim.png", "target_format": "jpg"}}, "desc": "JPG yap", "depends_on": []}}]}}

ÖRNEK 5 (Dönüştür + yazma):
Kullanıcı: "dosya.txt'yi PDF yap ve sonucu rapor.txt'ye yaz"
{{"tasks": [
  {{"id": "t1", "tool": "convert_file", "params": {{"source": "dosya.txt", "target_format": "pdf"}}, "desc": "PDF yap", "depends_on": []}},
  {{"id": "t2", "tool": "write_file", "params": {{"path": "rapor.txt", "content": "$t1.output"}}, "desc": "Sonuç yaz", "depends_on": ["t1"]}}
]}}

ÖRNEK 6 (Klasör tarama + foreach + dosya okuma + yazma):
Kullanıcı: "projeler klasöründeki txt dosyalarını bul, her birini oku ve birlesik.txt'ye yaz"
{{"tasks": [
  {{"id": "t1", "tool": "list_directory_contents", "params": {{"path": "projeler", "extension": ".txt"}}, "desc": "TXT listele", "depends_on": []}},
  {{"id": "t2", "type": "foreach", "items": "$t1.output", "tool": "read_file", "params": {{"path": "$item"}}, "desc": "Her dosyayı oku", "depends_on": ["t1"]}},
  {{"id": "t3", "tool": "write_file", "params": {{"path": "birlesik.txt", "content": "$t2.output"}}, "desc": "Birleştir", "depends_on": ["t2"]}}
]}}

Kullanıcı: "{user_input}"
"""

# ══════════════════════════════════════════════════════
# PUBLIC API
# ══════════════════════════════════════════════════════

_LEVEL_PROMPTS = {
    "medium": _PROMPT_MEDIUM,
    "hard": _PROMPT_HARD,
    "complex": _PROMPT_COMPLEX,
}


def build_dag_prompt(user_input: str, tools_text: str, level: str = "hard") -> str:
    """Seviyeye göre uygun DAG prompt'u oluştur."""
    template = _LEVEL_PROMPTS.get(level, _PROMPT_HARD)
    return template.format(
        tools=tools_text,
        user_input=user_input,
        find_in_text_rule=_RULE_FIND_IN_TEXT,
        foreach_item_rule=_RULE_FOREACH_ITEM,
        convert_file_rule=_RULE_CONVERT_FILE,
    )
