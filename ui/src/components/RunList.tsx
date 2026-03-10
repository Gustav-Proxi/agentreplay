import type { Run } from "../types";

function formatTimeAgo(ts: number): string {
  const diff = Date.now() / 1000 - ts;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

const STATUS_DOT: Record<Run["status"], string> = {
  running: "bg-[#e0b85c] animate-pulse",
  success: "bg-[#5ce05c]",
  error: "bg-[#e05c5c]",
};

interface Props {
  runs: Run[];
  loading: boolean;
  selectedRunId: string | null;
  onSelect: (id: string) => void;

  search: string;
  setSearch: (v: string) => void;
  status: string;
  setStatus: (v: string) => void;
}

export default function RunList({
  runs,
  loading,
  selectedRunId,
  onSelect,
  search,
  setSearch,
  status,
  setStatus,
}: Props) {
  return (
    <div className="w-60 bg-[#1a1a1a] border-r border-[#2a2a2a] flex flex-col h-full shrink-0">
      <div className="p-4 border-b border-[#2a2a2a]">
        <h1 className="text-lg font-semibold text-[#e8e8e8]">AgentReplay</h1>
        <p className="text-xs text-[#6a6a6a] mt-0.5">time-travel debugger</p>
      </div>
      <div className="p-3 border-b border-[#2a2a2a] space-y-2">
        {/* Search */}
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search runs..."
          className="w-full px-2 py-1 text-xs bg-[#252525] border border-[#333] rounded text-[#e8e8e8]"
        />

        {/* Status filters */}
        <div className="flex gap-1 text-xs">
          <button
            onClick={() => setStatus("")}
            className={`px-2 py-1 rounded ${status === "" ? "bg-[#333]" : "bg-[#252525]"}`}
          >
            All
          </button>

          <button
            onClick={() => setStatus("running")}
            className={`px-2 py-1 rounded ${status === "running" ? "bg-[#333]" : "bg-[#252525]"}`}
          >
            Running
          </button>

          <button
            onClick={() => setStatus("success")}
            className={`px-2 py-1 rounded ${status === "success" ? "bg-[#333]" : "bg-[#252525]"}`}
          >
            Success
          </button>

          <button
            onClick={() => setStatus("error")}
            className={`px-2 py-1 rounded ${status === "error" ? "bg-[#333]" : "bg-[#252525]"}`}
          >
            Error
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {loading && (
          <div className="p-4 text-[#8a8a8a] text-sm">Loading runs...</div>
        )}

        {!loading && runs.length === 0 && (
          <div className="p-4 text-[#8a8a8a] text-sm">
            No runs yet.
            <br />
            Run your agent to start tracing.
          </div>
        )}

        {!loading && runs.length > 0 && (
          <>
            <div className="px-4 pt-3 pb-1 text-[#6a6a6a] text-xs font-semibold uppercase tracking-wide">
              Runs
            </div>
            <div className="divide-y divide-[#2a2a2a]">
              {runs.map((run) => (
                <button
                  key={run.id}
                  onClick={() => onSelect(run.id)}
                  className={`w-full text-left p-3 transition-colors ${
                    selectedRunId === run.id
                      ? "bg-[#2a2a2a] border-l-2 border-[#e05c5c]"
                      : "hover:bg-[#252525] border-l-2 border-transparent"
                  }`}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <span
                      className={`w-2 h-2 rounded-full shrink-0 ${STATUS_DOT[run.status]}`}
                    />
                    <span className="text-xs text-[#e8e8e8] truncate flex-1">
                      {run.name}
                    </span>
                  </div>
                  <div className="text-xs text-[#8a8a8a] pl-4">
                    {formatTimeAgo(run.start_time)}
                  </div>
                </button>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
