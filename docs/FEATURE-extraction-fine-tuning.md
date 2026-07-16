# Extraction Fine-Tuning: Structured-Output Reliability, Prompt Hardening, and Evaluation

| | |
|---|---|
| **Document** | Design Proposal (no implementation) |
| **Product** | KnowledgeBook (Document Knowledge Graph) |
| **Date** | 2026-07-16 |
| **Status** | PROPOSED |
| **Parents** | `feature-tracking.md`, `ARCHITECTURE-mvp.md`, `PRD-knowledge-graph-mvp.md` |
| **Companion** | `FEATURE-extraction-fine-tuning.ctx.md` (AI-agent digest) |

---

## 1. Problem Statement

The extraction pipeline converts PDF text into a structured knowledge graph via per-chunk LLM calls and a synthesis Brief. In production, several failure modes have been observed that degrade reliability, output quality, and user experience:

### 1.1 Observed Failure Modes (production evidence)

**FM-1: JSON parse failures from reasoning models.**
The live provider is NVIDIA's OpenAI-compatible endpoint running a Qwen reasoning model. Reasoning models spend tokens on internal "thinking" (e.g. `<think>...</think>` blocks) before emitting the answer. Under a tight `max_tokens` budget, the response gets truncated mid-JSON, and `extract_json_object` (`app/llm/_json.py:7`) raises `"no JSON object found in model response"`. This has broken:
- Per-chunk extraction (chunk retries exhausted; chunks marked failed)
- The Brief (`_make_brief` returns `None`; doc saved with `BRIEF_FAILED`)
- Downstream features that depend on valid Brief JSON (interview prep)

Band-aid fixes are in place (retry loop in `_make_brief` at `pipeline.py:402`, chunk retries via `chunk_retries` config), but these are ad-hoc per call site rather than a principled strategy.

**FM-2: JSON mode disabled for NVIDIA endpoints.**
`openai_provider.py:23` sets `self._json_mode = not base_url`. When `OPENAI_BASE_URL` is set (as it must be for NVIDIA), `response_format={"type":"json_object"}` is never sent. The pipeline relies solely on the prompt instruction "output a single JSON object, and NOTHING else" plus `extract_json_object`'s brace-matching. This is the single most reliable lever for structured output --- and it is off for the live configuration.

**FM-3: Reasoning-model overhead.**
Reasoning models generate long internal monologues before answering. For structured extraction (where the "reasoning" adds no value --- the task is template-filling, not problem-solving), this wastes tokens, increases latency, and raises the risk of truncation (FM-1). A batched flow on the live model took ~11 min for a medium-length book.

**FM-4: Malformed structure in LLM output.**
The LLM occasionally returns a concept or relation as a bare string instead of the expected object. `graph_builder.py:69-71` already guards against this (`if isinstance(c, dict)`), but this is defensive patching at the merge layer, not prevention at the extraction layer. There is no systematic schema-coercion or normalization step.

**FM-5: Control characters in extracted text.**
OCR text can contain NUL bytes (`\x00`), form-feeds, and other control characters that end up in node definitions and relation evidence. These break PostgreSQL `json` column casts (the `graph` column is `JSON` not `JSONB` per `models.py:86`) and cause issues in downstream JSON consumers (frontend rendering, exports, API responses).

---

## 2. Structured-Output Reliability Strategy

### 2.1 Current Approach and Its Limitations

Today, structured output reliability is a stack of independent, per-call-site patches:

| Layer | Mechanism | Limitation |
|---|---|---|
| Prompt | "Output a single JSON object, and NOTHING else" | Reasoning models ignore this during their think phase; no schema provided in prompt |
| Provider | `response_format={"type":"json_object"}` | Disabled for NVIDIA (`_json_mode = not base_url`) |
| Parser | `extract_json_object`: find outermost `{...}` | Fails on truncated JSON; does not strip `<think>` preambles; no repair |
| Retry | `chunk_retries=2` (3 total attempts) | Same params each attempt; no escalation; tokens/temp unchanged |
| Brief | Hardcoded 2-attempt retry in `_make_brief` | Ad-hoc; no token escalation; no partial salvage |

### 2.2 Proposed Strategy: Layered Defense

Replace the ad-hoc patches with a principled, layered reliability strategy. Each layer independently improves reliability; together they make JSON parse failures rare.

#### Layer 1: Provider Capability-Aware JSON Mode

**Problem:** The most reliable lever --- server-side JSON enforcement --- is unconditionally disabled for all non-OpenAI endpoints.

