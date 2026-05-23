"""Symbolic Grammar cognition architecture (Arch #2).

Deterministic CFG + template-substitution mutator — no API calls, no
model downloads (unless SYMBOLIC_USE_SENTENCE_TRANSFORMER=true).
"""

from architectures.symbolic_grammar.adapter import SymbolicGrammarCognition

__all__ = ["SymbolicGrammarCognition"]
