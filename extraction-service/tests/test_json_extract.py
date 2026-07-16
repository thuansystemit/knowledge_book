"""Unit tests for EFT-01 (extract_json_object preprocessing) and EFT-03 (sanitize_text).

Run with: python -m pytest tests/test_json_extract.py -v
"""
import json
import pytest

from app.llm._json import extract_json_object
from app.extraction.chunker import sanitize_text


# ---------------------------------------------------------------------------
# EFT-01: extract_json_object — <think> stripping + fence stripping
# ---------------------------------------------------------------------------

class TestExtractJsonObject:
    """EFT-01: response preprocessing in extract_json_object."""

    def test_bare_json(self):
        """Already-clean JSON parses as-is."""
        assert extract_json_object('{"a": 1}') == {"a": 1}

    def test_think_block_stripped(self):
        """<think>…</think> reasoning preamble is removed before parsing."""
        text = '<think>let me reason about this...</think>{"a": 1}'
        assert extract_json_object(text) == {"a": 1}

    def test_think_block_multiline(self):
        """Multi-line <think> block with nested content is stripped."""
        text = (
            "<think>\nI need to extract concepts.\n"
            "The text mentions DRY principle.\n</think>\n"
            '{"concepts": [], "relations": []}'
        )
        result = extract_json_object(text)
        assert result == {"concepts": [], "relations": []}

    def test_think_block_case_insensitive(self):
        """<THINK> and <Think> are both stripped."""
        text = '<THINK>reasoning</THINK>{"ok": true}'
        assert extract_json_object(text) == {"ok": True}

    def test_markdown_fence_json(self):
        """Markdown ```json … ``` fences are stripped."""
        text = '```json\n{"a": 1}\n```'
        assert extract_json_object(text) == {"a": 1}

    def test_markdown_fence_bare(self):
        """Bare ``` … ``` fences (no language tag) are stripped."""
        text = '```\n{"a": 1}\n```'
        assert extract_json_object(text) == {"a": 1}

    def test_think_plus_fence(self):
        """Both <think> and fences present — both stripped."""
        text = '<think>blah</think>\n```json\n{"a": 1}\n```'
        assert extract_json_object(text) == {"a": 1}

    def test_prose_around_json(self):
        """JSON embedded in prose (outermost brace extraction)."""
        text = 'Here is the result: {"a": 1} hope that helps!'
        assert extract_json_object(text) == {"a": 1}

    def test_no_json_raises(self):
        """No JSON at all raises JSONDecodeError."""
        with pytest.raises(json.JSONDecodeError):
            extract_json_object("just some text with no braces")

    def test_empty_string(self):
        """Empty/None input raises JSONDecodeError."""
        with pytest.raises(json.JSONDecodeError):
            extract_json_object("")
        with pytest.raises(json.JSONDecodeError):
            extract_json_object(None)

    def test_nested_json(self):
        """Nested objects parse correctly."""
        text = '{"concepts": [{"name": "DRY", "type": "Principle"}], "relations": []}'
        result = extract_json_object(text)
        assert result["concepts"][0]["name"] == "DRY"

    def test_think_with_json_inside_think(self):
        """JSON-like content inside <think> is ignored; outer JSON is returned."""
        text = '<think>{"wrong": true}</think>{"right": true}'
        assert extract_json_object(text) == {"right": True}

    def test_existing_behavior_preserved(self):
        """Pre-existing outermost-brace extraction still works."""
        text = 'Some preamble text\n{"key": "value"}\nSome trailing text'
        assert extract_json_object(text) == {"key": "value"}


# ---------------------------------------------------------------------------
# EFT-03: sanitize_text — control character stripping
# ---------------------------------------------------------------------------

