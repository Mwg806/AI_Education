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

export interface StudentLoginProfile {
  role: "student";
  studentName: string;
  studentId: string;
  grade: "grade_10" | "grade_11" | "grade_12";
  provinceCode: string;
  targetExamYear: number;
}

export interface TeacherLoginProfile {
  role: "teacher";
  teacherName: string;
  teacherId: string;
  schoolName: string;
  subject?: SubjectKey | null;
}

export type UserLoginProfile = StudentLoginProfile | TeacherLoginProfile;

export interface AuthSession {
  access_token: string;
  token_type: "bearer";
  expires_at: string;
  profile: UserLoginProfile;
}

export interface PlannerSubjectPlan {
  subject: SubjectKey;
  curriculumVersion: string;
  classProgress: string[];
  currentScore: number;
  targetScore: number;
  deadline: string;
  priority: 1 | 2 | 3;
}

export interface PlannerFormData {
  studentId: string;
  grade: "grade_10" | "grade_11" | "grade_12";
  schoolTerm: string;
  provinceCode: string;
  targetExamYear: number;
  selectedSubjects: SubjectKey[];
  subjectPlans: PlannerSubjectPlan[];
  weeklyMinutes: number;
  weekdayMinutes: number;
  weekendMinutes: number;
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
  generation_basis?: Record<string, string>;
  subject_goals?: Array<{
    subject: SubjectKey;
    current_value: number;
    target_value: number;
    deadline: string;
    priority: number;
    curriculum_version?: string | null;
    class_progress?: string[];
  }>;
  validation?: {
    valid: boolean;
    checks: Record<string, boolean>;
    errors: string[];
    warnings: string[];
  };
  explanations?: {
    student?: string;
    teacher?: string;
    strategy?: string;
    [key: string]: string | undefined;
  };
}

export interface KnowledgeState {
  knowledge_id: string;
  mastery_probability: number;
  mastery_level: string;
  confidence: number;
  forgetting_risk: number;
  objective_evidence_count?: number;
  self_report_evidence_count?: number;
  credible_interval_low?: number;
  credible_interval_high?: number;
  calibration_bias?: number | null;
}

export interface DiagnosticEvidence {
  knowledge_id: string;
  score: number;
  weight: number;
  source_type: "adaptive_diagnostic";
  source_id: string;
  description: string;
  observed_at: string;
  error_tags: string[];
}

export interface DiagnosticQuestion {
  question_id: string;
  knowledge_focus: string;
  dimension: string;
  difficulty: number;
  prompt: string;
  prompt_html?: string;
  options: string[];
  options_html?: string[];
  scope_id?: string;
  scope_label?: string;
  provenance?: {
    mode: "knowledge_grounded_ai" | "verified_question_bank";
    source_id: string;
    source_paper_id?: string;
    title: string;
    document_type?: string;
    authority_level?: string;
    page_start?: number | null;
    page_end?: number | null;
    source_url?: string | null;
    scope_match_verified: boolean;
    scope_match_level?: "subject_whole_book" | "chapter_keyword";
    excerpt_verified?: boolean;
  };
  expected_seconds: number;
}

export interface DiagnosticSession {
  diagnostic_id: string;
  student_id: string;
  subject: SubjectKey;
  chapter_id: string;
  chapter_ids: string[];
  progress_label: string;
  scope_type: "chapter" | "multi_chapter" | "whole_book";
  generation_mode: "llm" | "fixed_bank_fallback";
  fallback_reason: string;
  grounding: {
    mode: "knowledge_grounded_ai" | "verified_question_bank";
    status: "verified";
    source_count: number;
    sources: Array<Record<string, unknown>>;
    generation_attempts: number;
    scope_match_verified: boolean;
    excerpt_verified: boolean;
  };
  status: "in_progress";
  question_count: number;
  questions: DiagnosticQuestion[];
  created_at: string;
}

export interface DiagnosticAnswer {
  question_id: string;
  selected_option: number;
  response_time_seconds: number;
  confidence: number;
}

