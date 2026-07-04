# Feature Tracking — Retrieval Chat (Zero-LLM Q&A)

| | |
|---|---|
| **Document** | Feature & Work-Item Tracker |
| **Feature** | Retrieval Chat — chat over an extracted document **without a query-time LLM** |
| **Version** | 1.0 |
| **Date** | 2026-07-04 |
| **Status** | ACTIVE — core already shipped; improvements proposed |
| **Owner** | Engineering Lead |
| **Parents** | `PRD-knowledge-graph-mvp.md`, `FEATURE-document-chat.md`, `ARCHITECTURE-mvp.md`, `feature-tracking.md`, `monetization-pricing.md` |

---

## What this feature is

After a document is extracted into a knowledge graph, a user (including a **viewer**)
can ask questions and get **grounded, cited answers composed deterministically from
the graph** — no per-question LLM call, no embeddings, no token cost. It is the
default chat mode (`CHAT_MODE=retrieval`) and coexists with the optional LLM mode
(`CHAT_MODE=llm`) behind the same API + SSE contract.

**Why it matters:** free to run, private, offline-capable, instant, and 100%
cited — which fits the product's "verifiable, no hallucination" promise and is a
natural Free-tier capability (see Part 4).

### Status legend
`Done` acceptance passed · `In Progress` active · `Not Started` · `Blocked` (see Deps) · `Proposed` (idea, not yet scheduled) · `Deferred`.
Priority is MoSCoW. Items marked **pre-existing** were built before this tracker and need an acceptance pass, not construction.

---

## Part 1 — Core retrieval chat (already shipped)

| ID | Feature / Task | Category | Priority | Owner | Status | Acceptance Criteria | Dependencies |
|---|---|---|---|---|---|---|---|
| RC-01 | Deterministic retrieval over the graph: keyword-overlap scoring of concept name/definition vs. the question (`chat.retrieve`) | Retrieval | Must | E2 | Done (pre-existing) | A question returns the top-N matching concept nodes; no LLM/embedding call; pure Python | graph exists (GRP-02) |
| RC-02 | Chapter-scoped retrieval: "chapter N" in the question filters to nodes tagged to that chapter | Retrieval | Should | E2 | Done (pre-existing) | "what's in chapter 3?" returns chapter-3 concepts | RC-01 |
| RC-03 | Deterministic answer composition (`chat.compose_answer`): stitches concept definitions + relationships (+ brief) into a readable reply | Compose | Must | E2 | Done (pre-existing) | For a matched question, the answer contains the concept definitions and how they connect; zero LLM | RC-01 |
| RC-04 | Summary/thesis questions answered from the Brief ("summarize", "thesis", "tl;dr") | Compose | Should | E2 | Done (pre-existing) | A "summarize this" question returns the brief thesis/summary | RC-01, OUT-01 |
| RC-05 | Citations on every answer (`_citations`): deduped `source_refs` (chapter + page range) | Trust | Must | E2 | Done (pre-existing) | Every non-empty answer carries ≤12 citations resolving to chapter/pages | RC-03 |
| RC-06 | Graceful no-match fallback: falls back to the brief, then to a clear "no matching concepts" message | Compose | Must | E2 | Done (pre-existing) | A question with no graph match returns a helpful message, never an error | RC-03 |
| RC-07 | SSE contract parity with LLM mode: one token frame + done frame + `end` event, so the chat UI is identical in both modes | API | Must | E1 | Done (pre-existing) | Frontend chat renders retrieval answers with no code path difference | RC-03 |
| RC-08 | `CHAT_MODE` switch (`retrieval` default \| `llm`), exposed to the SPA via `/api/me` (`chat_mode`) | Config | Must | E1 | Done (pre-existing) | Flipping `CHAT_MODE` changes behaviour with no rebuild; SPA can read the mode | — |
| RC-09 | Viewer access: any role (viewer included) may chat, gated per-document by category ACL | Access | Must | E1 | Done (pre-existing) | A viewer with `view` on a document can chat over it in retrieval mode | AUTH-02 |