**Proposal:** Replace the boolean `_json_mode = not base_url` with a per-provider/per-model capability flag in config.

**Key finding on NVIDIA:** NVIDIA's OpenAI-compatible endpoint (`integrate.api.nvidia.com/v1`) does support `response_format={"type":"json_object"}` for most hosted models including Qwen variants. It also supports structured output via JSON schema (`response_format={"type":"json_schema", "json_schema": {...}}`). The current blanket disable is overly conservative.

**Recommendation:** Add an env var `OPENAI_JSON_MODE` (default `"auto"`) with values:
- `"auto"` (default): enable `response_format` when the first LLM call succeeds with it; disable and retry without it if the endpoint returns 400/422. Cache the decision for the process lifetime.
- `"force"`: always send `response_format`.
- `"off"`: current behavior (prompt-only).

This is safe: a 400 from an incompatible endpoint is caught and the fallback is the current behavior. No data loss, no silent failure.

**Verification step before implementation:** Run this curl against the live endpoint to confirm:
```bash
curl -s https://integrate.api.nvidia.com/v1/chat/completions \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"MODEL_ID","messages":[{"role":"user","content":"say hello as JSON"}],"response_format":{"type":"json_object"},"max_tokens":100}'
```
If it returns valid JSON without a 400/422, JSON mode is supported.

#### Layer 2: Response Preprocessing (Strip Reasoning Preamble)

**Problem:** Reasoning models emit `<think>...</think>` blocks or prose preambles before the JSON. `extract_json_object` finds the first `{` which may be inside the think block, not the actual answer.

**Proposal:** Add a preprocessing step in `extract_json_object` before brace-matching:
1. Strip `<think>...</think>` blocks (regex: `<think>[\s\S]*?</think>`)
2. Strip markdown code fences (` ```json ... ``` `)
3. Then apply the existing outermost-brace extraction

This is a narrow, safe change to `_json.py` that benefits all providers.

#### Layer 3: JSON Repair / Salvage

**Problem:** Truncated responses produce incomplete JSON. The current parser gives up entirely.

**Proposal:** After `extract_json_object` fails, attempt repair:
1. **Brace-balancing:** Count `{` and `}` in the response; if unbalanced, append the missing closing braces.
2. **Trailing-comma cleanup:** Remove trailing commas before `}` or `]`.
3. **Truncation recovery:** If the response ends mid-string, close the string, close all open containers.
4. **Partial extraction:** If the repaired JSON parses and contains at least one concept, accept it (with a `"partial": true` flag).

This is not a general-purpose JSON repair library --- it is a focused set of heuristics for the specific failure pattern (truncated structured output). A ~30-line function.

**Trade-off:** Repaired JSON may lose the last 1-2 concepts/relations from a truncated chunk. This is acceptable: the alternative is losing the entire chunk.

#### Layer 4: Escalating Retry with Parameter Variation

**Problem:** Current retries use identical parameters. If the model truncates at 8000 tokens on attempt 1, it will truncate again on attempt 2.

**Proposal:** Each retry attempt escalates:

| Attempt | `max_tokens` | Temperature | Notes |
|---|---|---|---|
| 1 | Configured default (8000) | Provider default | Normal path |
| 2 | 1.5x default (12000) | 0.3 | More budget, lower creativity |
| 3 | 2x default (16000) | 0.1 | Maximum budget, near-deterministic |

The escalation is driven by a small retry-policy object, not hardcoded per call site. Both `_call_chunk` and `_make_brief` use it.

**Config:** `EXTRACT_MAX_TOKENS` (default 8000), `BRIEF_MAX_TOKENS` (default 6000) --- named per stage so they can be tuned independently.

#### Layer 5: Partial-Result Salvage at the Pipeline Level

**Problem:** If `_make_brief` fails after all retries, the doc is saved with `brief: null`. The graph may still be valid.

**Proposal:** The pipeline already does this for chunks (failed chunks are recorded, graph is built from successful ones). Extend the principle:
- Brief failure: save the doc with `brief: null` and a warning (already happens), but also set a `brief_status: "failed"` flag so a backfill job can re-attempt it later.
- Chunk failure: already handled. Add a `partial_extraction: true` flag when >20% of chunks failed, so the UI can warn.

---

## 3. Prompt Tuning

### 3.1 `kg_extract.txt` Review

The current prompt (`app/prompts/kg_extract.txt`) is well-structured but has gaps that reasoning models exploit:

