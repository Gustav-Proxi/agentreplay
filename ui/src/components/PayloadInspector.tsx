import type { TraceNode } from '../types';

function formatTime(ts: number) {
  return new Date(ts * 1000).toISOString().replace('T', ' ').slice(0, 19);
}

function latency(node: TraceNode) {
  if (!node.end_time) return 'running…';
  return `${((node.end_time - node.start_time) * 1000).toFixed(1)}ms`;
}

function JsonValue({ value, depth = 0 }: { value: unknown; depth?: number }) {
  if (value === null || value === undefined)
    return <span className="text-[#6a6a6a]">null</span>;
  if (typeof value === 'boolean')
    return <span className="text-[#e0b85c]">{String(value)}</span>;
  if (typeof value === 'number')
    return <span className="text-[#e0b85c]">{value}</span>;
  if (typeof value === 'string') {
    const truncated = value.length > 600 ? value.slice(0, 600) : value;
    const suffix = value.length > 600 ? `…+${value.length - 600} chars` : '';
    return (
      <span className="text-[#5ce05c]">
        "{truncated}
        {suffix && <span className="text-[#6a6a6a]">{suffix}</span>}"
      </span>
    );
  }
  if (Array.isArray(value)) {
    if (value.length === 0) return <span className="text-[#8a8a8a]">[]</span>;
    return (
      <span>
        {'['}
        <div style={{ paddingLeft: 14 }}>
          {value.map((v, i) => (
            <div key={i}>
              <JsonValue value={v} depth={depth + 1} />
              {i < value.length - 1 && <span className="text-[#6a6a6a]">,</span>}
            </div>
          ))}
        </div>
        {']'}
      </span>
    );
  }
  if (typeof value === 'object') {
    const entries = Object.entries(value as Record<string, unknown>);
    if (entries.length === 0) return <span className="text-[#8a8a8a]">{'{}'}</span>;
    return (
      <span>
        {'{'}
        <div style={{ paddingLeft: 14 }}>
          {entries.map(([k, v], i) => (
            <div key={k}>
              <span className="text-[#5c9ce0]">"{k}"</span>
              <span className="text-[#8a8a8a]">: </span>
              <JsonValue value={v} depth={depth + 1} />
              {i < entries.length - 1 && <span className="text-[#6a6a6a]">,</span>}
            </div>
          ))}
        </div>
        {'}'}
      </span>
    );
  }
  return <span>{String(value)}</span>;
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-5">
      <div className="text-[10px] text-[#6a6a6a] font-semibold uppercase tracking-wide mb-2">
        {title}
      </div>
      {children}
    </div>
  );
}

export default function PayloadInspector({ node }: { node: TraceNode }) {
  return (
    <div className="flex-1 overflow-y-auto p-4 font-mono text-xs leading-relaxed">
      <Section title="Node">
        <div className="space-y-0.5 text-[#e8e8e8]">
          <div><span className="text-[#8a8a8a]">name: </span>{node.name}</div>
          <div><span className="text-[#8a8a8a]">type: </span>{node.node_type}</div>
          {node.model_name && <div><span className="text-[#8a8a8a]">model: </span>{node.model_name}</div>}
          <div><span className="text-[#8a8a8a]">started: </span>{formatTime(node.start_time)}</div>
          <div><span className="text-[#8a8a8a]">latency: </span>{latency(node)}</div>
        </div>
      </Section>

      {node.token_usage && (
        <Section title="Token Usage">
          <div className="space-y-0.5">
            {Object.entries(node.token_usage).map(([k, v]) => (
              <div key={k}>
                <span className="text-[#8a8a8a]">{k}: </span>
                <span className="text-[#e0b85c]">{v}</span>
              </div>
            ))}
          </div>
        </Section>
      )}

      {node.error && (
        <Section title="Error">
          <div className="bg-[#2a1a1a] border border-[#3a2020] rounded p-3 text-[#e05c5c] whitespace-pre-wrap break-all">
            {node.error}
          </div>
        </Section>
      )}

      <Section title="Inputs">
        <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded p-3 overflow-x-auto">
          <JsonValue value={node.inputs} />
        </div>
      </Section>

      <Section title="Outputs">
        <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded p-3 overflow-x-auto">
          <JsonValue value={node.outputs} />
        </div>
      </Section>
    </div>
  );
}
