# Knowledge-Graph Extraction Service

Dockerized service that ingests a PDF (digital **or scanned** — OCR built in) and
builds a **knowledge graph** of concepts + relationships, then synthesises an
executive Brief. Implements the MVP pipeline in `../docs/PRD-knowledge-graph-mvp.md`.

Reuses the proven structure of the `toeic_app/extraction-service`: the same
multi-provider LLM abstraction (`ollama | claude | openai`, `.env`-driven) and the
OCR-capable PDF text extractor. **Defaults to a LOCAL Ollama model** — no API key,
runs offline; switch to Claude/OpenAI via `.env` when you want cloud quality.

## Pipeline
```
PDF → classify (digital/scanned/hybrid) → extract text (pdfplumber + Tesseract OCR fallback)
    → chunk (section-level, page+chapter anchored) → per-chunk LLM concept/relation extraction
    → merge + conservative dedup → graph.json  (+ brief.md)
```
Every node/edge carries `source_refs` (chapter + page range) and a `confidence`
score; edges are explicit-only (no inferred/hallucinated relationships in MVP).

## Run with Docker (local Ollama, default)
```bash
# 0. one-time: install Ollama (https://ollama.com) and pull a model
ollama pull llama3.1

cd extraction-service
cp .env.example .env            # default provider = ollama (no API key needed)
mkdir -p out
docker compose run --rm extractor                    # processes ../data/the-pragmatic-programmer.pdf
docker compose run --rm extractor /data/other.pdf    # any PDF placed in ../data
```
Docker reaches the Ollama server on your host via `host.docker.internal` (wired
in `docker-compose.yml`). Outputs land in `./out/<name>.graph.json` and
`./out/<name>.brief.md`.

## Run locally (without Docker)
```bash
cd extraction-service
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt          # plus `brew install tesseract` for OCR
ollama pull llama3.1                      # local model
export ENV_FILE=.env                      # uses .env (LLM_PROVIDER=ollama, localhost)
OUTPUT_DIR=./out python -m app.main ../data/the-pragmatic-programmer.pdf
```

## Switching LLMs
Edit `.env` — no rebuild needed:
- `LLM_PROVIDER=ollama` + `OLLAMA_MODEL=llama3.1` (local, no key — **default**)
- `LLM_PROVIDER=claude` + `ANTHROPIC_MODEL=claude-opus-4-8` (cloud, best quality)
- `LLM_PROVIDER=openai` + `OPENAI_MODEL=gpt-4o`

> Tip: small local models (≤3b params) extract more reliably with smaller chunks —
> set `CHUNK_TOKENS=600` in `.env`.

## Layout
```
app/
  config.py              # live .env-driven settings
  extraction/
    text_extractor.py    # pdfplumber + OCR fallback + PDF type detection
    chunker.py           # section-level prose chunking (page+chapter anchored)
  llm/                   # provider abstraction: claude / openai / ollama
  domain/graph_schema.py # node + edge types, canonical_key for dedup
  prompts/               # kg_extract.txt, brief.txt
  graph_builder.py       # merge + conservative dedup
  pipeline.py            # orchestration
  main.py                # CLI entrypoint (Docker ENTRYPOINT)
```
