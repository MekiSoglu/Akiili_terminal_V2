"""
ToolSelector — ChromaDB + intfloat/multilingual-e5-base ile araç seçimi.
Bağlaç bölme + vektör arama ile kullanıcı isteğine en uygun araçları bulur.
"""

import chromadb
import re
import time
from typing import List, Dict, Optional

from src.tools.Tool_registry import TOTAL_TOOLS, TOOL_REGISTRY

try:
    from sentence_transformers import SentenceTransformer

    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False


# ══════════════════════════════════════════════
# Karmaşıklık Tahmin (Complexity Estimator)
# ══════════════════════════════════════════════

# Türkçe fiil kalıpları — görev tespiti için
_VERB_PATTERNS = [
    r"\boku\b",
    r"\byaz\b",
    r"\bbul\b",
    r"\bara\b",
    r"\bsil\b",
    r"kopyala",
    r"taşı",
    r"listele",
    r"tara\b",
    r"\bping\b",
    r"bağlan",
    r"kontrol",
    r"oluştur",
    r"göster",
    r"ölç\b",
    r"değiştir",
    r"\baç\b",
    r"kapat",
    r"denetle",
    r"indir",
    r"yükle",
    r"engelle",
    r"temizle",
    r"kaydet",
    r"çözümle",
    r"tespit",
    r"izle\b",
    r"yakala",
    r"paylaş",
    r"getir",
    r"sorgula",
    r"karşılaştır",
    r"birleştir",
    r"filtrele",
    r"çalıştır",
    r"gönder",
    r"al\b",
    r"ekle\b",
    r"çıkar",
    r"yedekle",
    r"güncelle",
    r"doğrula",
]

# Bağlaç/sıralama ifadeleri
_CONJUNCTIONS = [
    "sonra ",
    "ardından ",
    "daha sonra ",
    "sonrasında ",
    "sonucu",
    "sonucunu",
    "sonuçları",
    " ve ",
    ", ",
    "; ",
]

# Döngü/çoğul ifadeler
_LOOP_PATTERNS = [
    r"her\s+bir",
    r"tüm\s",
    r"hepsi",
    r"her\s",
    r"tümünü",
    r"hepsini",
    r"herbir",
]

# Dosya referansları — domain'leri (.com, .net) yakalamamalı
_FILE_PATTERNS = [
    r"dosya",
    r"klasör",
    r"dizin",
    r"\b\w+\.(?:txt|log|csv|json|xml|yaml|yml|cfg|conf|ini|dat|md|pdf|doc|docx|xlsx|py|sh|bat|zip|tar|gz)\b",
    r"\boku\b",
    r"\byaz\b",
    r"kaydet",
]

# Ağ referansları
_NETWORK_PATTERNS = [
    r"\bping\b",
    r"\bdns\b",
    r"\bvpn\b",
    r"\bağ\b",
    r"internet",
    r"\bsite\b",
    r"\burl\b",
    r"\bhttp\b",
    r"\bip\b",
    r"firewall",
    r"güvenlik",
    r"wifi",
    r"proxy",
    r"port\b",
    r"bağlantı",
]


