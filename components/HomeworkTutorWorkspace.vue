<script setup lang="ts">
import {
  ArrowRight, BookOpenText, BrainCircuit, Camera, CheckCircle2, CircleAlert,
  Database, Lightbulb, LoaderCircle, MessageCircleQuestion, RefreshCw, Send,
  ShieldCheck, Sparkles, Target, Upload, X,
} from "@lucide/vue";
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";

import { subjectLabels } from "@/lib/curriculum-catalog";
import {
  confirmHomeworkOcr,
  createHomeworkSession,
  fetchQuestionBankSummary,
  requestHomeworkVariant,
  submitHomeworkAnswer,
  submitHomeworkTurn,
  type HomeworkTurnRequest,
} from "@/lib/homework-client";
import type {
  HomeworkEnvelope, HomeworkQuestion, HomeworkSession, PlanTask,
  QuestionBankMatch, QuestionBankSummary, StudentLoginProfile, SubjectKey,
} from "@/lib/types";

interface ConversationItem {
  id: string;
  role: "student" | "assistant";
  title: string;
  text: string;
  guidance?: string;
  question?: string;
  warning?: string;
}

const props = defineProps<{
  profile: StudentLoginProfile;
  planTasks?: PlanTask[];
  initialSubject?: SubjectKey;
}>();

const subjects: SubjectKey[] = [
  "chinese", "mathematics", "foreign_language", "physics", "chemistry",
  "biology", "history", "geography", "ideology_politics", "technology",
];
const subject = ref<SubjectKey>(props.initialSubject || "mathematics");
const linkedTaskId = ref("");
const questionText = ref("");
const studentWork = ref("");
const studentMessage = ref("");
const imageFile = ref<File | null>(null);
const imagePreview = ref("");
const fileInput = ref<HTMLInputElement | null>(null);
const session = ref<HomeworkSession | null>(null);
const question = ref<HomeworkQuestion | null>(null);
const matches = ref<QuestionBankMatch[]>([]);
const summary = ref<QuestionBankSummary | null>(null);
const conversations = ref<ConversationItem[]>([]);
const busyAction = ref("");
const error = ref("");
const mode = ref<"live" | "demo">("live");
const awaitingOcrConfirmation = ref(false);

const availableTasks = computed(() => (props.planTasks || []).filter((task) => task.subject === subject.value));
const canSend = computed(() => Boolean(questionText.value.trim() || imageFile.value || question.value));
const currentHintLevel = computed(() => session.value?.hint_runtime.current_level || 0);
const exerciseCount = computed(() => summary.value?.content_roles.exercise || 4634);
const secureCount = computed(() => (
  (summary.value?.content_roles.answer_secure || 478)
  + (summary.value?.content_roles.explanation_secure || 1462)
));

watch(subject, () => {
  if (!availableTasks.value.some((task) => task.task_id === linkedTaskId.value)) linkedTaskId.value = "";
});
onMounted(async () => {
  try { summary.value = await fetchQuestionBankSummary(); } catch { /* non-blocking metric */ }
});
onBeforeUnmount(() => { if (imagePreview.value) URL.revokeObjectURL(imagePreview.value); });

function formatNumber(value?: number) {
  return new Intl.NumberFormat("zh-CN").format(value || 0);
}

function selectImage(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0] || null;
  if (!file) return;
  if (file.size > 10 * 1024 * 1024) { error.value = "图片不能超过 10MB"; return; }
  if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) {
    error.value = "仅支持 JPG、PNG 或 WebP 图片"; return;
  }
  if (imagePreview.value) URL.revokeObjectURL(imagePreview.value);
  imageFile.value = file;
  imagePreview.value = URL.createObjectURL(file);
  error.value = "";
}

function clearImage() {
  if (imagePreview.value) URL.revokeObjectURL(imagePreview.value);
  imageFile.value = null;
  imagePreview.value = "";
  if (fileInput.value) fileInput.value.value = "";
}

