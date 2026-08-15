import { demoResponse } from "@/lib/demo-agent";
import { subjectLabels, subjectScoreMax } from "@/lib/curriculum-catalog";
import type {
  AgentActionRequest,
  AgentEnvelope,
  DiagnosticAnswer,
  DiagnosticEvidence,
  DiagnosticResult,
  DiagnosticSession,
  HomeworkHealth,
  PlannerFormData,
  PlannerSubjectPlan,
} from "@/lib/types";

const API_BASE = (import.meta.env.VITE_AGENT_API_BASE_URL || "/agent-api").replace(/\/$/, "");
const DEMO_MODE =
  import.meta.env.VITE_AGENT_DEMO_MODE === "true" ||
  (import.meta.env.PROD && import.meta.env.VITE_AGENT_DEMO_MODE !== "false");

function initializePayload(
  form: PlannerFormData,
  diagnosticEvidenceBySubject: Partial<
    Record<PlannerSubjectPlan["subject"], DiagnosticEvidence[]>
  > = {},
) {
  const targetYear = form.targetExamYear;
  const daily = [1, 2, 3, 4, 5].map((weekday) => ({
    weekday,
    available_minutes: form.weekdayMinutes,
    preferred_period: "evening",
  }));
  daily.push(
    { weekday: 6, available_minutes: form.weekendMinutes, preferred_period: "morning" },
    { weekday: 7, available_minutes: form.weekendMinutes, preferred_period: "morning" },
  );

  const primary = form.subjectPlans[0];
  if (!primary) throw new Error("请至少选择一个规划科目");
  const curriculumVersions = Object.fromEntries(
    form.subjectPlans.map((item) => [item.subject, item.curriculumVersion]),
  );
  const classProgress = Object.fromEntries(
    form.subjectPlans.map((item) => [item.subject, item.classProgress]),
  );
  const priorityWeights = { 1: 1, 2: 0.75, 3: 0.55 } as const;
  const goals = form.subjectPlans.map((item) => ({
    subject: item.subject,
    current_value: item.currentScore,
    target_value: item.targetScore,
    deadline: item.deadline,
    priority: item.priority,
    curriculum_version: item.curriculumVersion,
    class_progress: item.classProgress,
  }));
  const goalText = form.subjectPlans
    .map(
      (item) =>
        `${subjectLabels[item.subject]}目前约 ${item.currentScore} 分，目标 ${item.targetScore} 分`,
    )
    .join("；");
  return {
    student_id: form.studentId,
    idempotency_key: `${form.studentId}_initialize_${Date.now()}`,
    payload: {
      student_profile: {
        student_id: form.studentId,
        grade: form.grade,
        school_term: form.schoolTerm,
        province_code: form.provinceCode,
        school_entry_year: targetYear - 3,
        target_exam_year: targetYear,
        curriculum_versions: curriculumVersions,
        selected_subjects: form.selectedSubjects,
        subject_selection_confirmed: true,
        class_progress: classProgress,
      },
      goal_text: goalText,
      goal_deadline: primary.deadline,
      goals,
      goal_fields: {
        subject: primary.subject,
        goal_type: "subject_score",
        current_value: primary.currentScore,
        target_value: primary.targetScore,
        deadline: primary.deadline,
      },
      weekly_available_minutes: form.weeklyMinutes,
      subject_factors: Object.fromEntries(
        form.subjectPlans.map((item) => [
          item.subject,
          {
            goal_priority: priorityWeights[item.priority],
            score_gap: Math.max(
              0.2,
              (item.targetScore - item.currentScore) /
                subjectScoreMax(item.subject),
            ),
            expected_score_gain: 1,
            urgency:
              item.priority === 1 ? 0.9 : item.priority === 2 ? 0.75 : 0.6,
            knowledge_dependency: 1,
          },
        ]),
      ),
      knowledge_evidence_by_subject: diagnosticEvidenceBySubject,
      daily_capacity: daily,
    },
  };
}

function targetFor(body: AgentActionRequest): { path: string; method: "GET" | "POST"; payload?: unknown } {
  switch (body.action) {
    case "health":
      return { path: "/health", method: "GET" };
    case "initialize":
      if (!body.form) throw new Error("缺少学习画像数据");
      return {
        path: "/api/v1/planner/initialize",
        method: "POST",
        payload: initializePayload(
          body.form,
          body.diagnosticEvidenceBySubject,
        ),
      };
    case "confirm":
      if (!body.planId || !body.studentId || !body.version) throw new Error("缺少计划确认参数");
      return {
        path: `/api/v1/plans/${encodeURIComponent(body.planId)}/confirm`,
        method: "POST",
        payload: {
          student_id: body.studentId,
          expected_version: body.version,
          idempotency_key: `${body.studentId}_confirm_${body.planId}_${body.version}`,
        },
      };
    case "practice":
      if (!body.studentId || !body.event) throw new Error("缺少练习反馈参数");
      return {
        path: "/api/v1/learning-events",
        method: "POST",
        payload: {
          student_id: body.studentId,
          event: body.event,
          idempotency_key: String(body.event.event_id || `event_${Date.now()}`),
        },
      };
  }
}