def estimate_complexity(query: str) -> dict:
    q = query.lower()

    # ══════════════════════════════════════════════
    # A) KELİME SKORU (mevcut sistem)
    # ══════════════════════════════════════════════

    verb_count = sum(1 for p in _VERB_PATTERNS if re.search(p, q))
    conj_count = sum(1 for c in _CONJUNCTIONS if c in q)
    loop_count = sum(1 for p in _LOOP_PATTERNS if re.search(p, q))

    has_file = any(re.search(p, q) for p in _FILE_PATTERNS)
    has_network = any(re.search(p, q) for p in _NETWORK_PATTERNS)
    cross_module = has_file and has_network

    word_score = verb_count + conj_count
    if loop_count > 0:
        word_score += 3
    if cross_module:
        word_score += 2

    # ══════════════════════════════════════════════
    # B) YAPISAL SKOR (görev yapısı analizi)
    # ══════════════════════════════════════════════

    structural_score = 0

    # 1. Dinamik hedef tespiti
    _KNOWN_TLDS = (
        r"\.(com|net|org|io|dev|gov|edu|co|tr|uk|de|fr|ru|cn|jp|info|biz|me)\b"
    )
    _SOURCE_PATTERNS = [
        r"\b\w+\.(?:txt|log|csv|json|xml|yaml|yml|cfg|conf|ini|dat|md|pdf|doc|docx|xlsx|py|sh|bat)\b",
        r"dosya\w*",
        r"klasör\w*",
        r"dizin\w*",
        r"içindeki",
        r"içerisindeki",
        r"deki\b",
        r"daki\b",
    ]
    has_source = any(re.search(p, q) for p in _SOURCE_PATTERNS)
    if (
        has_source
        and re.search(_KNOWN_TLDS, q)
        and not any(re.search(p, q) for p in _SOURCE_PATTERNS[:1])
    ):
        has_source = any(re.search(p, q) for p in _SOURCE_PATTERNS[1:])

    _ACTION_PATTERNS = [
        r"\bping\b",
        r"\bdns\b",
        r"traceroute",
        r"port",
        r"\byaz\b",
        r"kaydet",
        r"gönder",
        r"mail\b",
        r"\bsil\b",
        r"kopyala",
        r"taşı",
    ]
    has_action = any(re.search(p, q) for p in _ACTION_PATTERNS)

    is_dynamic = has_source and has_action

    if is_dynamic:
        structural_score = 5

    # 2. Çapraz modül
    if cross_module:
        structural_score = max(structural_score, 5)

    # 3. Filtreleme/koşul tespiti: "uzantılı", ".py", "boyutu X'den büyük" gibi
    _FILTER_PATTERNS = [
        r"uzantılı",
        r"uzantısı",  # .py uzantılı
        r"\.\w{1,4}\s+uzantılı",  # .py uzantılı (boşluklu)
        r"boyut\w*\s*(büyük|küçük|fazla|az)",  # boyutu büyük
        r"tarih\w*\s*(önce|sonra|yeni|eski)",  # tarihi yeni
        r"içeren\b",
        r"içermeyen\b",  # X içeren dosyalar
        r"sadece\b",
        r"yalnızca\b",  # sadece .py dosyaları
    ]
    has_filter = any(re.search(p, q) for p in _FILTER_PATTERNS)

    # Kaynak + filtreleme = en az 2 adımlı iş (listele → filtrele)
    if has_source and has_filter:
        structural_score = max(structural_score, 4)  # minimum medium

    # 4. Çoklu bilgi talebi: "isimlerini ve boyutlarını", "adını ve tarihini"
    _MULTI_INFO = [
        r"isim\w*\s*(ve|ile)\s*boyut",  # isim ve boyut
        r"ad\w*\s*(ve|ile)\s*tarih",  # ad ve tarih
        r"bilgi\w*\s*getir",
        r"detay\w*\s*getir",  # bilgileri getir
        r"isim\w*\s*(ve|ile)\s*uzant",  # isim ve uzantı
    ]
    has_multi_info = any(re.search(p, q) for p in _MULTI_INFO)

    if has_source and has_filter and has_multi_info:
        structural_score = max(structural_score, 5)

    # 5. İterasyon/döngü
    _PLURAL_TARGET = [
        r"lere\b",
        r"lara\b",
        r"ları\b",
        r"leri\b",
        r"lerin\b",
        r"ların\b",  # domainlerin, dosyaların
        r"lerini\b",
        r"larını\b",  # dosyalarını, adreslerini
        r"lerine\b",
        r"larına\b",  # adreslerine
        r"lerinden\b",
        r"larından\b",  # dosyalarından
        r"hepsi\w*",
        r"tüm\w*",
        r"her\s",
        r"herbir\w*",
        r"herbirine",
    ]
    has_iteration = loop_count > 0 or any(re.search(p, q) for p in _PLURAL_TARGET)

    if is_dynamic and has_iteration:
        structural_score = max(structural_score, 7)  # foreach gerekir

    # 4. Sonuç yazma: iterasyon + çıktı dosyası
    _OUTPUT_PATTERNS = [
        r"\byaz\b",
        r"kaydet",
        r"rapor",
        r"sonuç",
        r"çıktı",
        r"dönüştür",
        r"oluştur",
    ]
    has_output = any(re.search(p, q) for p in _OUTPUT_PATTERNS)

    if is_dynamic and has_iteration and has_output:
        structural_score = max(structural_score, 9)  # foreach + write = tam zincir

    # ══════════════════════════════════════════════
    # C) FİNAL SKOR: ikisinin max'ı
    # ══════════════════════════════════════════════

    final_score = max(word_score, structural_score)

    # Seviye belirleme (3 katman)
    if final_score <= 4:
        level = "medium"
        model = "7b"
    elif final_score <= 7:
        level = "hard"
        model = "8b"
    else:
        level = "complex"
        model = "12b"

    return {
        "level": level,
        "score": final_score,
        "model": model,
        "details": {
            "word_score": word_score,
            "structural_score": structural_score,
            "verbs": verb_count,
            "conjunctions": conj_count,
            "loops": loop_count,
            "cross_module": cross_module,
            "dynamic_target": is_dynamic,
            "iteration": has_iteration,
            "has_output": has_output,
            "has_filter": has_filter,
        },
    }


