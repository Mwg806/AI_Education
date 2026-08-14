const API_BASE = (
  import.meta.env.VITE_AGENT_API_BASE_URL || "/agent-api"
).replace(/\/$/, "");

export type EnglishTrainingMode = "reading_multiple_choice" | "seven_of_five";
export type EnglishTaskType =
  | "reading_comprehension"
  | "vocabulary_explanation"
  | "grammar_correction"
  | "writing_revision"
  | "translation"
  | "speaking_practice"
  | "exam_practice"
  | "learning_plan"
  | "progress_query";
export type NationalISection =
  | "reading"
  | "seven_of_five"
  | "cloze"
  | "grammar_fill"
  | "writing"
  | "integrated";
export type EnglishResponseMode =
  "quick" | "teaching" | "guided" | "exam" | "immersive" | "correction";
export type EnglishLevel = "A1" | "A2" | "B1" | "B2" | "C1" | "C2";

export interface EnglishLearnerProfile {
  student_id: string;
  target_language: "en";
  estimated_level: EnglishLevel;
  self_reported_level: EnglishLevel;
  daily_minutes: number;
  level_confidence: number;
  preferred_mode: EnglishResponseMode;
  explanation_depth: "brief" | "medium" | "detailed";
  show_examples: boolean;
  show_exercises: boolean;
  learning_goals: string[];
  weaknesses: string[];
  evidence_count: number;
}

export interface EnglishLanguageAnswer {
  primary_intent: EnglishTaskType;
  learner_level: EnglishLevel;
  title: string;
  display_markdown: string;
  short_answer: string;
  revised_text: string;
  translation: string;
  agent_reply: string;
  next_question: string;
  main_idea: string;
  summary: string;
  structure: string[];
  key_facts: string[];
  reading_evidence: Array<{
    claim: string;
    evidence_quote: string;
    evidence_type: "fact" | "inference";
  }>;
  vocabulary: Array<{
    word: string;
    phonetic: string;
    part_of_speech: string;
    contextual_meaning: string;
    collocations: string[];
    example: string;
    common_mistake: string;
  }>;
  grammar_points: string[];
  corrections: Array<{
    original: string;
    corrected: string;
    category: string;
    severity: string;
    explanation: string;
    alternatives: string[];
  }>;
  strengths: string[];
  priority_improvements: string[];
  reusable_expressions: string[];
  exercises: string[];
  scores: Record<string, number | null>;
}

export interface EnglishLanguageTaskResult {
  task: {
    primary_intent: EnglishTaskType;
    response_mode: EnglishResponseMode;
    learner_level: EnglishLevel;
    national_i_candidate: true;
  };
  answer: EnglishLanguageAnswer;
  learning_record: {
    saved: boolean;
    event_id: string | null;
    new_vocabulary: EnglishVocabularyRecord[];
    grammar_updates: EnglishGrammarRecord[];
    review_items: EnglishReview[];
  };
  learner_profile: EnglishLearnerProfile;
  exam_profile: EnglishDashboard["exam_profile"];
  generation_mode: "llm" | "rule_fallback";
  national_i_blueprint?: NationalIExamBlueprint;
}

export interface NationalIExamBlueprint {
  paper_variant: "新高考全国Ⅰ卷";
  target_users: string;
  score: number;
  version?: string;
  sections: Array<{
    id: string;
    label: string;
    score: number;
    question_count?: number;
    status: "ready" | "planned";
  }>;
  notes: string[];
}

export interface EnglishVocabularyRecord {
  word_key: string;
  word: string;
  contextual_meaning: string;
  phonetic: string;
  part_of_speech: string;
  collocations: string[];
  example: string;
  status: string;
  contexts_seen: number;
  mastery_score: number;
  next_review_at: string;
}

export interface EnglishGrammarRecord {
  grammar_key: string;
  label: string;
  error_count: number;
  mastery_score: number;
  confidence: number;
  stable_weakness: boolean;
  example_error: string;
}

export interface EnglishPersonalizationSummary {
  mode: "evidence_personalized" | "standard_student_baseline";
  evidence_count: number;
  source_agents: string[];
  weak_points: string[];
  strengths: string[];
}

export interface EnglishGrammarTrainingQuestion {
  question_id: string;
  prompt: string;
  instruction: string;
  grammar_focus: string;
  difficulty: "基础" | "中等" | "提高";
}

export interface EnglishGrammarTrainingFeedback {
  question_id: string;
  is_correct: boolean;
  score: number;
  feedback: string;
  defect_tag: string;
  improvement_step: string;
  self_check_question: string;
}

export interface EnglishGrammarTrainingAssessment {
  overall_score: number;
  summary: string;
  strengths: string[];
  weaknesses: string[];
  next_focus: string;
  feedback: EnglishGrammarTrainingFeedback[];
}

