import { NextResponse } from "next/server";

import { demoResponse } from "@/lib/demo-agent";
import type { AgentActionRequest, PlannerFormData } from "@/lib/types";

export const runtime = "nodejs";

const API_BASE = (process.env.AI_EDUCATION_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

function initializePayload(form: PlannerFormData) {
  const targetYear = Number(form.deadline.slice(0, 4));
  const daily = [1, 2, 3, 4, 5].map((weekday) => ({
    weekday,
    available_minutes: form.weekdayMinutes,
    preferred_period: "evening",
  }));
  daily.push(
    { weekday: 6, available_minutes: form.weekendMinutes, preferred_period: "morning" },
    { weekday: 7, available_minutes: form.weekendMinutes, preferred_period: "morning" },
  );

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
        curriculum_versions: { mathematics: form.curriculumVersion },
        selected_subjects: form.selectedSubjects,
        subject_selection_confirmed: true,
        class_progress: { mathematics: form.classProgress },
      },
      goal_text: `我数学目前约 ${form.currentScore} 分，希望在目标考试达到 ${form.targetScore} 分`,
      goal_deadline: form.deadline,
      goal_fields: {
        subject: "mathematics",
        goal_type: "subject_score",
        current_value: form.currentScore,
        target_value: form.targetScore,
        deadline: form.deadline,
      },
      weekly_available_minutes: form.weeklyMinutes,
      subject_factors: {
        mathematics: {
          goal_priority: 1,
          score_gap: Math.max(0.2, (form.targetScore - form.currentScore) / 50),
          expected_score_gain: 1,
          urgency: 0.85,
          knowledge_dependency: 1,
        },
      },
      knowledge_evidence: [
        {
          knowledge_id: "math_function_foundation",
          score: form.foundationMastery / 100,
          weight: 0.9,
          source_type: "student_self_assessment",
          source_id: `${form.studentId}_foundation`,
          description: "函数与导数基础自评证据",
        },
        {
          knowledge_id: "math_function_application",
          score: form.applicationMastery / 100,
          weight: 0.75,
          source_type: "student_self_assessment",
          source_id: `${form.studentId}_application`,
          description: "综合应用能力自评证据",
        },
      ],
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
      return { path: "/api/v1/planner/initialize", method: "POST", payload: initializePayload(body.form) };
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

export async function POST(request: Request) {
  let body: AgentActionRequest;
  try {
    body = (await request.json()) as AgentActionRequest;
  } catch {
    return NextResponse.json({ status: "failed", errors: [{ code: "INVALID_JSON", message: "请求格式无效" }] }, { status: 400 });
  }

  if (process.env.AI_EDUCATION_DEMO_MODE === "true") {
    return NextResponse.json(demoResponse(body));
  }

  try {
    const target = targetFor(body);
    const response = await fetch(`${API_BASE}${target.path}`, {
      method: target.method,
      headers: target.payload ? { "Content-Type": "application/json" } : undefined,
      body: target.payload ? JSON.stringify(target.payload) : undefined,
      cache: "no-store",
      signal: AbortSignal.timeout(45_000),
    });
    const data = await response.json();
    return NextResponse.json({ ...data, _meta: { mode: "live", backend: API_BASE } }, { status: response.status });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Agent 服务暂时不可用";
    return NextResponse.json(
      {
        status: "failed",
        errors: [{ code: "AGENT_UNAVAILABLE", message: `无法连接学习规划 Agent：${message}` }],
        _meta: { mode: "live", backend: API_BASE },
      },
      { status: 503 },
    );
  }
}