# ══════════════════════════════════════════════
# Embedding Function
# ══════════════════════════════════════════════


class E5EmbeddingFunction:
    """intfloat/multilingual-e5-base embedding üretici."""

    def __init__(self):
        if not HAS_SENTENCE_TRANSFORMERS:
            raise ImportError(
                "sentence-transformers gerekli: pip install sentence-transformers"
            )
        print(" Embedding modeli yükleniyor (intfloat/multilingual-e5-base)...")
        start = time.time()
        self.model = SentenceTransformer("intfloat/multilingual-e5-base")
        print(f" Model hazır ({time.time() - start:.1f}s)")

    def __call__(self, input: list) -> list:
        embeddings = self.model.encode(input, show_progress_bar=False)
        return embeddings.tolist()

    def embed_documents(self, input: list) -> list:
        return self.__call__(input)

    def embed_query(self, input: list) -> list:
        return self.__call__(input)


# ══════════════════════════════════════════════
# Bağlaç Bölme (Conjunction Split)
# ══════════════════════════════════════════════

TURKISH_CONJUNCTIONS = [
    " ve sonra ",
    " ardından ",
    " daha sonra ",
    " sonrasında ",
    " sonucu ",
    " sonucunu ",
    " sonuçları ",
    " ayrıca ",
    " ek olarak ",
    " bunun yanında ",
    " eğer ",
    " ise ",
    " yoksa ",
    " varsa ",
    ", ",
    "; ",
    " ve ",  # En son — en yaygın
]


def conjunction_split(text: str) -> List[str]:
    """Türkçe bağlaçlardan cümleyi parçalara böler."""
    chunks = [text]
    for sep in TURKISH_CONJUNCTIONS:
        new_chunks = []
        for chunk in chunks:
            parts = chunk.split(sep)
            new_chunks.extend(
                [p.strip() for p in parts if p.strip() and len(p.strip()) > 3]
            )
        chunks = new_chunks
    return chunks if chunks else [text]


# ══════════════════════════════════════════════
# ToolSelector Sınıfı
# ══════════════════════════════════════════════


