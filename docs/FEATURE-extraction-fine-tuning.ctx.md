# CTX: Extraction Fine-Tuning (structured-output reliability + prompt hardening + eval)

> **AI digest of `FEATURE-extraction-fine-tuning.md`. Self-contained -- read this alone.**
> Status: PROPOSED, not started (2026-07-16). Convention: paired `*.ctx.md`; keep in sync.

## What
Harden the extraction pipeline so LLM calls reliably produce valid JSON (concepts/relations for chunks, Brief for docs). Replace ad-hoc retry/token patches with a principled layered strategy: capability-aware JSON mode per provider, response preprocessing (strip reasoning preambles), JSON repair/salvage, escalating retries, prompt hardening, text sanitization, an eval harness, and a backfill path for damaged docs. Optional Phase 3: LoRA fine-tuning data collection.

## Failure modes (production evidence)
1. **FM-1 JSON truncation** -- reasoning model (qwen via NVIDIA) spends tokens on `<think>` blocks, hits `max_tokens`, truncates mid-JSON -> `extract_json_object` raises `"no JSON object found"`. Breaks chunks + Brief.
2. **FM-2 JSON mode disabled** -- `openai_provider.py:23` `self._json_mode = not base_url` -> NVIDIA endpoint never gets `response_format`. The single most reliable structured-output lever is off.
3. **FM-3 Reasoning overhead** -- thinking tokens waste budget + increase latency + raise truncation risk. Structured extraction is template-filling, not problem-solving.
4. **FM-4 Malformed structure** -- LLM emits bare strings instead of objects in `concepts`/`relations` arrays. `graph_builder.py:69-71` guards defensively but doesn't prevent.
5. **FM-5 Control chars** -- OCR NUL/control chars in text -> node definitions -> `JSON` column (`models.py:86`) -> breaks casts/rendering.

## Locked decisions
- **No new dependencies.** JSON repair is a ~30-line function in `_json.py`, not a library.
- **Config-driven JSON mode** via `OPENAI_JSON_MODE` env var (auto|force|off). Auto-detection caches result for process lifetime.
- **Prompt changes auto-invalidate chunk cache.** Cache key includes prompt text (`chunk_cache.key(model_id, kg_prompt, header)`); no separate versioning mechanism needed.
- **`graph` column stays `JSON` (not `JSONB`).** Both reject NUL; sanitization required regardless. No migration needed.
- **Fine-tuning deferred** to Phase 3. Prompt + JSON mode + instruct model tried first.
- **Eval harness before any A/B testing.** No prompt/model change ships without measured metrics.

## NVIDIA JSON mode viability
NVIDIA `integrate.api.nvidia.com/v1` supports `response_format={"type":"json_object"}` for most hosted models incl. Qwen instruct variants. Also supports `{"type":"json_schema","json_schema":{...}}` for structured output. **Verify** before implementing:
```bash
curl -s https://integrate.api.nvidia.com/v1/chat/completions \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"MODEL_ID","messages":[{"role":"user","content":"say hello as JSON"}],"response_format":{"type":"json_object"},"max_tokens":100}'
```
200 + valid JSON = supported. 400/422 = not supported for that model; `OPENAI_JSON_MODE=off` stays.

## File pointers (existing code to modify)

| File | Lines | What |
|---|---|---|
| `app/llm/_json.py` | 1-17 | `extract_json_object` -- add `<think>` stripping (EFT-01), JSON repair (EFT-06) |
| `app/llm/openai_provider.py` | 23 | `self._json_mode = not base_url` -- replace with capability flag (EFT-05) |
| `app/llm/openai_provider.py` | 38-55 | `complete_json` -- read `_json_mode` from config, send `response_format` conditionally |
| `app/pipeline.py` | 268 | `max_tokens=8000` hardcoded in `_call_chunk` -- read from `cfg.extract_max_tokens` (EFT-04) |
| `app/pipeline.py` | 266-278 | `_call_chunk` retry loop -- replace with escalating retry policy (EFT-07) |
| `app/pipeline.py` | 383-412 | `_make_brief` -- use `cfg.brief_max_tokens` + escalating retry (EFT-04/07) |
| `app/pipeline.py` | 404 | `max_tokens=6000` hardcoded in `_make_brief` -- read from config (EFT-04) |
| `app/prompts/kg_extract.txt` | 1-40 | Extraction prompt -- add anti-reasoning preamble, schema enforcement, few-shot (EFT-02) |
| `app/prompts/brief.txt` | 1-17 | Brief prompt -- add anti-reasoning preamble, word cap (EFT-02) |
| `app/extraction/chunker.py` | 79 | Chunk content assembly -- sanitize control chars (EFT-03) |
| `app/graph_builder.py` | 77-97 | `_add_concept` / `_add_relation` -- sanitize name/definition/evidence (EFT-03) |
| `app/config.py` | 62-83 | Add new settings (EFT-04/05) |
| `app/costs.py` | 18-22 | Add NVIDIA model pricing if metered |
| `app/models.py` | 86 | `graph` column is `JSON` not `JSONB` -- note only, no change |

