import { useState } from 'react';
import PayloadInspector from './components/PayloadInspector';
import RunList from './components/RunList';
import TimelineView from './components/TimelineView';
import { useNodes, useRuns } from './hooks/useApi';
import type { TraceNode } from './types';

function ScrubBar({
  nodes,
  value,
  onChange,
}: {
  nodes: TraceNode[];
  value: number | null;
  onChange: (t: number | null) => void;
}) {
  if (nodes.length < 2) return null;
  const times = nodes.map((n) => n.start_time);
  const min = Math.min(...times);
  const max = Math.max(...times);
  if (min === max) return null;

  return (
    <div className="px-4 py-2 border-t border-[#2a2a2a] flex items-center gap-3">
      <span className="text-[10px] text-[#6a6a6a] font-semibold uppercase tracking-wide shrink-0">
        Time-Scrub
      </span>
      <input
        type="range"
        min={min}
        max={max}
        step={(max - min) / 1000}
        value={value ?? max}
        onChange={(e) => onChange(Number(e.target.value))}
        className="flex-1 accent-[#e05c5c]"
      />
      {value !== null && (
        <button
          onClick={() => onChange(null)}
          className="text-[10px] text-[#6a6a6a] hover:text-[#8a8a8a] transition-colors shrink-0"
        >
          reset
        </button>
      )}
    </div>
  );
}

export default function App() {
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [scrubTime, setScrubTime] = useState<number | null>(null);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const { runs, loading: runsLoading } = useRuns(search, status);

  const { nodes, loading: nodesLoading } = useNodes(selectedRunId);
  const selectedNode = nodes.find((n) => n.id === selectedNodeId) ?? null;

  function handleRunSelect(id: string) {
    setSelectedRunId(id);
    setSelectedNodeId(null);
    setScrubTime(null);
  }

  return (
    <div className="flex h-screen bg-[#0f0f0f]">
      {/* Sidebar */}
<RunList
  runs={runs}
  loading={runsLoading}
  selectedRunId={selectedRunId}
  onSelect={handleRunSelect}
  search={search}
  setSearch={setSearch}
  status={status}
  setStatus={setStatus}
/>

      {/* Timeline panel */}
      <div className="flex-1 flex flex-col border-r border-[#2a2a2a] min-w-0">
        <div className="px-4 py-3 border-b border-[#2a2a2a] flex items-center justify-between">
          <span className="text-xs text-[#6a6a6a] font-semibold uppercase tracking-wide">
            {selectedRunId
              ? nodesLoading
                ? 'Loading trace...'
                : `${nodes.length} nodes`
              : 'Select a run'}
          </span>
        </div>

        <div className="flex-1 overflow-y-auto">
          {selectedRunId && (
            <TimelineView
              nodes={nodes}
              selected={selectedNodeId}
              onSelect={setSelectedNodeId}
              scrubTime={scrubTime}
            />
          )}
          {!selectedRunId && (
            <div className="flex items-center justify-center h-full">
              <div className="text-center">
                <p className="text-2xl font-semibold text-[#e8e8e8] mb-2">AgentReplay</p>
                <p className="text-[#8a8a8a]">Select a run to inspect its trace</p>
              </div>
            </div>
          )}
        </div>

        {selectedRunId && (
          <ScrubBar nodes={nodes} value={scrubTime} onChange={setScrubTime} />
        )}
      </div>

      {/* Inspector panel */}
      <div className="w-96 flex flex-col shrink-0">
        <div className="px-4 py-3 border-b border-[#2a2a2a]">
          <span className="text-xs text-[#6a6a6a] font-semibold uppercase tracking-wide">
            {selectedNode ? selectedNode.name : 'Node Inspector'}
          </span>
        </div>
        {selectedNode ? (
          <PayloadInspector node={selectedNode} />
        ) : (
          <div className="flex-1 flex items-center justify-center">
            <p className="text-[#8a8a8a] text-sm">Click a node to inspect</p>
          </div>
        )}
      </div>
    </div>
  );
}