export interface DiagnosticResult {
  diagnostic_id: string;
  status: "completed";
  question_count: number;
  correct_count: number;
  objective_score: number;
  foundation_score: number;
  application_score: number;
  metacognitive_accuracy: number;
  objective_evidence_count: number;
  knowledge_evidence: DiagnosticEvidence[];
}

export interface AgentEnvelope {
  status: string;
  lifecycle_status?: string;
  trace_id?: string;
  data_version?: string;
  result?: {
    plan?: LearningPlan;
    student_profile?: {
      student_id: string;
      grade: StudentLoginProfile["grade"];
      school_term: string;
      province_code: string;
      target_exam_year: number;
      curriculum_versions: Record<string, string>;
      selected_subjects: SubjectKey[];
      class_progress: Record<string, unknown>;
    } | null;
    knowledge_profile?: {
      priority_gaps: string[];
      assessment_quality: Record<string, number>;
      knowledge_states: KnowledgeState[];
    };
    knowledge_profiles_by_subject?: Partial<
      Record<
        SubjectKey,
        {
          priority_gaps: string[];
          assessment_quality: Record<string, number>;
          knowledge_states: KnowledgeState[];
        }
      >
    >;
    time_profile?: {
      weekly_effective_minutes: number;
      recommended_scheduled_minutes: number;
      buffer_minutes: number;
    } | null;
    event?: string;
    practice_update?: Record<string, unknown>;
  };
  errors?: Array<{
    code: string;
    message: string;
    details?: Record<string, unknown>;
  }>;
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
  diagnosticEvidenceBySubject?: Partial<
    Record<SubjectKey, DiagnosticEvidence[]>
  >;
  event?: Record<string, unknown>;
}

export interface HomeworkHealth {
  status: string;
  llm_enabled: boolean;
  llm_provider?: string | null;
  llm_model?: string | null;
  planner_generation_mode: "llm" | "unavailable";
  homework_generation_mode: "llm" | "rule_test_only" | "unavailable";
  vision_input_enabled: boolean;
  diagnosis_report_generation_mode?: "llm" | "unavailable";
  learning_diagnosis_graph?: "ready";
  english_learning_graph?: "ready";
  english_learning_generation_mode?: "llm" | "evidence_template";
  exam_diagnostic_bank?: "ready" | "unavailable";
  exam_constructed_grading?: "multimodal_llm" | "unavailable";
}

export interface ExamDiagnosticPaperSummary {
  paper_id: string;
  title: string;
  description: string;
  question_count: number;
  multiple_choice_count: number;
  constructed_response_count: number;
  total_score: number;
  duration_minutes: number;
}

export interface ExamDiagnosticCatalogSubject {
  subject: SubjectKey;
  subject_label: string;
  paper_count: number;
  papers: ExamDiagnosticPaperSummary[];
}

export interface ExamDiagnosticCatalog {
  schema_version: string;
  paper_count: number;
  subjects: ExamDiagnosticCatalogSubject[];
  answer_content_exposed: false;
  constructed_response_grading: "multimodal_llm" | "unavailable";
}

export interface ExamDiagnosticQuestion {
  question_id: string;
  sequence: number;
  type: "multiple_choice" | "constructed_response";
  stem_html: string;
  options: Array<{ key: "A" | "B" | "C" | "D"; content_html: string }>;
  max_score: number;
  knowledge_tags: string[];
  difficulty: number;
  source: {
    document: string;
    document_sha256: string;
    original_number: number;
    source_title: string;
  };
}

export interface ExamDiagnosticPaper extends ExamDiagnosticPaperSummary {
  schema_version: string;
  subject: SubjectKey;
  subject_label: string;
  source_documents: Array<{
    document: string;
    document_sha256: string;
    source_title: string;
  }>;
  questions: ExamDiagnosticQuestion[];
}

export interface ExamConstructedGrade {
  score: number | null;
  max_score: number;
  recognized_student_work: string;
  criteria: Array<{
    criterion: string;
    awarded: number;
    possible: number;
    evidence: string;
  }>;
  strengths: string[];
  issues: string[];
  feedback: string;
  confidence: number;
  image_is_legible: boolean;
  requires_manual_review: boolean;
  review_reason: string;
  graded_by: "multimodal_llm";
}