function actionLabel(action?: string) {
  return ({
    release_hint: "分步提示", verify_step: "步骤检查", knowledge_review: "知识回顾",
    answer_verification: "作答校验", request_parse_confirmation: "请确认题目识别",
    variant_practice: "同类训练",
  } as Record<string, string>)[action || ""] || "辅导建议";
}

function applyResponse(response: HomeworkEnvelope, append = true) {
  if (response.result.session) session.value = response.result.session;
  if (response.result.question) question.value = response.result.question;
  if (response.result.question_bank_matches) matches.value = response.result.question_bank_matches;
  if (response._meta?.mode) mode.value = response._meta.mode;
  awaitingOcrConfirmation.value = response.result.tutoring?.action === "request_parse_confirmation";
  const content = response.result.tutoring?.student_visible_content;
  if (append && content) conversations.value.push({
    id: `assistant_${Date.now()}_${conversations.value.length}`,
    role: "assistant", title: actionLabel(response.result.tutoring?.action),
    text: content.acknowledgement, guidance: content.guidance,
    question: content.question_to_student, warning: content.warning,
  });
}

function addStudentMessage(text: string) {
  conversations.value.push({
    id: `student_${Date.now()}_${conversations.value.length}`,
    role: "student", title: "我的问题", text,
  });
}

async function ensureSession() {
  if (session.value) return session.value;
  const response = await createHomeworkSession(props.profile, subject.value, linkedTaskId.value);
  applyResponse(response, false);
  if (!response.result.session) throw new Error("辅导 Agent 未能创建学习会话");
  return response.result.session;
}

function turnBody(intent: HomeworkTurnRequest["intent"], message: string, active: HomeworkSession): HomeworkTurnRequest {
  return {
    sessionId: active.session_id, studentId: props.profile.studentId, subject: subject.value,
    questionText: questionText.value.trim(), studentWork: studentWork.value.trim(),
    message, intent, image: imageFile.value,
  };
}

async function sendTurn(intent: HomeworkTurnRequest["intent"], defaultMessage: string) {
  if (!canSend.value) { error.value = "请粘贴题目文字，或上传一张清晰的题目图片"; return; }
  busyAction.value = intent;
  error.value = "";
  const message = studentMessage.value.trim() || defaultMessage;
  try {
    const active = await ensureSession();
    addStudentMessage(message);
    applyResponse(await submitHomeworkTurn(turnBody(intent, message, active)));
    studentMessage.value = "";
    clearImage();
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "本轮辅导失败，请稍后重试";
  } finally { busyAction.value = ""; }
}

async function confirmOcr() {
  if (!session.value || !questionText.value.trim()) { error.value = "请在题目框中修正识别文字后再确认"; return; }
  busyAction.value = "confirm_ocr";
  error.value = "";
  try {
    addStudentMessage("我已检查并确认题目文字");
    applyResponse(await confirmHomeworkOcr(
      session.value.session_id, props.profile.studentId, subject.value,
      questionText.value.trim(), studentWork.value.trim(),
    ));
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "题目确认失败";
  } finally { busyAction.value = ""; }
}

async function submitAnswer() {
  if (!studentWork.value.trim()) { error.value = "请先填写你的完整作答过程"; return; }
  busyAction.value = "submit_answer";
  error.value = "";
  try {
    const active = await ensureSession();
    if (!question.value) applyResponse(await submitHomeworkTurn(
      turnBody("check_step", "这是我的完整作答，请先读取题目并检查。", active),
    ));
    if (!question.value) throw new Error("题目尚未解析完成，请先确认题目内容");
    addStudentMessage("提交完整作答，申请过程校验");
    applyResponse(await submitHomeworkAnswer(
      props.profile.studentId, question.value.question_id, studentWork.value.trim(),
      turnBody("check_step", "提交完整作答", active),
    ));
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "作答提交失败";
  } finally { busyAction.value = ""; }
}

async function requestVariant() {
  if (!question.value || !session.value) { error.value = "请先完成当前题目的读取与辅导"; return; }
  busyAction.value = "variant";
  error.value = "";
  try {
    addStudentMessage("请给我一道同知识点、相近难度的训练题");
    applyResponse(await requestHomeworkVariant(
      props.profile.studentId, question.value.question_id,
      turnBody("request_next_hint", "请求同类训练", session.value),
    ));
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "同类训练获取失败";
  } finally { busyAction.value = ""; }
}

