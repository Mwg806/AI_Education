<script setup lang="ts">
import {
  BookOpenText,
  BrainCircuit,
  Camera,
  CheckCircle2,
  CircleAlert,
  Database,
  History,
  Lightbulb,
  LoaderCircle,
  MessageCircleQuestion,
  MessageSquarePlus,
  Paperclip,
  Send,
  ShieldCheck,
  Sparkles,
  Target,
  X,
} from "@lucide/vue";
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from "vue";

import PaginationControls from "@/components/PaginationControls.vue";
import {
  aiTaskPending,
  beginAiTask,
  completeAiTask,
  failAiTask,
  usePersistentAiState,
} from "@/lib/ai-runtime";
import {
  confirmHomeworkOcr,
  createHomeworkSession,
  fetchHomeworkSession,
  fetchHomeworkSessions,
  fetchHomeworkHealth,
  fetchQuestionBankSummary,
  requestHomeworkVariant,
  submitHomeworkAnswer,
  submitHomeworkTurn,
  type HomeworkTurnRequest,
} from "@/lib/homework-client";
import type {
  HomeworkConversationSummary,
  HomeworkEnvelope,
  HomeworkHealth,
  HomeworkKnowledgeSource,
  HomeworkQuestion,
  HomeworkSession,
  PlanTask,
  QuestionBankMatch,
  QuestionBankSummary,
  StudentLoginProfile,
  SubjectKey,
} from "@/lib/types";
import { subjectLabels } from "@/lib/curriculum-catalog";

type TurnIntent = HomeworkTurnRequest["intent"] | "submit_answer";

interface ConversationItem {
  id: string;
  role: "student" | "assistant";
  title: string;
  text: string;
  imageUrl?: string;
  guidance?: string;
  question?: string;
  warning?: string;
}

const props = defineProps<{
  profile: StudentLoginProfile;
  planTasks?: PlanTask[];
  initialSubject?: SubjectKey;
}>();