**Issues:**
1. No explicit "do not include chain-of-thought / reasoning / commentary" instruction. Reasoning models treat "output a single JSON object, and NOTHING else" as applying to the final answer, not the internal monologue.
2. No schema enforcement beyond the example shape. The model can (and does) emit bare strings in the `concepts` array.
3. No few-shot exemplar showing the exact expected output.
4. No explicit instruction about character encoding (the model echoes OCR artifacts).

**Proposed additions to `kg_extract.txt`:**
- Add at the top: "Respond with ONLY a JSON object. No markdown fences, no commentary, no chain-of-thought, no explanation before or after the JSON."
- Add a `STRICT SCHEMA` section listing field types: `"name": string (required, non-empty)`, `"type": string (one of: Concept, Principle, Term, Example, Person, Tool)`, etc.
- Add one few-shot exemplar (a 3-concept, 2-relation example) so the model has a concrete format reference.
- Add: "Do not include control characters (NUL, tabs, form-feeds) in any string value. If the source text contains garbled characters, omit them."

### 3.2 `brief.txt` Review

**Issues:**
1. Same lack of anti-reasoning instructions.
2. The `summary` field is described as "~150 words" but reasoning models may over-generate, consuming token budget on the summary and getting truncated before closing the JSON.
3. No explicit "do not emit markdown fences around the JSON."

**Proposed additions to `brief.txt`:**
- Same anti-reasoning preamble as `kg_extract.txt`.
- Cap the summary: "The summary field must be 100-200 words. Do not exceed 200 words."
- Add: "Begin your response with `{` --- no preamble, no markdown."

### 3.3 Prompt Versioning

Currently prompts are loaded from text files with no versioning. When a prompt changes, cached chunk extractions (EXT-03) become stale.

**Proposal:** The chunk cache key already includes the prompt text (`chunk_cache.key(model_id, kg_prompt, header)`), so a prompt change automatically invalidates the cache. No additional versioning mechanism is needed. Document this invariant.

---

## 4. Token-Budget and Model Policy

### 4.1 Right-Sizing Token Budgets

The core problem: reasoning models consume tokens on internal monologue. For Qwen-class reasoning models, the "thinking" can be 2-5x the actual answer length.

**Current budgets:**
- Chunk extraction: `max_tokens=8000` (hardcoded in `_call_chunk`, `pipeline.py:268`)
- Brief: `max_tokens=6000` (hardcoded in `_make_brief`, `pipeline.py:404`)

**Proposed budgets (new config settings):**

| Setting | Default | Notes |
|---|---|---|
| `EXTRACT_MAX_TOKENS` | `8000` | Per-chunk extraction; sufficient for non-reasoning models; escalated on retry for reasoning models |
| `BRIEF_MAX_TOKENS` | `6000` | Brief synthesis; generous for a ~200 word JSON; escalated on retry |
| `EXTRACT_TEMPERATURE` | `""` (provider default) | Blank = do not send; numeric = override |

These replace the hardcoded values in `pipeline.py`.

### 4.2 Model Selection Guidance

**Recommendation:** Use a non-reasoning instruct model for structured extraction. Reasoning is wasted on template-filling tasks and actively harmful (token waste, truncation risk).

**Proposed config approach:** No new config needed --- the user already controls the model via `OPENAI_MODEL` / `OLLAMA_MODEL`. But the docs and `.env.example` should recommend:
- **For NVIDIA free tier:** `qwen/qwen2.5-7b-instruct` (not a reasoning model) or `meta/llama-3.1-8b-instruct` instead of a reasoning variant.
- **For Ollama local:** `qwen2.5:7b` (instruct, not `qwen2.5:7b-coder` or reasoning variants).
- **For Claude:** Already using `claude-opus-4-8` with `thinking={"type":"adaptive"}` --- the SDK handles thinking tokens separately from `max_tokens`, so truncation is not an issue. No change needed.

**Optional: Thinking-disable flag for OpenAI-compatible providers.** Some reasoning models accept a parameter to disable thinking (e.g., `extra_body={"enable_thinking": false}` or a model variant suffix). This is model-specific and fragile. **Recommendation:** Document it as an option but do not build provider-level support; switching to an instruct model is simpler and more reliable.

---

## 5. Text Sanitization

### 5.1 The Problem

