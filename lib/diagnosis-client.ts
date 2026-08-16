import type { LearningDiagnosisEnvelope, LearningEvidenceDraft, StudentLoginProfile, SubjectKey } from "@/lib/types";

const API_BASE = (import.meta.env.VITE_AGENT_API_BASE_URL || "/agent-api").replace(/\/$/, "");

export interface LearningRecordImageDetail {
  role: "question" | "solution";
  file_name: string;
  width: number;
  height: number;
  ocr_confidence: number;
  resolution_review_required: boolean;
  contrast_review_required: boolean;
  warnings: string[];
}

export interface LearningRecordImageResult {
  question_text: string;
  solution_text: string;
  question_image_count: number;
  solution_image_count: number;
  warnings: string[];
  image_details: LearningRecordImageDetail[];
  raw_images_persisted: false;
}

export async function processLearningRecordImages(
  questionImages: File[],
  solutionImages: File[],
): Promise<LearningRecordImageResult> {
  const form = new FormData();
  questionImages.slice(0, 3).forEach((file) => form.append("question_images", file));
  solutionImages.slice(0, 3).forEach((file) => form.append("solution_images", file));
  const response = await fetch(`${API_BASE}/api/v1/learning-diagnosis/record-images`, {
    method: "POST", body: form, signal: AbortSignal.timeout(120_000),
  });
  const data = await response.json() as LearningRecordImageResult & { detail?: string };
  if (!response.ok) throw new Error(data.detail || "题目或解法图片处理失败");
  return data;
}

export async function runLearningDiagnosis(input: {
  profile: StudentLoginProfile;
  subject: SubjectKey;
  curriculumVersion?: string;
  diagnosisRequest: string;
  records: LearningEvidenceDraft[];
}): Promise<LearningDiagnosisEnvelope> {
  const payload = {
    student_id: input.profile.studentId,
    grade: input.profile.grade,
    province_code: input.profile.provinceCode,
    subject: input.subject,
    target_exam_year: input.profile.targetExamYear,
    curriculum_version: input.curriculumVersion || null,
    diagnosis_request: input.diagnosisRequest,
    diagnosis_window: "recent_30_days",
    idempotency_key: `diagnosis_${input.profile.studentId}_${Date.now()}`,
    records: input.records.map(({
      local_id: _localId,
      question_text: _questionText,
      solution_text: _solutionText,
      question_image_names: _questionImages,
      solution_image_names: _solutionImages,
      ...record
    }) => ({
      ...record,
      source_id: record.source_id || `${record.assessment_id}:${record.question_id}`,
      ability_tags: record.ability_tags.filter(Boolean),
      error_tags: record.error_tags.filter(Boolean),
      step_trace: record.step_trace || null,
      duration_seconds: record.duration_seconds || null,
      occurred_at: new Date(`${record.occurred_at}T12:00:00`).toISOString(),
    })),
  };
  let response: Response;
  try {
    response = await fetch(`${API_BASE}/api/v1/learning-diagnosis/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      cache: "no-store",
      signal: AbortSignal.timeout(180_000),
    });
  } catch (error) {
    throw new Error(`无法连接学情诊断 Agent：${error instanceof Error ? error.message : "网络异常"}`);
  }
  const data = (await response.json()) as LearningDiagnosisEnvelope & { detail?: string };
  if (!response.ok || data.status === "failed" || data.status === "need_more_information") {
    throw new Error(data.errors?.[0]?.message || data.detail || "学情诊断请求失败");
  }
  return data;
}
