"""Shared JSON-object extraction. Tolerates code fences / surrounding prose by
isolating the outermost { ... }. Raises JSONDecodeError when nothing parses —
callers must record that as a chunk error, never silently drop the chunk.

EFT-01: strips <think>…</think> reasoning preambles (qwen, deepseek) and
markdown ```json…``` fences before brace extraction."""
import json
import re

# Reasoning-model preamble (qwen, deepseek, etc.) — strip before parsing.
_THINK_RE = re.compile(r"<think>[\s\S]*?</think>", re.IGNORECASE)

# Markdown code fences: ```json … ``` or bare ``` … ```.
_FENCE_RE = re.compile(r"```(?:json)?\s*\n?([\s\S]*?)```")


def extract_json_object(text: str) -> dict:
    text = (text or "").strip()
    # 1. Try raw parse (already clean JSON).
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # 2. Strip reasoning preamble + markdown fences, then retry.
    text = _THINK_RE.sub("", text).strip()
    text = _FENCE_RE.sub(r"\1", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # 3. Outermost brace extraction (tolerates prose around the JSON).
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass
    raise json.JSONDecodeError("no JSON object found in model response", text, 0)
