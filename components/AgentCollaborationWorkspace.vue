<script setup lang="ts">
import {
  ArrowRight,
  Bot,
  BrainCircuit,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  CircleAlert,
  Clock3,
  GitBranch,
  LoaderCircle,
  RefreshCw,
  Send,
  ShieldCheck,
  Sparkles,
  UserRound,
} from "@lucide/vue";
import { computed, nextTick, onMounted, ref } from "vue";

import {
  fetchCollaborationMemory,
  fetchUnifiedEvents,
  fetchUnifiedProfile,
  sendOrchestrationMessage,
  type CollaborationMemoryResponse,
  type OrchestrationResult,
} from "@/lib/orchestration-client";
import {
  aiTaskPending,
  beginAiTask,
  completeAiTask,
  failAiTask,
  usePersistentAiState,
} from "@/lib/ai-runtime";
import { subjectLabels } from "@/lib/curriculum-catalog";
import type { LearningPlan, StudentLoginProfile, SubjectKey } from "@/lib/types";

const props = defineProps<{
  profile: StudentLoginProfile;
  currentPlan?: LearningPlan | null;
}>();
const emit = defineEmits<{ openPlanningCenter: [] }>();

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  result?: OrchestrationResult;
}

const subject = ref<SubjectKey>("foreign_language");
const input = ref("");
const error = ref("");
const detailsOpen = ref<Record<string, boolean>>({});
const conversation = ref<HTMLElement | null>(null);
const sessionId = usePersistentAiState(
  props.profile.studentId,
  "planning-collaboration-session",
  `orchestrator_session_${Date.now().toString(36)}`,
);
const unifiedProfile = ref<Record<string, unknown>>({});
const recentEvents = ref<Array<Record<string, unknown>>>([]);
const collaborationMemory = ref<CollaborationMemoryResponse | null>(null);
const messages = usePersistentAiState<ChatMessage[]>(
  props.profile.studentId,
  "planning-collaboration-messages",
  [
  {
    id: "welcome",
    role: "assistant",
    content: `你好，${props.profile.studentName}。我会结合你在各学习模块中的对话、诊断和训练记录，持续总结学习状态并帮助你调整下一步计划。`,
  },
  ],
  50,
);
const loading = aiTaskPending(
  props.profile.studentId,
  "planning-collaboration",
);

const examples = [
  {
    label: "总结与当前重点",
    subject: "mathematics" as SubjectKey,
    text: "结合我在平台上的近期记录，生成当前学习总结，并给出不超过 3 项当前计划重点；如果证据不足，请明确说明还需要完成哪些学习活动。",
  },
  {
    label: "调整本周计划",
    subject: "mathematics" as SubjectKey,
    text: "结合最近英语和数学的学习记录，在对话中总结变化并给出本周最重要的 3 项计划重点。",
  },
  { label: "规划编程路线", subject: "technology" as SubjectKey, text: "结合我的现有基础和训练记录，规划下一阶段的 Python 学习路线。" },
  { label: "检查规划证据", subject: "mathematics" as SubjectKey, text: "当前证据是否足够支持学习规划？还需要补充什么记录？" },
];

const latest = computed(() => [...messages.value].reverse().find((item) => item.result)?.result);
const profileVersion = computed(() => latest.value?.profile_version || Number(unifiedProfile.value.profile_version || 1));
const memoryLabel = computed(() => {
  const memory = collaborationMemory.value?.memory;
  if (!memory?.interaction_count) return "首次使用 · 等待积累学习证据";
  return "已恢复 " + memory.interaction_count + " 轮规划记忆";
});
function eventSourceLabel(event: Record<string, unknown>) {
  if (event.event_type === "PLAN_UPDATED") return "个性化学习计划";
  if (event.agent === "english_reading_language") return "外语学习";
  if (event.agent === "programming_learning") return "职业教育";
  if (event.agent === "learning_diagnosis" || event.event_type === "DIAGNOSIS_UPDATED") return "学情诊断与学习记录";
  if (event.agent === "homework_tutor") return "作业辅导";
  return "其他学习记录";
}
const planningSourceNames = computed(() => {
  const names = new Set(recentEvents.value.map(eventSourceLabel));
  if (props.currentPlan) names.add("个性化学习计划");
  return [...names];
});
const planningSourceLabel = computed(() => {
  if (!planningSourceNames.value.length) return "等待学习依据";
  const names = planningSourceNames.value.slice(0, 3).join("、");
  const more = planningSourceNames.value.length > 3 ? `等 ${planningSourceNames.value.length} 类` : "";
  return `${names}${more}已接入`;
});

