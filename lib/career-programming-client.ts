const API_BASE = (
  import.meta.env.VITE_AGENT_API_BASE_URL || "/agent-api"
).replace(/\/$/, "");

export interface CareerSkill {
  skill_id: string;
  name: string;
  domain: string;
  importance: number;
  mastery: number;
  confidence: number;
  evidence_count: number;
  level: string;
}

export interface CareerCodingTask {
  task_id: string;
  skill_id: string;
  difficulty: number;
  type: string;
  title: string;
  description: string;
  starter_code: string;
  acceptance: string[];
  estimated_minutes: number;
  status?: string;
}

export interface CareerDashboard {
  agent_version: "2.0";
  profile: {
    student_id: string;
    student_name: string;
    configured: boolean;
    target_role: "python_backend_engineer";
    target_level: "intern" | "junior";
    deadline_days: number;
    weekly_hours: number;
    current_identity:
      "vocational_student" | "undergraduate" | "career_switcher";
    python_experience: "none" | "basic" | "project";
    project_experience: "none" | "low" | "medium";
    interview_experience: "none" | "some";
  };
  role: { role_id: string; name: string; description: string };
  readiness: {
    score: number;
    percent: number;
    label: string;
    explanation: string;
  };
  priority_gaps: CareerSkill[];
  skill_domains: Array<{
    domain: string;
    mastery: number;
    skills: CareerSkill[];
  }>;
  learning_plan: Array<{
    phase: number;
    title: string;
    priority: "current" | "later";
    objective: string;
    task: string;
    acceptance: string;
    estimated_hours: number;
  }>;
  current_task: CareerCodingTask | null;
  recent_submissions: CareerSubmission[];
  next_action: string;
  progress: {
    diagnostic_completed: boolean;
    coding_attempts: number;
    completed_tasks: number;
  };
  runner: { mode: string; production_ready: boolean; notice: string };
}

export interface CareerDiagnostic {
  diagnostic_id: string;
  status: "in_progress";
  estimated_minutes: number;
  questions: Array<{
    question_id: string;
    dimension: string;
    skill_id: string;
    prompt: string;
    options: string[];
  }>;
}

export interface CareerDiagnosticResult {
  diagnostic_id: string;
  score: number;
  correct_count: number;
  question_count: number;
  priority_gaps: string[];
  next: string;
}

export interface CareerSubmission {
  submission_id: string;
  task_id: string;
  attempt: number;
  passed: boolean;
  execution: {
    execution_status: string;
    tests_passed: number;
    tests_failed: number;
    runtime_ms: number;
    runner_mode: string;
    safety_notice: string;
    message: string;
    console: string;
  };
  diagnosis: {
    error_type: string | null;
    message: string;
    related_skill_id: string;
  };
  feedback: { hint_level: number; hint: string; solution_unlocked: false };
  mastery_update: { previous_mastery: number; mastery: number; change: number };
  next_action: string;
}

interface Envelope<T> {
  status: string;
  result: T;
  errors?: Array<{ message: string }>;
  detail?: string;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: init.body
      ? { "Content-Type": "application/json", ...init.headers }
      : init.headers,
    cache: "no-store",
    signal: AbortSignal.timeout(30_000),
  });
  const data = (await response.json().catch(() => ({}))) as Envelope<T>;
  if (!response.ok || data.status === "failed") {
    throw new Error(
      data.errors?.[0]?.message || data.detail || "职业编程 Agent 请求失败",
    );
  }
  return data.result;
}

export const fetchCareerDashboard = () =>
  request<CareerDashboard>("/api/v1/programming-learning/dashboard");

export const configureCareerProfile = (payload: {
  target_level: "intern" | "junior";
  deadline_days: number;
  weekly_hours: number;
  current_identity: "vocational_student" | "undergraduate" | "career_switcher";
  python_experience: "none" | "basic" | "project";
  project_experience: "none" | "low" | "medium";
  interview_experience: "none" | "some";
}) =>
  request("/api/v1/programming-learning/career-profile", {
    method: "PUT",
    body: JSON.stringify(payload),
  });

export const createCareerDiagnostic = () =>
  request<CareerDiagnostic>("/api/v1/programming-learning/career-diagnostics", {
    method: "POST",
  });

export const submitCareerDiagnostic = (
  id: string,
  answers: Array<{
    question_id: string;
    selected_option: number;
    confidence: number;
  }>,
) =>
  request<CareerDiagnosticResult>(
    `/api/v1/programming-learning/career-diagnostics/${id}/submission`,
    { method: "POST", body: JSON.stringify({ answers }) },
  );

export const createCareerCodingTask = () =>
  request<CareerCodingTask>("/api/v1/programming-learning/coding/tasks", {
    method: "POST",
    body: JSON.stringify({}),
  });

export const submitCareerCode = (taskId: string, code: string) =>
  request<CareerSubmission>(
    `/api/v1/programming-learning/coding/tasks/${taskId}/submissions`,
    { method: "POST", body: JSON.stringify({ code }) },
  );

export const getCareerCodingHint = (taskId: string) =>
  request<{ task_id: string; hint_level: number; hint: string }>(
    `/api/v1/programming-learning/coding/tasks/${taskId}/hint`,
    { method: "POST" },
  );
