const API_BASE = (
  import.meta.env.VITE_AGENT_API_BASE_URL || "/agent-api"
).replace(/\/$/, "");

export type ProgrammingLearningMode = "beginner" | "advanced";
export type ProgrammingDirection =
  | "computer_science_exploration"
  | "artificial_intelligence"
  | "data_science"
  | "software_engineering"
  | "algorithm_advanced";

export interface ProgrammingProfile {
  student_id: string;
  grade: string;
  learning_mode: ProgrammingLearningMode;
  target_direction: ProgrammingDirection;
  weekly_available_minutes: number;
  effective_weekly_minutes: number;
  max_session_minutes: number;
  exam_period: boolean;
  programming_months: number;
  project_count: number;
  interests: string[];
  profile_version: number;
  configured: boolean;
}

export interface ProgrammingSkillState {
  skill_id: string;
  label: string;
  mastery: number;
  level: string;
  confidence: number;
  evidence_count: number;
  change: number;
}

export interface ProgrammingRoadmap {
  roadmap_id: string;
  duration_weeks: number;
  weekly_minutes: number;
  stages: Array<{
    stage: number;
    weeks: string;
    title: string;
    focus: string[];
    weekly_output: string;
    checkpoint: string;
  }>;
  exam_period_adjustment: {
    active: boolean;
    new_knowledge_ratio: number;
    review_ratio: number;
    reason: string;
  };
}

export interface ProgrammingProjectTask {
  task_id: string;
  title: string;
  estimated_minutes: number;
  required_skills: string[];
  deliverables: string[];
  acceptance_criteria: string[];
  status: string;
}

export interface ProgrammingProject {
  project_instance_id: string;
  project_id: string;
  title: string;
  difficulty: number;
  duration_weeks: number;
  estimated_total_minutes: number;
  target_skills: string[];
  cross_subject_links: string[];
  milestones: Array<{
    milestone_id: string;
    title: string;
    acceptance: string;
    tasks: ProgrammingProjectTask[];
  }>;
  portfolio_rule: string;
}

export interface ProgrammingWeeklyReport {
  completed_learning_events: number;
  evidence_count: number;
  hint_usage_count: number;
  average_hint_level: number;
  skill_changes: ProgrammingSkillState[];
  completed_outputs: string[];
  pace_adjustment: {
    status: string;
    recommended_weekly_minutes: number;
    new_knowledge_ratio?: number;
    restore_condition?: string | null;
  };
  data_quality: { coverage: number; limitations: string[] };
  next_step: string;
}

export interface ProgrammingDashboard {
  target_user: string;
  profile: ProgrammingProfile;
  major_direction: {
    direction_id: ProgrammingDirection;
    label: string;
    positioning: string;
    high_school_preparation: string[];
    uncertainties: string[];
  };
  roadmap: ProgrammingRoadmap | null;
  skill_states: ProgrammingSkillState[];
  active_projects: ProgrammingProject[];
  weekly_report: ProgrammingWeeklyReport;
  knowledge: {
    content_version: string;
    supported_languages: string[];
    source_references: Array<{ source_id: string; title: string }>;
  };
  safety: {
    full_answer_default: false;
    code_execution: string;
    minor_protection: true;
  };
}

export interface ProgrammingDiagnostic {
  diagnostic_id: string;
  status: "in_progress";
  estimated_minutes: number;
  answer_content_exposed: false;
  questions: Array<{
    question_id: string;
    dimension: string;
    skill_id: string;
    prompt: string;
    options: string[];
  }>;
}

export interface ProgrammingDiagnosticResult {
  diagnostic_id: string;
  status: "completed";
  correct_count: number;
  question_count: number;
  score: number;
  conclusion: { starting_point: string; next: string };
  results: Array<{
    question_id: string;
    dimension: string;
    correct: boolean;
    correct_option: number;
    explanation: string;
  }>;
}

