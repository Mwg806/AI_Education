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
  fetchUnifiedEvents,
  fetchUnifiedProfile,
  sendOrchestrationMessage,
  type OrchestrationResult,
} from "@/lib/orchestration-client";
import { subjectLabels } from "@/lib/curriculum-catalog";
import type { StudentLoginProfile, SubjectKey } from "@/lib/types";

const props = defineProps<{ profile: StudentLoginProfile }>();
const emit = defineEmits<{ openPlanningCenter: [] }>();

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  result?: OrchestrationResult;
}

const subject = ref<SubjectKey>("foreign_language");
const input = ref("");
const loading = ref(false);
const error = ref("");
const detailsOpen = ref<Record<string, boolean>>({});
const conversation = ref<HTMLElement | null>(null);
const sessionId = `orchestrator_session_${Date.now().toString(36)}`;
const unifiedProfile = ref<Record<string, unknown>>({});
const recentEvents = ref<Array<Record<string, unknown>>>([]);
const messages = ref<ChatMessage[]>([
  {
    id: "welcome",
    role: "assistant",
    content: `你好，${props.profile.studentName}。你可以直接告诉我最近哪里学得不顺、想完成什么，我会让合适的学习 Agent 协作处理，并把证据不足和需要确认的地方明确告诉你。`,
  },
]);

const examples = [
  { label: "英语诊断并规划", subject: "foreign_language" as SubjectKey, text: "英语阅读一直不好，分析原因然后安排怎么练。" },
  { label: "多科下周计划", subject: "mathematics" as SubjectKey, text: "帮我分析最近英语和数学的问题，并安排下周学习计划。" },
  { label: "编程学习路线", subject: "technology" as SubjectKey, text: "我想学 Python 后端，请结合我的基础给我下一步建议。" },
  { label: "证据是否足够", subject: "mathematics" as SubjectKey, text: "请判断我现在数学最薄弱的知识点。" },
];

const latest = computed(() => [...messages.value].reverse().find((item) => item.result)?.result);
const profileVersion = computed(() => latest.value?.profile_version || Number(unifiedProfile.value.profile_version || 1));

