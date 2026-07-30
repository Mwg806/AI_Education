import type {
  HomeworkEnvelope,
  HomeworkSession,
  QuestionBankMatch,
  QuestionBankSummary,
  StudentLoginProfile,
  SubjectKey,
} from "@/lib/types";
import { subjectLabels } from "@/lib/curriculum-catalog";

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

const demoSourceTemplates: Partial<Record<SubjectKey, Array<Omit<QuestionBankMatch, "subject" | "topic" | "confidence">>>> = {
  mathematics: [
    { source_id: "qb_e05c690b5052a56a66", title: "1_3.2　利用导数研究函数的单调性、极值和最值.pptx", edition: "B", region: "北京", content_role: "exercise", file_type: "pptx" },
    { source_id: "qb_d1cc787fe9f083edae", title: "1_3.2　利用导数研究函数的单调性、极值和最值.docx", edition: "B", region: "北京", content_role: "exercise", file_type: "docx" },
  ],
  physics: [
    { source_id: "qb_f0335e6009f2e904fa", title: "1_专题八　电路及其应用 训练册word.docx", edition: "B", region: "北京", content_role: "exercise", file_type: "docx" },
    { source_id: "qb_e71d7d67b02a9ccbe9", title: "2026新高考53A物理精练册(2).pdf", edition: "A", region: "全国新高考", content_role: "exercise", file_type: "pdf" },
  ],
  chemistry: [
    { source_id: "qb_2dce3b24437045dcf1", title: "2_专题七　化学反应的热效应　训练册WORD.docx", edition: "B", region: "北京", content_role: "exercise", file_type: "docx" },
  ],
  biology: [
    { source_id: "qb_42299591eda6a0c99a", title: "2_2.2026版5.3B 北京版 训练册PPT.pptx", edition: "B", region: "北京", content_role: "exercise", file_type: "pptx" },
  ],
  chinese: [
    { source_id: "qb_41db50ef2587045109", title: "3_4_专题四　古代诗歌阅读√.pptx", edition: "B", region: "天津", content_role: "exercise", file_type: "pptx" },
  ],
  foreign_language: [
    { source_id: "qb_47b3729176a660578e", title: "1_阅读理解真题汇编.docx", edition: "B", region: "北京", content_role: "exercise", file_type: "docx" },
  ],
  history: [
    { source_id: "qb_578b1ca917d7d5e7d4", title: "第二十单元 当代世界发展的特点与主要趋势.docx", edition: "B", region: "北京", content_role: "exercise", file_type: "docx" },
  ],
  geography: [
    { source_id: "qb_bd91a3d151315525e4", title: "2026新高考53A地理精练册(2).pdf", edition: "A", region: "全国新高考", content_role: "exercise", file_type: "pdf" },
  ],
  ideology_politics: [
    { source_id: "qb_90980515d89f3bde85", title: "专题三 生产资料所有制与经济体制-训练册.pptx", edition: "B", region: "北京", content_role: "exercise", file_type: "pptx" },
  ],
};

function demoTopic(subject: SubjectKey, text: string) {
  const rules: Partial<Record<SubjectKey, Array<[RegExp, string]>>> = {
    mathematics: [[/导数|单调|极值/, "导数与函数单调性"], [/数列|通项|前n项/, "数列"], [/概率|随机/, "概率与统计"], [/圆|直线|几何/, "解析几何"]],
    physics: [[/电路|电流|电压/, "电路及其应用"], [/力|加速度|速度/, "力与运动"], [/电场|磁场/, "电磁场"]],
    chemistry: [[/有机|烃|官能团/, "有机化学基础"], [/反应热|热效应/, "化学反应的热效应"], [/离子|溶液/, "离子反应与溶液"]],
    biology: [[/遗传|基因|DNA/, "遗传的分子基础"], [/细胞|线粒体|叶绿体/, "细胞结构与代谢"], [/生态|种群/, "生态系统"]],
    chinese: [[/诗歌|古诗/, "古代诗歌阅读"], [/文言/, "文言文阅读"], [/作文|写作/, "写作"]],
    foreign_language: [[/grammar|语法|时态/i, "英语语法"], [/cloze|完形/i, "完形填空"], [/read|阅读/i, "阅读理解"]],
    history: [[/世界|国际/, "世界史与国际格局"], [/中国|朝代|革命/, "中国史"]],
    geography: [[/气候|降水|温度/, "气候与自然环境"], [/人口|城市/, "人口与城市"], [/地形|地貌/, "地形地貌"]],
    ideology_politics: [[/哲学|矛盾|意识/, "哲学与文化"], [/经济|市场|生产资料/, "经济与社会"], [/法律|法治/, "政治与法治"]],
    technology: [[/算法|程序|流程图/, "算法与程序设计"], [/结构|设计|系统/, "技术设计与系统"]],
  };
  return rules[subject]?.find(([pattern]) => pattern.test(text))?.[1] || `${subjectLabels[subject]}综合题`;
}