export interface ExamDiagnosticSession {
  session_id: string;
  student_id: string;
  paper_id: string;
  subject: SubjectKey;
  assignment_id?: string | null;
  assignment_title?: string | null;
  assignment_classroom_id?: number | null;
  assignment_class_name?: string | null;
  grade: StudentLoginProfile["grade"];
  province_code: string;
  target_exam_year: number;
  status:
    "in_progress" | "provisional" | "manual_review_required" | "completed";
  created_at: string;
  answered_objective_count: number;
  graded_constructed_count: number;
  question_durations: Record<string, number>;
  constructed_grades: Record<string, ExamConstructedGrade>;
}

export interface ExamLearningRecord {
  record_type: "gaokao_diagnostic";
  assessment_id: string;
  student_id: string;
  subject: SubjectKey;
  paper_id: string;
  paper_title: string;
  started_at: string;
  completed_at: string;
  total_duration_seconds: number;
  objective_accuracy: number;
  score_accuracy: number;
  is_provisional: boolean;
  knowledge_statistics: Array<{
    knowledge_tag: string;
    question_count: number;
    scored_question_count: number;
    full_credit_count: number;
    score: number;
    max_score: number;
    accuracy: number | null;
    duration_seconds: number;
    average_duration_seconds: number;
  }>;
  question_records: Array<{
    question_id: string;
    sequence: number;
    question_type: "multiple_choice" | "constructed_response";
    knowledge_tags: string[];
    duration_seconds: number;
    score: number | null;
    max_score: number;
    is_correct: boolean | null;
    requires_manual_review: boolean;
    source_title: string;
    source_question_number: number;
  }>;
}

export interface ExamDiagnosticResult {
  session_id: string;
  paper_id: string;
  subject: SubjectKey;
  status: "provisional" | "manual_review_required" | "completed";
  score: number;
  scored_max: number;
  paper_max: number;
  objective_results: Array<{
    question_id: string;
    selected_option: "A" | "B" | "C" | "D";
    score: number;
    max_score: number;
    is_correct: boolean;
  }>;
  constructed_results: Array<{ question_id: string } & ExamConstructedGrade>;
  pending_constructed_question_ids: string[];
  manual_review_question_ids: string[];
  evidence_records: LearningEvidenceDraft[];
  learning_record: ExamLearningRecord;
  standard_answer_exposed: false;
  learning_diagnosis?: LearningDiagnosisEnvelope | null;
}

export interface LearningEvidenceDraft {
  local_id: string;
  question_text?: string;
  solution_text?: string;
  question_image_names?: string[];
  solution_image_names?: string[];
  assessment_id: string;
  assessment_type:
    | "formal_exam"
    | "mock_exam"
    | "diagnostic"
    | "homework"
    | "practice"
    | "teacher_evaluation"
    | "agent_feedback";
  question_id: string;
  knowledge_tags: string[];
  question_type: string;
  ability_tags: string[];
  difficulty: number;
  score: number;
  max_score: number;
  duration_seconds?: number;
  error_tags: string[];
  step_trace?: string;
  source_id?: string;
  occurred_at: string;
}

export interface DiagnosisDimensionState {
  dimension_id: string;
  dimension_label: string;
  mastery_probability: number;
  mastery_level:
    | "insufficient_evidence"
    | "needs_support"
    | "developing"
    | "proficient"
    | "strong";
  confidence: number;
  credible_interval_low: number;
  credible_interval_high: number;
  valid_evidence_count: number;
  independent_assessment_count: number;
  question_type_count: number;
  trend: "improving" | "stable" | "declining" | "unknown";
  evidence_ids: string[];
  status_basis: string;
}

