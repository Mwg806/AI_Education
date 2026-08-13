import type { SubjectKey } from "@/lib/types";

const API_BASE = (
  import.meta.env.VITE_AGENT_API_BASE_URL || "/agent-api"
).replace(/\/$/, "");

export interface MissingContextItem {
  field: string;
  prompt: string;
  reason: string;
  accepted_sources: string[];
}

export interface OrchestrationTask {
  task_id: string;
  agent: string;
  intent: string;
  objective: string;
  subject?: string | null;
  depends_on: string[];
  execution_group: number;
  missing_context: MissingContextItem[];
  status:
    | "pending"
    | "running"
    | "success"
    | "partial_success"
    | "needs_input"
    | "skipped"
    | "failed";
  status_message: string;
  latency_ms?: number | null;
}

export interface OrchestrationResult {
  run_id: string;
  trace_id: string;
  session_id: string;
  routing: {
    intents: string[];
    primary_agent: string;
    required_agents: string[];
    execution_mode: "single" | "sequential" | "parallel";
    reason: string;
    confidence: number;
  };
  plan?: {
    plan_id: string;
    goal: string;
    execution_mode: "single" | "sequential" | "parallel" | "hybrid";
    tasks: OrchestrationTask[];
    stop_conditions: string[];
  } | null;
  handoffs: Array<{
    handoff_id: string;
    from_agent: string;
    to_agent: string;
    reason: string;
    payload: Record<string, unknown>;
  }>;
  agent_results: Record<string, Record<string, unknown>>;
  task_results: Record<string, Record<string, unknown>>;
  final_response: string;
  response_generation_mode: "llm" | "rule_summary" | "unavailable";
  profile_version: number;
  profile_changes: Array<{
    field: string;
    before: unknown;
    after: unknown;
    reason: string;
  }>;
  event_count: number;
  requires_confirmation: boolean;
  confirmation?: {
    type: string;
    label: string;
    notice: string;
    mutation_applied: boolean;
  } | null;
  status: string;
  personalization_mode: "standard_student_baseline" | "evidence_personalized";
  memory_version: number;
  memory_sources: string[];
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    cache: "no-store",
    signal: AbortSignal.timeout(180_000),
    ...init,
  });
  const data = (await response.json().catch(() => ({}))) as T & {
    detail?: string;
  };
  if (!response.ok) throw new Error(data.detail || "智能规划服务请求失败");
  return data;
}

export function sendOrchestrationMessage(input: {
  message: string;
  subject: SubjectKey;
  sessionId: string;
  context?: Record<string, unknown>;
}): Promise<OrchestrationResult> {
  return requestJson<OrchestrationResult>("/api/v1/orchestration/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message: input.message,
      subject: input.subject,
      session_id: input.sessionId,
      context: input.context || {},
    }),
  });
}

export async function fetchUnifiedProfile(): Promise<Record<string, unknown>> {
  const data = await requestJson<{ profile: Record<string, unknown> }>(
    "/api/v1/orchestration/profile",
  );
  return data.profile;
}

export async function fetchUnifiedEvents(
  limit = 20,
): Promise<Array<Record<string, unknown>>> {
  const data = await requestJson<{ events: Array<Record<string, unknown>> }>(
    `/api/v1/orchestration/events?limit=${limit}`,
  );
  return data.events;
}

export interface CollaborationMemoryResponse {
  personalization_mode: "standard_student_baseline" | "evidence_personalized";
  memory: null | {
    memory_version: number;
    session_count: number;
    interaction_count: number;
    subject_focus_counts: Record<string, number>;
    source_summary: Record<string, unknown>;
  };
  messages: Array<{
    role: "user" | "assistant";
    content: string;
    subject?: string | null;
    created_at: string;
  }>;
}

export function fetchCollaborationMemory(
  limit = 12,
): Promise<CollaborationMemoryResponse> {
  return requestJson<CollaborationMemoryResponse>(
    `/api/v1/orchestration/memory?limit=${limit}`,
  );
}