class ToolSelector:
    """ChromaDB tabanlı araç seçici."""

    def __init__(self, db_path: str = None):
        """
        Args:
            db_path: ChromaDB kalıcı depolama yolu (None = bellekte)
        """
        self._embedding_fn = None
        self._collection = None
        self._client = None
        self._db_path = db_path
        self._initialized = False

    def initialize(self):
        """Modeli yükle ve ChromaDB koleksiyonunu oluştur. Uygulama başlatılırken bir kere çağrılır."""
        if self._initialized:
            return

        print(f"\n ToolSelector başlatılıyor ({TOTAL_TOOLS} araç)...")
        start = time.time()

        # Embedding modeli
        self._embedding_fn = E5EmbeddingFunction()

        # ChromaDB client
        if self._db_path:
            self._client = chromadb.PersistentClient(path=self._db_path)
        else:
            self._client = chromadb.Client()

        # Koleksiyonu oluştur veya güncelle
        self._setup_collection()

        self._initialized = True
        print(f" ToolSelector hazır ({time.time() - start:.1f}s, {TOTAL_TOOLS} araç)\n")

    def _setup_collection(self):
        """Araçları ChromaDB'ye yükle."""
        # Varsa sil ve yeniden oluştur
        try:
            self._client.delete_collection("tools")
        except:
            pass

        self._collection = self._client.create_collection(
            name="tools",
            metadata={"hnsw:space": "cosine"},
            embedding_function=self._embedding_fn,
        )

        documents = []
        ids = []
        metadatas = []

        for tool in TOOL_REGISTRY:
            # Zengin belge: isim + açıklama + keyword'ler
            doc = f"{tool['name']}. {tool['desc']} {tool['keywords']}"
            documents.append(doc)
            ids.append(tool["id"])
            metadatas.append(
                {
                    "name": tool["name"],
                    "module": tool["module"],
                    "params": tool.get("params", ""),
                    "desc": tool["desc"],
                }
            )

        self._collection.add(documents=documents, ids=ids, metadatas=metadatas)

    def search(
        self, query: str, top_k: int = 7, top_k_per_chunk: int = 5
    ) -> List[Dict]:
        """
        Kullanıcı isteğine en uygun araçları bul.

        Args:
            query: Kullanıcı isteği
            top_k: Döndürülecek maksimum araç sayısı
            top_k_per_chunk: Her parça için getirilecek araç sayısı

        Returns:
            Benzerlik sırasına göre araç listesi
        """
        if not self._initialized:
            self.initialize()

        # Bağlaç bölme
        chunks = conjunction_split(query)

        if len(chunks) == 1:
            # Tek parça — direkt ara
            return self._search_single(chunks[0], top_k)
        else:
            # Birden fazla parça — her biri için ara, birleştir
            return self._search_multi_chunk(chunks, top_k, top_k_per_chunk)

    def _search_single(self, query: str, top_k: int) -> List[Dict]:
        """Tek sorgu ile arama."""
        results = self._collection.query(
            query_texts=[query],
            n_results=top_k,
        )

        found = []
        for i in range(len(results["ids"][0])):
            found.append(
                {
                    "id": results["ids"][0][i],
                    "name": results["metadatas"][0][i]["name"],
                    "module": results["metadatas"][0][i]["module"],
                    "params": results["metadatas"][0][i].get("params", ""),
                    "desc": results["metadatas"][0][i].get(
                        "desc", results["metadatas"][0][i]["name"]
                    ),
                    "similarity": round(1 - results["distances"][0][i], 4),
                }
            )
        return found

    def _search_multi_chunk(
        self, chunks: List[str], top_k: int, top_k_per_chunk: int
    ) -> List[Dict]:
        """Birden fazla parça ile arama — sonuçları birleştir."""
        all_results = {}

        for chunk in chunks:
            results = self._search_single(chunk, top_k_per_chunk)
            for r in results:
                tool_id = r["id"]
                # En yüksek benzerliği tut
                if (
                    tool_id not in all_results
                    or r["similarity"] > all_results[tool_id]["similarity"]
                ):
                    all_results[tool_id] = r
                    all_results[tool_id]["matched_chunk"] = chunk

        # Benzerliğe göre sırala ve top_k al
        sorted_results = sorted(
            all_results.values(), key=lambda x: x["similarity"], reverse=True
        )
        return sorted_results[:top_k]

    def get_tool_details(self, tool_ids: List[str]) -> List[Dict]:
        """Araç ID'lerinden detaylı bilgi getir."""
        details = []
        for tool in TOOL_REGISTRY:
            if tool["id"] in tool_ids:
                details.append(tool)
        return details

    def format_tools_for_llm(self, tools: List[Dict]) -> str:
        """Araçları LLM prompt'una uygun formata çevir.

        rich_info varsa → detaylı bilgi (çok yönlü araçlar)
        yoksa → kısa desc + params (tek yönlü araçlar)
        """
        lines = []
        for t in tools:
            if t.get("rich_info"):
                lines.append(t["rich_info"])
            else:
                params_str = f" (params: {t['params']})" if t.get("params") else ""
                output_str = f" → çıktı: {t['output']}" if t.get("output") else ""
                lines.append(f"- {t['id']}: {t['desc']}{params_str}{output_str}")
        return "\n".join(lines)


# ══════════════════════════════════════════════
# Singleton instance
# ══════════════════════════════════════════════

_selector_instance: Optional[ToolSelector] = None


def get_tool_selector(db_path: str = None) -> ToolSelector:
    """Singleton ToolSelector instance döndür."""
    global _selector_instance
    if _selector_instance is None:
        _selector_instance = ToolSelector(db_path=db_path)
    return _selector_instance


# ══════════════════════════════════════════════
# TEST
# ══════════════════════════════════════════════

if __name__ == "__main__":
    selector = get_tool_selector()
    selector.initialize()

    test_queries = [
        "config.txt dosyasını oku",
        "google.com'a ping at",
        "sunucular ayakta mı kontrol et",
        "config.txt'deki URL'lere ping at sonucu log.txt'ye yaz",
        "servers.txt dosyasındaki IP'leri bul ve DNS kayıtlarını çözümle",
        "Desktop'taki tüm dosyaları listele, txt olanları oku içinde URL varsa yanıt süresini ölç",
        "tamamen anonim şekilde internete bağlan",
        "ağımdaki güvenlik açıklarını tara",
        "WiFi şifremi göster",
        "firewall kurallarını listele",
    ]

    print(f"\n  {'═' * 70}")
    print(f"  TOOL SELECTOR TESTİ ({TOTAL_TOOLS} araç)")
    print(f"  {'═' * 70}\n")

    for query in test_queries:
        results = selector.search(query, top_k=7)
        chunks = conjunction_split(query)

        print(f' "{query}"')
        if len(chunks) > 1:
            print(f"     Parçalar: {chunks}")
        print("     Sonuçlar:")
        for r in results:
            print(f"       {r['similarity']:.3f}  {r['id']:<30} {r['name']}")
        print()
