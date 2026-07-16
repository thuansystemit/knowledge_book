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
    # 4. Repair/salvage a truncated object (EFT-06) — last resort before failing.
    repaired = _repair_json(text)
    if repaired is not None:
        repaired["repaired"] = True
        try:
            from app.observability import audit
            audit("CHUNK_REPAIRED", chars=len(text))
        except Exception:
            pass
        return repaired
    raise json.JSONDecodeError("no JSON object found in model response", text, 0)


def _repair_json(text: str) -> dict | None:
    """Salvage a truncated JSON object (EFT-06). Walks from the first `{` tracking
    string state and the open `{`/`[` stack, then closes a dangling string, drops a
    trailing comma, and closes the open structures in correct LIFO order. Returns
    the parsed dict, or None if it still won't parse. Never raises."""
    start = text.find("{")
    if start < 0:
        return None
    frag = text[start:]
    stack: list[str] = []
    in_str = False
    esc = False
    for ch in frag:
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch in "{[":
            stack.append(ch)
        elif ch == "}" and stack and stack[-1] == "{":
            stack.pop()
        elif ch == "]" and stack and stack[-1] == "[":
            stack.pop()
    if in_str:
        frag += '"'                       # close the truncated string value
    frag = re.sub(r",(\s*)$", r"\1", frag)  # drop a trailing comma
    for opener in reversed(stack):          # close open structures, innermost first
        frag += "}" if opener == "{" else "]"
    try:
        result = json.loads(frag)
        return result if isinstance(result, dict) else None
    except json.JSONDecodeError:
        return None
