export type NodeType = "chain" | "llm" | "tool" | "agent";
export type RunStatus = "running" | "success" | "error";

export interface Run {
  id: string;
  name: string;
  start_time: number;
  end_time: number | null;
  status: RunStatus;
  metadata: Record<string, unknown>;
}

export interface TraceNode {
  id: string;
  run_id: string;
  parent_id: string | null;
  node_type: NodeType;
  name: string;
  start_time: number;
  end_time: number | null;
  inputs: Record<string, unknown>;
  outputs: Record<string, unknown>;
  error: string | null;
  token_usage: Record<string, number> | null;
  model_name: string | null;
}
