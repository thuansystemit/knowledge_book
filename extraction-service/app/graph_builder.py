"""Merge per-chunk extractions into one deduplicated knowledge graph.

Entity resolution is conservative-lexical (PRD AD-6): nodes merge when their
canonical_key matches. On merge we keep the highest-confidence definition,
accumulate source_refs, and max the confidence. Edges merge on
(source_key, target_key, type). Edges whose endpoints didn't survive as nodes
are dropped (keeps the graph self-consistent)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from app.domain.graph_schema import EDGE_TYPES, NODE_TYPES, canonical_key


@dataclass
class _Node:
    name: str
    type: str
    definition: str
    confidence: float
    source_refs: List[dict] = field(default_factory=list)


@dataclass
class _Edge:
    source: str
    target: str
    type: str
    confidence: float
    evidence: str
    source_refs: List[dict] = field(default_factory=list)


class GraphBuilder:
    def __init__(self) -> None:
        self._nodes: Dict[str, _Node] = {}
        self._edges: Dict[tuple, _Edge] = {}

    @classmethod
    def from_graph(cls, graph: dict) -> "GraphBuilder":
        """Rehydrate a builder from a previously built graph so new chunks merge
        into it (used by retry-failed: append, don't rebuild from scratch). Node
        ids and edge source/target are canonical keys, so dedup keeps working."""
        b = cls()
        for n in graph.get("nodes", []) or []:
            b._nodes[n["id"]] = _Node(
                name=n["name"], type=n["type"], definition=n.get("definition", ""),
                confidence=float(n.get("confidence", 0.5)),
                source_refs=list(n.get("source_refs", [])),
            )
        for e in graph.get("edges", []) or []:
            b._edges[(e["source"], e["target"], e["type"])] = _Edge(
                source=e["source"], target=e["target"], type=e["type"],
                confidence=float(e.get("confidence", 0.5)),
                evidence=e.get("evidence", ""), source_refs=list(e.get("source_refs", [])),
            )
        return b

    def add_chunk(self, extraction: dict, source_ref: dict) -> None:
        """Fold one chunk's {concepts, relations} into the graph. `source_ref` is
        {chapter, page_start, page_end} — attached to every node/edge it produced."""
        for c in extraction.get("concepts", []) or []:
            self._add_concept(c, source_ref)
        for r in extraction.get("relations", []) or []:
            self._add_relation(r, source_ref)

    def _add_concept(self, c: dict, source_ref: dict) -> None:
        name = (c.get("name") or "").strip()
        ctype = c.get("type", "Concept")
        if not name or ctype not in NODE_TYPES:
            return
        key = canonical_key(name)
        if not key:
            return
        conf = _clamp(c.get("confidence", 0.5))
        node = self._nodes.get(key)
        if node is None:
            self._nodes[key] = _Node(
                name=name, type=ctype,
                definition=(c.get("definition") or "").strip(),
                confidence=conf, source_refs=[source_ref],
            )
        else:
            node.source_refs.append(source_ref)
            if conf > node.confidence:
                node.confidence = conf
                if c.get("definition"):
                    node.definition = c["definition"].strip()

    def _add_relation(self, r: dict, source_ref: dict) -> None:
        rtype = r.get("type")
        if rtype not in EDGE_TYPES:
            return
        sk, tk = canonical_key(r.get("source", "")), canonical_key(r.get("target", ""))
        if not sk or not tk or sk == tk:
            return
        key = (sk, tk, rtype)
        conf = _clamp(r.get("confidence", 0.5))
        edge = self._edges.get(key)
        if edge is None:
            self._edges[key] = _Edge(
                source=sk, target=tk, type=rtype, confidence=conf,
                evidence=(r.get("evidence") or "").strip(), source_refs=[source_ref],
            )
        else:
            edge.source_refs.append(source_ref)
            edge.confidence = max(edge.confidence, conf)

    def build(self) -> dict:
        """Emit the final graph dict. Drops edges whose endpoints aren't nodes."""
        node_keys = set(self._nodes)
        nodes = [
            {
                "id": key,
                "name": n.name,
                "type": n.type,
                "definition": n.definition,
                "confidence": round(n.confidence, 3),
                "source_refs": _dedupe_refs(n.source_refs),
            }
            for key, n in sorted(self._nodes.items(), key=lambda kv: -kv[1].confidence)
        ]
        edges = [
            {
                "source": e.source,
                "target": e.target,
                "type": e.type,
                "confidence": round(e.confidence, 3),
                "evidence": e.evidence,
                "extraction_method": "explicit",
                "source_refs": _dedupe_refs(e.source_refs),
            }
            for e in self._edges.values()
            if e.source in node_keys and e.target in node_keys
        ]
        return {
            "nodes": nodes,
            "edges": edges,
            "stats": {"node_count": len(nodes), "edge_count": len(edges)},
        }


def _clamp(v) -> float:
    try:
        return max(0.0, min(1.0, float(v)))
    except (TypeError, ValueError):
        return 0.5


def _dedupe_refs(refs: List[dict]) -> List[dict]:
    seen, out = set(), []
    for r in refs:
        k = (r.get("chapter", ""), r.get("page_start"), r.get("page_end"))
        if k not in seen:
            seen.add(k)
            out.append(r)
    return out