---

## Part 2 — Prerequisite for passage-level retrieval

| ID | Feature / Task | Category | Priority | Owner | Status | Acceptance Criteria | Dependencies |
|---|---|---|---|---|---|---|---|
| RC-10 | Persist section chunks for retrieval: store the extracted section chunks (text + `chapter_id` + page range) alongside the graph so retrieval can match full passages, not just concept names | Data | Should | E1 | Done | For a processed doc, section chunks are queryable by job; storage size bounded; no re-extraction needed to retrieve. **Done:** `graph["chunks"]` persisted in the pipeline (+ preserved through retry); backward-compatible (old graphs simply have none). Unit-tested | ING-08, GRP-02 |

> Today retrieval matches only concept **nodes** (name + definition). Passage-level
> features (RC-11/RC-12) depend on RC-10 persisting the chunk text.

---

## Part 3 — Quality improvements (still no generative LLM)

| ID | Feature / Task | Category | Priority | Owner | Status | Acceptance Criteria | Dependencies |
|---|---|---|---|---|---|---|---|
| RC-11 | BM25 / TF-IDF ranking over section chunks (in addition to concept-node overlap) | Retrieval | Should | E2 | Done | Measurably better recall than keyword overlap on an eval set (RC-16); pure Python, no model. **Done:** IDF-weighted stem overlap for both concepts and chunks (`_idf`, name-token bonus) + light stemmer (`_stem`/`_tokens`); RC-16 shows **morphological recall@3 0.00→1.00**, core recall held at 1.00, no regression. Live-verified | RC-10, RC-16 |
| RC-12 | Extractive answers: return the top matching source **excerpts verbatim** as the answer body, alongside concept definitions | Compose | Should | E2 | Done | Answers to passage-style questions include the relevant verbatim excerpt + citation. **Done:** `compose_answer` appends up to 2 keyword-centred verbatim excerpts (`_best_excerpt`) with chapter/page citations; also rescues no-concept-match questions. Unit-tested | RC-10 |
| RC-13 | Synonym expansion + stemming on the query and concept text (lexical recall for paraphrased questions) | Retrieval | Could | E2 | In Progress | "drawbacks" matches a concept named "limitations"; measured lift on RC-16. **Done:** stemming (folds plural/tense — morphological recall 0.00→1.00, done with RC-11). **Remaining:** synonym expansion (the hard-paraphrase set is still 0.33) | RC-01 |
| RC-14 | Local semantic retrieval via an **embedding** index (no generative LLM, no per-token billing) — the one "gray area" vs. strict no-model | Retrieval | Could | E2 | Proposed | Paraphrased queries retrieve the right chunks; runs locally; clearly labelled as embeddings, not chat-LLM | OUT-04 (embedding index) |
| RC-15 | Retrieval confidence + honest "not covered": when top score is below a threshold, say the document doesn't cover it rather than forcing a weak answer | Trust | Should | E2 | Done | Low-confidence questions return "not covered in this document"; threshold documented/tunable. **Done:** `compose_answer` now answers only on a *real* keyword match (`_match_concepts`; chunks need ≥2 overlap) and stops using `retrieve`'s top-N fallback that leaked unrelated concepts; honest "doesn't appear to cover that" (or brief overview) otherwise. Unit-tested + live-verified | RC-01 |
| RC-16 | Retrieval-quality eval harness: a fixed Q→expected-concept set to score recall/precision of RC-01/11/13 changes | QA | Should | E2 | Done | A script reports recall@k on the eval set; regressions caught before merge. **Done:** `eval/retrieval_eval.py` — self-contained fixture graph + Q→expected set; reports concept recall@1/3/5, chunk recall, off-topic not-covered rate, and a **hard-paraphrase recall@3 (baseline 0.33)** as the headroom to beat; non-zero exit below threshold (CI-gateable). Runs with plain `python3`, no DB/model | RC-01 |
| RC-17 | Conversational follow-up without an LLM: cheap query rewriting (carry the last concept/topic into the next question) | Retrieval | Could | E2 | Proposed | "and its drawbacks?" resolves against the previous turn's concept | RC-01 |

