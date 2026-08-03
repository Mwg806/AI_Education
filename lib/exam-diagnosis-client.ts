import type {
  ExamConstructedGrade, ExamDiagnosticCatalog, ExamDiagnosticPaper,
  ExamDiagnosticResult, ExamDiagnosticSession, StudentLoginProfile,
} from "@/lib/types";

const API_BASE = (import.meta.env.VITE_AGENT_API_BASE_URL || "/agent-api").replace(/\/$/, "");
const ASSET_API_PATH = "/api/v1/exam-diagnostics/assets/";

function normalizeAssetHtml(html: string): string {
  return html
    .replaceAll('src="/agent-api/api/v1/exam-diagnostics/assets/', `src="${API_BASE}${ASSET_API_PATH}`)
    .replaceAll('src="/api/v1/exam-diagnostics/assets/', `src="${API_BASE}${ASSET_API_PATH}`)
    .replace(
      /class="exam-inline-image"(?=\s+src="[^"]+\.svg)/g,
      'class="exam-inline-image exam-formula-image"',
    )
    .replace(/src="([^"]+\/exam-diagnostics\/assets\/[^"]+)"/g, 'src="$1?asset_version=20260802f"');
}

function normalizePaperAssets(paper: ExamDiagnosticPaper): ExamDiagnosticPaper {
  return {
    ...paper,
    questions: paper.questions.map((question) => ({
      ...question,
      stem_html: normalizeAssetHtml(question.stem_html),
      options: question.options.map((option) => ({
        ...option,
        content_html: normalizeAssetHtml(option.content_html),
      })),
    })),
  };
}

async function parseResponse<T>(response: Response): Promise<T> {
  const data = await response.json() as T & {
    detail?: string;
    errors?: Array<{ message: string }>;
  };
  if (!response.ok) {
    throw new Error(data.errors?.[0]?.message || data.detail || "高考真题诊断服务请求失败");
  }
  return data;
}

export async function fetchExamDiagnosticCatalog(): Promise<ExamDiagnosticCatalog> {
  const response = await fetch(`${API_BASE}/api/v1/exam-diagnostics/catalog`, {
    cache: "no-store", signal: AbortSignal.timeout(30_000),
  });
  return parseResponse<ExamDiagnosticCatalog>(response);
}

export async function createExamDiagnosticSession(
  profile: StudentLoginProfile,
  paperId: string,
): Promise<{ session: ExamDiagnosticSession; paper: ExamDiagnosticPaper }> {
  const response = await fetch(`${API_BASE}/api/v1/exam-diagnostics/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      student_id: profile.studentId,
      paper_id: paperId,
      grade: profile.grade,
      province_code: profile.provinceCode,
      target_exam_year: profile.targetExamYear,
    }),
    signal: AbortSignal.timeout(45_000),
  });
  const payload = await parseResponse<{ session: ExamDiagnosticSession; paper: ExamDiagnosticPaper }>(response);
  return { ...payload, paper: normalizePaperAssets(payload.paper) };
}

export async function gradeExamConstructedResponse(
  sessionId: string,
  questionId: string,
  studentId: string,
  images: File[],
  durationSeconds: number,
): Promise<{ question_id: string; grading: ExamConstructedGrade }> {
  const form = new FormData();
  form.append("student_id", studentId);
  form.append("duration_seconds", String(Math.max(1, Math.min(14_400, Math.round(durationSeconds)))));
  images.slice(0, 3).forEach((image) => form.append("images", image));
  const response = await fetch(
    `${API_BASE}/api/v1/exam-diagnostics/sessions/${encodeURIComponent(sessionId)}/questions/${encodeURIComponent(questionId)}/grade`,
    { method: "POST", body: form, signal: AbortSignal.timeout(180_000) },
  );
  return parseResponse(response);
}

export async function submitExamDiagnostic(
  sessionId: string,
  studentId: string,
  answers: Array<{ question_id: string; selected_option: string; duration_seconds: number }>,
  questionDurations: Record<string, number>,
): Promise<ExamDiagnosticResult> {
  const response = await fetch(
    `${API_BASE}/api/v1/exam-diagnostics/sessions/${encodeURIComponent(sessionId)}/submit`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ student_id: studentId, answers, question_durations: questionDurations }),
      signal: AbortSignal.timeout(180_000),
    },
  );
  return parseResponse(response);
}
