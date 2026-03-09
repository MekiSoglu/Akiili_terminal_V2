"""
LLMClient - Ollama API İstemcisi.

Ollama üzerinde çalışan lokal modelle iletişim kurar.
Tek sorumluluk: prompt gönder, JSON cevap al.

v2 DEĞİŞİKLİK:
    - ask() artık model parametresi alıyor (1.5B/7B/14B seçimi)
    - Timeout model boyutuna göre ayarlanıyor
"""

import json
import logging
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)

# Model boyutuna göre timeout (saniye)
MODEL_TIMEOUTS = {
    "qwen2.5-coder:1.5b": 30,
    "gemma3:4b": 60,
    "deepseek-r1:8b": 100,
    "gemma3:12b": 180,
}


class LLMClient:
    """
    Ollama API ile haberleşir.
    Sadece metin gönderir, JSON döner.
    İş mantığı bilmez.
    """

    def __init__(self, config_path: str = "config.json"):
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        llm_config = config.get("llm", {})
        self.base_url = llm_config.get("base_url", "http://localhost:11434")
        self.default_model = llm_config.get("model", "qwen2.5:14b")
        self.temperature = llm_config.get("temperature", 0.1)
        self.max_retries = llm_config.get("max_retries", 2)

    def ask(self, prompt: str, model: str = None) -> dict | None:
        """
        Prompt gönder, JSON cevap al.

        Args:
            prompt: LLM'e gönderilecek prompt
            model: Kullanılacak model (None ise config'deki default)

        Returns:
            Parsed JSON dict veya None
        """
        active_model = model or self.default_model

        for attempt in range(self.max_retries + 1):
            raw_response = self._call_api(prompt, active_model)

            if raw_response is None:
                continue

            parsed = self._extract_json(raw_response)

            if parsed is not None:
                return parsed

            logger.warning(
                f"JSON parse hatası (deneme {attempt + 1}/{self.max_retries + 1})"
            )

        logger.error(f"LLM'den geçerli JSON alınamadı (model: {active_model})")
        return None

    def _call_api(self, prompt: str, model: str) -> str | None:
        """Ollama API'ye istek gönder."""
        url = f"{self.base_url}/api/generate"
        timeout = MODEL_TIMEOUTS.get(model, 120)

        payload = json.dumps(
            {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": self.temperature,
                    "num_predict": 1024,
                },
                "format": "json",
            }
        ).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
                return data.get("response", "")
        except urllib.error.URLError as e:
            logger.error(f"Ollama bağlantı hatası: {e}")
            return None
        except Exception as e:
            logger.error(f"API hatası: {e}")
            return None

    @staticmethod
    def _extract_json(text: str) -> dict | None:
        """
        LLM çıktısından JSON çıkar.
        Model bazen JSON'dan önce/sonra metin ekler,
        bu metot sadece JSON kısmını alır.
        """
        text = text.strip()

        # Direkt parse dene
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # JSON bloğunu bul
        import re

        patterns = [
            r"```json\s*(.*?)\s*```",
            r"```\s*(.*?)\s*```",
            r"\{.*\}",
            r"\[.*\]",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                try:
                    return json.loads(
                        match.group(1) if "```" in pattern else match.group(0)
                    )
                except (json.JSONDecodeError, IndexError):
                    continue

        return None