OCR text from `extract_text_with_quality` can contain:
- NUL bytes (`\x00`) --- PostgreSQL rejects these in `json`/`jsonb`/`text` columns
- Form-feed characters (`\x0c`) --- used as page markers internally but should not appear in node definitions
- Other C0 control characters (`\x01-\x08`, `\x0b`, `\x0e-\x1f`) --- no semantic value, break JSON serializers

These propagate through the pipeline: OCR text -> chunks -> LLM prompt -> LLM output -> graph nodes -> `JSON` column -> API response -> frontend.

### 5.2 Proposed Sanitization Points

**Point 1: At chunk creation (primary).** Strip control chars from `chunk.content` in `chunker.py` before the text enters the LLM prompt. This is the narrowest, highest-leverage point: it prevents bad chars from reaching the LLM, the graph, and the database.

```
Sanitize: strip chars in [\x00-\x08\x0b\x0e-\x1f] from chunk content.
Preserve: \x09 (tab), \x0a (newline), \x0d (carriage return), \x0c (form-feed, used as page marker).
```

**Point 2: At graph build (defense-in-depth).** Strip control chars from node `name`, `definition`, and edge `evidence` in `graph_builder.py` `_add_concept` / `_add_relation`. This catches anything the LLM generates or echoes from the prompt.

**Note on the `graph` column type:** The column is `JSON` (not `JSONB`) per `models.py:86`. PostgreSQL's `json` type also rejects NUL bytes, so sanitization is required regardless of column type. No schema migration needed.

---

## 6. Actual Model Fine-Tuning (LoRA / SFT)

### 6.1 Honest Assessment

Training a small local model specifically for `(chunk text) -> {concepts, relations}` JSON extraction is theoretically appealing: it would eliminate reasoning overhead, guarantee schema compliance, and reduce latency.

**However, it is not the right investment now:**

| Factor | Assessment |
|---|---|
| **Data availability** | No labeled extraction dataset exists. Building one requires collecting (chunk, gold-standard extraction) pairs from production, which requires the pipeline to already work reliably --- a chicken-and-egg problem. |
| **Labeling cost** | Each training example needs human review of the extracted concepts/relations. For a useful LoRA (500-1000 examples), this is 20-40 hours of expert annotation. |
| **Baseline quality** | Prompt + JSON mode + an instruct model has not yet been tried with JSON mode enabled. It may be "good enough" without fine-tuning. |
| **Maintenance burden** | A fine-tuned model is frozen to its training distribution. When the prompt schema changes (new node types, new edge types), the model must be retrained. |
| **Infrastructure** | Serving a fine-tuned model requires GPU infra (Ollama can do this, but the model must be hosted). The current NVIDIA free tier does not support custom models. |

### 6.2 When Fine-Tuning Pays Off

Fine-tuning becomes worthwhile when:
1. The pipeline is stable and reliable with prompt-based extraction (Phases 1-2 of this proposal).
2. A dataset of 500+ validated (chunk, extraction) pairs has been accumulated from production logs.
3. Latency or cost is the binding constraint (e.g., per-doc cost exceeds budget even with a cheap instruct model).

### 6.3 Data Collection Strategy (Phase 2, deferred)

When ready:
1. Log every successful extraction: `(chunk_text, prompt_hash, model_id, extraction_json)`.
2. Build a review UI: show the chunk and extraction side-by-side; human marks each concept/relation as correct/incorrect/missing.
3. Export validated pairs as SFT training data in the model's expected format.
4. Train a LoRA adapter on a small base model (e.g., Qwen 2.5 7B Instruct) using the validated data.
5. A/B test the fine-tuned model against the prompt-based approach using the eval harness (Section 7).

**Recommendation:** Defer to Phase 2. The prompt + JSON mode + instruct model approach should be tried first. If it achieves >95% JSON-valid rate and acceptable concept quality, fine-tuning is unnecessary.

---

## 7. Evaluation Harness

### 7.1 Why an Eval Harness is the Backbone

Without metrics, "fine-tuning" is guesswork. Every change to prompts, models, JSON mode settings, or token budgets needs to be measured against a consistent benchmark. The eval harness makes the reliability strategy data-driven.

### 7.2 Metrics

