const API_BASE = (
  import.meta.env.VITE_AGENT_API_BASE_URL || "/agent-api"
).replace(/\/$/, "");

export type CareerMode = "CAREER" | "PROJECT" | "CODING";

export interface SkillState {
  skill_id: string;
  name: string;
  domain: string;
  mastery: number;
  evidence_count: number;
  importance: number;
}

export interface CareerEducationDashboard {
  spec_version: "1.0";
  configured: boolean;
  profile: {
    student_id: string;
    student_name: string;
    target_job_id: "JOB_PY_BACKEND";
    identity: "vocational_student" | "undergraduate" | "career_switcher";
    education_stage: "vocational" | "undergraduate" | "graduate" | "other";
    programming_level: "beginner" | "basic" | "project";
    known_languages: string[];
    weekly_hours: number;
    learning_goal: "internship" | "campus_recruitment" | "career_change";
    target_period_weeks: number;
    current_mode: CareerMode;
  };
  jobs: Array<{ job_id: string; name: string; description: string }>;
  current_mode: CareerMode;
  summary: {
    readiness: { percent: number; label: string; explanation: string };
    project_count: number;
    project_average: number;
    coding_solved: number;
    coding_attempts: number;
    independent_pass_rate: number;
  };
  skill_profile: SkillState[];
  learning_plan: {
    weak_skills: string[];
    next_action: string;
    weekly_plan: Array<{
      skill: string;
      objective: string;
      estimated_hours: number;
      task: string;
      acceptance: string;
    }>;
  };
  recent_activity: Array<{
    type: string;
    status: string;
    title: string;
    updated_at: string;
  }>;
}

export type CareerOnboardingInput = Pick<
  CareerEducationDashboard["profile"],
  | "target_job_id"
  | "identity"
  | "education_stage"
  | "programming_level"
  | "known_languages"
  | "weekly_hours"
  | "learning_goal"
  | "target_period_weeks"
>;

export interface CareerChatResult {
  analysis: string;
  answer: string;
  task_breakdown: Array<{
    task: string;
    estimated_minutes: number;
    acceptance: string;
  }>;
  two_week_route: Array<{
    week: number;
    focus: string;
    estimated_hours: number;
  }>;
  recommended_mode: CareerMode;
  follow_up_question: string;
  generation_mode: "llm" | "rule_fallback";
  context_used: {
    target_job_id: string;
    weekly_hours: number;
    recent_evidence_count: number;
    conversation_turns: number;
  };
}

export interface ProjectTemplate {
  project_id: string;
  title: string;
  difficulty: number;
  background: string;
  business_goal: string;
  requirements: string[];
  non_functional_requirements: string[];
  skill_ids: string[];
}

export interface ProjectEvaluationDimension {
  key: string;
  name: string;
  weight: number;
  score: number;
  evidence: string[];
  strengths: string[];
  weaknesses: string[];
  suggestions: string[];
}

export interface ProjectEvaluation {
  total_score: number;
  dimensions: ProjectEvaluationDimension[];
  overall_strengths: string[];
  overall_weaknesses: string[];
  recommended_skills: string[];
  next_learning_actions: string[];
}

export interface ProjectSession {
  session_id: string;
  project_id: string;
  title: string;
  difficulty: number;
  status: "waiting_submission" | "submitted" | "evaluated";
  project: ProjectTemplate;
  requirement_doc: string;
  problem_doc: string;
  evaluation: ProjectEvaluation | null;
  mentor_opening?: ProjectChatResult;
}

export interface ProjectChatResult {
  message_id: string;
  session_id: string | null;
  answer: string;
  guiding_questions: string[];
  suggested_actions: string[];
  follow_up_question: string;
  generation_mode: "llm" | "rule_fallback";
  context_used: {
    project_loaded: boolean;
    conversation_turns: number;
  };
}

export interface CodingQuestion {
  question_id: string;
  title: string;
  category: string;
  difficulty: number;
  description: string;
  examples: Array<{ input: string; output: string }>;
  constraints: string[];
  starter_code: string;
  skill_ids: string[];
}

export interface CodingSession {
  session_id: string;
  question: CodingQuestion;
}

export interface CodingSubmission {
  submission_id: string;
  attempt_number: number;
  action: "run" | "submit";
  status: string;
  judge_result: {
    status: string;
    passed: number;
    total: number;
    runtime_ms: number;
    runner_mode: string;
    message: string;
  };
  feedback: {
    error_type: string | null;
    current_hint_level: number;
    analysis: string;
    hint: string | null;
    allow_solution: boolean;
    recommended_next_action: string;
  };
}

