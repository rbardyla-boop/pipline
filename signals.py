import re
from dataclasses import dataclass, field


@dataclass
class SignalResult:
    id: str
    label: str
    score: float
    uncertainty: float
    excerpts: list[str]
    rationale: str
    emotional_intensity: float = 0.0


_PATTERNS = {
    "fear": [
        r"dangerous", r"threat", r"crisis", r"catastrophic", r"risk\s+to\s+public\s+safety"
    ],
    "urgency": [
        r"urgent", r"immediately", r"right\s+now", r"breaking", r"critical",
        r"before\s+it\s+is\s+too\s+late"
    ],
    "authority": [
        r"experts\s+say", r"officials\s+stated", r"government\s+sources", r"scientists\s+confirm"
    ],
    "loss_aversion": [
        r"lose\s+access", r"irreversible\s+damage", r"too\s+late", r"no\s+longer\s+available"
    ],
}


def _detect_pattern_signal(signal_id: str, regexes: list[str], text: str) -> SignalResult:
    sentences = re.split(r"[.!?\n]+", text)
    matched_excerpts: list[str] = []
    match_count = 0

    for sentence in sentences:
        s = sentence.strip()
        if not s:
            continue
        for regex in regexes:
            if re.search(regex, s, re.IGNORECASE):
                matched_excerpts.append(s)
                match_count += 1
                break

    score = round(min(1.0, match_count / 3.0), 2)
    return SignalResult(
        id=signal_id,
        label=signal_id.replace("_", " ").title(),
        score=score,
        uncertainty=round(0.15 if score > 0 else 0.05, 2),
        excerpts=list(dict.fromkeys(matched_excerpts))[:3],
        rationale=f"Identified {match_count} distinct pattern matches within the processed text layer.",
        emotional_intensity=round(min(1.0, score * 1.1), 2),
    )


def _detect_entropy(text: str) -> SignalResult:
    words = re.findall(r"\b\w+\b", text.lower())
    total = len(words)
    if total == 0:
        return SignalResult(
            id="entropy", label="Narrative Entropy", score=0.0,
            uncertainty=0.1, excerpts=[], rationale="No word tokens found."
        )
    ratio = len(set(words)) / total
    entropy_score = round(1.0 - ratio, 2)
    return SignalResult(
        id="entropy",
        label="Narrative Entropy",
        score=entropy_score,
        uncertainty=0.1,
        excerpts=[],
        rationale=f"Lexical variation ratio: {ratio:.4f}. Low diversity = high narrative control.",
    )


def run_analysis(text: str) -> list[SignalResult]:
    results = [
        _detect_pattern_signal(sid, regexes, text)
        for sid, regexes in _PATTERNS.items()
    ]
    results.append(_detect_entropy(text))
    return results


def format_signal_profile(signals: list[SignalResult]) -> str:
    return " ".join(f"{s.id}={s.score}" for s in signals)
