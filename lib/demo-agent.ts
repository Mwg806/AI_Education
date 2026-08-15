import type { AgentActionRequest, AgentEnvelope, LearningPlan, PlannerFormData } from "@/lib/types";
import { progressLabel } from "@/lib/curriculum-catalog";

const taskTypes = [
  ["concept_repair", "概念与定义复核", "先对照所选章节的课标要求梳理概念、条件和表示方法。"],
  ["targeted_practice", "基础题型训练", "用分层题组检验基础理解，不预设尚未提供的具体错因。"],
  ["spaced_review", "错题间隔复习", "在遗忘窗口前回访本章真实错题，巩固可迁移步骤。"],
  ["timed_training", "章节限时训练", "逐步建立本章的时间分配和步骤得分意识。"],
  ["stage_assessment", "本周阶段测评", "用小型测评补充客观证据，再决定下一阶段安排。"],
] as const;

function futureDate(offset: number, hour = 19): string {
  const date = new Date();
  date.setDate(date.getDate() + offset);
  date.setHours(hour, 30, 0, 0);
  return date.toISOString();
}

function dateOnly(offset: number): string {
  return futureDate(offset).slice(0, 10);
}

function createPlan(form: PlannerFormData): LearningPlan {
  const subjectPlans = form.subjectPlans.length
    ? form.subjectPlans
    : [];
  const primary = subjectPlans[0];
  if (!primary) throw new Error("请至少选择一个规划科目");
  const planned = Math.min(Math.round(form.weeklyMinutes * 0.82), 560);
  const durations = [60, 75, 45, 90, 60];
  const total = durations.reduce((sum, duration) => sum + duration, 0);
  const subjectBudget = Math.floor(planned / subjectPlans.length);
  const factor = subjectBudget / total;
  const tasks = subjectPlans.flatMap((item, subjectIndex) => {
    const scopes = item.classProgress.length
      ? item.classProgress
      : ["selected_chapter"];
    const scopeLabel = scopes
      .map((chapterId) =>
        progressLabel(item.subject, item.curriculumVersion, chapterId),
      )
      .join("、");
    return taskTypes.map(([type, title, rationale], index) => ({
      task_id: `task_demo_${subjectIndex + 1}_${index + 1}`,
      subject: item.subject,
      task_type: type,
      knowledge_ids: [`${scopes[index % scopes.length]}_${type}`],
      planned_start: futureDate(index + 1, index === 4 ? 9 : 19),
      planned_duration_minutes: Math.max(
        5,
        Math.round((durations[index] * factor) / 5) * 5,
      ),
      difficulty: 0.42 + index * 0.09,
      exam_relevance: 0.74 + index * 0.05,
      status: "scheduled",
      rationale: `${title}：${scopeLabel}；${rationale}`,
    }));
  });
  const scheduledMinutes = tasks.reduce(
    (sum, task) => sum + task.planned_duration_minutes,
    0,
  );

  return {
    plan_id: "plan_demo_personalized_001",
    student_id: form.studentId,
    version: 1,
    status: "waiting_for_confirmation",
    plan_start: dateOnly(1),
    plan_end: subjectPlans
      .map((item) => item.deadline)
      .sort()[0],
    stages: [
      {
        stage_id: "stage_foundation",
        name: "第一阶段 · 基础修复",
        start_date: dateOnly(1),
        end_date: dateOnly(28),
        objective: `围绕 ${subjectPlans.length} 科的已选章节补充客观诊断证据，为各科成绩目标建立可持续提升路径`,
      },
    ],
    tasks,
    weekly_capacity_minutes: form.weeklyMinutes,
    scheduled_minutes: scheduledMinutes,
    buffer_minutes: Math.max(form.weeklyMinutes - scheduledMinutes, 0),
    subject_time_budgets: Object.fromEntries(
      subjectPlans.map((item) => [item.subject, subjectBudget]),
    ),
    subject_goals: subjectPlans.map((item) => ({
      subject: item.subject,
      current_value: item.currentScore,
      target_value: item.targetScore,
      deadline: item.deadline,
      priority: item.priority,
      curriculum_version: item.curriculumVersion,
      class_progress: item.classProgress,
    })),
    validation: {
      valid: true,
      checks: {
        capacity_respected: true,
        prerequisites_respected: true,
        spaced_review_included: true,
        assessment_included: true,
      },
      errors: [],
      warnings: [],
    },
    explanations: {
      strategy: `当前只围绕 ${subjectPlans.length} 科已确认的教材进度安排诊断、复习与测评，不推断未提供的章节或错因。`,
      adjustment: "系统将依据完成率、正确率和可用时间变化评估是否需要局部调整。",
    },
  };
}

export function demoResponse(body: AgentActionRequest): AgentEnvelope {
  if (body.action === "health") {
    return { status: "ok", lifecycle_status: "ready", _meta: { mode: "demo" } };
  }

  if (body.action === "confirm") {
    return {
      status: "success",
      lifecycle_status: "active",
      result: { event: "PlanPublished" },
      _meta: { mode: "demo" },
    };
  }

  if (body.action === "practice") {
    return {
      status: "success",
      lifecycle_status: "active",
      result: {
        practice_update: {
          valid: true,
          duplicate: false,
          quality_score: 0.84,
          mastery_updates: [{ knowledge_id: "selected_chapter_foundation", delta: 0.04 }],
          replan_check_required: false,
        },
      },
      _meta: { mode: "demo" },
    };
  }

  if (!body.form) {
    return {
      status: "failed",
      errors: [{ code: "FORM_REQUIRED", message: "缺少学习画像数据" }],
      _meta: { mode: "demo" },
    };
  }

  const plan = createPlan(body.form);
  const primaryChapter =
    body.form.subjectPlans[0]?.classProgress[0] || "selected_chapter";
  return {
    status: "success",
    lifecycle_status: "waiting_for_confirmation",
    trace_id: "trace_demo_preview",
    data_version: "v1",
    result: {
      plan,
      knowledge_profile: {
        priority_gaps: ["所选章节概念基础", "基础题型稳定性", "综合应用证据不足"],
        assessment_quality: { coverage: 0.78, confidence: 0.81 },
        knowledge_states: [
          {
            knowledge_id: `${primaryChapter} · 基础理解`,
            mastery_probability: 0.52,
            mastery_level: "developing",
            confidence: 0.82,
            forgetting_risk: 0.31,
          },
          {
            knowledge_id: `${primaryChapter} · 基础应用`,
            mastery_probability: Math.min(0.95, 0.52 + 0.08),
            mastery_level: "developing",
            confidence: 0.77,
            forgetting_risk: 0.38,
          },
          {
            knowledge_id: `${primaryChapter} · 综合应用`,
            mastery_probability: 0.44,
            mastery_level: "emerging",
            confidence: 0.72,
            forgetting_risk: 0.46,
          },
        ],
      },
      time_profile: {
        weekly_effective_minutes: body.form.weeklyMinutes,
        recommended_scheduled_minutes: plan.scheduled_minutes,
        buffer_minutes: plan.buffer_minutes,
      },
    },
    _meta: { mode: "demo" },
  };
}
