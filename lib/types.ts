export type SubjectKey =
  | "chinese"
  | "mathematics"
  | "foreign_language"
  | "physics"
  | "chemistry"
  | "biology"
  | "history"
  | "geography"
  | "ideology_politics"
  | "technology";

export interface PlannerFormData {
  studentId: string;
  grade: "grade_10" | "grade_11" | "grade_12";
  schoolTerm: string;
  provinceCode: string;
  targetExamYear: number;
  selectedSubjects: SubjectKey[];
  planningSubject: SubjectKey;
  curriculumVersion: string;
  classProgress: string;
  currentScore: number;
  targetScore: number;
  deadline: string;
  weeklyMinutes: number;
  weekdayMinutes: number;
  weekendMinutes: number;
  foundationMastery: number;
  applicationMastery: number;
}

export interface PlanTask {
  task_id: string;
  subject: string;
  task_type: string;
  knowledge_ids: string[];
  planned_start: string;
  planned_duration_minutes: number;
  difficulty: number;
  exam_relevance: number;
  status: string;
  rationale: string;
}

export interface LearningPlan {
  plan_id: string;
  student_id: string;
  version: number;
  status: string;
  plan_start: string;
  plan_end: string;
  stages: Array<{
    stage_id: string;
    name: string;
    start_date: string;
    end_date: string;
    objective: string;
  }>;
  tasks: PlanTask[];
  weekly_capacity_minutes: number;
  scheduled_minutes: number;
  buffer_minutes: number;
  subject_time_budgets: Record<string, number>;
  validation?: {
    valid: boolean;
    checks: Record<string, boolean>;
    errors: string[];
    warnings: string[];
  };
  explanations?: Record<string, string>;
}

export interface KnowledgeState {
  knowledge_id: string;
  mastery_probability: number;
  mastery_level: string;
  confidence: number;
  forgetting_risk: number;
}

export interface AgentEnvelope {
  status: string;
  lifecycle_status?: string;
  trace_id?: string;
  data_version?: string;
  result?: {
    plan?: LearningPlan;
    knowledge_profile?: {
      priority_gaps: string[];
      assessment_quality: Record<string, number>;
      knowledge_states: KnowledgeState[];
    };
    time_profile?: {
      weekly_effective_minutes: number;
      recommended_scheduled_minutes: number;
      buffer_minutes: number;
    };
    event?: string;
    practice_update?: Record<string, unknown>;
  };
  errors?: Array<{ code: string; message: string; details?: Record<string, unknown> }>;
  warnings?: Array<{ code: string; message: string }>;
  _meta?: {
    mode: "live" | "demo";
    backend?: string;
  };
}

export interface AgentActionRequest {
  action: "health" | "initialize" | "confirm" | "practice";
  studentId?: string;
  planId?: string;
  version?: number;
  form?: PlannerFormData;
  event?: Record<string, unknown>;
}
