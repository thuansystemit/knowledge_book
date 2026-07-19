"""OCRQ-01/02/03: OCR confidence accounting for the ING-06 quality gate.

Regression coverage for the "low scan quality" false-positive
(docs/ISSUE-ocr-quality-false-positive.md).
"""
from app.extraction.text_extractor import _summarize_ocr_quality

THRESHOLD = 70.0
MIN_RATIO = 0.5


def test_native_text_pdf_with_blank_pages_not_flagged():
    """AC-1/AC-2: a mostly born-digital doc (12 pages) where OCR only ran on 2
    pages — one blank (empty OCR), one low-confidence bibliography — must NOT
    raise the document-level low_confidence flag, and the blank page must be
    excluded from the mean and from low_pages."""
    recognised = {
        3: ("", None),        # blank separator page -> excluded entirely
        7: ("references ...", 44.3),  # genuine low-confidence furniture page
    }
    q = _summarize_ocr_quality(recognised, total_pages=12,
                               threshold=THRESHOLD, min_ratio=MIN_RATIO)
    assert q["low_confidence"] is False          # native-text gate (OCRQ-03)
    assert q["low_pages"] == [7]                  # blank page 3 excluded (OCRQ-02)
    assert q["mean_confidence"] == 44.3           # blank's ~0% not averaged in
    assert q["ocr_page_ratio"] == round(1 / 12, 3)  # only 1 non-blank OCR page


def test_blank_pages_excluded_from_mean():
    """OCRQ-02: an empty OCR result would score ~0% and must not drag the mean."""
    recognised = {
        0: ("", 0.0),          # blank -> excluded
        1: ("good text", 90.0),
        2: ("more text", 88.0),
    }
    q = _summarize_ocr_quality(recognised, total_pages=3,
                               threshold=THRESHOLD, min_ratio=MIN_RATIO)
    assert q["mean_confidence"] == 89.0            # (90+88)/2, blank ignored
    assert q["low_pages"] == []


def test_genuine_scan_still_flagged_no_regression():
    """AC-3: a truly scanned, low-quality document (high OCR coverage, low mean)
    must STILL raise low_confidence — the fix must not suppress true positives."""
    recognised = {i: (f"page {i} text", 40.0) for i in range(10)}
    q = _summarize_ocr_quality(recognised, total_pages=10,
                               threshold=THRESHOLD, min_ratio=MIN_RATIO)
    assert q["low_confidence"] is True
    assert q["ocr_page_ratio"] == 1.0
    assert len(q["low_pages"]) == 10


def test_high_coverage_high_confidence_not_flagged():
    """A clean full scan (high coverage, high confidence) is not flagged."""
    recognised = {i: (f"page {i}", 95.0) for i in range(10)}
    q = _summarize_ocr_quality(recognised, total_pages=10,
                               threshold=THRESHOLD, min_ratio=MIN_RATIO)
    assert q["low_confidence"] is False
    assert q["low_pages"] == []


def test_all_blank_ocr_pages():
    """Defensive: if every OCR'd page is blank, no confidence data exists ->
    not flagged, ratio 0."""
    recognised = {0: ("", None), 1: ("  ", None)}
    q = _summarize_ocr_quality(recognised, total_pages=5,
                               threshold=THRESHOLD, min_ratio=MIN_RATIO)
    assert q["mean_confidence"] is None
    assert q["low_confidence"] is False
    assert q["ocr_page_ratio"] == 0.0