export interface EnglishGrammarTrainingSession {
  session_id: string;
  status: "in_progress" | "completed";
  title: string;
  display_text: string;
  focus: string;
  level: EnglishLevel;
  questions: EnglishGrammarTrainingQuestion[];
  answers: Array<{ question_id: string; answer: string }>;
  assessment: EnglishGrammarTrainingAssessment | null;
  generation_mode: "llm" | "reference_template";
  evaluation_mode?: "llm" | "reference_template";
  model_name: string;
  personalization: EnglishPersonalizationSummary;
  created_at: string;
  updated_at: string;
}

export interface EnglishWritingTrainingPrompt {
  prompt_id: string;
  title: string;
  task_type: "application" | "continuation";
  prompt: string;
  requirements: string[];
  suggested_minutes: number;
  word_count: string;
}

export interface EnglishWritingPromptSet {
  generation_mode: "llm" | "reference_template";
  model_name: string;
  personalization: EnglishPersonalizationSummary;
  prompts: EnglishWritingTrainingPrompt[];
}

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
  analysis: EnglishAnalysis;
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
    target_user: string;
    audience_eligible: boolean;
  };
  target_user: string;
  learner_profile: EnglishLearnerProfile;
  mastery_states: EnglishMasteryState[];
  due_reviews: EnglishReview[];
  recent_sessions: EnglishSession[];
  recent_analyses: EnglishAnalysis[];
  data_sufficiency: {
    evidence_count: number;
    score_prediction_available: false;
    message: string;
  };
  learning_records: {
    events: Array<{
      event_id: string;
      task_type: EnglishTaskType;
      source_excerpt: string;
      created_at: string;
    }>;
    vocabulary: EnglishVocabularyRecord[];
    grammar: EnglishGrammarRecord[];
  };
  weekly_report: {
    completed_tasks: number;
    task_counts: Partial<Record<EnglishTaskType, number>>;
    vocabulary_count: number;
    stable_grammar_weaknesses: EnglishGrammarRecord[];
    next_step: string;
  };
  ability_profile: {
    reading: number | null;
    vocabulary: number | null;
    grammar: number | null;
    writing: number | null;
    speaking: null;
    reading_dimensions: Record<
      string,
      { label: string; score: number; evidence_count: number }
    >;
  };
  recommendation: {
    review: string[];
    next_learning: string[];
    suggested_task: { type: "reading"; difficulty: number; reason: string };
  };
  exam_blueprint: NationalIExamBlueprint;
}

export interface ReadingBankItem {
  reading_id: string;
  title: string;
  source_label: string;
  year: number | null;
  section: string;
  topic: string;
  category: "simulation" | "past_exam";
  question_count: number;
  word_count: number;
  difficulty: number;
  status: "not_started" | "in_progress" | "completed";
  elapsed_seconds: number;
  score: number | null;
  session_id: string | null;
  answered_count: number;
}

export interface ReadingBankPaper extends Omit<ReadingBankItem, "status"> {
  article: string;
  images: string[];
  questions: Array<{
    question_id: string;
    number: number;
    stem: string;
    options: string[];
  }>;
}

export interface ReadingBankProgress {
  reading_id: string;
  session_id: string;
  status: "in_progress" | "completed";
  elapsed_seconds: number;
  answers: Record<string, number>;
  score: number | null;
  result?: Array<{
    question_id: string;
    selected_option: number;
    correct_option: number;
    is_correct: boolean;
    explanation: string;
  }> | null;
}

export interface WordStudyDetail {
  word: string;
  phonetic: string;
  part_of_speech: string;
  contextual_meaning: string;
  morphology: string;
  sentence_role: string;
  collocations: string[];
  example: string;
  common_mistake: string;
  difficulty: "基础" | "重点" | "拓展";
}