class TestSanitizeText:
    """EFT-03: C0 control character sanitization."""

    def test_nul_stripped(self):
        """NUL bytes are removed."""
        assert sanitize_text("foo\x00bar") == "foobar"

    def test_tab_preserved(self):
        """Tab characters are preserved."""
        assert sanitize_text("foo\tbar") == "foo\tbar"

    def test_newline_preserved(self):
        """Newlines are preserved."""
        assert sanitize_text("foo\nbar") == "foo\nbar"

    def test_cr_preserved(self):
        """Carriage returns are preserved."""
        assert sanitize_text("foo\rbar") == "foo\rbar"

    def test_formfeed_preserved(self):
        """Form-feed (page marker) is preserved."""
        assert sanitize_text("foo\fbar") == "foo\fbar"

    def test_bell_stripped(self):
        """BEL (\x07) is stripped."""
        assert sanitize_text("foo\x07bar") == "foobar"

    def test_backspace_stripped(self):
        """Backspace (\x08) is stripped."""
        assert sanitize_text("foo\x08bar") == "foobar"

    def test_vt_stripped(self):
        """Vertical tab (\x0b) is stripped."""
        assert sanitize_text("foo\x0bbar") == "foobar"

    def test_multiple_control_chars(self):
        """Multiple different control chars in one string."""
        assert sanitize_text("\x00hello\x01\x02world\x1f") == "helloworld"

    def test_clean_text_unchanged(self):
        """Already-clean text is a no-op (idempotent)."""
        clean = "Hello, world! This is a test.\nNew line.\tTab."
        assert sanitize_text(clean) == clean

    def test_idempotent(self):
        """Running sanitize twice gives the same result."""
        dirty = "foo\x00\x01bar\x1fbaz"
        once = sanitize_text(dirty)
        twice = sanitize_text(once)
        assert once == twice == "foobarbaz"

    def test_empty_string(self):
        """Empty string is handled."""
        assert sanitize_text("") == ""


# ---------------------------------------------------------------------------
# EFT-06: JSON repair / salvage of truncated objects
# ---------------------------------------------------------------------------
from app.llm._json import _repair_json  # noqa: E402


class TestRepairJson:
    def test_truncated_nested_object(self):
        """Truncated mid-string in a nested array repairs to valid, parseable JSON."""
        out = _repair_json('{"concepts":[{"name":"X","type":"C')
        assert out == {"concepts": [{"name": "X", "type": "C"}]}

    def test_truncated_after_comma(self):
        out = _repair_json('{"a": 1, "b": 2,')
        assert out == {"a": 1, "b": 2}

    def test_unterminated_string_value(self):
        out = _repair_json('{"summary": "an incomplete sen')
        assert out == {"summary": "an incomplete sen"}

    def test_garbage_returns_none(self):
        assert _repair_json("not json at all") is None
        assert _repair_json("") is None
        assert _repair_json("[1,2,3") is None  # top-level array, not an object

    def test_already_valid_passthrough(self):
        assert _repair_json('{"a": 1}') == {"a": 1}

    def test_extract_json_object_uses_repair_and_flags(self):
        """extract_json_object salvages a truncated object and marks it repaired."""
        out = extract_json_object('{"concepts":[{"name":"X","type":"C')
        assert out.get("repaired") is True
        assert out["concepts"] == [{"name": "X", "type": "C"}]

    def test_extract_json_object_still_raises_on_garbage(self):
        with pytest.raises(json.JSONDecodeError):
            extract_json_object("this has no json object")


# ---------------------------------------------------------------------------
# EFT-11: extraction logging (SFT data collection) — on/off + dedup
# ---------------------------------------------------------------------------
import glob  # noqa: E402
from types import SimpleNamespace  # noqa: E402


class TestLogExtraction:
    def test_off_is_noop(self, tmp_path):
        from app.pipeline import _log_extraction
        d = str(tmp_path / "log")
        cfg = SimpleNamespace(log_extractions=False, extraction_log_dir=d)
        _log_extraction(cfg, "m", "prompt", "chunk", {"concepts": []})
        assert not glob.glob(d + "/*.json")

    def test_on_writes_deduped_record(self, tmp_path):
        from app.pipeline import _log_extraction
        d = str(tmp_path / "log")
        cfg = SimpleNamespace(log_extractions=True, extraction_log_dir=d)
        _log_extraction(cfg, "m1", "the-prompt", "chunk text", {"concepts": [{"name": "X"}]})
        files = glob.glob(d + "/*.json")
        assert len(files) == 1
        rec = json.load(open(files[0]))
        assert rec["chunk_text"] == "chunk text"
        assert rec["model_id"] == "m1"
        assert rec["extraction_json"] == {"concepts": [{"name": "X"}]}
        assert rec["prompt_hash"]
        # idempotent: same (model, prompt, chunk) does not write a second file
        _log_extraction(cfg, "m1", "the-prompt", "chunk text", {"concepts": [{"name": "X"}]})
        assert len(glob.glob(d + "/*.json")) == 1

    def test_never_raises_on_bad_dir(self):
        from app.pipeline import _log_extraction
        cfg = SimpleNamespace(log_extractions=True, extraction_log_dir="/proc/nonwritable/x")
        _log_extraction(cfg, "m", "p", "c", {"concepts": []})  # must not raise