const agentLabels: Record<string, string> = {
  supervisor: "智能规划总控",
  personalized_learning_planner: "智能规划 Agent",
  homework_tutor: "作业辅导 Agent",
  learning_diagnosis: "学情诊断 Agent",
  teacher_preparation: "教师备课 Agent",
  english_reading_language: "外语学习",
  programming_learning: "职业教育",
};
const statusLabels: Record<string, string> = {
  success: "已完成",
  partial_success: "部分完成",
  needs_input: "等待补充",
  need_more_information: "等待补充",
  skipped: "已跳过",
  failed: "执行失败",
  pending: "等待执行",
  running: "执行中",
};
const hiddenPlanningHeadings = ["原因与依据", "建议下一步", "证据边界", "需要你确认"];
const internalPlanningMarkers = [
  "verified_results",
  "task_statuses",
  "missing_context",
  "personalization_context",
  "verified_cross_module_evidence",
  "formal_plan_requires_confirmation",
];

onMounted(async () => {
  const [profileResult, eventResult, memoryResult] = await Promise.allSettled([
    fetchUnifiedProfile(),
    fetchUnifiedEvents(),
    fetchCollaborationMemory(),
  ]);
  if (profileResult.status === "fulfilled") unifiedProfile.value = profileResult.value;
  if (eventResult.status === "fulfilled") recentEvents.value = eventResult.value;
  if (memoryResult.status === "fulfilled") applyMemory(memoryResult.value, true);
});

function applyMemory(value: CollaborationMemoryResponse, restoreMessages = false) {
  collaborationMemory.value = value;
  if (!restoreMessages || !value.messages.length || messages.value.length > 1) return;
  const history = value.messages
    .filter((message) => message.content.trim())
    .map((message, index) => ({
      id: `memory_${message.created_at}_${index}`,
      role: message.role,
      content: message.content,
    } satisfies ChatMessage));
  messages.value = [
    {
      id: "welcome",
      role: "assistant",
      content: `欢迎回来，${props.profile.studentName}。下方已恢复最近的规划对话，你可以直接围绕已有总结和计划重点继续追问。`,
    },
    ...history,
  ];
  void nextTick().then(scrollBottom);
}

async function sendExample(item: typeof examples[number]) {
  if (loading.value) return;
  subject.value = item.subject;
  input.value = item.text;
  await nextTick();
  await submit();
}

async function submit() {
  const content = input.value.trim();
  if (!content || loading.value) return;
  input.value = "";
  error.value = "";
  messages.value.push({ id: `user_${Date.now()}`, role: "user", content });
  const taskId = beginAiTask({
    studentId: props.profile.studentId,
    channel: "planning-collaboration",
    title: "智能规划 AI 已回复",
    destination: { view: "collaboration" },
  });
  await scrollBottom();
  try {
    const result = await sendOrchestrationMessage({
      message: content,
      subject: subject.value,
      sessionId: sessionId.value,
    });
    messages.value.push({
      id: result.run_id,
      role: "assistant",
      content: result.final_response,
      result,
    });
    const [profileResult, eventResult, memoryResult] = await Promise.allSettled([
      fetchUnifiedProfile(),
      fetchUnifiedEvents(),
      fetchCollaborationMemory(),
    ]);
    if (profileResult.status === "fulfilled") unifiedProfile.value = profileResult.value;
    if (eventResult.status === "fulfilled") recentEvents.value = eventResult.value;
    if (memoryResult.status === "fulfilled") applyMemory(memoryResult.value);
    completeAiTask(taskId, "你的智能规划对话已经生成新回复。");
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "智能规划暂时不可用";
    messages.value.push({
      id: `failed_${Date.now()}`,
      role: "assistant",
      content: "这次规划请求没有成功送达。错误已明确显示，没有使用固定答案冒充模型回复。",
    });
    failAiTask(taskId, "智能规划请求未完成，点击返回查看原因。");
  } finally {
    await scrollBottom();
  }
}

