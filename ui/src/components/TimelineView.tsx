import { useState } from 'react';
import type { TraceNode } from '../types';

const NODE_COLOR: Record<string, string> = {
  chain:  '#8a8a8a',
  llm:    '#9c5ce0',
  tool:   '#5ce05c',
  agent:  '#e05c5c',
};

const NODE_LABEL: Record<string, string> = {
  chain:  'CHAIN',
  llm:    'LLM',
  tool:   'TOOL',
  agent:  'AGENT',
};

function buildTree(nodes: TraceNode[]) {
  const map = new Map<string | null, TraceNode[]>();
  for (const n of nodes) {
    const key = n.parent_id ?? null;
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(n);
  }
  return map;
}

function latency(node: TraceNode) {
  if (!node.end_time) return '…';
  return `${((node.end_time - node.start_time) * 1000).toFixed(0)}ms`;
}

function NodeRow({
  node,
  tree,
  depth,
  selected,
  onSelect,
  scrubTime,
}: {
  node: TraceNode;
  tree: Map<string | null, TraceNode[]>;
  depth: number;
  selected: string | null;
  onSelect: (id: string) => void;
  scrubTime: number | null;
}) {
  const [open, setOpen] = useState(true);
  const children = tree.get(node.id) ?? [];
  const color = NODE_COLOR[node.node_type] ?? '#8a8a8a';
  const isSelected = selected === node.id;
  const faded = scrubTime !== null && node.start_time > scrubTime;

  return (
    <div className={faded ? 'opacity-20' : ''}>
      <button
        onClick={() => onSelect(node.id)}
        className={`w-full text-left flex items-center gap-2 px-3 py-2 transition-colors ${
          isSelected ? 'bg-[#2a2a2a] border-l-2 border-[#e05c5c]' : 'hover:bg-[#252525] border-l-2 border-transparent'
        }`}
        style={{ paddingLeft: `${depth * 16 + 12}px` }}
      >
        {/* expand toggle */}
        {children.length > 0 ? (
          <span
            onClick={(e) => { e.stopPropagation(); setOpen(!open); }}
            className="text-[#6a6a6a] text-xs w-3 shrink-0"
          >
            {open ? '▾' : '▸'}
          </span>
        ) : (
          <span className="w-3 shrink-0" />
        )}

        {/* type badge */}
        <span
          className="text-[10px] font-semibold px-1.5 py-0.5 rounded shrink-0"
          style={{ background: `${color}20`, color }}
        >
          {NODE_LABEL[node.node_type] ?? node.node_type.toUpperCase()}
        </span>

        {/* name */}
        <span className="flex-1 text-xs text-[#e8e8e8] truncate">{node.name}</span>

        {/* error indicator */}
        {node.error && (
          <span className="text-[10px] text-[#e05c5c] shrink-0">error</span>
        )}

        {/* latency */}
        <span className="text-[10px] text-[#6a6a6a] shrink-0 font-mono">{latency(node)}</span>
      </button>

      {open && children.length > 0 && (
        <div style={{ borderLeft: `1px solid #2a2a2a`, marginLeft: `${depth * 16 + 22}px` }}>
          {children.map((c) => (
            <NodeRow
              key={c.id}
              node={c}
              tree={tree}
              depth={depth + 1}
              selected={selected}
              onSelect={onSelect}
              scrubTime={scrubTime}
            />
          ))}
        </div>
      )}
    </div>
  );
}

interface Props {
  nodes: TraceNode[];
  selected: string | null;
  onSelect: (id: string) => void;
  scrubTime: number | null;
}

export default function TimelineView({ nodes, selected, onSelect, scrubTime }: Props) {
  const tree = buildTree(nodes);
  const roots = tree.get(null) ?? [];

  if (roots.length === 0) {
    return (
      <div className="p-4 text-[#8a8a8a] text-sm">No trace nodes recorded yet.</div>
    );
  }

  return (
    <div className="py-2">
      {roots.map((r) => (
        <NodeRow
          key={r.id}
          node={r}
          tree={tree}
          depth={0}
          selected={selected}
          onSelect={onSelect}
          scrubTime={scrubTime}
        />
      ))}
    </div>
  );
}