| Metric | Definition | Target | Source |
|---|---|---|---|
| `json_valid_rate` | % of LLM calls that return parseable JSON (no repair needed) | >95% | Count parse successes vs. failures in `_call_chunk` and `_make_brief` |
| `json_repaired_rate` | % of LLM calls that required JSON repair to parse | <5% | Count repair invocations |
| `chunk_success_rate` | % of chunks that produce a non-null extraction | >95% | `len(failed_chunks) / total_chunks` per doc |
| `brief_present_rate` | % of completed docs that have a non-null Brief | >98% | `brief is not None` per doc |
| `concepts_per_doc` | Mean number of concepts extracted per document | 15-50 (depends on doc length) | `graph.stats.node_count` |
| `relations_per_doc` | Mean number of relations extracted per document | 10-40 | `graph.stats.edge_count` |
| `cost_per_doc_usd` | Mean LLM cost per document | <$0.50 (free tier), <$2.00 (paid) | `graph.cost.usd` |
| `latency_p90_s` | p90 end-to-end pipeline latency | <300s digital, <720s scanned | `graph.stage_timings.total_s` |
| `concepts_precision` | % of extracted concepts judged correct by human review | >80% | Manual eval on test set |

### 7.3 Eval Set

Build a small, curated eval set of 5-10 documents:
- 3 digital PDFs (varying length: 50, 150, 300 pages)
- 2 scanned PDFs (one clean scan, one low-quality)
- 1 two-column academic paper
- 1 table-heavy report

For each document, manually curate a "gold standard" extraction (or at minimum, count the expected concept categories). Store as `tests/eval/` with the PDFs and expected metrics.

### 7.4 Running an Eval

A script (`scripts/eval_extraction.py`) processes each doc in the eval set, records all metrics, and outputs a comparison table. Usage:

```bash
# Compare current config vs. a change
python scripts/eval_extraction.py --tag baseline
# ... change prompt/model/config ...
python scripts/eval_extraction.py --tag json-mode-enabled
python scripts/eval_extraction.py --compare baseline json-mode-enabled
```

Results stored as JSON in `tests/eval/results/` for historical comparison.

### 7.5 CI Integration

Add a lightweight CI check: process one small test PDF and assert:
- `json_valid_rate >= 0.90`
- `brief_present_rate == 1.0`
- `concepts_per_doc >= 5`

This catches regressions in prompt changes or provider updates. The existing CI (`ci.yml`) already runs backend checks; this adds an extraction smoke test.

---

## 8. Backfill and Repair

### 8.1 Existing Damaged Documents

Documents processed during the FM-1/FM-2 failure window may have:
- `brief: null` (BRIEF_FAILED)
- Malformed or sparse graphs (chunks failed extraction)
- Control characters in node definitions

### 8.2 Repair Strategies

**Strategy A: Brief-only regeneration (quick, targeted).**
Add a management command / API endpoint that re-generates only the Brief from an existing graph, without re-processing chunks. This is fast (one LLM call per doc) and fixes the most visible user-facing issue.

```
POST /api/admin/backfill-briefs
Body: { "doc_ids": [...] } or { "all_missing": true }
```

**Strategy B: Selective re-extraction (for sparse graphs).**
Use the existing `retry_failed` path (`pipeline.py:321`) which re-processes only the failed chunks and merges them into the existing graph. This is already built. Expose it more prominently in the admin UI.

**Strategy C: Full reprocess (nuclear option).**
Use the existing `POST /api/jobs/{id}/reprocess` endpoint (OUT-07). This re-runs the entire pipeline. Appropriate after a major prompt or model change, but expensive.

**Recommendation:** Implement Strategy A first (brief-only regen is a ~20 line function). For sparse graphs, use the existing retry-failed. Full reprocess only after the reliability improvements in this proposal are shipped.

### 8.3 Text Sanitization Backfill

After implementing sanitization (Section 5), run a one-time migration to strip control chars from all existing `graph` JSON values in the database. This is a SQL update, not a pipeline re-run:

```sql
UPDATE jobs
SET graph = regexp_replace(graph::text, '[\x00-\x08\x0b\x0e-\x1f]', '', 'g')::json
WHERE graph IS NOT NULL;
```

---

## 9. Phased Plan

### Phase 1: Quick Wins (1-2 days, independently shippable)

| ID | Task | Impact | Risk |
|---|---|---|---|
| EFT-01 | Response preprocessing: strip `<think>` blocks and markdown fences in `extract_json_object` | Fixes FM-1 for reasoning models immediately | Low --- additive change to parser |
| EFT-02 | Prompt hardening: add anti-reasoning preamble + schema enforcement to `kg_extract.txt` and `brief.txt` | Reduces reasoning overhead + malformed output | Low --- prompt-only change; cache auto-invalidates |
| EFT-03 | Text sanitization at chunk creation + graph build | Fixes FM-5 (control chars) | Low --- pure string cleanup |
| EFT-04 | Named token-budget settings: `EXTRACT_MAX_TOKENS`, `BRIEF_MAX_TOKENS` in config | Replaces hardcoded values; enables tuning without code changes | Low --- config addition |