interface Envelope<T> {
  status: string;
  result: T;
  errors?: Array<{ message: string }>;
  detail?: string | Array<{ msg?: string }>;
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  timeoutMs = 40_000,
): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers:
      init.body instanceof FormData
        ? init.headers
        : init.body
          ? { "Content-Type": "application/json", ...init.headers }
          : init.headers,
    cache: "no-store",
    signal: AbortSignal.timeout(timeoutMs),
  });
  const data = (await response.json().catch(() => ({}))) as Envelope<T>;
  const detail = Array.isArray(data.detail) ? data.detail[0]?.msg : data.detail;
  if (!response.ok || data.status === "failed") {
    throw new Error(
      data.errors?.[0]?.message || detail || "职业教育 Agent 请求失败",
    );
  }
  return data.result;
}

export const fetchCareerEducationDashboard = () =>
  request<CareerEducationDashboard>("/api/v1/career-education/dashboard");

export const onboardCareerEducation = (payload: CareerOnboardingInput) =>
  request("/api/v1/career-education/onboarding", {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const switchCareerMode = (mode: CareerMode) =>
  request<{ current_mode: CareerMode }>("/api/v1/career-education/mode", {
    method: "POST",
    body: JSON.stringify({ mode }),
  });

export const sendCareerChat = (message: string) =>
  request<CareerChatResult>(
    "/api/v1/career-education/career/chat",
    { method: "POST", body: JSON.stringify({ message }) },
    100_000,
  );

export const fetchProjectBank = () =>
  request<{ projects: ProjectTemplate[] }>("/api/v1/career-education/projects");

export const startProject = (projectId: string) =>
  request<ProjectSession>("/api/v1/career-education/projects/start", {
    method: "POST",
    body: JSON.stringify({ project_id: projectId, randomize: false }),
  });

export const sendProjectChat = (message: string, sessionId?: string) =>
  request<ProjectChatResult>(
    "/api/v1/career-education/project/chat",
    {
      method: "POST",
      body: JSON.stringify({ message, session_id: sessionId || null }),
    },
    100_000,
  );

export const submitProjectText = (
  sessionId: string,
  answer: Record<string, unknown>,
) =>
  request(
    `/api/v1/career-education/projects/sessions/${sessionId}/submit-text`,
    {
      method: "POST",
      body: JSON.stringify(answer),
    },
  );

export const uploadProjectDocument = (sessionId: string, file: File) => {
  const body = new FormData();
  body.append("file", file);
  return request(
    `/api/v1/career-education/projects/sessions/${sessionId}/upload`,
    {
      method: "POST",
      body,
    },
  );
};

export const evaluateProject = (sessionId: string) =>
  request<ProjectEvaluation>(
    `/api/v1/career-education/projects/sessions/${sessionId}/evaluate`,
    { method: "POST" },
  );

export async function downloadProjectDocument(sessionId: string, type: string) {
  const response = await fetch(
    `${API_BASE}/api/v1/career-education/projects/sessions/${sessionId}/documents/${type}`,
    { cache: "no-store", signal: AbortSignal.timeout(40_000) },
  );
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || "项目文档下载失败");
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${type}.md`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export const nextCodingQuestion = (
  language = "python",
  excludeQuestionId?: string,
) =>
  request<CodingSession>("/api/v1/career-education/coding/next", {
    method: "POST",
    body: JSON.stringify({
      language,
      exclude_question_id: excludeQuestionId || null,
      category: null,
      difficulty: null,
    }),
  });

export const submitCodingAnswer = (
  sessionId: string,
  code: string,
  action: "run" | "submit",
) =>
  request<CodingSubmission>(
    `/api/v1/career-education/coding/sessions/${sessionId}/submit`,
    { method: "POST", body: JSON.stringify({ code, action }) },
  );

export const requestCodingHint = (sessionId: string) =>
  request<{ hint_level: number; hint: string }>(
    `/api/v1/career-education/coding/sessions/${sessionId}/hint`,
    { method: "POST" },
  );

export const requestCodingSolution = (sessionId: string) =>
  request<{
    reference_solution: string;
    solution_explanation: string;
    mastery_notice: string;
  }>(`/api/v1/career-education/coding/sessions/${sessionId}/solution`, {
    method: "POST",
    body: JSON.stringify({ confirm: true }),
  });

export const fetchCodingHistory = () =>
  request<{ submissions: CodingSubmission[] }>(
    "/api/v1/career-education/coding/history",
  );
