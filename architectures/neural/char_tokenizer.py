"""Character-level tokenizer — no external dependencies.

Builds a vocabulary from the provided corpus text plus a fixed set of
printable ASCII characters. Unknown characters map to index 0 (the
padding/unknown token).
"""

from __future__ import annotations


_BASE_CHARS = (
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789"
    " .,!?:;'-\"\n\t()[]{}—–"
)


class CharTokenizer:
    """Character-level tokenizer with a fixed vocabulary.

    Args:
        corpus: Text used to extend the vocabulary beyond the base character
                set. Any character appearing in *corpus* but not in the base
                set is added to the vocabulary.
    """

    def __init__(self, corpus: str = "") -> None:
        chars = sorted(set(_BASE_CHARS + corpus))
        # Index 0 reserved for unknown/padding
        self.itos: dict[int, str] = {0: "<unk>"}
        self.stoi: dict[str, int] = {"<unk>": 0}
        for i, ch in enumerate(chars, start=1):
            self.itos[i] = ch
            self.stoi[ch] = i
        self.vocab_size: int = len(self.itos)

    def encode(self, text: str) -> list[int]:
        """Encode *text* to a list of token ids."""
        return [self.stoi.get(c, 0) for c in text]

    def decode(self, ids: list[int]) -> str:
        """Decode a list of token ids back to a string."""
        return "".join(self.itos.get(i, "?") for i in ids if i != 0)
