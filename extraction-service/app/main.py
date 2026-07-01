"""CLI entrypoint: extract a knowledge graph from one PDF.

    python -m app.main /data/the-pragmatic-programmer.pdf

Writes <output_dir>/<stem>.graph.json (+ <stem>.brief.md if a Brief was made).
Designed to run in the Docker image (see ../Dockerfile, ../docker-compose.yml)."""
from __future__ import annotations

import json
import os
import sys

from app.config import get_settings
from app.llm.factory import get_provider
from app.observability import audit
from app.pipeline import run


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: python -m app.main <pdf_path>", file=sys.stderr)
        return 2

    pdf_path = argv[1]
    cfg = get_settings()

    if not os.path.exists(pdf_path):
        print(f"file not found: {pdf_path}", file=sys.stderr)
        return 1

    size = os.path.getsize(pdf_path)
    if size > cfg.max_file_bytes:
        print(f"file too large: {size} > {cfg.max_file_bytes} bytes", file=sys.stderr)
        return 1

    with open(pdf_path, "rb") as f:
        data = f.read()

    doc_title = os.path.splitext(os.path.basename(pdf_path))[0]
    audit("JOB_START", file=pdf_path, bytes=size, provider=cfg.provider, model=cfg.anthropic_model)

    provider = get_provider()
    graph = run(data, doc_title, provider, cfg)

    os.makedirs(cfg.output_dir, exist_ok=True)
    graph_path = os.path.join(cfg.output_dir, f"{doc_title}.graph.json")
    with open(graph_path, "w", encoding="utf-8") as f:
        json.dump(graph, f, ensure_ascii=False, indent=2)
    audit("WROTE", path=graph_path, **graph["stats"])

    brief = graph.get("brief")
    if brief:
        brief_path = os.path.join(cfg.output_dir, f"{doc_title}.brief.md")
        with open(brief_path, "w", encoding="utf-8") as f:
            f.write(_brief_markdown(doc_title, brief))
        audit("WROTE", path=brief_path)

    print(f"Done: {graph['stats']['node_count']} concepts, "
          f"{graph['stats']['edge_count']} relations -> {graph_path}")
    return 0


def _brief_markdown(title: str, brief: dict) -> str:
    lines = [f"# Brief: {title}", "", f"**Thesis:** {brief.get('thesis','')}", ""]
    if brief.get("core_concepts"):
        lines += ["## Core concepts", *[f"- {c}" for c in brief["core_concepts"]], ""]
    if brief.get("key_principles"):
        lines += ["## Key principles", *[f"- {p}" for p in brief["key_principles"]], ""]
    if brief.get("audience"):
        lines += [f"**Audience:** {brief['audience']}", ""]
    if brief.get("summary"):
        lines += ["## Summary", brief["summary"], ""]
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
