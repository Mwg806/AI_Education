<script setup lang="ts">
import {
  BookOpenText,
  BrainCircuit,
  Camera,
  CheckCircle2,
  CircleAlert,
  Database,
  Lightbulb,
  LoaderCircle,
  MessageCircleQuestion,
  Paperclip,
  RefreshCw,
  Send,
  ShieldCheck,
  Sparkles,
  Target,
  X,
} from "@lucide/vue";
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from "vue";

import PaginationControls from "@/components/PaginationControls.vue";
import {
  confirmHomeworkOcr,
  createHomeworkSession,
  fetchHomeworkHealth,
  fetchQuestionBankSummary,
  requestHomeworkVariant,
  submitHomeworkAnswer,
  submitHomeworkTurn,
  type HomeworkTurnRequest,
} from "@/lib/homework-client";
import type {
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
const session = ref<HomeworkSession | null>(null);
const question = ref<HomeworkQuestion | null>(null);
const matches = ref<QuestionBankMatch[]>([]);
const knowledgeSources = ref<HomeworkKnowledgeSource[]>([]);
const summary = ref<QuestionBankSummary | null>(null);
const health = ref<HomeworkHealth | null>(null);
const conversations = ref<ConversationItem[]>([]);
const conversationPage = ref(1);
const CONVERSATION_PAGE_SIZE = 6;
const busyAction = ref("");
const error = ref("");
const mode = ref<"live" | "demo">("live");
const awaitingOcrConfirmation = ref(false);

const canSend = computed(() => Boolean(messageText.value.trim() || imageFile.value));
const currentHintLevel = computed(() => session.value?.hint_runtime.current_level || 0);
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
  const [summaryResult, healthResult] = await Promise.allSettled([
    fetchQuestionBankSummary(),
    fetchHomeworkHealth(),
  ]);
  if (summaryResult.status === "fulfilled") summary.value = summaryResult.value;
  if (healthResult.status === "fulfilled") health.value = healthResult.value;
});
onBeforeUnmount(() => {
  if (imagePreview.value) URL.revokeObjectURL(imagePreview.value);
  sentImageUrls.forEach((url) => URL.revokeObjectURL(url));
});

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

async function scrollToLatest() {
  conversationPage.value = Math.max(
    1,
    Math.ceil(conversations.value.length / CONVERSATION_PAGE_SIZE),
  );
  await nextTick();
  conversationList.value?.scrollIntoView({ block: "nearest", behavior: "smooth" });
}

function addStudentMessage(text: string, imageUrl?: string) {
  conversations.value.push({
    id: `student_${Date.now()}_${conversations.value.length}`,
    role: "student",
    title: imageUrl && text ? "图文题目 / 作答" : imageUrl ? "图片题目" : "文字题目 / 作答",
    text: text || "上传了一张题目图片",
    imageUrl,
  });
  void scrollToLatest();
}

function applyResponse(response: HomeworkEnvelope, append = true) {
  if (response.result.session) session.value = response.result.session;
  if (response.result.question) question.value = response.result.question;
  matches.value = response.result.question_bank_matches || [];
  knowledgeSources.value = response.result.knowledge_sources || [];
  if (response._meta?.mode) mode.value = response._meta.mode;
  awaitingOcrConfirmation.value = response.result.tutoring?.action === "request_parse_confirmation";
  const content = response.result.tutoring?.student_visible_content;
  if (append && content) {
    conversations.value.push({
      id: `assistant_${Date.now()}_${conversations.value.length}`,
      role: "assistant",
      title: actionLabel(response.result.tutoring?.action),
      text: content.acknowledgement,
      guidance: content.guidance,
      question: content.question_to_student,
      warning: content.warning,
    });
    if (awaitingOcrConfirmation.value && !messageText.value.trim() && content.guidance) {
      messageText.value = content.guidance;
    }
  }
  void scrollToLatest();
}

async function ensureSession() {
  if (session.value) return session.value;
  const response = await createHomeworkSession(props.profile, subject.value);
  applyResponse(response, false);
  if (!response.result.session) throw new Error("辅导 Agent 未能创建会话");
  return response.result.session;
}

function inferIntent(text: string): TurnIntent {
  if (/提交|完整作答|最终答案/.test(text) && question.value) return "submit_answer";
  if (/检查|对不对|是否正确|这一步/.test(text)) return "check_step";
  if (/知识点|公式|概念|回顾/.test(text)) return "request_knowledge_review";
  return "request_hint";
}

function turnBody(intent: HomeworkTurnRequest["intent"], text: string, active: HomeworkSession): HomeworkTurnRequest {
  const firstQuestion = !question.value;
  return {
    sessionId: active.session_id,
    studentId: props.profile.studentId,
    subject: subject.value,
    questionText: firstQuestion ? text : question.value?.stem || "",
    studentWork: firstQuestion ? "" : text,
    message: text || (imageFile.value ? "请读取我上传的题目图片并开始辅导" : "请继续辅导"),
    intent,
    image: imageFile.value,
  };
}