export interface LearningDiagnosisState {
  diagnosis_id: string;
  student_id: string;
  subject: SubjectKey;
  state_version: number;
  blueprint_version: string;
  schema_version: string;
  diagnosis_status:
    "insufficient_evidence" | "preliminary" | "stable" | "review_required";
  evidence_gate: {
    valid_evidence_count: number;
    rejected_evidence_count: number;
    independent_assessment_count: number;
    question_type_count: number;
    difficulty_band_count: number;
    coverage_score: number;
    consistency_score: number;
    sufficiency_level: "insufficient" | "preliminary" | "stable";
    allowed_conclusion: string;
    missing_evidence: string[];
  };
  knowledge_states: DiagnosisDimensionState[];
  question_type_states: DiagnosisDimensionState[];
  ability_states: DiagnosisDimensionState[];
  observed_facts: string[];
  stable_error_patterns: Array<{
    pattern_id: string;
    label: string;
    description: string;
    occurrence_count: number;
    independent_assessment_count: number;
    knowledge_tags: string[];
    evidence_ids: string[];
    confidence: number;
  }>;
  cause_hypotheses: Array<{
    hypothesis_id: string;
    hypothesis: string;
    support: string[];
    counterevidence: string[];
    confidence: number;
    verification_needed: string;
  }>;
  missing_evidence: string[];
  reassessment_spec: Record<string, unknown>;
  narrative: DiagnosisNarrative;
  review_status: string;
  previous_version?: number | null;
  created_at: string;
}

export interface DiagnosisNarrative {
  student_summary: string;
  teacher_summary: string;
  evidence_boundary: string;
  next_evidence_request: string;
  generation_mode: "llm" | "unavailable";
}

export interface LearningDiagnosisEnvelope {
  status: string;
  lifecycle_status: string;
  trace_id: string;
  result: {
    learning_state: LearningDiagnosisState;
    diagnosis_report: DiagnosisNarrative;
    evidence_summary: {
      received_now: number;
      inserted_now: number;
      duplicates_ignored: number;
      total: number;
    };
    diagnosis_event: Record<string, unknown>;
  };
  warnings: Array<{ code: string; message: string }>;
  errors: Array<{ code: string; message: string }>;
}

export interface HomeworkSession {
  session_id: string;
  student_id: string;
  status: string;
  state_version: number;
  plan_task_id?: string | null;
  hint_runtime: {
    current_level: number;
    hint_dependency_score: number;
    student_attempt_count: number;
  };
}

export interface HomeworkQuestion {
  question_id: string;
  subject: SubjectKey;
  question_type: string;
  stem: string;
  knowledge_ids: string[];
  parse_confidence: number;
  gaokao_relevance: number;
}

export interface QuestionBankMatch {
  source_id: string;
  title: string;
  subject: SubjectKey | null;
  edition: "A" | "B" | "unknown";
  region: string;
  content_role: string;
  topic: string | null;
  file_type: string;
  confidence: number;
}

export interface HomeworkKnowledgeSource {
  source_id: string;
  title: string;
  document_type: string;
  authority_level: string;
  review_status: string;
  summary: string;
  source_url?: string | null;
  page_start?: number | null;
  page_end?: number | null;
  module_id?: string | null;
}

export interface TutoringPayload {
  action: string;
  student_visible_content: {
    acknowledgement: string;
    guidance: string;
    question_to_student: string;
    warning: string;
  };
  pedagogical_metadata?: {
    hint_level?: number;
    knowledge_ids?: string[];
  };
  verification?: {
    result: string;
    issues: string[];
    next_action: string;
  };
  variant_package?: {
    variant_id: string;
    source_locator?: Record<string, string | null> | null;
    release_policy: string;
  };
  confidence: number;
}

export interface HomeworkEnvelope {
  status: string;
  lifecycle_status: string;
  trace_id?: string;
  result: {
    session?: HomeworkSession;
    question?: HomeworkQuestion | null;
    tutoring?: TutoringPayload;
    question_bank_matches?: QuestionBankMatch[];
    knowledge_sources?: HomeworkKnowledgeSource[];
    question_bank_secure_source_count?: number;
    planner_feedback?: Record<string, unknown> | null;
    guard?: {
      passed: boolean;
      risk_score: number;
      sanitized: boolean;
    };
  };
  errors?: Array<{ code: string; message: string }>;
  warnings?: Array<{ code: string; message: string }>;
  _meta?: { mode: "live" | "demo"; backend?: string };
}

export interface QuestionBankSummary {
  total_files: number;
  subjects: Record<string, number>;
  editions: Record<string, number>;
  content_roles: Record<string, number>;
  file_types: Record<string, number>;
  total_bytes: number;
}
