"""Shared JSON-object extraction. Tolerates code fences / surrounding prose by
isolating the outermost { ... }. Raises JSONDecodeError when nothing parses —
callers must record that as a chunk error, never silently drop the chunk."""
import json


def extract_json_object(text: str) -> dict:
    text = (text or "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return json.loads(text[start : end + 1])
    raise json.JSONDecodeError("no JSON object found in model response", text, 0)