interface EnglishEnvelope<T> {
  status: string;
  lifecycle_status: string;
  result: T;
  errors?: Array<{ message: string }>;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const isMultipart = init.body instanceof FormData;
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: init.body
      ? isMultipart
        ? init.headers
        : { "Content-Type": "application/json", ...init.headers }
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

export function fetchEnglishReadingBank(): Promise<{
  reading_count: number;
  simulation_count: number;
  completed_count: number;
  items: ReadingBankItem[];
}> {
  return request("/api/v1/english-learning/reading-bank");
}

export function startEnglishReadingBank(
  readingId: string,
  restart = false,
): Promise<{ reading: ReadingBankPaper; progress: ReadingBankProgress }> {
  return request("/api/v1/english-learning/reading-bank/start", {
    method: "POST",
    body: JSON.stringify({ reading_id: readingId, restart }),
  });
}

export function saveEnglishReadingBankProgress(
  readingId: string,
  answers: Record<string, number>,
  elapsedSeconds: number,
): Promise<ReadingBankProgress> {
  return request(
    "/api/v1/english-learning/reading-bank/" + readingId + "/progress",
    {
      method: "PUT",
      body: JSON.stringify({ answers, elapsed_seconds: elapsedSeconds }),
    },
  );
}

export function submitEnglishReadingBank(
  readingId: string,
  answers: Record<string, number>,
  elapsedSeconds: number,
): Promise<{
  reading: ReadingBankPaper;
  progress: ReadingBankProgress;
  results: NonNullable<ReadingBankProgress["result"]>;
}> {
  return request(
    "/api/v1/english-learning/reading-bank/" + readingId + "/submit",
    {
      method: "POST",
      body: JSON.stringify({ answers, elapsed_seconds: elapsedSeconds }),
    },
  );
}

export function analyzeEnglishLanguageV2(
  text: string,
  mode: "vocabulary" | "grammar",
): Promise<{
  mode: "vocabulary" | "grammar";
  vocabulary?: { summary: string; words: WordStudyDetail[] };
  grammar?: {
    is_complete_sentence: boolean;
    sentence_type: string;
    overall_feedback: string;
    issues: Array<{
      original: string;
      issue_type: string;
      explanation: string;
      hint: string;
    }>;
    correction_steps: string[];
    corrected_sentence: string;
    practice: string[];
  };
}> {
  return request("/api/v1/english-learning/language-analysis", {
    method: "POST",
    body: JSON.stringify({ text, mode }),
  });
}

export function saveSelectedEnglishVocabulary(
  sourceText: string,
  words: WordStudyDetail[],
): Promise<{ saved_count: number }> {
  return request("/api/v1/english-learning/vocabulary", {
    method: "POST",
    body: JSON.stringify({ source_text: sourceText, words }),
  });
}

export function startEnglishGrammarTraining(
  focus: string,
): Promise<EnglishGrammarTrainingSession> {
  return request("/api/v1/english-learning/grammar-training/start", {
    method: "POST",
    body: JSON.stringify({ focus }),
  });
}

export function submitEnglishGrammarTraining(
  sessionId: string,
  answers: Array<{ question_id: string; answer: string }>,
): Promise<EnglishGrammarTrainingSession> {
  return request("/api/v1/english-learning/grammar-training/submit", {
    method: "POST",
    body: JSON.stringify({ session_id: sessionId, answers }),
  });
}

export function generateEnglishWritingPrompts(
  taskType: "mixed" | "application" | "continuation",
): Promise<EnglishWritingPromptSet> {
  return request("/api/v1/english-learning/writing-prompts", {
    method: "POST",
    body: JSON.stringify({ task_type: taskType }),
  });
}

export function assessEnglishSpeaking(
  audio: Blob,
  topic: string,
  durationSeconds: number,
  browserTranscript: string,
): Promise<{
  topic: string;
  transcript: string;
  transcription_source: string;
  duration_seconds: number;
  audio_persisted: false;
  assessment: {
    reply: string;
    next_question: string;
    scores: Record<string, number>;
    strengths: string[];
    improvements: string[];
    corrected_expression: string;
    practice_advice: string[];
  };
}> {
  const body = new FormData();
  body.append("audio", audio, "speaking.webm");
  body.append("topic", topic);
  body.append("duration_seconds", String(durationSeconds));
  body.append("browser_transcript", browserTranscript);
  return request("/api/v1/english-learning/speaking/assess", {
    method: "POST",
    body,
  });
}

export function executeEnglishLanguageTask(payload: {
  task_type: EnglishTaskType;
  source_text: string;
  user_message?: string;
  response_mode: EnglishResponseMode;
  detail_level: "brief" | "medium" | "detailed";
  revision_level?: number;
  feedback_mode?: "instant" | "delayed";
  scenario?: string;
  include_exercises: boolean;
  include_learning_record: boolean;
  exam_section?: NationalISection;
  question_count?: number;
}): Promise<EnglishLanguageTaskResult> {
  return request("/api/v1/english-learning/tasks", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function fetchNationalIExamBlueprint(): Promise<NationalIExamBlueprint> {
  return request("/api/v1/english-learning/exam-blueprint");
}

export function updateEnglishLearnerProfile(payload: {
  self_reported_level: EnglishLevel;
  daily_minutes: number;
  preferred_mode: EnglishResponseMode;
  explanation_depth: "brief" | "medium" | "detailed";
  show_examples: boolean;
  show_exercises: boolean;
  learning_goals: string[];
}): Promise<EnglishLearnerProfile> {
  return request("/api/v1/english-learning/profile", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function deleteEnglishLearningRecord(
  recordType: "event" | "vocabulary",
  recordId: string,
): Promise<{ deleted: true }> {
  return request(
    `/api/v1/english-learning/records/${recordType}/${encodeURIComponent(recordId)}`,
    { method: "DELETE" },
  );
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

export function requestEnglishReadingHint(
  sessionId: string,
  questionId: string,
  level: number,
): Promise<{
  question_id: string;
  level: number;
  content: string;
  answer_exposed: boolean;
  next_level: number | null;
}> {
  return request(`/api/v1/english-learning/sessions/${sessionId}/hint`, {
    method: "POST",
    body: JSON.stringify({ question_id: questionId, level }),
  });
}

export function extractEnglishReadingMaterial(file: File): Promise<{
  filename: string;
  source_type: "pdf" | "image" | "text";
  text: string;
  character_count: number;
  warnings: string[];
  raw_upload_persisted: false;
}> {
  const body = new FormData();
  body.append("material", file);
  return request("/api/v1/english-learning/materials/extract", {
    method: "POST",
    body,
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