export interface ProgrammingCodeReview {
  review_id: string;
  parse_coverage: number;
  execution: { status: "not_executed"; reason: string };
  findings: Array<{
    finding_id: string;
    severity: "high" | "medium" | "low";
    category: string;
    line_start: number;
    message: string;
  }>;
  next_hint: {
    hint_level: number;
    content: string;
    answer_leakage_blocked: boolean;
  };
  validation_plan: string[];
  must_fix_count: number;
}

export interface ProgrammingInterview {
  session_id: string;
  status: "in_progress";
  rules: string[];
  questions: Array<{ question_id: string; topic: string; prompt: string }>;
}

export interface ProgrammingInterviewScore {
  overall_score: number;
  dimension_scores: Record<string, number>;
  strengths: string[];
  missing_points: string[];
  recommended_followup: string;
  authenticity_notice: string;
}

interface ProgrammingEnvelope<T> {
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
  const data = (await response
    .json()
    .catch(() => ({}))) as ProgrammingEnvelope<T>;
  if (!response.ok || data.status === "failed") {
    throw new Error(
      data.errors?.[0]?.message || data.detail || "编程成长 Agent 请求失败",
    );
  }
  return data.result;
}

export function fetchProgrammingDashboard(): Promise<ProgrammingDashboard> {
  return request("/api/v1/programming-learning/dashboard");
}

export function updateProgrammingProfile(payload: {
  learning_mode: ProgrammingLearningMode;
  target_direction: ProgrammingDirection;
  weekly_available_minutes: number;
  max_session_minutes: number;
  exam_period: boolean;
  programming_months: number;
  project_count: number;
  interests: string[];
}): Promise<ProgrammingProfile & { roadmap: ProgrammingRoadmap }> {
  return request("/api/v1/programming-learning/profile", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function createProgrammingDiagnostic(): Promise<ProgrammingDiagnostic> {
  return request("/api/v1/programming-learning/diagnostics", {
    method: "POST",
  });
}

export function submitProgrammingDiagnostic(
  diagnosticId: string,
  answers: Array<{
    question_id: string;
    selected_option: number;
    confidence: number;
  }>,
): Promise<ProgrammingDiagnosticResult> {
  return request(
    `/api/v1/programming-learning/diagnostics/${diagnosticId}/submission`,
    { method: "POST", body: JSON.stringify({ answers }) },
  );
}

export function reviewProgrammingCode(payload: {
  code: string;
  problem_statement: string;
  expected_behavior: string;
  observed_problem: string;
  hint_level: number;
  review_stage: boolean;
  teacher_authorized: boolean;
}): Promise<ProgrammingCodeReview> {
  return request("/api/v1/programming-learning/code-reviews", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function recommendProgrammingProject(payload: {
  interest: string;
  available_weeks: number;
  use_for_portfolio: boolean;
}): Promise<ProgrammingProject> {
  return request("/api/v1/programming-learning/projects/recommendations", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function requestProgrammingProjectHint(
  projectId: string,
  payload: {
    task_id: string;
    observed_problem: string;
    previous_hint_levels: number[];
    max_allowed_level: number;
    review_stage: boolean;
    teacher_authorized: boolean;
  },
): Promise<{
  hint_level: number;
  hint: string;
  check_questions: string[];
  verification_action: string;
}> {
  return request(`/api/v1/programming-learning/projects/${projectId}/hints`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function createProgrammingInterview(): Promise<ProgrammingInterview> {
  return request("/api/v1/programming-learning/interviews", {
    method: "POST",
    body: JSON.stringify({
      interview_type: "project_presentation",
      focus: "project_experience",
      available_minutes: 15,
    }),
  });
}

export function scoreProgrammingInterviewAnswer(
  sessionId: string,
  payload: { question_id: string; answer_text: string },
): Promise<ProgrammingInterviewScore> {
  return request(
    `/api/v1/programming-learning/interviews/${sessionId}/answers`,
    { method: "POST", body: JSON.stringify(payload) },
  );
}