async function scrollBottom() {
  await nextTick();
  conversation.value?.scrollTo({ top: conversation.value.scrollHeight, behavior: "smooth" });
}

function toggle(runId: string) {
  detailsOpen.value[runId] = !detailsOpen.value[runId];
}

function formatValue(value: unknown) {
  if (Array.isArray(value)) return value.length ? value.join("、") : "暂无";
  if (value && typeof value === "object") return "结构化学习状态已更新";
  return String(value ?? "暂无");
}

function planningMessageContent(message: ChatMessage) {
  if (message.role === "user") return message.content;
  const visibleLines: string[] = [];
  for (const line of message.content.trim().split("\n")) {
    const normalized = line.trim();
    if (hiddenPlanningHeadings.some((heading) => normalized.startsWith(heading + "：") || normalized.startsWith(heading + ":"))) break;
    if (internalPlanningMarkers.some((marker) => normalized.includes(marker))) continue;
    visibleLines.push(line);
  }
  const visible = visibleLines.join("\n").trim();
  return visible || "这条历史回复仅包含内部生成说明，已隐藏。请重新生成学习总结和当前计划重点。";
}
</script>

<template>
  <div class="collab-workspace planning-workspace">
    <section class="collab-hero planning-hero student-module-hero">
      <div>
        <span><Sparkles :size="16" /> CONTINUOUS LEARNING PLANNING</span>
        <h1>智能规划</h1>
        <p>持续汇总你在各学习模块中的对话、诊断与训练记录，形成有依据的学习总结，并帮助你决定下一步先做什么。</p>
      </div>
      <div class="collab-health">
        <span><i />{{ planningSourceLabel }}</span>
        <strong>学习画像 v{{ profileVersion }}</strong>
        <small>{{ memoryLabel }}</small>
        <small>近期学习证据 {{ recentEvents.length }} 条</small>
        <small v-if="planningSourceNames.length">来源：{{ planningSourceNames.join("、") }}</small>
      </div>
    </section>

    <section class="planning-evidence-strip" aria-label="规划依据状态">
      <article>
        <span><RefreshCw :size="18" /></span>
        <div><strong>事件驱动更新</strong><small>完成诊断、训练或有效对话后刷新建议</small></div>
      </article>
      <article>
        <span><ShieldCheck :size="18" /></span>
        <div><strong>只依据真实记录</strong><small>证据不足时明确提示需要补充什么</small></div>
      </article>
      <article>
        <span><CheckCircle2 :size="18" /></span>
        <div><strong>计划由你确认</strong><small>建议不会自动覆盖正在执行的正式计划</small></div>
      </article>
    </section>

    <div class="collab-layout">
      <section class="collab-chat-card planning-chat-card">
        <header>
          <div><Bot :size="21" /><span><strong>智能规划助手</strong><small>学习总结和当前计划重点都在这里生成，可直接继续追问</small></span></div>
          <label><span>本次关注学科</span><select v-model="subject"><option v-for="(label, key) in subjectLabels" :key="key" :value="key">{{ label }}</option></select></label>
        </header>

        <div ref="conversation" class="collab-conversation planning-conversation">
          <article v-for="message in messages" :key="message.id" class="collab-message" :class="message.role">
            <span class="collab-avatar"><UserRound v-if="message.role === &quot;user&quot;" :size="18" /><Bot v-else :size="18" /></span>
            <div class="collab-bubble">
              <small>{{ message.role === "user" ? profile.studentName : "智能规划助手" }}</small>
              <p>{{ planningMessageContent(message) }}</p>

              <template v-if="message.result?.plan">
                <button class="trace-toggle" @click="toggle(message.result.run_id)">
                  <GitBranch :size="16" />
                  查看规划依据与 {{ message.result.plan.tasks.length }} 个处理步骤
                  <ChevronUp v-if="detailsOpen[message.result.run_id]" :size="16" /><ChevronDown v-else :size="16" />
                </button>
                <div v-if="detailsOpen[message.result.run_id]" class="collab-trace">
                  <div class="trace-summary"><span>执行模式：{{ message.result.plan.execution_mode }}</span><span>学习事件：{{ message.result.event_count }}</span><span>记录编号：{{ message.result.run_id.slice(-8) }}</span></div>
                  <div v-if="message.result.evidence_summary?.modules?.length" class="planning-source-detail">
                    <strong>本次实际读取的学习依据</strong>
                    <p>{{ message.result.evidence_summary?.selection_policy }}</p>
                    <div>
                      <span v-for="item in message.result.evidence_summary?.modules || []" :key="item.module">
                        {{ item.label }} · {{ item.event_count }} 条
                      </span>
                    </div>
                  </div>
                  <article v-for="(task, index) in message.result.plan.tasks" :key="task.task_id" :class="task.status">
                    <span>{{ index + 1 }}</span>
                    <div><strong>{{ agentLabels[task.agent] || task.agent }}</strong><small>{{ task.objective }}</small><p>{{ task.status_message }}</p><em v-if="task.latency_ms != null"><Clock3 :size="13" />{{ task.latency_ms }} ms</em></div>
                    <b>{{ statusLabels[task.status] || task.status }}</b>
                  </article>
                  <div v-if="message.result.handoffs.length" class="handoff-list"><strong>学习能力衔接</strong><p v-for="item in message.result.handoffs" :key="item.handoff_id">{{ agentLabels[item.from_agent] || item.from_agent }} <ArrowRight :size="13" /> {{ agentLabels[item.to_agent] || item.to_agent }}：{{ item.reason }}</p></div>
                </div>

                <div v-if="message.result.profile_changes.length" class="profile-diff">
                  <header><BrainCircuit :size="17" /><strong>本次学习画像变化</strong><span>v{{ message.result.profile_version }}</span></header>
                  <p v-for="change in message.result.profile_changes.slice(0, 4)" :key="change.field"><b>{{ change.field }}</b><span>{{ formatValue(change.before) }}</span><ArrowRight :size="13" /><span>{{ formatValue(change.after) }}</span></p>
                </div>

                <button v-if="message.result.requires_confirmation" class="confirm-suggestion" @click="emit(&quot;openPlanningCenter&quot;)"><ShieldCheck :size="17" />{{ message.result.confirmation?.label || "前往计划设置确认" }}</button>
                <small class="summary-mode"><ShieldCheck :size="13" />{{ message.result.response_generation_mode === "llm" ? "规划总结由受事实约束的模型生成" : "当前展示各模块已验证结果的结构化汇总" }}；正式计划不会自动覆盖。</small>
              </template>
            </div>
          </article>
          <article v-if="loading" class="collab-message assistant"><span class="collab-avatar"><Bot :size="18" /></span><div class="collab-bubble typing"><LoaderCircle class="spin" :size="17" /><span>正在读取学习记录并形成规划建议…</span></div></article>
        </div>

        <div class="collab-quick-prompts"><span>常用规划</span><div><button v-for="item in examples" :key="item.label" type="button" :title="item.text" :disabled="loading" @click="sendExample(item)">{{ item.label }}</button></div></div>

        <div v-if="error" class="collab-error"><CircleAlert :size="17" />{{ error }}</div>
        <form class="collab-composer" @submit.prevent="submit">
          <textarea v-model="input" rows="3" placeholder="例如：总结近期学习情况，列出当前 3 项计划重点，并说明依据" @keydown.enter.exact.prevent="submit" />
          <div><span>Enter 发送 · Shift + Enter 换行</span><button class="planning-primary-action" :disabled="loading || !input.trim()"><Send :size="17" />生成规划建议</button></div>
        </form>
      </section>

      <section class="collab-principles planning-boundary"><header><CheckCircle2 :size="18" /><div><strong>规划边界</strong><small>规划与作业辅导职责分离</small></div></header><ul><li>负责总结、优先级和时间安排</li><li>具体题目请进入作业辅导</li><li>缺少学习证据时先提示补充</li><li>正式计划必须由学生确认</li></ul><button class="refresh-context" @click="fetchUnifiedEvents().then(value => recentEvents = value)"><RefreshCw :size="16" />刷新学习依据</button></section>
    </div>
  </div>
</template>
