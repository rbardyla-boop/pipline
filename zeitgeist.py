import os
import json
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

load_dotenv()

try:
    from tavily import TavilyClient
    TAVILY_AVAILABLE = True
except ImportError:
    TAVILY_AVAILABLE = False

FALLBACK_SIGNALS = [
    "2026 geopolitical oil price shock energy anxiety blackout",
    "AI slop fatigue authentic human creativity demand",
    "Gen Z identity crisis IRL authenticity nostalgia craft revival",
    "attention war budget reallocation mental health loneliness epidemic",
    "legacy meaning-making amid global uncertainty economic sacrifice"
]

CACHE_FILE = "logs/zeitgeist_cache.json"
CACHE_TTL_HOURS = 6


class ZeitgeistInjector:
    def __init__(self):
        self.model = SentenceTransformer(os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2"))
        self.api_key = os.getenv("TAVILY_API_KEY")
        Path("logs").mkdir(exist_ok=True)

    def _load_cache(self) -> dict | None:
        if not Path(CACHE_FILE).exists():
            return None
        with open(CACHE_FILE) as f:
            cache = json.load(f)
        cached_at = datetime.fromisoformat(cache["timestamp"])
        if datetime.now() - cached_at < timedelta(hours=CACHE_TTL_HOURS):
            return cache
        return None

    def _save_cache(self, data: dict):
        data["timestamp"] = datetime.now().isoformat()
        with open(CACHE_FILE, "w") as f:
            json.dump(data, f, indent=2)

    def fetch_signals(self, domain: str = "general") -> str:
        cached = self._load_cache()
        if cached and cached.get("domain") == domain:
            print(f"[ZEITGEIST] Using cached signals (TTL={CACHE_TTL_HOURS}h)")
            return cached["raw_text"]

        if TAVILY_AVAILABLE and self.api_key and self.api_key != "your_key_here":
            queries = [
                f"2026 cultural anxiety trends {domain}",
                "generational zeitgeist creative economy 2026",
                "attention economy slop fatigue authentic hit creation 2026"
            ]
            client = TavilyClient(api_key=self.api_key)
            snippets = []
            for q in queries:
                try:
                    result = client.search(q, max_results=3)
                    for r in result.get("results", []):
                        snippets.append(r.get("content", "")[:300])
                except Exception as e:
                    print(f"[ZEITGEIST] Tavily error: {e}")
            raw_text = " ".join(snippets) if snippets else " ".join(FALLBACK_SIGNALS)
        else:
            print("[ZEITGEIST] No Tavily key — using calibrated fallback signals.")
            raw_text = " ".join(FALLBACK_SIGNALS)

        self._save_cache({"domain": domain, "raw_text": raw_text})
        return raw_text

    def get_vector(self, domain: str = "general") -> np.ndarray:
        raw = self.fetch_signals(domain)
        return self.model.encode(raw, normalize_embeddings=True)

    def get_formatted_context(self, domain: str = "general") -> str:
        from signals import run_analysis, format_signal_profile
        raw = self.fetch_signals(domain)
        signal_results = run_analysis(raw)

        profile = format_signal_profile(signal_results)

        high_excerpts = []
        for s in signal_results:
            for excerpt in s.excerpts[:1]:
                high_excerpts.append(f'- [{s.id}] "...{excerpt[:120]}..."')

        lines = [
            f"[LIVE 2026 CULTURAL FRACTURES — {domain.upper()}]",
            f"Signal profile: {profile}",
            "",
            "High-intensity excerpts:",
        ]
        if high_excerpts:
            lines.extend(high_excerpts)
        else:
            lines.append("- No high-intensity rhetorical patterns detected in current window.")

        lines.append(f"\nRaw context: {raw[:800]}")
        return "\n".join(lines)
