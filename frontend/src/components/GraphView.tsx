import { useEffect, useMemo, useRef, useState } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import type { Graph, GraphNode } from '../api/jobs.api';

// Node colours — warm "Archivist" palette (terracotta, tan, dusty-pink, olive…).
const TYPE_COLORS: Record<string, string> = {
  Concept:   '#b5551f',  // terracotta (primary document / concept node)
  Principle: '#8f9c6c',  // olive green
  Term:      '#c9bb96',  // warm tan
  Example:   '#e8b4b8',  // dusty pink
  Person:    '#c47f5c',  // mid rust-orange
  Tool:      '#a89070',  // warm brown
};
const DIM = '#e5ddd5';  // warm border color for dimmed links

export function GraphView({ graph }: { graph: Graph }) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(800);
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    const measure = () => setWidth(wrapRef.current?.clientWidth ?? 800);
    measure();
    window.addEventListener('resize', measure);
    return () => window.removeEventListener('resize', measure);
  }, []);

  // Map our graph (nodes/edges) into the force-graph shape (nodes/links).
  // Clone so the layout mutates its own copy, not our data.
  const data = useMemo(
    () => ({
      nodes: graph.nodes.map((n) => ({ ...n })),
      links: graph.edges.map((e) => ({ source: e.source, target: e.target, type: e.type })),
    }),
    [graph],
  );

  const neighbors = useMemo(() => {
    const m = new Map<string, Set<string>>();
    const add = (a: string, b: string) => {
      if (!m.has(a)) m.set(a, new Set());
      m.get(a)!.add(b);
    };
    for (const e of graph.edges) {
      add(e.source, e.target);
      add(e.target, e.source);
    }
    return m;
  }, [graph]);

  const active = (id: string) =>
    !selected || id === selected || !!neighbors.get(selected)?.has(id);

  const sel = selected ? graph.nodes.find((n) => n.id === selected) : null;

  return (
    <div className="graph-wrap" ref={wrapRef}>
      <div className="graph-legend">
        {Object.entries(TYPE_COLORS).map(([t, c]) => (
          <span key={t} className="graph-legend-item">
            <span className="graph-legend-dot" style={{ background: c }}></span>
            {t}
          </span>
        ))}
      </div>
      <ForceGraph2D
        graphData={data}
        width={width}
        height={520}
        nodeRelSize={5}
        linkColor={() => DIM}
        linkDirectionalArrowLength={3}
        cooldownTicks={120}
        onNodeClick={(n: any) => setSelected(n.id === selected ? null : n.id)}
        nodeCanvasObject={(node: any, ctx, scale) => {
          const n = node as GraphNode & { x: number; y: number };
          const on = active(n.id);
          const r = 4 + (n.confidence ?? 0.5) * 4;
          ctx.globalAlpha = on ? 1 : 0.15;
          ctx.beginPath();
          ctx.arc(n.x, n.y, r, 0, 2 * Math.PI);
          ctx.fillStyle = TYPE_COLORS[n.type] ?? '#64748b';
          ctx.fill();
          if (scale > 1.5 && on) {
            ctx.fillStyle = '#1c1208';
            ctx.font = `600 ${11 / scale}px 'Playfair Display', Georgia, serif`;
            ctx.fillText(n.name, n.x + r + 1, n.y + 3);
          }
          ctx.globalAlpha = 1;
        }}
      />
      {sel && (
        <div className="node-card card shadow border-0 rounded-4">
          <div className="card-body p-3">
            <div className="d-flex align-items-center gap-2 flex-wrap">
              <span className="rounded-circle d-inline-block" style={{ width: 10, height: 10, background: TYPE_COLORS[sel.type] ?? '#64748b' }} />
              <strong>{sel.name}</strong>
              <span className="badge text-bg-light">{sel.type}</span>
              <span className="text-secondary small ms-auto">conf {sel.confidence}</span>
            </div>
            {sel.definition && <p className="small text-body-secondary mb-1 mt-2">{sel.definition}</p>}
            {sel.source_refs?.length > 0 && (
              <p className="small text-secondary mb-0">
                {sel.source_refs.map((s) => `${s.chapter || '(unknown)'} p.${s.page_start}-${s.page_end}`).join(' · ')}
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