function newQuestion() {
  session.value = null; question.value = null; matches.value = []; conversations.value = [];
  questionText.value = ""; studentWork.value = ""; studentMessage.value = "";
  awaitingOcrConfirmation.value = false; clearImage(); error.value = "";
}
</script>

<template>
  <div class="tutor-page">
    <section class="tutor-hero">
      <div>
        <span class="tutor-eyebrow"><Sparkles :size="15" /> 作业辅导 Agent</span>
        <h1>不替你抄答案，陪你真正做出来。</h1>
        <p>基于全国新课标Ⅰ卷范围与本地 5·3 题库，逐步识别卡点、释放最小提示，并把有效学习证据反馈给规划 Agent。</p>
        <div class="hero-tags">
          <span><ShieldCheck :size="14" /> 标准答案隔离</span>
          <span><Lightbulb :size="14" /> 每轮一个提示</span>
          <span><BrainCircuit :size="14" /> 过程证据可追溯</span>
        </div>
      </div>
      <div class="corpus-card">
        <Database :size="24" />
        <div><strong>{{ formatNumber(summary?.total_files || 7577) }}</strong><small>题库资源</small></div>
        <div><strong>{{ formatNumber(exerciseCount) }}</strong><small>练习资源</small></div>
        <div><strong>{{ formatNumber(secureCount) }}</strong><small>隔离答案/解析</small></div>
      </div>
    </section>

    <section v-if="mode === 'demo'" class="tutor-demo"><CircleAlert :size="17" /><span><strong>在线演示模式</strong> 当前展示完整交互和安全边界；服务器页面连接真实 LangGraph Agent 与题库索引。</span></section>

    <div class="tutor-layout">
      <aside class="question-panel">
        <div class="panel-heading"><div><small>QUESTION INPUT</small><h2>录入作业题目</h2></div><button @click="newQuestion"><RefreshCw :size="16" />新题</button></div>
        <label class="field"><span>辅导科目</span><select v-model="subject"><option v-for="key in subjects" :key="key" :value="key">{{ subjectLabels[key] }}</option></select></label>
        <label v-if="availableTasks.length" class="field"><span>关联学习计划 <i>可选</i></span><select v-model="linkedTaskId" :disabled="Boolean(session)"><option value="">不关联计划任务</option><option v-for="task in availableTasks" :key="task.task_id" :value="task.task_id">{{ task.rationale.split('：')[0] }}</option></select></label>
        <label class="field"><span>题目文字 <i>可粘贴或由图片识别后修正</i></span><textarea v-model="questionText" rows="6" placeholder="例如：已知函数 f(x)=...，求单调区间。" /></label>
        <div class="upload-zone" :class="{ populated: imagePreview }" @click="fileInput?.click()">
          <input ref="fileInput" type="file" accept="image/jpeg,image/png,image/webp" @change="selectImage" />
          <template v-if="imagePreview"><img :src="imagePreview" alt="题目预览" /><div><strong>{{ imageFile?.name }}</strong><small>点击可重新选择</small></div><button aria-label="移除图片" @click.stop="clearImage"><X :size="15" /></button></template>
          <template v-else><span><Camera :size="22" /></span><div><strong>拍照或上传题目</strong><small>JPG / PNG / WebP · 最大 10MB · 原图不持久化</small></div><Upload :size="18" /></template>
        </div>
        <label class="field"><span>你的当前思路或步骤 <i>建议填写</i></span><textarea v-model="studentWork" rows="5" placeholder="写下已想到的公式、推导或答案。Agent 会从卡点继续。" /></label>
        <div v-if="error" class="tutor-message"><CircleAlert :size="16" />{{ error }}</div>
        <div v-if="session" class="session-state"><span><i />会话已建立</span><span>提示 L{{ currentHintLevel }}</span><span>状态 v{{ session.state_version }}</span></div>
      </aside>

      <main class="dialog-panel">
        <div class="dialog-heading"><div><span><MessageCircleQuestion :size="20" /></span><div><h2>分步辅导</h2><small>先尝试 · 再提示 · 后校验 · 最后迁移</small></div></div><span class="agent-status"><i /> HomeworkTutor 在线</span></div>
        <div v-if="!conversations.length" class="dialog-empty">
          <span><BookOpenText :size="31" /></span><h3>把题目和你的思路交给我</h3>
          <p>我会先判断学科、题型和知识点，再检索 5·3 题库。答案与解析仅用于受控校验，不会直接泄露。</p>
          <div><button @click="sendTurn('request_hint', '我卡住了，请给我第一个提示')"><Lightbulb :size="16" />给我一个提示</button><button @click="sendTurn('check_step', '请检查我现在这一步')"><CheckCircle2 :size="16" />检查当前步骤</button><button @click="sendTurn('request_knowledge_review', '请回顾这道题需要的核心知识')"><BrainCircuit :size="16" />回顾知识点</button></div>
        </div>
        <div v-else class="conversation-list">
          <article v-for="item in conversations" :key="item.id" :class="['conversation', item.role]">
            <span class="conversation-avatar"><MessageCircleQuestion v-if="item.role === 'assistant'" :size="18" /><span v-else>{{ profile.studentName.slice(0, 1) }}</span></span>
            <div><small>{{ item.role === 'assistant' ? item.title : profile.studentName }}</small><p>{{ item.text }}</p><div v-if="item.guidance" class="guidance"><Lightbulb :size="16" /><span>{{ item.guidance }}</span></div><div v-if="item.question" class="follow-question"><ArrowRight :size="15" />{{ item.question }}</div><div v-if="item.warning" class="safety-note"><ShieldCheck :size="14" />{{ item.warning }}</div></div>
          </article>
        </div>
        <div v-if="awaitingOcrConfirmation" class="ocr-confirm"><CircleAlert :size="18" /><div><strong>识别结果需要确认</strong><small>请在左侧修正题目文字，再继续分析。</small></div><button :disabled="Boolean(busyAction)" @click="confirmOcr"><LoaderCircle v-if="busyAction === 'confirm_ocr'" class="spin" :size="16" /><CheckCircle2 v-else :size="16" />确认题目</button></div>
        <section v-if="matches.length" class="evidence-strip">
          <div class="evidence-title"><div><Database :size="17" /><span><strong>题库依据</strong><small>{{ matches.length }} 条受控检索结果</small></span></div><span><ShieldCheck :size="13" />答案未暴露</span></div>
          <div class="evidence-list"><article v-for="match in matches.slice(0, 3)" :key="match.source_id"><span>{{ match.edition }}版</span><div><strong>{{ match.topic || match.title }}</strong><small>{{ match.region }} · {{ match.file_type.toUpperCase() }} · 匹配 {{ Math.round(match.confidence * 100) }}%</small></div></article></div>
        </section>
        <div class="dialog-compose">
          <textarea v-model="studentMessage" rows="2" placeholder="告诉 Agent 你卡在哪里，例如：我不确定第二步能不能除以 x。" @keydown.ctrl.enter="sendTurn('request_hint', '请根据我的问题继续提示')" />
          <div class="compose-actions">
            <button :disabled="Boolean(busyAction)" @click="sendTurn('request_hint', '我卡住了，请给我一个提示')"><LoaderCircle v-if="busyAction === 'request_hint'" class="spin" :size="16" /><Lightbulb v-else :size="16" />提示</button>
            <button :disabled="Boolean(busyAction)" @click="sendTurn('check_step', '请检查我现在这一步')"><LoaderCircle v-if="busyAction === 'check_step'" class="spin" :size="16" /><CheckCircle2 v-else :size="16" />检查步骤</button>
            <button :disabled="Boolean(busyAction)" @click="sendTurn('request_knowledge_review', '请回顾这道题需要的核心知识')"><BrainCircuit :size="16" />知识回顾</button>
            <button class="submit-answer" :disabled="Boolean(busyAction)" @click="submitAnswer"><LoaderCircle v-if="busyAction === 'submit_answer'" class="spin" :size="16" /><Send v-else :size="16" />提交作答</button>
            <button :disabled="Boolean(busyAction) || !question" @click="requestVariant"><Target :size="16" />同类训练</button>
          </div><small>Ctrl + Enter 发送 · Agent 不会在你完成前给出可直接抄写的完整答案</small>
        </div>
      </main>
    </div>
  </div>
