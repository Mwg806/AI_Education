import type {
  HomeworkEnvelope,
  HomeworkSession,
  QuestionBankSummary,
  StudentLoginProfile,
  SubjectKey,
} from "@/lib/types";

const API_BASE = (import.meta.env.VITE_AGENT_API_BASE_URL || "/agent-api").replace(/\/$/, "");
const DEMO_MODE =
  import.meta.env.VITE_AGENT_DEMO_MODE === "true"
  || (import.meta.env.PROD && import.meta.env.VITE_AGENT_DEMO_MODE !== "false");

export interface HomeworkTurnRequest {
  sessionId: string;
  studentId: string;
  subject: SubjectKey;
  questionText: string;
  studentWork: string;
  message: string;
  intent: "request_hint" | "request_next_hint" | "check_step" | "request_knowledge_review";
  image?: File | null;
}

let demoSession: HomeworkSession | null = null;
let demoHintLevel = 0;

const demoSummary: QuestionBankSummary = {
  total_files: 7577,
  subjects: {
    mathematics: 752,
    physics: 1129,
    chemistry: 709,
    biology: 1123,
    chinese: 215,
    foreign_language: 355,
    history: 1314,
    geography: 928,
    ideology_politics: 1052,
  },
  editions: { A: 191, B: 7386 },
  content_roles: { exercise: 4634, answer_secure: 478, explanation_secure: 1462 },
  file_types: { pdf: 1671, docx: 3103, pptx: 2694 },
  total_bytes: 41716431393,
};

function demoCreate(studentId: string): HomeworkEnvelope {
  demoSession = {
    session_id: "hw_session_demo_001",
    student_id: studentId,
    status: "received",
    state_version: 1,
    hint_runtime: { current_level: 0, hint_dependency_score: 0, student_attempt_count: 0 },
  };
  return {
    status: "success",
    lifecycle_status: "received",
    result: { session: demoSession },
    _meta: { mode: "demo" },
  };
}

function demoTurn(body: HomeworkTurnRequest, action = "release_hint"): HomeworkEnvelope {
  if (!demoSession) demoCreate(body.studentId);
  demoHintLevel = action === "release_hint" ? Math.min(demoHintLevel + 1, 5) : demoHintLevel;
  demoSession = {
    ...demoSession!,
    status: action === "answer_verification" ? "verifying" : "waiting_for_student",
    state_version: demoSession!.state_version + 1,
    hint_runtime: {
      current_level: demoHintLevel,
      hint_dependency_score: demoHintLevel * 0.12,
      student_attempt_count: body.studentWork ? 1 : 0,
    },
  };
  const isDirect = /直接|只要|答案/.test(body.message);
  return {
    status: action === "answer_verification" ? "partial_success" : "success",
    lifecycle_status: demoSession.status,
    result: {
      session: demoSession,
      question: {
        question_id: "q_demo_001",
        subject: body.subject,
        question_type: "subjective_calculation",
        stem: body.questionText,
        knowledge_ids: [`${body.subject}:题库专题匹配`],
        parse_confidence: 0.96,
        gaokao_relevance: 0.82,
      },
      tutoring: {
        action,
        student_visible_content: action === "answer_verification"
          ? {
              acknowledgement: "你的完整作答已提交并进入过程校验。",
              guidance: "当前演示环境不会虚构标准答案，请先选择你最不确定的一步。",
              question_to_student: "你希望先检查条件、方法、计算还是表达？",
              warning: "正式后端会结合题库证据与评分依据进行受控校验。",
            }
          : {
              acknowledgement: isDirect
                ? "我知道你想尽快完成，但我不能直接给可抄写答案。"
                : body.studentWork
                  ? "我已经看到你的当前尝试，会从你停下的位置继续。"
                  : "先不用急着计算，我们先把题目结构看清楚。",
              guidance: body.studentWork
                ? "保留当前步骤，只检查下一步需要使用的条件和方法是否匹配。"
                : "先圈出已知条件、目标量和隐含约束，再决定第一步。",
              question_to_student: "你准备先使用哪一个已知条件？",
              warning: "本轮只释放一个提示，不展开完整答案。",
            },
        pedagogical_metadata: { hint_level: demoHintLevel },
        confidence: 0.82,
      },
      question_bank_matches: [
        {
          source_id: "qb_demo_53b_math",
          title: "1_训练册WORD.docx",
          subject: body.subject,
          edition: "B",
          region: "新高考",
          content_role: "exercise",
          topic: "专题三 函数与导数",
          file_type: "docx",
          confidence: 0.88,
        },
        {
          source_id: "qb_demo_53a_math",
          title: "2026新高考53A数学精练册.pdf",
          subject: body.subject,
          edition: "A",
          region: "全国新高考",
          content_role: "exercise",
          topic: "函数与导数专项",
          file_type: "pdf",
          confidence: 0.84,
        },
      ],
      question_bank_secure_source_count: 2,
      guard: { passed: true, risk_score: 0, sanitized: false },
    },
    _meta: { mode: "demo" },
  };
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    cache: "no-store",
    signal: AbortSignal.timeout(60_000),
  });
  const result = await response.json() as T & { status?: string; errors?: Array<{ message: string }> };
  if (!response.ok || result.status === "failed") {
    throw new Error(result.errors?.[0]?.message || "作业辅导 Agent 暂时无法完成请求");
  }
  return result;
}

