"""Tests for uaf.llm.metrics (automatic evaluation metrics)."""

import pytest
from uaf.llm.metrics import bleu, rouge_n, rouge_l, exact_match, token_f1


# --- BLEU ---

def test_bleu_perfect_match():
    score = bleu("the cat sat on the mat", "the cat sat on the mat")
    assert score.score > 0.9


def test_bleu_empty_hypothesis():
    score = bleu("", "the cat sat on the mat")
    assert score.score == 0.0


def test_bleu_no_overlap():
    score = bleu("completely different words here", "the cat sat on the mat")
    assert score.score < 0.1


def test_bleu_partial_overlap():
    score = bleu("the cat sat", "the cat sat on the mat")
    assert 0.0 < score.score < 1.0


def test_bleu_brevity_penalty_short_hyp():
    # Short hypothesis → brevity penalty < 1
    score = bleu("cat", "the cat sat on the mat")
    assert score.brevity_penalty < 1.0


def test_bleu_no_brevity_penalty_long_hyp():
    # Hypothesis at least as long as reference → bp = 1
    score = bleu("the cat sat on the mat today", "the cat sat on the mat")
    assert score.brevity_penalty == 1.0


def test_bleu_precisions_length():
    score = bleu("a b c", "a b c d", max_n=4)
    assert len(score.precisions) == 4


def test_bleu_score_in_range():
    score = bleu("hello world", "hello there world")
    assert 0.0 <= score.score <= 1.0


# --- ROUGE-N ---

def test_rouge_1_perfect():
    r = rouge_n("the cat sat", "the cat sat")
    assert r.f1 > 0.99


def test_rouge_1_no_overlap():
    r = rouge_n("hello world", "foo bar baz")
    assert r.f1 == 0.0


def test_rouge_1_partial():
    r = rouge_n("the cat sat on mat", "the cat sat on the mat")
    assert 0.0 < r.f1 <= 1.0


def test_rouge_2_bigrams():
    r = rouge_n("the cat sat on the mat", "the cat sat on the mat", n=2)
    assert r.f1 > 0.9


def test_rouge_f1_between_precision_recall():
    r = rouge_n("the quick brown fox", "the quick brown fox jumps")
    # F1 should be between precision and recall
    assert min(r.precision, r.recall) <= r.f1 <= max(r.precision, r.recall) + 0.001


def test_rouge_scores_in_range():
    r = rouge_n("some hypothesis text", "some reference text here")
    assert 0.0 <= r.precision <= 1.0
    assert 0.0 <= r.recall <= 1.0
    assert 0.0 <= r.f1 <= 1.0


# --- ROUGE-L ---

def test_rouge_l_perfect():
    r = rouge_l("the cat sat on the mat", "the cat sat on the mat")
    assert r.f1 > 0.99


def test_rouge_l_subsequence():
    # LCS of "the cat sat" and "the sat cat" is "the cat" or "the sat" (len 2)
    r = rouge_l("the cat sat", "the sat cat")
    assert r.f1 > 0.0


def test_rouge_l_no_overlap():
    r = rouge_l("alpha beta gamma", "delta epsilon zeta")
    assert r.f1 == 0.0


def test_rouge_l_scores_in_range():
    r = rouge_l("some words here", "different words there")
    assert 0.0 <= r.f1 <= 1.0


# --- Exact Match ---

def test_exact_match_identical():
    assert exact_match("hello world", "hello world") is True


def test_exact_match_different():
    assert exact_match("hello world", "goodbye world") is False


def test_exact_match_normalized():
    assert exact_match("  Hello World  ", "hello world") is True


def test_exact_match_case_sensitive():
    assert exact_match("Hello", "hello", normalize=False) is False


def test_exact_match_unnormalized_identical():
    assert exact_match("hello", "hello", normalize=False) is True


# --- Token F1 ---

def test_token_f1_perfect():
    assert token_f1("the cat sat", "the cat sat") == 1.0


def test_token_f1_no_overlap():
    assert token_f1("apple orange", "banana mango") == 0.0


def test_token_f1_partial():
    score = token_f1("the cat sat on the mat", "the dog sat on the floor")
    assert 0.0 < score < 1.0


def test_token_f1_in_range():
    score = token_f1("some hypothesis here", "some reference words")
    assert 0.0 <= score <= 1.0
