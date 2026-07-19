"""OUT-04e: chunk sub-passage splitting for full-coverage embedding. Pure (no DB,
no embedding host) — safe in CI."""
from app.embeddings import split_passages


def test_empty_and_whitespace():
    assert split_passages("", 100) == []
    assert split_passages("   \n  ", 100) == []


def test_short_text_is_one_passage():
    assert split_passages("a short chunk", 100) == ["a short chunk"]


def test_long_text_splits_and_covers_everything():
    text = "".join(str(i % 10) for i in range(250))  # 250 chars
    parts = split_passages(text, 100)
    assert len(parts) == 3                      # 100 + 100 + 50
    assert "".join(parts) == text               # full coverage, no gaps
    assert all(len(p) <= 100 for p in parts)    # every sub-passage within budget


def test_boundary_exact_multiple():
    text = "x" * 200
    parts = split_passages(text, 100)
    assert parts == ["x" * 100, "x" * 100]