const subject = ref<SubjectKey>(props.initialSubject || "mathematics");
const messageText = ref("");
const imageFile = ref<File | null>(null);
const imagePreview = ref("");
const sentImageUrls = new Set<string>();
const fileInput = ref<HTMLInputElement | null>(null);
const conversationList = ref<HTMLElement | null>(null);
const session = usePersistentAiState<HomeworkSession | null>(
  props.profile.studentId,
  "homework-session",
  null,
);
const question = usePersistentAiState<HomeworkQuestion | null>(
  props.profile.studentId,
  "homework-question",
  null,
);
const matches = usePersistentAiState<QuestionBankMatch[]>(
  props.profile.studentId,
  "homework-matches",
  [],
  20,
);
const knowledgeSources = usePersistentAiState<HomeworkKnowledgeSource[]>(
  props.profile.studentId,
  "homework-knowledge-sources",
  [],
  20,
);
const summary = ref<QuestionBankSummary | null>(null);
const health = ref<HomeworkHealth | null>(null);
const createDraftId = () =>
  `homework_draft_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
const activeSessionId = usePersistentAiState(
  props.profile.studentId,
  "homework-active-conversation",
  createDraftId(),
);
const conversationSessions = ref<HomeworkConversationSummary[]>([]);
const conversationMessages = ref<Record<string, ConversationItem[]>>({});
const conversationsLoading = ref(true);
const historyOpen = ref(typeof window === "undefined" || window.innerWidth > 900);
const memoryWindowCount = ref(0);
const pendingSessionId = ref<string | null>(null);
const conversationPage = ref(1);
const CONVERSATION_PAGE_SIZE = 6;
const busyAction = ref("");
const error = ref("");
const mode = ref<"live" | "demo">("live");
const awaitingOcrConfirmation = ref(false);
const tutorThinking = aiTaskPending(props.profile.studentId, "homework-tutor");

const conversations = computed<ConversationItem[]>({
  get: () => conversationMessages.value[activeSessionId.value] || [],
  set: (value) => {
    conversationMessages.value = {
      ...conversationMessages.value,
      [activeSessionId.value]: value,
    };
  },
});
const canSend = computed(() => Boolean(messageText.value.trim() || imageFile.value));
const exerciseCount = computed(() => summary.value?.content_roles.exercise || 4634);
const secureCount = computed(() => (
  (summary.value?.content_roles.answer_secure || 478)
  + (summary.value?.content_roles.explanation_secure || 1462)
));
const pagedConversations = computed(() => {
  const start = (conversationPage.value - 1) * CONVERSATION_PAGE_SIZE;
  return conversations.value.slice(start, start + CONVERSATION_PAGE_SIZE);
});

onMounted(async () => {
  const [summaryResult, healthResult, sessionsResult] = await Promise.allSettled([
    fetchQuestionBankSummary(),
    fetchHomeworkHealth(),
    fetchHomeworkSessions(props.profile.studentId),
  ]);
  if (summaryResult.status === "fulfilled") summary.value = summaryResult.value;
  if (healthResult.status === "fulfilled") health.value = healthResult.value;
  if (sessionsResult.status === "fulfilled") {
    conversationSessions.value = sessionsResult.value.sessions;
    memoryWindowCount.value = sessionsResult.value.memory_window_count;
  }
  conversationsLoading.value = false;
  if (conversationSessions.value.length) {
    const selected = conversationSessions.value.some(
      (item) => item.session_id === activeSessionId.value,
    )
      ? activeSessionId.value
      : conversationSessions.value[0].session_id;
    await selectConversation(selected);
  } else {
    startNewConversation();
  }
});
onBeforeUnmount(() => {
  if (imagePreview.value) URL.revokeObjectURL(imagePreview.value);
  releaseSentImages();
});

function welcomeMessage(sessionId: string): ConversationItem {
  return {
    id: `welcome_${sessionId}`,
    role: "assistant",
    title: "问鹿作业辅导",
    text: `你好，${props.profile.studentName}。这是一个独立的作业辅导窗口。当前题目的上下文只保留在这里；我会参考你在其他窗口沉淀的知识点与学习方式，但不会把旧题或旧答案混进来。`,
  };
}

function setConversationMessages(sessionId: string, items: ConversationItem[]) {
  conversationMessages.value = {
    ...conversationMessages.value,
    [sessionId]: items,
  };
}

function ensureConversationMessages(sessionId: string) {
  if (!conversationMessages.value[sessionId]) {
    setConversationMessages(sessionId, [welcomeMessage(sessionId)]);
  }
}

function appendConversation(sessionId: string, item: ConversationItem) {
  ensureConversationMessages(sessionId);
  setConversationMessages(sessionId, [
    ...conversationMessages.value[sessionId],
    item,
  ]);
}

function restoredMessages(homeworkSession: HomeworkSession): ConversationItem[] {
  const items: ConversationItem[] = [welcomeMessage(homeworkSession.session_id)];
  for (const turn of homeworkSession.turns || []) {
    if (turn.student_message.trim()) {
      items.push({
        id: `${turn.turn_id}_student`,
        role: "student",
        title: props.profile.studentName,
        text: turn.student_message,
      });
    }
    const content = turn.student_visible_content || {};
    items.push({
      id: `${turn.turn_id}_assistant`,
      role: "assistant",
      title: actionLabel(turn.assistant_action),
      text: content.acknowledgement || "已完成本轮辅导。",
      guidance: content.guidance,
      question: content.question_to_student,
      warning: content.warning,
    });
  }
  return items;
}

function resetActiveLearningState() {
  session.value = null;
  question.value = null;
  matches.value = [];
  knowledgeSources.value = [];
  messageText.value = "";
  awaitingOcrConfirmation.value = false;
  removePendingImage();
  error.value = "";
  conversationPage.value = 1;
}

function startNewConversation() {
  const current = conversationSessions.value.find(
    (item) => item.session_id === activeSessionId.value,
  );
  if (current?.session_id.startsWith("homework_draft_") && current.message_count === 0) {
    resetActiveLearningState();
    ensureConversationMessages(current.session_id);
    return;
  }
  releaseSentImages();
  const sessionId = createDraftId();
  const now = new Date().toISOString();
  activeSessionId.value = sessionId;
  setConversationMessages(sessionId, [welcomeMessage(sessionId)]);
  conversationSessions.value = [
    {
      session_id: sessionId,
      title: "新对话",
      preview: "从一道新题开始",
      subject: subject.value,
      status: "draft",
      message_count: 0,
      hint_level: 0,
      created_at: now,
      updated_at: now,
    },
    ...conversationSessions.value,
  ];
  resetActiveLearningState();
  void nextTick().then(scrollToLatest);
}

async function selectConversation(sessionId: string) {
  if (
    sessionId === activeSessionId.value
    && session.value
    && conversationMessages.value[sessionId]?.length
  ) return;
  releaseSentImages();
  activeSessionId.value = sessionId;
  resetActiveLearningState();
  ensureConversationMessages(sessionId);
  if (sessionId.startsWith("homework_draft_")) return;
  try {
    const response = await fetchHomeworkSession(sessionId, props.profile.studentId);
    const restored = response.result.session;
    if (!restored) throw new Error("历史对话内容为空");
    session.value = restored;
    question.value = restored.active_question || null;
    if (restored.subject_hint) subject.value = restored.subject_hint;
    if (response._meta?.mode) mode.value = response._meta.mode;
    setConversationMessages(sessionId, restoredMessages(restored));
    await scrollToLatest();
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "历史对话加载失败";
  }
}

async function refreshConversationSessions() {
  try {
    const response = await fetchHomeworkSessions(props.profile.studentId);
    const draft = conversationSessions.value.find(
      (item) => item.session_id === activeSessionId.value && item.session_id.startsWith("homework_draft_"),
    );
    conversationSessions.value = draft ? [draft, ...response.sessions] : response.sessions;
    memoryWindowCount.value = response.memory_window_count;
  } catch {
    // Keep the current window usable when history refresh is temporarily unavailable.
  }
}

function updateConversationSummary(sessionId: string, text: string, assistant = false) {
  const now = new Date().toISOString();
  const current = conversationSessions.value.find((item) => item.session_id === sessionId);
  if (!current) return;
  const firstStudent = (conversationMessages.value[sessionId] || []).find(
    (item) => item.role === "student",
  );
  const titleText = firstStudent?.text.trim() || "新对话";
  const updated: HomeworkConversationSummary = {
    ...current,
    title: titleText.length > 28 ? `${titleText.slice(0, 28)}…` : titleText,
    preview: text.length > 64 ? `${text.slice(0, 64)}…` : text,
    message_count: Math.max(current.message_count + 1, assistant ? 2 : 1),
    updated_at: now,
  };
  conversationSessions.value = [
    updated,
    ...conversationSessions.value.filter((item) => item.session_id !== sessionId),
  ];
}

function formatConversationTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "刚刚";
  const today = new Date();
  if (date.toDateString() === today.toDateString()) {
    return date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
  }
  return date.toLocaleDateString("zh-CN", { month: "numeric", day: "numeric" });
}

function formatNumber(value?: number) {
  return new Intl.NumberFormat("zh-CN").format(value || 0);
}

function actionLabel(action?: string) {
  return ({
    general_response: "普通问答",
    knowledge_explanation: "知识点讲解",
    release_hint: "针对题目的分步反馈",
    check_step: "当前步骤检查",
    knowledge_review: "相关知识回顾",
    answer_verification: "完整作答反馈",
    request_parse_confirmation: "请确认图片识别内容",
    variant_practice: "同类训练",
  } as Record<string, string>)[action || ""] || "辅导反馈";
}

function selectImage(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0] || null;
  if (!file) return;
  if (file.size > 10 * 1024 * 1024) { error.value = "图片不能超过 10MB"; return; }
  if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) {
    error.value = "仅支持 JPG、PNG 或 WebP 图片";
    return;
  }
  if (imagePreview.value) URL.revokeObjectURL(imagePreview.value);
  imageFile.value = file;
  imagePreview.value = URL.createObjectURL(file);
  error.value = "";
}

function removePendingImage() {
  if (imagePreview.value) URL.revokeObjectURL(imagePreview.value);
  imageFile.value = null;
  imagePreview.value = "";
  if (fileInput.value) fileInput.value.value = "";
}

function consumePendingImage() {
  const url = imagePreview.value;
  if (url) sentImageUrls.add(url);
  imageFile.value = null;
  imagePreview.value = "";
  if (fileInput.value) fileInput.value.value = "";
  return url;
}

function releaseSentImages() {
  if (!sentImageUrls.size) return;
  conversations.value = conversations.value.map((item) =>
    item.imageUrl && sentImageUrls.has(item.imageUrl)
      ? { ...item, imageUrl: undefined }
      : item,
  );
  sentImageUrls.forEach((url) => URL.revokeObjectURL(url));
  sentImageUrls.clear();
}

async function scrollToLatest() {
  conversationPage.value = Math.max(
    1,
    Math.ceil(conversations.value.length / CONVERSATION_PAGE_SIZE),
  );
  await nextTick();
  conversationList.value?.scrollIntoView({ block: "nearest", behavior: "smooth" });
}

function addStudentMessage(text: string, imageUrl?: string, sessionId = activeSessionId.value) {
  appendConversation(sessionId, {
    id: "student_" + Date.now() + "_" + (conversationMessages.value[sessionId]?.length || 0),
    role: "student",
    title: imageUrl && text ? "图文题目 / 作答" : imageUrl ? "图片题目" : "文字题目 / 作答",
    text: text || "上传了一张题目图片",
    imageUrl,
  });
  updateConversationSummary(sessionId, text || "上传了一张题目图片");
  void scrollToLatest();
}

function applyResponse(response: HomeworkEnvelope, append = true, sessionId = activeSessionId.value) {
  const isActiveWindow = sessionId === activeSessionId.value;
  if (isActiveWindow && response.result.session) session.value = response.result.session;
  if (isActiveWindow && response.result.question) question.value = response.result.question;
  if (isActiveWindow) {
    matches.value = response.result.question_bank_matches || [];
    knowledgeSources.value = response.result.knowledge_sources || [];
    awaitingOcrConfirmation.value = response.result.tutoring?.action === "request_parse_confirmation";
  }
  if (response._meta?.mode) mode.value = response._meta.mode;
  const content = response.result.tutoring?.student_visible_content;
  if (append && content) {
    appendConversation(sessionId, {
      id: "assistant_" + Date.now() + "_" + (conversationMessages.value[sessionId]?.length || 0),
      role: "assistant",
      title: actionLabel(response.result.tutoring?.action),
      text: content.acknowledgement,
      guidance: content.guidance,
      question: content.question_to_student,
      warning: content.warning,
    });
    updateConversationSummary(sessionId, content.guidance || content.acknowledgement, true);
    if (isActiveWindow && awaitingOcrConfirmation.value && !messageText.value.trim() && content.guidance) {
      messageText.value = content.guidance;
    }
  }
  if (isActiveWindow) void scrollToLatest();
}

async function ensureSession() {
  if (session.value?.session_id === activeSessionId.value) return session.value;
  const draftId = activeSessionId.value;
  const response = await createHomeworkSession(props.profile, subject.value);
  const created = response.result.session;
  if (!created) throw new Error("辅导 Agent 未能创建会话");
  const draftSummary = conversationSessions.value.find((item) => item.session_id === draftId);
  const existingMessages = conversationMessages.value[draftId] || [];
  setConversationMessages(created.session_id, [
    welcomeMessage(created.session_id),
    ...existingMessages.filter((item) => !item.id.startsWith("welcome_")),
  ]);
  const nextMessages = { ...conversationMessages.value };
  delete nextMessages[draftId];
  conversationMessages.value = nextMessages;
  const draftWasStillActive = activeSessionId.value === draftId;
  if (draftWasStillActive) {
    activeSessionId.value = created.session_id;
    session.value = created;
  }
  if (response._meta?.mode) mode.value = response._meta.mode;
  const now = new Date().toISOString();
  conversationSessions.value = [
    {
      session_id: created.session_id,
      title: draftSummary?.title || "新对话",
      preview: draftSummary?.preview || "从一道新题开始",
      subject: created.subject_hint || subject.value,
      status: created.status,
      message_count: draftSummary?.message_count || 0,
      hint_level: created.hint_runtime.current_level,
      created_at: created.created_at || now,
      updated_at: created.updated_at || now,
    },
    ...conversationSessions.value.filter((item) => item.session_id !== draftId),
  ];
  return created;
}

function inferIntent(text: string): TurnIntent {
  if (/提交|完整作答|最终答案/.test(text) && question.value) return "submit_answer";
  if (/检查|对不对|是否正确|这一步/.test(text)) return "check_step";
  if (/知识点|公式|概念|回顾/.test(text)) return "request_knowledge_review";
  return "request_hint";
}

function turnBody(
  intent: HomeworkTurnRequest["intent"],
  text: string,
  active: HomeworkSession,
  attachedImage = imageFile.value,
): HomeworkTurnRequest {
  const firstQuestion = !question.value;
  return {
    sessionId: active.session_id,
    studentId: props.profile.studentId,
    subject: subject.value,
    questionText: firstQuestion ? text : question.value?.stem || "",
    studentWork: firstQuestion ? "" : text,
    message: text || (attachedImage ? "请读取我上传的题目图片并开始辅导" : "请继续辅导"),
    intent,
    image: attachedImage,
  };
}

async function send(intent?: TurnIntent) {
  if (tutorThinking.value) return;
  if (!canSend.value) { error.value = "请输入题目或作答文字，也可以只上传一张题目图片"; return; }
  const text = messageText.value.trim();
  const selectedIntent = intent || inferIntent(text);
  if (selectedIntent === "submit_answer" && !question.value) {
    error.value = "请先发送题目，Agent 读取题目后再提交完整作答";
    return;
  }
  busyAction.value = selectedIntent;
  error.value = "";
  const taskId = beginAiTask({
    studentId: props.profile.studentId,
    channel: "homework-tutor",
    title: "作业辅导 AI 已回复",
    destination: { view: "tutor" },
  });
  const pendingImage = imagePreview.value;
  const pendingImageFile = imageFile.value;
  addStudentMessage(text, pendingImage);
  if (pendingImage) consumePendingImage();
  messageText.value = "";
  try {
    const active = await ensureSession();
    pendingSessionId.value = active.session_id;
    const body = turnBody(
      selectedIntent === "submit_answer" ? "check_step" : selectedIntent,
      text,
      active,
      pendingImageFile,
    );
    const response = selectedIntent === "submit_answer" && question.value
      ? await submitHomeworkAnswer(
          props.profile.studentId,
          question.value.question_id,
          text,
          body,
        )
      : await submitHomeworkTurn(body);
    applyResponse(response, true, active.session_id);
    await refreshConversationSessions();
    completeAiTask(taskId, "你的作业问题已经得到新的辅导回复。");
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "本轮辅导失败，请稍后重试";
    failAiTask(taskId, "作业辅导请求未完成，点击返回查看原因。");
  } finally {
    busyAction.value = "";
    pendingSessionId.value = null;
  }
}

async function confirmOcr() {
  if (tutorThinking.value) return;
  if (!session.value || !messageText.value.trim()) { error.value = "请修正识别文字后再确认"; return; }
  busyAction.value = "confirm_ocr";
  error.value = "";
  const text = messageText.value.trim();
  const requestSessionId = session.value.session_id;
  pendingSessionId.value = requestSessionId;
  const taskId = beginAiTask({
    studentId: props.profile.studentId,
    channel: "homework-tutor",
    title: "作业辅导 AI 已回复",
    destination: { view: "tutor" },
  });
  try {
    addStudentMessage(text, undefined, requestSessionId);
    const response = await confirmHomeworkOcr(
      requestSessionId,
      props.profile.studentId,
      subject.value,
      text,
      "",
    );
    applyResponse(response, true, requestSessionId);
    await refreshConversationSessions();
    messageText.value = "";
    completeAiTask(taskId, "题目识别已经确认，辅导回复已更新。");
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "题目确认失败";
    failAiTask(taskId, "题目确认未完成，点击返回查看原因。");
  } finally {
    busyAction.value = "";
    pendingSessionId.value = null;
  }
}

async function requestVariant() {
  if (tutorThinking.value) return;
  if (!question.value || !session.value) { error.value = "请先发送并完成当前题目的读取"; return; }
  busyAction.value = "variant";
  const requestSessionId = session.value.session_id;
  pendingSessionId.value = requestSessionId;
  const taskId = beginAiTask({
    studentId: props.profile.studentId,
    channel: "homework-tutor",
    title: "作业辅导 AI 已回复",
    destination: { view: "tutor" },
  });
  try {
    addStudentMessage("请给我一道同知识点、相近难度的训练题", undefined, requestSessionId);
    const response = await requestHomeworkVariant(
      props.profile.studentId,
      question.value.question_id,
      turnBody("request_next_hint", "请求同类训练", session.value),
    );
    applyResponse(response, true, requestSessionId);
    await refreshConversationSessions();
    completeAiTask(taskId, "同知识点训练题已经准备完成。");
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "同类训练获取失败";
    failAiTask(taskId, "同类训练获取失败，点击返回查看原因。");
  } finally {
    busyAction.value = "";
    pendingSessionId.value = null;
  }
}
</script>

<template>
  <div class="tutor-page">
    <section class="tutor-hero student-module-hero">
      <div><span class="tutor-eyebrow"><Sparkles :size="15" /> 作业辅导 Agent</span><h1>把题目发进对话，和 Agent 一起做出来。</h1><p>支持纯文字、纯图片或图文组合。每次消息都会重新理解题目、当前步骤与提问，并实时刷新 5·3 题库依据。</p></div>
      <div class="corpus-card"><Database :size="23" /><div><strong>{{ formatNumber(summary?.total_files || 7577) }}</strong><small>题库资源</small></div><div><strong>{{ formatNumber(exerciseCount) }}</strong><small>练习资源</small></div><div><strong>{{ formatNumber(secureCount) }}</strong><small>隔离答案/解析</small></div></div>
    </section>

    <div class="tutor-conversation-shell">
      <aside :class="[`tutor-session-panel`, { open: historyOpen }]" aria-label="作业辅导对话历史">
        <header class="session-panel-header">
          <div><span><History :size="18" /></span><div><strong>辅导对话</strong><small>历史记录自动保留</small></div></div>
          <button type="button" @click="historyOpen = !historyOpen">{{ historyOpen ? "收起" : "展开" }}</button>
        </header>
        <button class="tutor-new-session" type="button" @click="startNewConversation">
          <MessageSquarePlus :size="18" />
          <span><strong>新对话</strong><small>打开独立辅导窗口</small></span>
        </button>
        <div class="tutor-session-list">
          <div v-if="conversationsLoading" class="session-list-state"><LoaderCircle class="spin" :size="17" />正在读取对话记录</div>
          <div v-else-if="!conversationSessions.length" class="session-list-state">暂无历史对话</div>
          <button
            v-for="item in conversationSessions"
            :key="item.session_id"
            type="button"
            :class="{ active: item.session_id === activeSessionId }"
            @click="selectConversation(item.session_id)"
          >
            <span class="session-item-heading">
              <strong>{{ item.title }}</strong>
              <i v-if="pendingSessionId === item.session_id" title="问鹿AI 正在思考" />
            </span>
            <span class="session-preview">{{ item.preview }}</span>
            <span class="session-meta">
              <em>{{ item.subject ? subjectLabels[item.subject] : "综合辅导" }}</em>
              <small>{{ item.message_count }} 条消息 · {{ formatConversationTime(item.updated_at) }}</small>
            </span>
          </button>
        </div>
        <footer class="session-memory-note">
          <BrainCircuit :size="17" />
          <span><strong>跨对话学习记忆</strong><small>已关联 {{ memoryWindowCount }} 个有效窗口，仅复用知识点与学习方式</small></span>
        </footer>
      </aside>

      <section class="tutor-chat">
        <header class="chat-header">
          <div><span><MessageCircleQuestion :size="21" /></span><div><h2>全科图文作业辅导</h2></div></div>
          <div class="chat-controls">
            <button title="打开一个新的作业辅导对话" @click="startNewConversation"><MessageSquarePlus :size="16" />新对话</button>
          </div>
        </header>

      <div ref="conversationList" class="conversation-list">
        <div v-if="!conversations.length" class="chat-empty">
          <span><BookOpenText :size="32" /></span><h3>直接在下方发送你的题目</h3><p>可以只输入文字、只上传图片，也可以同时附上图片和补充说明。发送后，上传内容会完整显示在对话中。</p>
          <div><span><Camera :size="15" />题目拍照识别</span><span><BrainCircuit :size="15" />内容感知反馈</span><span><ShieldCheck :size="15" />答案安全校验</span></div>
        </div>

        <article v-for="item in pagedConversations" :key="item.id" :class="['conversation', item.role]">
          <span class="avatar"><MessageCircleQuestion v-if="item.role === 'assistant'" :size="18" /><b v-else>{{ profile.studentName.slice(0, 1) }}</b></span>
          <div class="bubble"><small>{{ item.role === 'assistant' ? item.title : profile.studentName }}</small><img v-if="item.imageUrl" :src="item.imageUrl" alt="用户上传的题目图片" /><p>{{ item.text }}</p><div v-if="item.guidance" class="guidance"><Lightbulb :size="16" /><span>{{ item.guidance }}</span></div><div v-if="item.question" class="follow-question"><Target :size="14" />{{ item.question }}</div><div v-if="item.warning" class="safety-note"><ShieldCheck :size="14" />{{ item.warning }}</div></div>
        </article>
        <article v-if="tutorThinking && pendingSessionId === activeSessionId" class="conversation assistant thinking-message">
          <span class="avatar"><LoaderCircle class="spin" :size="18" /></span>
          <div class="bubble"><small>问鹿AI</small><p>正在理解题目与当前步骤，请稍候……</p></div>
        </article>
        <PaginationControls :page="conversationPage" :total="conversations.length" :page-size="CONVERSATION_PAGE_SIZE" label="条消息" @change="conversationPage=$event" />

        <section v-if="knowledgeSources.length" class="evidence-strip knowledge-evidence">
          <div class="evidence-title"><div><BookOpenText :size="17" /><span><strong>本轮课程知识依据</strong><small>{{ knowledgeSources.length }} 条 · 课程标准 / 知识分类 / 教材目录</small></span></div><span><ShieldCheck :size="13" />只读安全来源</span></div>
          <div class="knowledge-source-list"><article v-for="source in knowledgeSources.slice(0, 4)" :key="source.source_id"><span>{{ source.authority_level }}级</span><div><strong>{{ source.title }}</strong><small>{{ source.document_type }}<template v-if="source.page_start"> · 第 {{ source.page_start }} 页</template></small><p>{{ source.summary }}</p></div></article></div>
        </section>

        <section v-if="matches.length" class="evidence-strip">
          <div class="evidence-title"><div><Database :size="17" /><span><strong>随本轮输入实时更新的题库依据</strong><small>{{ matches.length }} 条匹配 · 仅展示安全元数据</small></span></div><span><ShieldCheck :size="13" />答案未暴露</span></div>
          <div class="evidence-list"><article v-for="match in matches.slice(0, 4)" :key="match.source_id"><span>{{ match.edition }}版</span><div><strong>{{ match.topic || match.title }}</strong><small>{{ match.region }} · {{ match.file_type.toUpperCase() }} · {{ Math.round(match.confidence * 100) }}%</small></div></article></div>
        </section>
      </div>

      <div v-if="health && health.homework_generation_mode !== 'llm'" class="model-offline-note"><CircleAlert :size="15" />作业辅导大模型尚未连接。当前不会使用规则模板代替回答，请先配置模型 API 后再发送。</div>
            <div v-if="mode === 'demo'" class="demo-note"><CircleAlert :size="15" />线上站点使用内容感知演示推理；服务器页面连接真实 LangGraph、OCR 与本地题库索引。</div>
      <div v-if="error" class="error-note"><CircleAlert :size="16" />{{ error }}</div>

      <footer class="chat-composer">
        <div v-if="imagePreview" class="pending-image"><img :src="imagePreview" alt="待发送图片" /><div><Paperclip :size="15" /><span><strong>{{ imageFile?.name }}</strong><small>图片会随本条消息一起发送</small></span></div><button aria-label="移除图片" @click="removePendingImage"><X :size="16" /></button></div>
        <div class="compose-main"><button class="attach-button" title="上传题目图片" @click="fileInput?.click()"><Camera :size="20" /></button><input ref="fileInput" type="file" accept="image/jpeg,image/png,image/webp" @change="selectImage" /><textarea v-model="messageText" rows="3" placeholder="输入题目、你的步骤或具体疑问；也可以只上传图片……" @keydown.ctrl.enter="send()" /><button class="send-button" :disabled="!canSend || Boolean(busyAction) || tutorThinking" @click="send()"><LoaderCircle v-if="busyAction || tutorThinking" class="spin" :size="19" /><Send v-else :size="19" /><span>{{ tutorThinking ? "思考中" : "发送" }}</span></button></div>
        <div class="quick-actions">
          <span>本轮希望 Agent：</span><button :disabled="Boolean(busyAction) || tutorThinking" @click="send('request_hint')"><Lightbulb :size="14" />给出提示</button><button :disabled="Boolean(busyAction) || tutorThinking" @click="send('check_step')"><CheckCircle2 :size="14" />检查步骤</button><button :disabled="Boolean(busyAction) || tutorThinking" @click="send('request_knowledge_review')"><BrainCircuit :size="14" />回顾知识</button><button :disabled="Boolean(busyAction) || tutorThinking || !question" @click="send('submit_answer')"><ShieldCheck :size="14" />提交完整作答</button><button :disabled="Boolean(busyAction) || tutorThinking || !question" @click="requestVariant"><Target :size="14" />同类训练</button>
        </div>
        <div v-if="awaitingOcrConfirmation" class="ocr-confirm"><CircleAlert :size="16" /><span>请修改输入框中的识别文字，确认无误后继续。</span><button @click="confirmOcr">确认识别内容</button></div>
        <small>Ctrl + Enter 发送 · 图片仅在本轮内存处理 · 题库依据会随每次输入重新检索</small>
      </footer>
      </section>
    </div>
  </div>
</template>

<style scoped>
.tutor-page{display:grid;gap:16px;color:#263b5d}.tutor-hero{position:relative;display:flex;min-height:190px;align-items:center;justify-content:space-between;overflow:hidden;padding:31px 36px;color:#fff;background:linear-gradient(135deg,#0d3578,#155eef 65%,#4b91ff);border-radius:18px;box-shadow:0 20px 40px rgba(21,94,239,.17)}.tutor-hero:after{position:absolute;top:-150px;right:-30px;width:340px;height:340px;content:"";border:1px solid rgba(255,255,255,.17);border-radius:50%;box-shadow:0 0 0 48px rgba(255,255,255,.045)}.tutor-hero>div:first-child{position:relative;z-index:1;max-width:760px}.tutor-eyebrow{display:inline-flex;align-items:center;gap:6px;color:#d5e5ff;font-size:10px;font-weight:800}.tutor-hero h1{margin:14px 0 8px;font-size:clamp(25px,3vw,38px);letter-spacing:-.04em}.tutor-hero p{margin:0;color:rgba(255,255,255,.75);font-size:11px;line-height:1.8}.corpus-card{position:relative;z-index:1;display:grid;grid-template-columns:auto repeat(3,auto);gap:20px;align-items:center;padding:18px 21px;border:1px solid rgba(255,255,255,.2);background:rgba(255,255,255,.09);border-radius:14px}.corpus-card div{display:flex;flex-direction:column;gap:3px}.corpus-card strong{font-size:15px}.corpus-card small{color:rgba(255,255,255,.6);font-size:8px}
.tutor-chat{overflow:hidden;border:1px solid #dce5f2;background:#fff;border-radius:16px;box-shadow:0 9px 28px rgba(28,64,118,.07)}.chat-header{display:flex;min-height:76px;align-items:center;justify-content:space-between;gap:18px;padding:13px 22px;border-bottom:1px solid #e7edf6;background:#fbfdff}.chat-header>div:first-child{display:flex;align-items:center;gap:10px}.chat-header>div:first-child>span{display:grid;width:40px;height:40px;place-items:center;color:#fff;background:linear-gradient(135deg,#0e3f91,#2474ff);border-radius:11px}.chat-header h2{margin:0 0 4px;color:#18365f;font-size:15px}.chat-header small{display:flex;align-items:center;gap:5px;color:#8294ad;font-size:8px}.chat-header small i{width:6px;height:6px;background:#2bb381;border-radius:50%}.chat-header small i.offline{background:#e68a2e}.chat-controls{display:flex;gap:7px}.chat-controls select,.chat-controls button{height:35px;padding:0 10px;color:#526b8a;border:1px solid #d8e2ef;background:#fff;border-radius:8px;font-size:9px}.chat-controls button{display:inline-flex;align-items:center;gap:5px}.conversation-list{display:grid;align-content:start;gap:20px;min-height:410px;max-height:620px;overflow:auto;padding:25px;background:linear-gradient(180deg,#fff,#fbfdff)}.chat-empty{display:flex;min-height:360px;align-items:center;justify-content:center;flex-direction:column;text-align:center}.chat-empty>span{display:grid;width:72px;height:72px;place-items:center;color:#155eef;background:#eaf2ff;border-radius:21px}.chat-empty h3{margin:18px 0 8px;color:#274668;font-size:16px}.chat-empty p{max-width:560px;margin:0;color:#7b8da6;font-size:10px;line-height:1.8}.chat-empty>div{display:flex;flex-wrap:wrap;gap:8px;margin-top:18px}.chat-empty>div span{display:inline-flex;align-items:center;gap:5px;padding:7px 10px;color:#55708f;background:#f1f6fd;border-radius:7px;font-size:8px}.conversation{display:flex;gap:10px;max-width:min(86%,820px)}.conversation.student{justify-self:end;flex-direction:row-reverse}.avatar{display:grid;width:35px;height:35px;flex:0 0 auto;place-items:center;color:#155eef;background:#e9f2ff;border-radius:10px;font-size:10px}.conversation.student .avatar{color:#fff;background:#1c5ec8}.bubble{min-width:160px;padding:13px 15px;border:1px solid #dfe8f4;background:#fff;border-radius:4px 13px 13px;box-shadow:0 4px 13px rgba(31,65,112,.045)}.conversation.student .bubble{color:#fff;border:0;background:#155eef;border-radius:13px 4px 13px 13px}.bubble>small{color:#6e88aa;font-size:8px;font-weight:750}.conversation.student .bubble>small{color:rgba(255,255,255,.67)}.bubble>img{display:block;max-width:min(100%,420px);max-height:330px;margin:9px 0;object-fit:contain;background:#eef3f9;border-radius:9px}.bubble>p{margin:7px 0 0;color:#324d70;font-size:10px;line-height:1.7;white-space:pre-wrap}.conversation.student .bubble>p{color:#fff}.guidance{display:flex;align-items:flex-start;gap:7px;margin-top:10px;padding:10px;color:#265591;background:#edf5ff;border-radius:8px;font-size:10px;line-height:1.65}.guidance svg{flex:0 0 auto;color:#155eef}.follow-question,.safety-note{display:flex;align-items:flex-start;gap:6px;margin-top:9px;color:#334f73;font-size:9px;line-height:1.5}.safety-note{color:#788ba4;font-size:8px}
.evidence-strip{padding:14px;border:1px solid #d9e6f7;background:#f5f9ff;border-radius:11px}.evidence-title{display:flex;align-items:center;justify-content:space-between}.evidence-title>div{display:flex;align-items:center;gap:8px;color:#155eef}.evidence-title>div span{display:flex;flex-direction:column;gap:2px}.evidence-title strong{color:#345277;font-size:10px}.evidence-title small{color:#8a9ab0;font-size:8px}.evidence-title>span{display:inline-flex;align-items:center;gap:4px;color:#278764;font-size:8px}.evidence-list{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:11px}.evidence-list article{display:flex;min-width:0;gap:7px;padding:9px;border:1px solid #e1e8f2;background:#fff;border-radius:8px}.evidence-list article>span{height:max-content;padding:4px 6px;color:#155eef;background:#eaf2ff;border-radius:5px;font-size:7px;font-weight:800}.evidence-list article div{display:flex;min-width:0;flex-direction:column;gap:4px}.evidence-list strong{overflow:hidden;color:#3b5271;font-size:8px;text-overflow:ellipsis;white-space:nowrap}.evidence-list small{color:#8a9ab0;font-size:7px}.knowledge-evidence{background:#f8fbff}.knowledge-source-list{display:grid;grid-template-columns:repeat(2,1fr);gap:8px;margin-top:11px}.knowledge-source-list article{display:flex;min-width:0;gap:8px;padding:10px;border:1px solid #e1e8f2;background:#fff;border-radius:8px}.knowledge-source-list article>span{height:max-content;padding:4px 6px;color:#28745a;background:#eaf8f1;border-radius:5px;font-size:7px;font-weight:800}.knowledge-source-list article div{min-width:0}.knowledge-source-list strong{display:block;overflow:hidden;color:#3b5271;font-size:9px;text-overflow:ellipsis;white-space:nowrap}.knowledge-source-list small{color:#8a9ab0;font-size:7px}.knowledge-source-list p{display:-webkit-box;overflow:hidden;margin:5px 0 0;color:#657b97;font-size:8px;line-height:1.5;-webkit-box-orient:vertical;-webkit-line-clamp:2}.demo-note,.error-note,.model-offline-note{display:flex;align-items:center;gap:7px;margin:0 22px 11px;padding:9px 11px;border-radius:8px;font-size:8px}.demo-note{color:#76551e;background:#fff8e9}.model-offline-note{color:#9a5b13;background:#fff4df}.error-note{color:#b42318;background:#fff0ef}
.chat-composer{padding:16px 22px 18px;border-top:1px solid #e7edf6;background:#f8fbff}.pending-image{display:flex;max-width:470px;align-items:center;gap:10px;margin-bottom:10px;padding:8px;border:1px solid #cfe0f6;background:#fff;border-radius:10px}.pending-image img{width:62px;height:55px;object-fit:cover;border-radius:7px}.pending-image>div{display:flex;min-width:0;flex:1;align-items:center;gap:7px;color:#155eef}.pending-image>div span{display:flex;min-width:0;flex-direction:column;gap:3px}.pending-image strong{overflow:hidden;color:#405b7d;font-size:9px;text-overflow:ellipsis;white-space:nowrap}.pending-image small{color:#8798af;font-size:7px}.pending-image button{display:grid;width:27px;height:27px;place-items:center;color:#6d8099;border:0;background:#eef3f9;border-radius:7px}.compose-main{display:grid;grid-template-columns:42px 1fr auto;gap:8px;align-items:end}.compose-main>input{display:none}.attach-button{display:grid;width:42px;height:42px;place-items:center;color:#155eef;border:1px solid #cbdcf3;background:#fff;border-radius:10px}.compose-main textarea{width:100%;min-height:72px;padding:11px 13px;color:#263b5d;border:1px solid #cedbec;outline:none;background:#fff;border-radius:10px;font:inherit;font-size:10px;line-height:1.65;resize:none}.compose-main textarea:focus{border-color:#6ba1ff;box-shadow:0 0 0 3px rgba(21,94,239,.08)}.send-button{display:flex;min-width:88px;height:42px;align-items:center;justify-content:center;gap:6px;color:#fff;border:0;background:#155eef;border-radius:10px;font-size:10px;font-weight:750}.quick-actions{display:flex;flex-wrap:wrap;align-items:center;gap:6px;margin-top:9px}.quick-actions>span{color:#8090a6;font-size:8px}.quick-actions button{display:inline-flex;height:29px;align-items:center;gap:4px;padding:0 8px;color:#4f6988;border:1px solid #d5e0ee;background:#fff;border-radius:7px;font-size:8px}.quick-actions button:hover{color:#155eef;border-color:#9dc0fb}.ocr-confirm{display:flex;align-items:center;gap:7px;margin-top:10px;padding:9px 10px;color:#77521c;background:#fff5dc;border-radius:8px;font-size:8px}.ocr-confirm span{flex:1}.ocr-confirm button{padding:6px 8px;color:#fff;border:0;background:#a46a0b;border-radius:6px;font-size:8px}.chat-composer>small{display:block;margin-top:9px;color:#8c9caf;font-size:7px}.spin{animation:spin 1s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}
@media(max-width:1180px){.corpus-card{display:none}.evidence-list{grid-template-columns:repeat(2,1fr)}}@media(max-width:820px){.knowledge-source-list{grid-template-columns:1fr}.tutor-hero{padding:27px 23px}.chat-header{align-items:flex-start;flex-direction:column}.chat-controls{width:100%;flex-wrap:wrap}.chat-controls select{flex:1}.conversation-list{max-height:none;padding:18px}.conversation{max-width:96%}.evidence-list{grid-template-columns:1fr}.compose-main{grid-template-columns:40px 1fr}.send-button{grid-column:2;width:100%}}@media(max-width:560px){.tutor-hero h1{font-size:27px}.conversation{max-width:100%}.bubble>img{max-height:240px}.quick-actions>span{width:100%}.quick-actions button{flex:1}.demo-note,.error-note{margin-inline:14px}.chat-composer{padding-inline:14px}}
/* Readable chat typography and paged messages without an inner scrollbar. */
.tutor-page{font-size:15px;line-height:1.55}.tutor-eyebrow{font-size:13px}.tutor-hero p{font-size:15px}.corpus-card small{font-size:12px}.chat-header h2{font-size:19px}.chat-header small{font-size:12px}.chat-controls select,.chat-controls button{height:44px;font-size:14px}
.conversation-list{min-height:410px;max-height:none;overflow:visible}.chat-empty p{font-size:14px}.chat-empty>div span{font-size:13px}.bubble>small{font-size:12px}.bubble>p,.guidance{font-size:15px}.follow-question,.safety-note{font-size:13px}.evidence-title strong,.knowledge-source-list strong{font-size:14px}.evidence-title small,.evidence-title>span,.evidence-list small,.knowledge-source-list small{font-size:12px}.evidence-list strong,.knowledge-source-list p{font-size:13px}.evidence-list article>span,.knowledge-source-list article>span{font-size:11px}
.demo-note,.error-note,.model-offline-note{font-size:13px}.compose-main textarea{min-height:88px;font-size:15px}.send-button{height:48px;font-size:14px}.quick-actions>span,.quick-actions button,.ocr-confirm,.ocr-confirm button{font-size:13px}.quick-actions button{height:38px}.chat-composer>small,.pending-image small{font-size:12px}.pending-image strong{font-size:14px}
.tutor-conversation-shell{display:grid;grid-template-columns:minmax(250px,286px) minmax(0,1fr);gap:16px;align-items:start}
.tutor-session-panel{position:sticky;top:16px;display:flex;min-width:0;max-height:760px;overflow:hidden;flex-direction:column;border:1px solid #dce5f2;background:#fff;border-radius:16px;box-shadow:0 9px 28px rgba(28,64,118,.07)}
.session-panel-header{display:flex;min-height:76px;align-items:center;justify-content:space-between;gap:8px;padding:13px 14px;border-bottom:1px solid #e7edf6;background:#fbfdff}.session-panel-header>div{display:flex;min-width:0;align-items:center;gap:9px}.session-panel-header>div>span{display:grid;width:36px;height:36px;flex:0 0 auto;place-items:center;color:#155eef;background:#eaf2ff;border-radius:10px}.session-panel-header>div>div,.tutor-new-session span,.session-memory-note span{display:flex;min-width:0;flex-direction:column;gap:2px}.session-panel-header strong{color:#18365f;font-size:15px}.session-panel-header small{color:#8798af;font-size:12px}.session-panel-header>button{display:none;padding:5px 7px;color:#56708f;border:0;background:#eef4fb;border-radius:6px;font-size:12px}
.tutor-new-session{display:flex;align-items:center;gap:9px;margin:12px;padding:11px 12px;color:#fff;border:0;background:linear-gradient(135deg,#0f4db2,#2474ff);border-radius:10px;text-align:left;box-shadow:0 7px 18px rgba(21,94,239,.2)}.tutor-new-session svg{flex:0 0 auto}.tutor-new-session strong{font-size:14px}.tutor-new-session small{color:rgba(255,255,255,.72);font-size:11px}
.tutor-session-list{display:grid;gap:7px;min-height:160px;overflow:auto;padding:0 9px 10px}.tutor-session-list>button{display:flex;min-width:0;flex-direction:column;gap:6px;padding:11px;color:#526b8a;border:1px solid transparent;background:transparent;border-radius:10px;text-align:left;transition:background .16s ease,border-color .16s ease,transform .16s ease}.tutor-session-list>button:hover{border-color:#d9e6f7;background:#f7faff;transform:translateY(-1px)}.tutor-session-list>button.active{border-color:#b8d2fb;background:#edf5ff;box-shadow:inset 3px 0 #155eef}.session-item-heading,.session-meta{display:flex;width:100%;min-width:0;align-items:center;justify-content:space-between;gap:8px}.session-item-heading strong{overflow:hidden;color:#294766;font-size:13px;text-overflow:ellipsis;white-space:nowrap}.session-item-heading i{width:7px;height:7px;flex:0 0 auto;background:#2d7af0;border-radius:50%;box-shadow:0 0 0 4px rgba(45,122,240,.12);animation:pulse 1.4s ease-in-out infinite}.session-preview{display:-webkit-box;overflow:hidden;color:#7589a3;font-size:12px;line-height:1.5;-webkit-box-orient:vertical;-webkit-line-clamp:2}.session-meta em{padding:3px 6px;color:#155eef;background:#e5efff;border-radius:5px;font-size:10px;font-style:normal;font-weight:700}.session-meta small{color:#94a2b5;font-size:10px}.session-list-state{display:flex;min-height:120px;align-items:center;justify-content:center;gap:7px;color:#8496ad;font-size:12px;text-align:center}
.session-memory-note{display:flex;align-items:flex-start;gap:8px;margin-top:auto;padding:12px 13px;color:#315d95;border-top:1px solid #e8eef6;background:#f5f9ff}.session-memory-note svg{flex:0 0 auto;margin-top:2px}.session-memory-note strong{font-size:12px}.session-memory-note small{color:#758ba7;font-size:10px;line-height:1.5}.tutor-chat{min-width:0}.thinking-message .bubble{border-color:#cfe0fa;background:#f7fbff}
@keyframes pulse{50%{opacity:.45;transform:scale(.82)}}
@media(max-width:900px){.tutor-conversation-shell{grid-template-columns:1fr}.tutor-session-panel{position:static;max-height:none}.session-panel-header>button{display:block}.tutor-session-panel:not(.open) .tutor-new-session,.tutor-session-panel:not(.open) .tutor-session-list,.tutor-session-panel:not(.open) .session-memory-note{display:none}.tutor-session-list{max-height:330px}.session-memory-note{margin-top:0}}
@media(max-width:560px){.tutor-conversation-shell{gap:12px}.session-panel-header{min-height:64px}.chat-controls button{width:100%;justify-content:center}.session-meta{align-items:flex-start;flex-direction:column}}
</style>