function demoGuidance(subject: SubjectKey, topic: string, text: string, work: string, action: string) {
  const excerpt = (work || text).replace(/\s+/g, " ").slice(0, 90);
  const method: Record<SubjectKey, string> = {
    mathematics: /导数|单调/.test(text) ? "先写出导函数并求临界点，再按临界点分区间判断导数正负；不要跳过定义域。" : "把已知量、目标量和约束分别列出，再选择对应公式或定理。",
    physics: "先确定研究对象和过程，画示意图并统一正方向，再逐段列物理规律与单位。",
    chemistry: "先判断反应体系和条件，再检查守恒关系、离子形式以及量纲是否一致。",
    biology: "先定位材料中的生物学过程，再区分题干事实、变量关系和需要作出的推论。",
    chinese: "先锁定题干要求与文本证据，再按“依据—分析—结论”组织答案，避免只写空泛评价。",
    foreign_language: "先判断设空处承担的句法成分，再结合上下文逻辑、时态和固定搭配作答。",
    history: "先明确时间、空间与材料立场，再用材料证据连接背景、变化和影响。",
    geography: "先读取区域位置与图表变量，再按自然和人文要素建立因果链。",
    ideology_politics: "先锁定材料关键词对应的理论范围，再用“理论依据+材料分析+结论”作答。",
    technology: "先明确输入、处理与输出，再逐项检查约束、流程和评价指标。",
  };
  if (action === "answer_verification") {
    return `我读取到你的作答“${excerpt || "尚无可识别文字"}”。针对“${topic}”，${method[subject]}当前反馈依据的是你提交的具体内容，不会用固定结论代替校验。`;
  }
  if (action === "check_step") {
    return `你希望检查的是“${excerpt || "当前步骤"}”。针对“${topic}”，${method[subject]}`;
  }
  return `题目当前识别为“${topic}”。${method[subject]}`;
}

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
  const resolvedAction = action !== "release_hint"
    ? action
    : body.intent === "check_step"
      ? "check_step"
      : body.intent === "request_knowledge_review"
        ? "knowledge_review"
        : "release_hint";
  demoHintLevel = resolvedAction === "release_hint" ? Math.min(demoHintLevel + 1, 5) : demoHintLevel;
  demoSession = {
    ...demoSession!,
    status: resolvedAction === "answer_verification" ? "verifying" : "waiting_for_student",
    state_version: demoSession!.state_version + 1,
    hint_runtime: {
      current_level: demoHintLevel,
      hint_dependency_score: demoHintLevel * 0.12,
      student_attempt_count: body.studentWork ? 1 : 0,
    },
  };
  const combined = `${body.questionText}\n${body.studentWork}\n${body.message}`;
  const topic = demoTopic(body.subject, combined);
  const templates = demoSourceTemplates[body.subject] || [];
  const liveMatches: QuestionBankMatch[] = templates.map((item, index) => ({
    ...item,
    subject: body.subject,
    topic,
    confidence: Math.max(0.72, 0.91 - index * 0.05 - (combined.length < 12 ? 0.08 : 0)),
  }));
  const isDirect = /直接|只要|答案/.test(body.message);
  return {
    status: resolvedAction === "answer_verification" ? "partial_success" : "success",
    lifecycle_status: demoSession.status,
    result: {
      session: demoSession,
      question: {
        question_id: "q_demo_001",
        subject: body.subject,
        question_type: "subjective_calculation",
        stem: body.questionText,
        knowledge_ids: [`${body.subject}:${topic}`],
        parse_confidence: 0.96,
        gaokao_relevance: 0.82,
      },
      tutoring: {
        action: resolvedAction,
        student_visible_content: resolvedAction === "answer_verification"
          ? {
              acknowledgement: `已收到你针对“${topic}”的完整作答，并按本次内容开始校验。`,
              guidance: demoGuidance(body.subject, topic, body.questionText, body.studentWork, resolvedAction),
              question_to_student: "请对照上述检查点说明你最不确定的一步，我会继续核对该步。",
              warning: "没有唯一题号与评分答案映射时会明确标记不确定，不会伪造正误。",
            }
          : {
              acknowledgement: isDirect
                ? "我知道你想尽快完成，但我不能直接给可抄写答案。"
                : body.studentWork
                  ? `我已读取你的具体步骤，并将本题识别为“${topic}”。`
                  : `我已根据本轮输入将题目识别为“${topic}”。`,
              guidance: demoGuidance(body.subject, topic, body.questionText, body.studentWork, resolvedAction),
              question_to_student: resolvedAction === "knowledge_review" ? "请用自己的话说明这个方法的适用条件。" : "请按这个检查点写出下一步，我再继续核对。",
              warning: "本轮只释放一个提示，不展开完整答案。",
            },
        pedagogical_metadata: { hint_level: demoHintLevel },
        confidence: 0.82,
      },
      question_bank_matches: liveMatches,
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