async function plannerRequest<T>(path: string, payload: unknown, timeout = 180_000): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      cache: "no-store",
      signal: AbortSignal.timeout(timeout),
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "规划服务暂时不可用";
    throw new Error(`无法连接学习规划 Agent：${message}`);
  }
  const data = (await response.json()) as T & {
    detail?: string;
    errors?: Array<{ message: string }>;
  };
  if (!response.ok) {
    throw new Error(data.errors?.[0]?.message || data.detail || "规划服务请求失败");
  }
  return data;
}

export async function startPlannerDiagnostic(
  form: PlannerFormData,
  subjectPlan: PlannerSubjectPlan,
): Promise<DiagnosticSession> {
  if (DEMO_MODE) throw new Error("快速诊断必须连接真实规划模型");
  return plannerRequest<DiagnosticSession>("/api/v1/planner/diagnostics", {
    student_id: form.studentId,
    grade: form.grade,
    subject: subjectPlan.subject,
    curriculum_version: subjectPlan.curriculumVersion,
    chapter_ids: subjectPlan.classProgress,
  });
}

export function resolveDiagnosticAssetHtml(html: string): string {
  return html.replaceAll(
    'src="/api/v1/exam-diagnostics/assets/',
    `src="${API_BASE}/api/v1/exam-diagnostics/assets/`,
  );
}

export async function submitPlannerDiagnostic(
  studentId: string,
  diagnosticId: string,
  responses: DiagnosticAnswer[],
): Promise<DiagnosticResult> {
  return plannerRequest<DiagnosticResult>(
    `/api/v1/planner/diagnostics/${encodeURIComponent(diagnosticId)}/submit`,
    { student_id: studentId, responses },
    45_000,
  );
}

export async function fetchPlannerHealth(): Promise<HomeworkHealth> {
  const response = await fetch(`${API_BASE}/health`, { cache: "no-store" });
  if (!response.ok) throw new Error("无法读取规划模型状态");
  return response.json() as Promise<HomeworkHealth>;
}

export async function fetchLatestPlan(studentId: string): Promise<AgentEnvelope | null> {
  if (DEMO_MODE) return null;
  let response: Response;
  try {
    response = await fetch(
      `${API_BASE}/api/v1/students/${encodeURIComponent(studentId)}/plans/latest`,
      {
        cache: "no-store",
        signal: AbortSignal.timeout(20_000),
      },
    );
  } catch (error) {
    const message = error instanceof Error ? error.message : "最近规划读取失败";
    throw new Error(`无法恢复最近一次学习规划：${message}`);
  }
  const data = await response.json() as AgentEnvelope & { detail?: string };
  const firstError = data.errors?.[0];
  if (
    firstError?.code === "INPUT_VALIDATION_ERROR"
    && firstError.message.includes("未找到计划")
  ) {
    return null;
  }
  if (!response.ok || data.status === "failed") {
    throw new Error(firstError?.message || data.detail || "最近规划读取失败");
  }
  return { ...data, _meta: { mode: "live", backend: API_BASE } };
}

export async function callAgent(body: AgentActionRequest): Promise<AgentEnvelope> {
  if (DEMO_MODE) return demoResponse(body);

  const target = targetFor(body);
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${target.path}`, {
      method: target.method,
      headers: target.payload ? { "Content-Type": "application/json" } : undefined,
      body: target.payload ? JSON.stringify(target.payload) : undefined,
      cache: "no-store",
      signal: AbortSignal.timeout(body.action === "initialize" ? 180_000 : 45_000),
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Agent 服务暂时不可用";
    throw new Error(`无法连接学习规划 Agent：${message}`);
  }

  const data = (await response.json()) as AgentEnvelope;
  const result = { ...data, _meta: { mode: "live" as const, backend: API_BASE } };
  if (!response.ok || result.status === "failed" || result.status === "need_more_information") {
    throw new Error(result.errors?.[0]?.message || "Agent 暂时无法完成这次请求");
  }
  return result;
}