const agentLabels: Record<string, string> = {
  supervisor: "智能协作总控",
  personalized_learning_planner: "个性学习规划 Agent",
  homework_tutor: "作业辅导 Agent",
  learning_diagnosis: "学情诊断 Agent",
  teacher_preparation: "教师备课 Agent",
  english_reading_language: "英语阅读 Agent",
  programming_learning: "职业教育 Agent",
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

onMounted(async () => {
  const [profileResult, eventResult] = await Promise.allSettled([
    fetchUnifiedProfile(),
    fetchUnifiedEvents(),
  ]);
  if (profileResult.status === "fulfilled") unifiedProfile.value = profileResult.value;
  if (eventResult.status === "fulfilled") recentEvents.value = eventResult.value;
});

function useExample(item: typeof examples[number]) {
  subject.value = item.subject;
  input.value = item.text;
}

async function submit() {
  const content = input.value.trim();
  if (!content || loading.value) return;
  input.value = "";
  error.value = "";
  messages.value.push({ id: `user_${Date.now()}`, role: "user", content });
  loading.value = true;
  await scrollBottom();
  try {
    const result = await sendOrchestrationMessage({
      message: content,
      subject: subject.value,
      sessionId,
    });
    messages.value.push({
      id: result.run_id,
      role: "assistant",
      content: result.final_response,
      result,
    });
    const [profileResult, eventResult] = await Promise.allSettled([
      fetchUnifiedProfile(),
      fetchUnifiedEvents(),
    ]);
    if (profileResult.status === "fulfilled") unifiedProfile.value = profileResult.value;
    if (eventResult.status === "fulfilled") recentEvents.value = eventResult.value;
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "智能协作暂时不可用";
    messages.value.push({
      id: `failed_${Date.now()}`,
      role: "assistant",
      content: "这次协作请求没有成功送达。错误已明确显示，没有使用固定答案冒充模型回复。",
    });
  } finally {
    loading.value = false;
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
</script>

<template>
  <div class="collab-workspace">
    <section class="collab-hero">
      <div>
        <span><Sparkles :size="16" /> MULTI-AGENT COLLABORATION</span>
        <h1>智能协作中心</h1>
        <p>用一句自然语言发起任务。系统只调用真实在线 Agent，展示执行顺序、证据边界和需要你确认的变化。</p>
      </div>
      <div class="collab-health">
        <span><i />6 个专业 Agent 已接入</span>
        <strong>画像版本 v{{ profileVersion }}</strong>
        <small>近期统一事件 {{ recentEvents.length }} 条</small>
      </div>
    </section>

    <div class="collab-layout">
      <section class="collab-chat-card">
        <header>
          <div><Bot :size="21" /><span><strong>学习协作助手</strong><small>不会在证据不足时猜测结论</small></span></div>
          <label><span>当前主学科</span><select v-model="subject"><option v-for="(label, key) in subjectLabels" :key="key" :value="key">{{ label }}</option></select></label>
        </header>

        <div ref="conversation" class="collab-conversation">
          <article v-for="message in messages" :key="message.id" class="collab-message" :class="message.role">
            <span class="collab-avatar"><UserRound v-if="message.role==='user'" :size="18" /><Bot v-else :size="18" /></span>
            <div class="collab-bubble">
              <small>{{ message.role === "user" ? profile.studentName : "智能协作助手" }}</small>
              <p>{{ message.content }}</p>

              <template v-if="message.result?.plan">
                <button class="trace-toggle" @click="toggle(message.result.run_id)">
                  <GitBranch :size="16" />
                  {{ message.result.plan.tasks.length }} 个执行步骤 · {{ Math.round(message.result.routing.confidence * 100) }}% 路由置信度
                  <ChevronUp v-if="detailsOpen[message.result.run_id]" :size="16" /><ChevronDown v-else :size="16" />
                </button>
                <div v-if="detailsOpen[message.result.run_id]" class="collab-trace">
                  <div class="trace-summary"><span>执行模式：{{ message.result.plan.execution_mode }}</span><span>学习事件：{{ message.result.event_count }}</span><span>运行 ID：{{ message.result.run_id.slice(-8) }}</span></div>
                  <article v-for="(task, index) in message.result.plan.tasks" :key="task.task_id" :class="task.status">
                    <span>{{ index + 1 }}</span>
                    <div><strong>{{ agentLabels[task.agent] || task.agent }}</strong><small>{{ task.objective }}</small><p>{{ task.status_message }}</p><em v-if="task.latency_ms != null"><Clock3 :size="13" />{{ task.latency_ms }} ms</em></div>
                    <b>{{ statusLabels[task.status] || task.status }}</b>
                  </article>
                  <div v-if="message.result.handoffs.length" class="handoff-list"><strong>Agent 交接</strong><p v-for="item in message.result.handoffs" :key="item.handoff_id">{{ agentLabels[item.from_agent] || item.from_agent }} <ArrowRight :size="13" /> {{ agentLabels[item.to_agent] || item.to_agent }}：{{ item.reason }}</p></div>
                </div>

                <div v-if="message.result.profile_changes.length" class="profile-diff">
                  <header><BrainCircuit :size="17" /><strong>本次画像变化</strong><span>v{{ message.result.profile_version }}</span></header>
                  <p v-for="change in message.result.profile_changes.slice(0, 4)" :key="change.field"><b>{{ change.field }}</b><span>{{ formatValue(change.before) }}</span><ArrowRight :size="13" /><span>{{ formatValue(change.after) }}</span></p>
                </div>

                <button v-if="message.result.requires_confirmation" class="confirm-suggestion" @click="emit('openPlanningCenter')"><ShieldCheck :size="17" />{{ message.result.confirmation?.label || "前往规划中心确认" }}</button>
                <small class="summary-mode"><ShieldCheck :size="13" />{{ message.result.response_generation_mode === "llm" ? "综合回复由受事实约束的模型生成" : "当前展示各 Agent 已验证结果的结构化汇总" }}；正式计划不会自动覆盖。</small>
              </template>
            </div>
          </article>
          <article v-if="loading" class="collab-message assistant"><span class="collab-avatar"><Bot :size="18" /></span><div class="collab-bubble typing"><LoaderCircle class="spin" :size="17" /><span>正在构造执行计划并调用专业 Agent…</span></div></article>
        </div>

        <div v-if="error" class="collab-error"><CircleAlert :size="17" />{{ error }}</div>
        <form class="collab-composer" @submit.prevent="submit">
          <textarea v-model="input" rows="3" placeholder="例如：帮我分析最近英语和数学的问题，并安排下周学习计划" @keydown.enter.exact.prevent="submit" />
          <div><span>Enter 发送 · Shift + Enter 换行</span><button :disabled="loading || !input.trim()"><Send :size="17" />发送</button></div>
        </form>
      </section>

      <aside class="collab-side">
        <section><header><Sparkles :size="18" /><div><strong>试试这样问</strong><small>覆盖典型跨 Agent 场景</small></div></header><button v-for="item in examples" :key="item.label" @click="useExample(item)"><span>{{ item.label }}</span><small>{{ item.text }}</small><ArrowRight :size="15" /></button></section>
        <section><header><CheckCircle2 :size="18" /><div><strong>协作原则</strong><small>每一步都可解释</small></div></header><ul><li>只使用已注册的 6 个专业 Agent</li><li>缺少题目、会话或证据时先追问</li><li>任一子任务失败都会单独标注</li><li>学习计划必须由学生确认</li></ul></section>
        <button class="refresh-context" @click="fetchUnifiedEvents().then(value => recentEvents = value)"><RefreshCw :size="16" />刷新学习上下文</button>
      </aside>
    </div>
  </div>
</template>