## New config settings (app/config.py)

```python
# --- Extraction reliability (EFT-*) ----------------------------------------
# Per-chunk extraction max tokens (base; escalated on retry).
extract_max_tokens: int = field(default_factory=lambda: int(os.environ.get("EXTRACT_MAX_TOKENS", "8000")))
# Brief synthesis max tokens (base; escalated on retry).
brief_max_tokens: int = field(default_factory=lambda: int(os.environ.get("BRIEF_MAX_TOKENS", "6000")))
# OpenAI-compatible endpoint JSON mode: "auto" (detect on first call),
# "force" (always send response_format), "off" (prompt-only, current behavior).
openai_json_mode: str = field(default_factory=lambda: os.environ.get("OPENAI_JSON_MODE", "auto").strip().lower())
# Temperature override for extraction (blank = provider default).
extract_temperature: str = field(default_factory=lambda: os.environ.get("EXTRACT_TEMPERATURE", "").strip())
```

## Response preprocessing (EFT-01) -- `_json.py`

Before brace-matching in `extract_json_object`:
1. Strip `<think>[\s\S]*?</think>` (reasoning model preamble)
2. Strip `` ```json ... ``` `` markdown fences
3. Then existing outermost-brace extraction

Pseudocode:
```python
import re
_THINK_RE = re.compile(r"<think>[\s\S]*?</think>", re.IGNORECASE)
_FENCE_RE = re.compile(r"```(?:json)?\s*\n?([\s\S]*?)```")

def extract_json_object(text: str) -> dict:
    text = (text or "").strip()
    # 1. Try raw parse
    try: return json.loads(text)
    except json.JSONDecodeError: pass
    # 2. Strip reasoning preamble
    text = _THINK_RE.sub("", text).strip()
    text = _FENCE_RE.sub(r"\1", text).strip()
    try: return json.loads(text)
    except json.JSONDecodeError: pass
    # 3. Outermost brace extraction
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        try: return json.loads(text[start:end+1])
        except json.JSONDecodeError: pass
    # 4. JSON repair (EFT-06)
    repaired = _repair_json(text)
    if repaired is not None:
        return repaired
    raise json.JSONDecodeError("no JSON object found in model response", text, 0)
```

## JSON repair (EFT-06) -- `_json.py`

```python
def _repair_json(text: str) -> dict | None:
    """Attempt to fix truncated JSON by balancing braces and cleaning."""
    start = text.find("{")
    if start < 0:
        return None
    fragment = text[start:]
    # Remove trailing incomplete string (ends mid-quote)
    if fragment.count('"') % 2 == 1:
        last_quote = fragment.rfind('"')
        fragment = fragment[:last_quote] + '"'
    # Remove trailing comma
    fragment = re.sub(r",\s*$", "", fragment)
    # Balance braces
    opens = fragment.count("{") - fragment.count("}")
    if opens > 0:
        fragment += "}" * opens
    opens = fragment.count("[") - fragment.count("]")
    if opens > 0:
        fragment += "]" * opens
    try:
        return json.loads(fragment)
    except json.JSONDecodeError:
        return None
```

## Escalating retry policy (EFT-07)

```python
@dataclass
class RetryPolicy:
    base_max_tokens: int
    max_attempts: int = 3
    token_multipliers: tuple = (1.0, 1.5, 2.0)
    temperatures: tuple = (None, 0.3, 0.1)  # None = provider default

    def params(self, attempt: int) -> dict:
        i = min(attempt, len(self.token_multipliers) - 1)
        return {
            "max_tokens": int(self.base_max_tokens * self.token_multipliers[i]),
            "temperature": self.temperatures[i],
        }
```

Applied in `_call_chunk` and `_make_brief` -- replaces the hardcoded retry loops.

## Capability-aware JSON mode (EFT-05) -- `openai_provider.py`

