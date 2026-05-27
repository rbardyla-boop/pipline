"""Automatic evaluation metrics for LLM outputs.

Implements the metrics described in the LLM Evaluation guide:
  - BLEU:        n-gram precision for translation
  - ROUGE-N:     n-gram recall for summarization
  - ROUGE-L:     longest common subsequence
  - Exact Match: strict equality check
  - Token F1:    token-level overlap (QA)

All implementations are pure Python — no external NLP libraries required.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class BLEUScore:
    score: float         # corpus/sentence BLEU in [0, 1]
    precisions: list[float]  # per-n-gram precision
    brevity_penalty: float


@dataclass(frozen=True)
class ROUGEScore:
    precision: float
    recall: float
    f1: float


def _ngrams(tokens: list[str], n: int) -> Counter:
    return Counter(tuple(tokens[i: i + n]) for i in range(len(tokens) - n + 1))


def bleu(hypothesis: str, reference: str, max_n: int = 4) -> BLEUScore:
    """Sentence BLEU score (modified precision with brevity penalty).

    Args:
        hypothesis: Model output string.
        reference:  Gold reference string.
        max_n:      Maximum n-gram order (default 4 = BLEU-4).

    Returns:
        BLEUScore with the final score and per-order precisions.
    """
    hyp_tokens = hypothesis.lower().split()
    ref_tokens = reference.lower().split()

    if not hyp_tokens:
        return BLEUScore(0.0, [0.0] * max_n, 0.0)

    precisions: list[float] = []
    for n in range(1, max_n + 1):
        hyp_ngrams = _ngrams(hyp_tokens, n)
        ref_ngrams = _ngrams(ref_tokens, n)
        if not hyp_ngrams:
            precisions.append(0.0)
            continue
        clipped = {ng: min(c, ref_ngrams[ng]) for ng, c in hyp_ngrams.items()}
        p = sum(clipped.values()) / max(1, sum(hyp_ngrams.values()))
        precisions.append(p)

    # Geometric mean of precisions (smoothed)
    log_avg = 0.0
    for p in precisions:
        log_avg += math.log(p + 1e-10) / max_n

    # Brevity penalty
    bp = min(1.0, math.exp(1 - len(ref_tokens) / max(1, len(hyp_tokens))))
    score = bp * math.exp(log_avg)

    return BLEUScore(round(score, 4), [round(p, 4) for p in precisions], round(bp, 4))


def rouge_n(hypothesis: str, reference: str, n: int = 1) -> ROUGEScore:
    """ROUGE-N score (recall-oriented).

    Args:
        hypothesis: Model output.
        reference:  Gold reference.
        n:          N-gram order.

    Returns:
        ROUGEScore with precision, recall, and F1.
    """
    hyp_tokens = hypothesis.lower().split()
    ref_tokens = reference.lower().split()

    hyp_ngrams = _ngrams(hyp_tokens, n)
    ref_ngrams = _ngrams(ref_tokens, n)

    overlap = sum(min(c, ref_ngrams[ng]) for ng, c in hyp_ngrams.items())
    ref_total = max(1, sum(ref_ngrams.values()))
    hyp_total = max(1, sum(hyp_ngrams.values()))

    precision = overlap / hyp_total
    recall = overlap / ref_total
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    return ROUGEScore(round(precision, 4), round(recall, 4), round(f1, 4))


def rouge_l(hypothesis: str, reference: str) -> ROUGEScore:
    """ROUGE-L score using longest common subsequence.

    Args:
        hypothesis: Model output.
        reference:  Gold reference.

    Returns:
        ROUGEScore with precision, recall, and F1.
    """
    hyp = hypothesis.lower().split()
    ref = reference.lower().split()
    lcs_len = _lcs_length(hyp, ref)

    precision = lcs_len / max(1, len(hyp))
    recall = lcs_len / max(1, len(ref))
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    return ROUGEScore(round(precision, 4), round(recall, 4), round(f1, 4))


def _lcs_length(a: list[str], b: list[str]) -> int:
    """Compute length of longest common subsequence (DP)."""
    m, n = len(a), len(b)
    if m == 0 or n == 0:
        return 0
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if a[i - 1] == b[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
    return dp[m][n]


def exact_match(hypothesis: str, reference: str, normalize: bool = True) -> bool:
    """Exact Match metric (EM).

    Args:
        hypothesis: Model output.
        reference:  Gold reference.
        normalize:  Strip whitespace and lowercase before comparison.

    Returns:
        True if strings match exactly after normalization.
    """
    if normalize:
        return hypothesis.strip().lower() == reference.strip().lower()
    return hypothesis == reference


def token_f1(hypothesis: str, reference: str) -> float:
    """Token-level F1 score — common in QA evaluation.

    Treats hypothesis and reference as bags of tokens, measures overlap.
    """
    hyp_tokens = hypothesis.lower().split()
    ref_tokens = reference.lower().split()
    hyp_counts = Counter(hyp_tokens)
    ref_counts = Counter(ref_tokens)

    overlap = sum(min(c, ref_counts[t]) for t, c in hyp_counts.items())
    precision = overlap / max(1, len(hyp_tokens))
    recall = overlap / max(1, len(ref_tokens))
    if precision + recall == 0:
        return 0.0
    return round(2 * precision * recall / (precision + recall), 4)
