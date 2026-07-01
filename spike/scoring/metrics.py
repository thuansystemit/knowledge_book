"""Core measurement primitives for the spike. Dependency-light on purpose.

char_fidelity  -> digital extraction quality (H1)   target >= 0.98
word_accuracy  -> OCR quality via 1 - WER (H3, H4)  target >= 0.95

Both operate on a single sample page's text vs. its ground truth. We score
sample pages only (5 per doc), so an O(n*m) edit-distance is fine.
"""
from __future__ import annotations
import re


def _normalize(text: str) -> str:
    """Whitespace-collapse + strip. Keeps case/punctuation: extraction should
    preserve them. Hyphenation/line-wrap artifacts are intentionally NOT fixed
    here — we want to *measure* them, not hide them."""
    return re.sub(r"\s+", " ", text).strip()


def _levenshtein(a: str, b: str) -> int:
    """Classic DP edit distance over characters."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cur[j] = min(
                prev[j] + 1,        # deletion
                cur[j - 1] + 1,     # insertion
                prev[j - 1] + (ca != cb),  # substitution
            )
        prev = cur
    return prev[-1]


def char_fidelity(extracted: str, reference: str) -> float:
    """1 - (char edit distance / reference length). Clamped to [0, 1]."""
    ref = _normalize(reference)
    ext = _normalize(extracted)
    if not ref:
        return 1.0 if not ext else 0.0
    dist = _levenshtein(ext, ref)
    return max(0.0, 1.0 - dist / len(ref))


def _word_levenshtein(a: list[str], b: list[str]) -> int:
    """Edit distance over word tokens — the numerator of WER."""
    if a == b:
        return 0
    prev = list(range(len(b) + 1))
    for i, wa in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, wb in enumerate(b, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (wa != wb))
        prev = cur
    return prev[-1]


def word_accuracy(hypothesis: str, reference: str) -> float:
    """1 - WER. Word Error Rate = word-edit-distance / reference word count."""
    ref_words = _normalize(reference).split()
    hyp_words = _normalize(hypothesis).split()
    if not ref_words:
        return 1.0 if not hyp_words else 0.0
    wer = _word_levenshtein(hyp_words, ref_words) / len(ref_words)
    return max(0.0, 1.0 - wer)