</template>

<style scoped>
.tutor-page{display:grid;gap:16px;color:#263b5d}.tutor-hero{position:relative;display:flex;min-height:210px;align-items:center;justify-content:space-between;overflow:hidden;padding:34px 38px;color:#fff;background:linear-gradient(135deg,#0d3578,#155eef 65%,#4b91ff);border-radius:18px;box-shadow:0 20px 40px rgba(21,94,239,.17)}.tutor-hero:after{position:absolute;top:-120px;right:-40px;width:330px;height:330px;content:"";border:1px solid rgba(255,255,255,.17);border-radius:50%;box-shadow:0 0 0 48px rgba(255,255,255,.045)}.tutor-hero>div:first-child{position:relative;z-index:1;max-width:700px}.tutor-eyebrow{display:inline-flex;align-items:center;gap:6px;color:#d5e5ff;font-size:10px;font-weight:800;letter-spacing:.08em}.tutor-hero h1{margin:15px 0 9px;font-size:clamp(26px,3vw,40px);line-height:1.2;letter-spacing:-.04em}.tutor-hero p{max-width:660px;margin:0;color:rgba(255,255,255,.74);font-size:11px;line-height:1.8}.hero-tags{display:flex;flex-wrap:wrap;gap:9px;margin-top:18px}.hero-tags span{display:inline-flex;align-items:center;gap:5px;padding:7px 10px;border:1px solid rgba(255,255,255,.16);background:rgba(255,255,255,.08);border-radius:8px;font-size:9px}.corpus-card{position:relative;z-index:1;display:grid;grid-template-columns:auto repeat(3,auto);gap:20px;align-items:center;padding:20px 22px;border:1px solid rgba(255,255,255,.2);background:rgba(255,255,255,.09);border-radius:14px;backdrop-filter:blur(10px)}.corpus-card div{display:flex;flex-direction:column;gap:3px}.corpus-card strong{font-size:16px}.corpus-card small{color:rgba(255,255,255,.6);font-size:8px}.tutor-demo{display:flex;align-items:center;gap:9px;padding:11px 14px;color:#7a5516;border:1px solid #f3d9a9;background:#fff8e9;border-radius:10px;font-size:10px}.tutor-demo strong{margin-right:7px}
.tutor-layout{display:grid;grid-template-columns:minmax(310px,.72fr) minmax(0,1.45fr);gap:16px;align-items:start}.question-panel,.dialog-panel{border:1px solid #dfe7f3;background:#fff;border-radius:15px;box-shadow:0 7px 22px rgba(26,64,123,.055)}.question-panel{display:grid;gap:15px;padding:22px}.panel-heading,.dialog-heading,.evidence-title{display:flex;align-items:center;justify-content:space-between}.panel-heading{padding-bottom:15px;border-bottom:1px solid #edf1f7}.panel-heading small{color:#155eef;font-size:8px;font-weight:800;letter-spacing:.14em}.panel-heading h2,.dialog-heading h2{margin:4px 0 0;color:#18365f;font-size:15px}.panel-heading button{display:inline-flex;align-items:center;gap:5px;padding:7px 9px;color:#5e718e;border:1px solid #dbe4f1;background:#fff;border-radius:8px;font-size:9px}.field{display:grid;gap:7px}.field>span{color:#40536f;font-size:10px;font-weight:750}.field>span i{margin-left:5px;color:#94a3b8;font-size:8px;font-style:normal;font-weight:500}.field select,.field textarea,.dialog-compose textarea{width:100%;padding:11px 12px;color:#263b5d;border:1px solid #d8e2f0;outline:none;background:#fbfcff;border-radius:9px;font:inherit;font-size:10px;line-height:1.65;resize:vertical}.field select{height:42px;padding-block:0}.field textarea:focus,.field select:focus,.dialog-compose textarea:focus{border-color:#6ba1ff;background:#fff;box-shadow:0 0 0 3px rgba(21,94,239,.08)}.upload-zone{position:relative;display:flex;min-height:78px;align-items:center;gap:11px;overflow:hidden;padding:13px;border:1px dashed #a8c4eb;background:#f5f9ff;border-radius:10px;cursor:pointer}.upload-zone input{display:none}.upload-zone>span{display:grid;width:42px;height:42px;flex:0 0 auto;place-items:center;color:#155eef;background:#e5efff;border-radius:10px}.upload-zone>div{display:flex;min-width:0;flex:1;flex-direction:column;gap:4px}.upload-zone strong{overflow:hidden;color:#315178;font-size:10px;text-overflow:ellipsis;white-space:nowrap}.upload-zone small{color:#8496ae;font-size:8px}.upload-zone>svg{color:#7193bd}.upload-zone img{width:64px;height:64px;flex:0 0 auto;object-fit:cover;border-radius:8px}.upload-zone button{display:grid;width:26px;height:26px;place-items:center;color:#667b98;border:0;background:#e7eef8;border-radius:7px}.tutor-message{display:flex;gap:7px;padding:10px 12px;color:#b42318;background:#fff0ef;border-radius:9px;font-size:9px}.session-state{display:flex;flex-wrap:wrap;gap:7px;padding-top:13px;border-top:1px solid #edf1f7}.session-state span{display:inline-flex;align-items:center;gap:5px;padding:6px 8px;color:#617694;background:#f1f5fb;border-radius:7px;font-size:8px}.session-state i{width:6px;height:6px;background:#26af7d;border-radius:50%}
.dialog-panel{min-height:680px;overflow:hidden}.dialog-heading{height:72px;padding:0 22px;border-bottom:1px solid #e8eef6;background:#fbfdff}.dialog-heading>div{display:flex;align-items:center;gap:10px}.dialog-heading>div>span{display:grid;width:38px;height:38px;place-items:center;color:#fff;background:linear-gradient(135deg,#0e3f91,#2474ff);border-radius:10px}.dialog-heading small{color:#8a9bb1;font-size:8px}.agent-status{display:inline-flex;align-items:center;gap:6px;color:#60728d;font-size:8px}.agent-status i{width:6px;height:6px;background:#2bb381;border-radius:50%;box-shadow:0 0 0 3px rgba(43,179,129,.12)}.dialog-empty{display:flex;min-height:380px;align-items:center;justify-content:center;flex-direction:column;padding:40px;text-align:center}.dialog-empty>span{display:grid;width:70px;height:70px;place-items:center;color:#155eef;background:#eaf2ff;border-radius:20px}.dialog-empty h3{margin:18px 0 8px;color:#274668;font-size:16px}.dialog-empty p{max-width:520px;margin:0;color:#7a8da7;font-size:10px;line-height:1.8}.dialog-empty>div{display:flex;flex-wrap:wrap;justify-content:center;gap:8px;margin-top:20px}.dialog-empty button,.compose-actions button,.ocr-confirm button{display:inline-flex;min-height:36px;align-items:center;justify-content:center;gap:6px;padding:0 11px;color:#426184;border:1px solid #d5e0ee;background:#fff;border-radius:8px;font-size:9px}.conversation-list{display:grid;gap:20px;max-height:470px;overflow:auto;padding:24px}.conversation{display:flex;gap:10px;max-width:88%}.conversation.student{justify-self:end;flex-direction:row-reverse}.conversation-avatar{display:grid;width:34px;height:34px;flex:0 0 auto;place-items:center;color:#155eef;background:#e9f2ff;border-radius:10px;font-size:10px;font-weight:800}.conversation.student .conversation-avatar{color:#fff;background:#1c5ec8}.conversation>div{padding:12px 14px;border:1px solid #e0e8f3;background:#fff;border-radius:4px 12px 12px;box-shadow:0 4px 12px rgba(31,65,112,.04)}.conversation.student>div{color:#fff;border:0;background:#155eef;border-radius:12px 4px 12px 12px}.conversation small{color:#6e88aa;font-size:8px;font-weight:750}.conversation.student small{color:rgba(255,255,255,.68)}.conversation p{margin:7px 0 0;color:#324d70;font-size:10px;line-height:1.7}.conversation.student p{color:#fff}.guidance{display:flex;align-items:flex-start;gap:7px;margin-top:10px;padding:10px;color:#265591;background:#edf5ff;border-radius:8px;font-size:10px;line-height:1.65}.guidance svg{flex:0 0 auto;color:#155eef}.follow-question,.safety-note{display:flex;align-items:flex-start;gap:5px;margin-top:9px;color:#334f73;font-size:9px;line-height:1.5}.safety-note{color:#788ba4;font-size:8px}
.ocr-confirm{display:flex;align-items:center;gap:10px;margin:0 22px 16px;padding:12px 14px;color:#6e501a;border:1px solid #f0d39c;background:#fff9e8;border-radius:10px}.ocr-confirm>div{display:flex;flex:1;flex-direction:column;gap:3px}.ocr-confirm strong{font-size:10px}.ocr-confirm small{font-size:8px}.ocr-confirm button{color:#fff;border:0;background:#a46a0b}.evidence-strip{margin:0 22px 16px;padding:14px;border:1px solid #d9e6f7;background:#f7faff;border-radius:11px}.evidence-title>div{display:flex;align-items:center;gap:8px;color:#155eef}.evidence-title>div span{display:flex;flex-direction:column;gap:2px}.evidence-title strong{color:#345277;font-size:10px}.evidence-title small{color:#8a9ab0;font-size:8px}.evidence-title>span{display:inline-flex;align-items:center;gap:4px;color:#278764;font-size:8px}.evidence-list{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:11px}.evidence-list article{display:flex;min-width:0;gap:8px;padding:9px;border:1px solid #e1e8f2;background:#fff;border-radius:8px}.evidence-list article>span{height:max-content;padding:4px 6px;color:#155eef;background:#eaf2ff;border-radius:5px;font-size:7px;font-weight:800}.evidence-list article div{display:flex;min-width:0;flex-direction:column;gap:4px}.evidence-list strong{overflow:hidden;color:#3b5271;font-size:8px;text-overflow:ellipsis;white-space:nowrap}.evidence-list small{color:#8a9ab0;font-size:7px}.dialog-compose{padding:18px 22px;border-top:1px solid #e8eef6;background:#fbfdff}.dialog-compose textarea{min-height:62px;background:#fff;resize:none}.compose-actions{display:flex;flex-wrap:wrap;gap:7px;margin-top:9px}.compose-actions .submit-answer{color:#fff;border-color:#155eef;background:#155eef}.compose-actions button:disabled,.ocr-confirm button:disabled{cursor:not-allowed;opacity:.55}.dialog-compose>small{display:block;margin-top:9px;color:#8c9caf;font-size:7px}.spin{animation:spin 1s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}
@media(max-width:1180px){.corpus-card{display:none}.tutor-layout{grid-template-columns:minmax(280px,.78fr) minmax(0,1.2fr)}.evidence-list{grid-template-columns:1fr}}@media(max-width:860px){.tutor-hero{padding:28px 24px}.tutor-layout{grid-template-columns:1fr}.dialog-panel{min-height:auto}.conversation-list{max-height:none;padding:18px 16px}.evidence-strip{margin-inline:16px}.dialog-compose{padding:16px}}@media(max-width:560px){.tutor-hero h1{font-size:27px}.hero-tags{display:none}.question-panel{padding:18px}.agent-status{display:none}.conversation{max-width:100%}.dialog-empty{min-height:320px;padding:30px 18px}.compose-actions button{flex:1 1 calc(50% - 7px)}}
</style>