---

## Part 4 — Monetization & UX

| ID | Feature / Task | Category | Priority | Owner | Status | Acceptance Criteria | Dependencies |
|---|---|---|---|---|---|---|---|
| RC-20 | Value-ladder rework: **Free = retrieval chat**, **Pro = LLM-synthesized chat** (instead of withholding Q&A from Free entirely) | Paywall | Should | Product | Proposed | Free users can ask grounded retrieval questions; LLM mode is gated to Pro/Scholar; decision recorded and PAY-01 updated | PAY-01, RC-08 |
| RC-21 | Answer provenance badge in the UI: label retrieval answers "Answered from the document — no AI generation" vs. LLM answers | UX | Should | E1 | Done | The chat UI shows which engine answered (reads `chat_mode` / message `model`). **Done:** per-assistant-message badge in `ChatTab` — "Answered from the document · no AI generation" (file icon) for retrieval, "AI-generated · <model>" (stars icon) for LLM; typecheck+build pass, live in bundle | RC-07, RC-08 |
| RC-22 | Contextual upgrade prompt: offer Pro's LLM chat when a retrieval answer is low-confidence (RC-15) | Paywall | Could | E1 | Proposed | A weak retrieval answer surfaces a "get a fuller answer with Pro" prompt | RC-15, RC-20, PAY-06 |
| RC-23 | Typing-effect streaming: stream the (instantly-computed) retrieval answer word-by-word like ChatGPT/Claude instead of dumping it at once | UX | Should | E1 | Done | Retrieval answers render incrementally; pace is env-tunable (`RETRIEVAL_STREAM_DELAY_MS`, default 18ms; 0 = instant). **Done:** `gen_retrieval` yields word-sized SSE token frames; frontend already appends them. Live-verified (62 frames vs 1) | RC-07 |

---

## Part 5 — Acceptance & hardening

| ID | Feature / Task | Category | Priority | Owner | Status | Acceptance Criteria | Dependencies |
|---|---|---|---|---|---|---|---|
| RC-30 | Acceptance pass on the shipped core (RC-01–09): verify grounding, citations, viewer access, and no-match handling on ≥3 real documents | QA | Must | E1+E2 | Not Started | All RC-01–09 acceptance criteria pass on real docs; results logged | RC-01–09 |
| RC-31 | Latency budget: retrieval answer p95 well under the LLM budget (target ≤ 500 ms compose time) | Perf | Should | E2 | Not Started | p95 compose latency measured and within target on a large graph | RC-03 |

---

## Milestones

| Milestone | Meaning | Gate |
|---|---|---|
| **RC-M0 — Core verified** | The already-shipped retrieval chat passes an acceptance pass | RC-30 done |
| **RC-M1 — Passage retrieval** | Answers can quote verbatim source excerpts | RC-10 + RC-11 + RC-12 done |
| **RC-M2 — Honest & measured** | Confidence gating + eval harness in place | RC-15 + RC-16 done |
| **RC-M3 — Value ladder** | Free=retrieval / Pro=LLM shipped with UI provenance | RC-20 + RC-21 done |

---

## Notes / decisions to make
- **Strict "no LLM" vs. "no generative LLM":** RC-11/12/13 use zero models. RC-14 uses a local **embedding** model (no token-billed generation) — decide whether that counts as "no LLM" for this feature.
- **RC-20 pricing decision** is a Product call; it changes the PAY-01 gating (currently Q&A is withheld from Free). Recommended: Free gets retrieval chat, Pro gets LLM chat.

*End of Retrieval-Chat feature tracking v1.0.*
