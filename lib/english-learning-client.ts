const API_BASE = (
  import.meta.env.VITE_AGENT_API_BASE_URL || "/agent-api"
).replace(/\/$/, "");

export type EnglishTrainingMode = "reading_multiple_choice" | "seven_of_five";

export interface EnglishQuestion {
  question_id: string;
  stem: string;
  skill: string;
  options: string[];
}

export interface EnglishSession {
  session_id: string;
  mode: EnglishTrainingMode;
  title: string;
  display_text: string;
  status: "in_progress" | "completed";
  difficulty: {
    absolute_score: number;
    relative_load: number;
    recommendation: string;
  };
  questions: EnglishQuestion[];
  generation_mode: "llm" | "evidence_template";
  quality_status: "passed";
  created_at: string;
  updated_at: string;
}

export interface EnglishAnalysis {
  analysis_id: string;
  title: string;
  normalized_text: string;
  statistics: {
    word_count: number;
    sentence_count: number;
    average_sentence_words: number;
    lexical_diversity: number;
  };
  difficulty: {
    absolute_score: number;
    relative_load: number;
    dimensions: { lexical: number; syntactic: number; discourse: number };
    recommendation: string;
  };
  vocabulary_coverage: { status: string; message: string };
  core_vocabulary: Array<{
    word: string;
    occurrences: number;
    context: string;
    learning_priority: string;
  }>;
  grammar_points: Array<{
    grammar_point: string;
    evidence: string;
    gaokao_relevance: string;
  }>;
  complex_sentences: Array<{
    sentence: string;
    word_count: number;
    segments: string[];
    guidance: string;
    gaokao_risks: string[];
  }>;
  exam_skill_mapping: Array<{
    skill: string;
    label: string;
    suitability: number;
  }>;
  source_references: Array<{
    source_id: string;
    title: string;
    document_type: string;
    authority_level: string;
    page_start?: number | null;
  }>;
  confidence: number;
  created_at: string;
}

export interface EnglishAttemptResult {
  question_id: string;
  is_correct: boolean;
  selected_option: number;
  correct_option: number;
  skill: string;
  skill_label: string;
  evidence_quote: string;
  reasoning: string;
  error_type: string;
  error_label: string;
  recommended_strategy: string;
}

export interface EnglishSubmissionResult {
  session: EnglishSession;
  attempt: {
    attempt_id: string;
    correct_count: number;
    question_count: number;
    score: number;
    results: EnglishAttemptResult[];
  };
  mastery_states: EnglishMasteryState[];
  new_reviews: EnglishReview[];
}

export interface EnglishMasteryState {
  skill_id: string;
  skill_label: string;
  mastery_probability: number;
  stability_days: number;
  evidence_count: number;
  confidence: number;
  next_review_at: string;
  recent_error_type?: string | null;
}

export interface EnglishReview {
  review_id: string;
  session_id: string;
  skill_id: string;
  skill_label: string;
  prompt: string;
  evidence_quote: string;
  due_at: string;
  status: "pending" | "completed";
}

export interface EnglishDashboard {
  exam_profile: {
    exam_profile_id: string;
    paper_variant: string;
    province_code: string;
    exam_year: number;
    verification_note: string;
  };
  mastery_states: EnglishMasteryState[];
  due_reviews: EnglishReview[];
  recent_sessions: EnglishSession[];
  recent_analyses: EnglishAnalysis[];
  data_sufficiency: {
    evidence_count: number;
    score_prediction_available: false;
    message: string;
  };
}

interface EnglishEnvelope<T> {
  status: string;
  lifecycle_status: string;
  result: T;
  errors?: Array<{ message: string }>;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: init.body
      ? { "Content-Type": "application/json", ...init.headers }
      : init.headers,
    cache: "no-store",
    signal: AbortSignal.timeout(90_000),
  });
  const data = (await response
    .json()
    .catch(() => ({}))) as EnglishEnvelope<T> & {
    detail?: string;
  };
  if (!response.ok || data.status === "failed") {
    throw new Error(
      data.errors?.[0]?.message || data.detail || "英语学习 Agent 请求失败",
    );
  }
  return data.result;
}

export function fetchEnglishDashboard(): Promise<EnglishDashboard> {
  return request("/api/v1/english-learning/dashboard");
}

export function analyzeEnglishText(payload: {
  title: string;
  text: string;
}): Promise<EnglishAnalysis> {
  return request("/api/v1/english-learning/analyses", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function createEnglishTraining(payload: {
  title: string;
  text: string;
  mode: EnglishTrainingMode;
  question_count: number;
}): Promise<EnglishSession> {
  return request("/api/v1/english-learning/sessions", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function submitEnglishTraining(
  sessionId: string,
  answers: Array<{
    question_id: string;
    selected_option: number;
    response_time_ms: number;
    hint_count: number;
  }>,
): Promise<EnglishSubmissionResult> {
  return request(`/api/v1/english-learning/sessions/${sessionId}/submission`, {
    method: "POST",
    body: JSON.stringify({ answers }),
  });
}

export function completeEnglishReview(
  reviewId: string,
  result: "remembered" | "needs_review",
): Promise<EnglishReview> {
  return request(`/api/v1/english-learning/reviews/${reviewId}`, {
    method: "PUT",
    body: JSON.stringify({ result }),
  });
}