### Phase 2: JSON Mode + Reliability Layer (3-5 days)

| ID | Task | Impact | Risk |
|---|---|---|---|
| EFT-05 | Capability-aware JSON mode: `OPENAI_JSON_MODE=auto\|force\|off` with auto-detection | Fixes FM-2 --- the single highest-leverage change | Medium --- needs testing against NVIDIA endpoint |
| EFT-06 | JSON repair / salvage pass in `extract_json_object` | Recovers truncated responses instead of losing entire chunks | Low --- fallback only; does not change happy path |
| EFT-07 | Escalating retry policy: increase tokens + lower temperature on each retry | Fixes FM-1 systematically | Low --- retry-policy object replaces ad-hoc retry loops |
| EFT-08 | Brief-only regeneration endpoint + backfill script | Repairs existing damaged docs | Low --- read-only on existing graphs |
| EFT-09 | Eval harness: script + eval set + metrics | Enables data-driven tuning | Low --- test infrastructure only |

### Phase 3: Model Optimization + Fine-Tuning Prep (deferred, optional)

| ID | Task | Impact | Risk |
|---|---|---|---|
| EFT-10 | Model selection guidance: document recommended models per provider | Addresses FM-3 (reasoning overhead) | Low --- documentation only |
| EFT-11 | Extraction logging for future fine-tuning data collection | Prepares SFT dataset | Low --- logging only |
| EFT-12 | LoRA fine-tuning of a small extraction model | Eliminates prompt/JSON-mode dependency | High --- requires labeled data, GPU infra, maintenance |

---

## 10. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| NVIDIA endpoint does not support `response_format` for the specific model | Low (most NVIDIA models support it) | Medium --- EFT-05 reverts to `off` | Auto-detection with graceful fallback |
| JSON repair produces incorrect but parseable JSON | Low | Medium --- wrong concepts in graph | Repair only runs after parse failure; partial flag set; eval harness catches quality drops |
| Prompt changes degrade extraction quality | Medium | High --- fewer/worse concepts | Eval harness (EFT-09) catches regressions before deployment |
| Escalating `max_tokens` increases cost per doc | Low | Low --- only on retries | Cost cap (`MAX_DOC_COST_USD`) already enforces the hard limit |
| Fine-tuned model over-fits to training data | Medium | Medium --- poor on new book types | Deferred to Phase 3; eval harness required first |

---

## 11. Open Questions for Requester

1. **NVIDIA model ID:** What is the exact model ID currently deployed (e.g., `qwen/qwen2.5-72b-instruct` vs. a reasoning variant)? This determines whether JSON mode is supported and whether the model has a thinking-disable flag.

2. **Eval set availability:** Are there 5-10 representative PDFs available for the eval set, or do we need to curate them?

3. **Brief-only backfill scope:** How many existing documents have `brief: null`? Should the backfill target all of them, or only recent ones?

4. **Cost tolerance for retries:** The escalating retry policy can use up to 2x the normal token budget per chunk on retries. Is this acceptable given the current `MAX_DOC_COST_USD=2.0` cap?

5. **Phase 3 interest level:** Is LoRA fine-tuning something the team wants to invest in after Phase 2, or should it remain permanently deferred (as noted in `feature-tracking.md` P2-11)?

---

## 12. Recommendation

**The single highest-leverage change is EFT-05: enabling JSON mode for the NVIDIA endpoint.** This is the difference between "the model is free to emit any text and we hope it is JSON" and "the model is constrained by the server to emit valid JSON." It directly addresses the root cause of FM-1 and FM-2 with minimal code change (a config flag + a ~10-line change to `openai_provider.py`).

If NVIDIA JSON mode is confirmed to work (via the verification curl in Section 2.2), the expected improvement is:
- `json_valid_rate`: from ~85% (estimated from failure logs) to >99%
- `brief_present_rate`: from ~90% to >99%
- `chunk_success_rate`: from ~92% to >99%

Combined with EFT-01 (strip `<think>` blocks) and EFT-02 (prompt hardening), the Phase 1 + EFT-05 package should bring the pipeline to production-grade reliability without any model change or fine-tuning.

---

*End of proposal. See `FEATURE-extraction-fine-tuning.ctx.md` for the AI-agent companion.*