export async function fetchQuestionBankSummary(): Promise<QuestionBankSummary> {
  if (DEMO_MODE) return demoSummary;
  return requestJson<QuestionBankSummary>("/api/v1/homework/question-bank/summary");
}

export async function createHomeworkSession(
  profile: StudentLoginProfile,
  subject: SubjectKey,
  planTaskId?: string,
): Promise<HomeworkEnvelope> {
  if (DEMO_MODE) return demoCreate(profile.studentId);
  return requestJson<HomeworkEnvelope>("/api/v1/homework/sessions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      student_id: profile.studentId,
      grade: profile.grade,
      province_code: profile.provinceCode,
      target_exam_year: profile.targetExamYear,
      subject_hint: subject,
      plan_task_id: planTaskId || null,
    }),
  });
}

export async function submitHomeworkTurn(body: HomeworkTurnRequest): Promise<HomeworkEnvelope> {
  if (DEMO_MODE) return demoTurn(body);
  const form = new FormData();
  form.set("student_id", body.studentId);
  form.set("subject", body.subject);
  form.set("question_text", body.questionText);
  form.set("student_work", body.studentWork);
  form.set("message", body.message);
  form.set("intent", body.intent);
  form.set("client_turn_id", `web_${Date.now()}_${Math.random().toString(16).slice(2)}`);
  if (body.image) form.append("images", body.image);
  return requestJson<HomeworkEnvelope>(
    `/api/v1/homework/sessions/${encodeURIComponent(body.sessionId)}/turns`,
    { method: "POST", body: form },
  );
}

export async function submitHomeworkAnswer(
  studentId: string,
  questionId: string,
  answer: string,
  fallback: HomeworkTurnRequest,
): Promise<HomeworkEnvelope> {
  if (DEMO_MODE) return demoTurn({ ...fallback, studentWork: answer }, "answer_verification");
  return requestJson<HomeworkEnvelope>(
    `/api/v1/homework/questions/${encodeURIComponent(questionId)}/submission`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        student_id: studentId,
        answer,
        idempotency_key: `web_submission_${questionId}_${Date.now()}`,
      }),
    },
  );
}

export async function confirmHomeworkOcr(
  sessionId: string,
  studentId: string,
  subject: SubjectKey,
  confirmedText: string,
  studentWork: string,
): Promise<HomeworkEnvelope> {
  if (DEMO_MODE) {
    return demoTurn({
      sessionId,
      studentId,
      subject,
      questionText: confirmedText,
      studentWork,
      message: "我已确认题目识别内容",
      intent: "request_hint",
    });
  }
  return requestJson<HomeworkEnvelope>(
    `/api/v1/homework/sessions/${encodeURIComponent(sessionId)}/ocr-confirmation`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        student_id: studentId,
        confirmed_text: confirmedText,
        student_work: studentWork,
        subject,
        idempotency_key: `web_ocr_${sessionId}_${Date.now()}`,
      }),
    },
  );
}

export async function requestHomeworkVariant(
  studentId: string,
  questionId: string,
  fallback: HomeworkTurnRequest,
): Promise<HomeworkEnvelope> {
  if (DEMO_MODE) {
    const response = demoTurn(fallback, "variant_practice");
    response.result.tutoring!.variant_package = {
      variant_id: "variant_demo_001",
      source_locator: { title: "53B 同专题训练册", topic: "同源变式训练" },
      release_policy: "after_student_submission",
    };
    return response;
  }
  return requestJson<HomeworkEnvelope>(
    `/api/v1/homework/questions/${encodeURIComponent(questionId)}/variants`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        student_id: studentId,
        idempotency_key: `web_variant_${questionId}_${Date.now()}`,
      }),
    },
  );
}
