import { useEffect, useState } from "react";
import type { Run, TraceNode } from "../types";

const BASE = "/api";

async function fetchJSON<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export function useRuns() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchJSON<Run[]>(`${BASE}/runs`)
      .then(setRuns)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, []);

  return { runs, loading, error };
}

export function useNodes(runId: string | null) {
  const [nodes, setNodes] = useState<TraceNode[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!runId) return;
    setLoading(true);
    fetchJSON<TraceNode[]>(`${BASE}/runs/${runId}/nodes`)
      .then(setNodes)
      .finally(() => setLoading(false));
  }, [runId]);

  return { nodes, loading };
}
