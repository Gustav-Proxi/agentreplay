import { useEffect, useState } from "react";
import type { Run, TraceNode } from "../types";

const BASE = "/api";

async function fetchJSON<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export function useRuns(search?: string, status?: string) {
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);

    const params = new URLSearchParams();

    if (search) params.append("q", search);
    if (status) params.append("status", status);

    const url = params.toString()
      ? `${BASE}/runs?${params.toString()}`
      : `${BASE}/runs`;

    fetchJSON<Run[]>(url)
      .then(setRuns)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [search, status]);

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