Replace `self._json_mode = not base_url` with:
```python
# In __init__:
self._json_mode_setting = json_mode  # "auto" | "force" | "off" from config
self._json_mode_resolved: bool | None = None  # None = not yet probed

# In complete_json:
if self._should_use_json_mode():
    kwargs["response_format"] = {"type": "json_object"}

def _should_use_json_mode(self) -> bool:
    if self._json_mode_setting == "off":
        return False
    if self._json_mode_setting == "force":
        return True
    # "auto": use cached probe result, or default to True (probe on error)
    if self._json_mode_resolved is not None:
        return self._json_mode_resolved
    return True  # optimistic; if 400/422, set _json_mode_resolved = False and retry
```

On 400/422 from the endpoint, catch in `complete_json`, set `self._json_mode_resolved = False`, and retry the same call without `response_format`. Log an audit event. This probes once per process.

Constructor signature change: `__init__(self, api_key, model, base_url=None, max_retries=5, json_mode="auto")`.
Factory change in `factory.py:25`: pass `json_mode=cfg.openai_json_mode`.

## Prompt hardening (EFT-02)

### kg_extract.txt additions (prepend):
```
CRITICAL: Respond with ONLY a raw JSON object. No markdown fences. No commentary.
No chain-of-thought. No explanation before or after the JSON. Begin your response
with the opening brace `{`.
```

Add after the schema example:
```
STRICT SCHEMA -- every item in "concepts" must be an object with keys: name (string,
required, non-empty), type (string, one of: Concept|Principle|Term|Example|Person|Tool),
definition (string, one-sentence), confidence (number 0.0-1.0). Every item in "relations"
must be an object with keys: source (string), target (string), type (string, one of the
listed types), evidence (string), confidence (number 0.0-1.0). Do not emit bare strings
or arrays where objects are expected. Do not include control characters in any string value.
```

### brief.txt additions (prepend):
```
CRITICAL: Respond with ONLY a raw JSON object. No markdown fences. No commentary.
No chain-of-thought. Begin your response with `{`.
The "summary" field must be 100-200 words. Do not exceed 200 words.
```

## Text sanitization (EFT-03)

```python
import re
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0e-\x1f]")

def _sanitize(text: str) -> str:
    """Strip C0 control chars except tab/newline/CR/FF."""
    return _CONTROL_RE.sub("", text)
```

Apply in:
- `chunker.py:79` -- `content = _sanitize("\n".join(...).strip())`
- `graph_builder.py:77` -- `name = _sanitize((c.get("name") or "").strip())`
- `graph_builder.py:89` -- `definition = _sanitize((c.get("definition") or "").strip())`
- `graph_builder.py:108` -- `evidence = _sanitize((r.get("evidence") or "").strip())`

Backfill existing data:
```sql
UPDATE jobs
SET graph = regexp_replace(graph::text, E'[\\x00-\\x08\\x0b\\x0e-\\x1f]', '', 'g')::json
WHERE graph IS NOT NULL;
```

## Eval harness (EFT-09)

Location: `scripts/eval_extraction.py` + `tests/eval/`

Metrics collected per doc:
- `json_valid_rate` (target >95%)
- `json_repaired_rate` (target <5%)
- `chunk_success_rate` (target >95%)
- `brief_present_rate` (target >98%)
- `concepts_per_doc` (node_count)
- `relations_per_doc` (edge_count)
- `cost_usd`
- `latency_total_s`

Output: JSON results file in `tests/eval/results/{tag}_{timestamp}.json`.

Comparison mode: `--compare tag1 tag2` prints a side-by-side table.

CI integration: add to `.github/workflows/ci.yml` a step that processes one small PDF and asserts thresholds (json_valid >= 0.90, brief_present == 1.0, concepts >= 5). Needs a test PDF checked into the repo.

## Brief-only backfill (EFT-08)

New function in `pipeline.py`:
```python
def regenerate_brief(graph: dict, doc_title: str, provider: LlmProvider,
                     cfg: Settings) -> dict | None:
    """Re-generate only the Brief from an existing graph. Does not re-extract chunks."""
    ledger = CostLedger()
    brief = _make_brief(graph, doc_title, provider, ledger)
    return brief
```

New admin endpoint in the admin routes:
```
POST /api/admin/backfill-briefs
Body: {"doc_ids": [...]} or {"all_missing": true}
```

Iterates docs, calls `regenerate_brief`, updates `job.graph["brief"]`, persists.

## Invariants (must hold after implementation)
1. **No silent data loss.** A chunk that fails extraction is recorded in `failed_chunks`, never silently dropped.
2. **Repair is flagged.** JSON repair sets a `"repaired": true` key on the returned dict; the audit log records `CHUNK_REPAIRED`.
3. **Config backward-compatible.** All new env vars have defaults matching current behavior. `OPENAI_JSON_MODE=auto` with an endpoint that returns 400 falls back to `off` (= current behavior).
4. **Prompt cache invalidation.** Any prompt text change auto-invalidates chunk cache (key includes prompt text). No manual cache purge needed.
5. **Cost cap still enforced.** Escalating retries increase per-chunk max_tokens but `_enforce_cost_cap` still aborts if total cost exceeds `MAX_DOC_COST_USD`.
6. **Sanitization is idempotent.** Running `_sanitize` on already-clean text is a no-op.
7. **Eval harness is non-destructive.** It reads PDFs, runs the pipeline, and writes results to `tests/eval/results/`. It does not modify the production database.

## Task list

| ID | Task | Phase | Acceptance criteria |
|---|---|---|---|
| EFT-01 | Response preprocessing: strip `<think>` + fences in `_json.py` | 1 | Unit test: `extract_json_object('<think>blah</think>{"a":1}')` returns `{"a":1}`. Existing tests still pass |
| EFT-02 | Prompt hardening: anti-reasoning + schema enforcement in kg_extract.txt + brief.txt | 1 | Prompt diff reviewed; chunk cache key changes (prompt text changed); extraction still produces valid JSON on a test PDF |
| EFT-03 | Text sanitization in chunker.py + graph_builder.py + SQL backfill | 1 | Unit test: `_sanitize("foo\x00bar")` returns `"foobar"`. `\t` and `\n` preserved. Backfill SQL runs without error |
| EFT-04 | Named token-budget settings: `EXTRACT_MAX_TOKENS`, `BRIEF_MAX_TOKENS` in config.py; wire into pipeline.py | 1 | Config values read from env; hardcoded 8000/6000 replaced; default behavior unchanged |
| EFT-05 | Capability-aware JSON mode: `OPENAI_JSON_MODE` in config + openai_provider.py + factory.py | 2 | `auto` probes on first call; `force` always sends; `off` = current behavior. 400/422 fallback tested. Audit event logged on probe |
| EFT-06 | JSON repair in `_json.py` | 2 | Unit test: truncated JSON `'{"concepts":[{"name":"X","type":"C'` repaired. Returns `None` on garbage |
| EFT-07 | Escalating retry policy in pipeline.py (replaces hardcoded loops in `_call_chunk` + `_make_brief`) | 2 | Attempt 2 uses 1.5x tokens; attempt 3 uses 2x tokens. Audit log shows escalation. Cost cap still enforced |
| EFT-08 | Brief-only regen: `regenerate_brief()` + `POST /api/admin/backfill-briefs` | 2 | Endpoint regenerates Brief for docs with `brief: null`; existing graph untouched; cost recorded |
| EFT-09 | Eval harness: `scripts/eval_extraction.py` + `tests/eval/` + CI check | 2 | Script runs on 1+ test PDF; outputs JSON metrics; `--compare` prints table; CI step passes on test PDF |
| EFT-10 | Model selection docs: recommended models per provider in .env.example + README | 3 | .env.example lists instruct models for NVIDIA/Ollama; warns against reasoning variants for extraction |
| EFT-11 | Extraction logging: persist (chunk_text, extraction_json, model_id) for SFT data collection | 3 | Logs written to `data/extraction_log/` on each successful chunk extraction; toggle via `LOG_EXTRACTIONS=true` |
| EFT-12 | LoRA fine-tuning: train small extraction model on logged data | 3 | Deferred. Requires 500+ validated pairs + GPU infra. Eval harness (EFT-09) required first |

## Files (new + modified)
`app/llm/_json.py` (EFT-01/06) . `app/llm/openai_provider.py` (EFT-05) . `app/llm/factory.py` (EFT-05) . `app/pipeline.py` (EFT-04/07/08) . `app/config.py` (EFT-04/05) . `app/prompts/kg_extract.txt` (EFT-02) . `app/prompts/brief.txt` (EFT-02) . `app/extraction/chunker.py` (EFT-03) . `app/graph_builder.py` (EFT-03) . `scripts/eval_extraction.py` (EFT-09, new) . `tests/eval/` (EFT-09, new dir) . `tests/test_json_extract.py` (EFT-01/06, new or extend) . `.env.example` (EFT-10)