async function send(intent?: TurnIntent) {
  if (!canSend.value) { error.value = "请输入题目或作答文字，也可以只上传一张题目图片"; return; }
  const text = messageText.value.trim();
  const selectedIntent = intent || inferIntent(text);
  if (selectedIntent === "submit_answer" && !question.value) {
    error.value = "请先发送题目，Agent 读取题目后再提交完整作答";
    return;
  }
  busyAction.value = selectedIntent;
  error.value = "";
  try {
    const active = await ensureSession();
    const body = turnBody(
      selectedIntent === "submit_answer" ? "check_step" : selectedIntent,
      text,
      active,
    );
    const pendingImage = imagePreview.value;
    const response = selectedIntent === "submit_answer" && question.value
      ? await submitHomeworkAnswer(
          props.profile.studentId,
          question.value.question_id,
          text,
          body,
        )
      : await submitHomeworkTurn(body);
    const sentImage = pendingImage ? consumePendingImage() : "";
    addStudentMessage(text, sentImage);
    messageText.value = "";
    applyResponse(response);
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "本轮辅导失败，请稍后重试";
  } finally { busyAction.value = ""; }
}

async function confirmOcr() {
  if (!session.value || !messageText.value.trim()) { error.value = "请修正识别文字后再确认"; return; }
  busyAction.value = "confirm_ocr";
  error.value = "";
  const text = messageText.value.trim();
  try {
    addStudentMessage(text);
    applyResponse(await confirmHomeworkOcr(
      session.value.session_id,
      props.profile.studentId,
      subject.value,
      text,
      "",
    ));
    messageText.value = "";
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "题目确认失败";
  } finally { busyAction.value = ""; }
}

async function requestVariant() {
  if (!question.value || !session.value) { error.value = "请先发送并完成当前题目的读取"; return; }
  busyAction.value = "variant";
  try {
    addStudentMessage("请给我一道同知识点、相近难度的训练题");
    applyResponse(await requestHomeworkVariant(
      props.profile.studentId,
      question.value.question_id,
      turnBody("request_next_hint", "请求同类训练", session.value),
    ));
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "同类训练获取失败";
  } finally { busyAction.value = ""; }
}

function newQuestion() {
  session.value = null;
  question.value = null;
  matches.value = [];
  knowledgeSources.value = [];
  conversations.value = [];
  conversationPage.value = 1;
  messageText.value = "";
  awaitingOcrConfirmation.value = false;
  removePendingImage();
  sentImageUrls.forEach((url) => URL.revokeObjectURL(url));
  sentImageUrls.clear();
  error.value = "";
}
</script>

<template>
  <div class="tutor-page">
    <section class="tutor-hero student-module-hero">
      <div><span class="tutor-eyebrow"><Sparkles :size="15" /> 作业辅导 Agent</span><h1>把题目发进对话，和 Agent 一起做出来。</h1><p>支持纯文字、纯图片或图文组合。每次消息都会重新理解题目、当前步骤与提问，并实时刷新 5·3 题库依据。</p></div>
      <div class="corpus-card"><Database :size="23" /><div><strong>{{ formatNumber(summary?.total_files || 7577) }}</strong><small>题库资源</small></div><div><strong>{{ formatNumber(exerciseCount) }}</strong><small>练习资源</small></div><div><strong>{{ formatNumber(secureCount) }}</strong><small>隔离答案/解析</small></div></div>
    </section>

    <section class="tutor-chat">
      <header class="chat-header">
        <div><span><MessageCircleQuestion :size="21" /></span><div><h2>全科图文作业辅导</h2><small><i :class="{ offline: health?.homework_generation_mode !== 'llm' }" /> {{ health?.homework_generation_mode === "llm" ? `大模型在线 · ${health.llm_model}` : "大模型未连接" }} · 提示层级 L{{ currentHintLevel }}</small></div></div>
        <div class="chat-controls">
          <button title="开始新题" @click="newQuestion"><RefreshCw :size="16" />新题</button>
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
        <div class="compose-main"><button class="attach-button" title="上传题目图片" @click="fileInput?.click()"><Camera :size="20" /></button><input ref="fileInput" type="file" accept="image/jpeg,image/png,image/webp" @change="selectImage" /><textarea v-model="messageText" rows="3" placeholder="输入题目、你的步骤或具体疑问；也可以只上传图片……" @keydown.ctrl.enter="send()" /><button class="send-button" :disabled="!canSend || Boolean(busyAction)" @click="send()"><LoaderCircle v-if="busyAction" class="spin" :size="19" /><Send v-else :size="19" /><span>发送</span></button></div>
        <div class="quick-actions">
          <span>本轮希望 Agent：</span><button :disabled="Boolean(busyAction)" @click="send('request_hint')"><Lightbulb :size="14" />给出提示</button><button :disabled="Boolean(busyAction)" @click="send('check_step')"><CheckCircle2 :size="14" />检查步骤</button><button :disabled="Boolean(busyAction)" @click="send('request_knowledge_review')"><BrainCircuit :size="14" />回顾知识</button><button :disabled="Boolean(busyAction) || !question" @click="send('submit_answer')"><ShieldCheck :size="14" />提交完整作答</button><button :disabled="Boolean(busyAction) || !question" @click="requestVariant"><Target :size="14" />同类训练</button>
        </div>
        <div v-if="awaitingOcrConfirmation" class="ocr-confirm"><CircleAlert :size="16" /><span>请修改输入框中的识别文字，确认无误后继续。</span><button @click="confirmOcr">确认识别内容</button></div>
        <small>Ctrl + Enter 发送 · 图片仅在本轮内存处理 · 题库依据会随每次输入重新检索</small>
      </footer>
    </section>
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
</style>
