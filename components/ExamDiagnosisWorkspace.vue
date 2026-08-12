<script setup lang="ts">
import {
  AlertTriangle, ArrowLeft, ArrowRight, BookOpenCheck, Camera, CheckCircle2,
  ClipboardList, Clock3, FileCheck2, LoaderCircle, LockKeyhole, RotateCcw,
  Send, ShieldCheck, Sparkles, Target, UploadCloud,
} from "@lucide/vue";
import { computed, onBeforeUnmount, onMounted, ref } from "vue";

import PaginationControls from "@/components/PaginationControls.vue";
import {
  createExamDiagnosticSession, fetchExamDiagnosticCatalog,
  gradeExamConstructedResponse, submitExamDiagnostic,
} from "@/lib/exam-diagnosis-client";
import type {
  ExamConstructedGrade, ExamDiagnosticCatalog, ExamDiagnosticPaper,
  ExamDiagnosticResult, ExamDiagnosticSession, StudentLoginProfile, SubjectKey,
} from "@/lib/types";

const props = defineProps<{
  profile: StudentLoginProfile;
  initialSubject: SubjectKey;
  initialPaperId?: string;
}>();

const catalog = ref<ExamDiagnosticCatalog | null>(null);
const selectedSubject = ref<SubjectKey>(props.initialSubject || "mathematics");
const selectedPaperId = ref("");
const session = ref<ExamDiagnosticSession | null>(null);
const paper = ref<ExamDiagnosticPaper | null>(null);
const currentIndex = ref(0);
const choices = ref<Record<string, "A" | "B" | "C" | "D">>({});
const questionDurations = ref<Record<string, number>>({});
const questionStartedAt = ref(Date.now());
const clockNow = ref(Date.now());
const timingPaused = ref(false);
const assetLoadFailures = ref(0);
const files = ref<Record<string, File[]>>({});
const previews = ref<Record<string, string[]>>({});
const grades = ref<Record<string, ExamConstructedGrade>>({});
const gradingId = ref("");
const loading = ref(true);
const starting = ref(false);
const submitting = ref(false);
const error = ref("");
const result = ref<ExamDiagnosticResult | null>(null);
const resultPage = ref(1);
const knowledgePage = ref(1);
const RESULT_PAGE_SIZE = 8;
const KNOWLEDGE_PAGE_SIZE = 6;

const catalogSubject = computed(() => catalog.value?.subjects.find((item) => item.subject === selectedSubject.value));
const currentQuestion = computed(() => paper.value?.questions[currentIndex.value] || null);
const answeredCount = computed(() => Object.keys(choices.value).length + Object.keys(grades.value).length);
const canSubmit = computed(() => {
  if (!paper.value) return false;
  return paper.value.questions.every((question) =>
    question.type === "multiple_choice" ? Boolean(choices.value[question.question_id]) : Boolean(grades.value[question.question_id]),
  );
});
const diagnosisState = computed(() => result.value?.learning_diagnosis?.result.learning_state || null);
const learningRecord = computed(() => result.value?.learning_record || null);
const pagedResultQuestions = computed(() => {
  const start = (resultPage.value - 1) * RESULT_PAGE_SIZE;
  return (paper.value?.questions || []).slice(start, start + RESULT_PAGE_SIZE);
});
const pagedKnowledgeStatistics = computed(() => {
  const start = (knowledgePage.value - 1) * KNOWLEDGE_PAGE_SIZE;
  return (learningRecord.value?.knowledge_statistics || []).slice(start, start + KNOWLEDGE_PAGE_SIZE);
});
const currentElapsedSeconds = computed(() => {
  const question = currentQuestion.value;
  if (!question) return 0;
  const stored = questionDurations.value[question.question_id] || 0;
  if (timingPaused.value) return stored;
  return stored + Math.max(0, Math.round((clockNow.value - questionStartedAt.value) / 1000));
});

let clockTimer = 0;

function handleVisibilityChange() {
  if (document.hidden) {
    commitCurrentTime();
    timingPaused.value = true;
  } else {
    timingPaused.value = false;
    questionStartedAt.value = Date.now();
    clockNow.value = Date.now();
  }
}

onMounted(async () => {
  clockTimer = window.setInterval(() => { clockNow.value = Date.now(); }, 1000);
  document.addEventListener("visibilitychange", handleVisibilityChange);
  try {
    catalog.value = await fetchExamDiagnosticCatalog();
    const assignedGroup = props.initialPaperId
      ? catalog.value.subjects.find((group) =>
        group.papers.some((paperItem) => paperItem.paper_id === props.initialPaperId),
      )
      : undefined;
    if (assignedGroup) {
      selectedSubject.value = assignedGroup.subject;
      selectedPaperId.value = props.initialPaperId || "";
    } else {
      if (!catalogSubject.value) selectedSubject.value = catalog.value.subjects[0].subject;
      selectedPaperId.value = catalogSubject.value?.papers[0]?.paper_id || "";
    }
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "真题诊断卷目录加载失败";
  } finally {
    loading.value = false;
  }
});

onBeforeUnmount(() => {
  commitCurrentTime();
  window.clearInterval(clockTimer);
  document.removeEventListener("visibilitychange", handleVisibilityChange);
  Object.values(previews.value).flat().forEach((url) => URL.revokeObjectURL(url));
});

function changeSubject(subject: SubjectKey) {
  selectedSubject.value = subject;
  selectedPaperId.value = catalog.value?.subjects.find((item) => item.subject === subject)?.papers[0]?.paper_id || "";
}

async function startPaper() {
  if (!selectedPaperId.value) return;
  starting.value = true;
  error.value = "";
  try {
    const created = await createExamDiagnosticSession(props.profile, selectedPaperId.value);
    session.value = created.session;
    paper.value = created.paper;
    currentIndex.value = 0;
    choices.value = {};
    questionDurations.value = {};
    files.value = {};
    previews.value = {};
    grades.value = {};
    assetLoadFailures.value = 0;
    questionStartedAt.value = Date.now();
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "诊断卷启动失败";
  } finally {
    starting.value = false;
  }
}

function commitCurrentTime(): number {
  const question = currentQuestion.value;
  if (!question) return 1;
  const elapsed = timingPaused.value ? 0 : Math.max(0, Math.round((Date.now() - questionStartedAt.value) / 1000));
  const accumulated = Math.min(14_400, (questionDurations.value[question.question_id] || 0) + elapsed);
  questionDurations.value[question.question_id] = accumulated;
  questionStartedAt.value = Date.now();
  clockNow.value = Date.now();
  return Math.max(1, accumulated);
}

function goTo(index: number) {
  if (!paper.value) return;
  commitCurrentTime();
  currentIndex.value = Math.max(0, Math.min(index, paper.value.questions.length - 1));
  questionStartedAt.value = Date.now();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function selectOption(key: "A" | "B" | "C" | "D") {
  const question = currentQuestion.value;
  if (!question) return;
  choices.value[question.question_id] = key;
  commitCurrentTime();
  if (paper.value && currentIndex.value < paper.value.questions.length - 1) {
    window.setTimeout(() => goTo(currentIndex.value + 1), 180);
  }
}

function chooseImages(event: Event) {
  const question = currentQuestion.value;
  const input = event.target as HTMLInputElement;
  if (!question || !input.files?.length) return;
  const selected = Array.from(input.files).slice(0, 3);
  files.value[question.question_id] = selected;
  previews.value[question.question_id] = selected.map((file) => URL.createObjectURL(file));
  grades.value = Object.fromEntries(Object.entries(grades.value).filter(([id]) => id !== question.question_id));
}

async function gradeCurrent() {
  const question = currentQuestion.value;
  if (!question || !session.value || !files.value[question.question_id]?.length) return;
  gradingId.value = question.question_id;
  const durationSeconds = commitCurrentTime();
  timingPaused.value = true;
  error.value = "";
  try {
    const response = await gradeExamConstructedResponse(
      session.value.session_id, question.question_id, props.profile.studentId,
      files.value[question.question_id], durationSeconds,
    );
    grades.value[question.question_id] = response.grading;
    if (paper.value && currentIndex.value < paper.value.questions.length - 1) goTo(currentIndex.value + 1);
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "主观题多模态评分失败";
  } finally {
    gradingId.value = "";
    timingPaused.value = false;
    questionStartedAt.value = Date.now();
  }
}

async function submitPaper() {
  if (!session.value || !paper.value || !canSubmit.value) return;
  submitting.value = true;
  commitCurrentTime();
  timingPaused.value = true;
  error.value = "";
  try {
    result.value = await submitExamDiagnostic(
      session.value.session_id,
      props.profile.studentId,
      paper.value.questions.filter((question) => question.type === "multiple_choice").map((question) => ({
        question_id: question.question_id,
        selected_option: choices.value[question.question_id],
        duration_seconds: Math.max(1, questionDurations.value[question.question_id] || 0),
      })),
      Object.fromEntries(paper.value.questions.map((question) => [
        question.question_id,
        Math.max(1, questionDurations.value[question.question_id] || 0),
      ])),
    );
    resultPage.value = 1;
    knowledgePage.value = 1;
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "诊断卷提交失败";
  } finally {
    submitting.value = false;
    timingPaused.value = false;
  }
}

function formatDuration(seconds: number): string {
  const safe = Math.max(0, Math.round(seconds));
  const minutes = Math.floor(safe / 60);
  const remainder = safe % 60;
  return minutes ? `${minutes}分${String(remainder).padStart(2, "0")}秒` : `${remainder}秒`;
}

function handleAssetError(event: Event) {
  const image = event.target as HTMLImageElement;
  if (!(image instanceof HTMLImageElement) || !image.classList.contains("exam-inline-image")) return;
  if (!image.dataset.examRetried) {
    image.dataset.examRetried = "1";
    image.dataset.originalSrc = image.src;
    const separator = image.src.includes("?") ? "&" : "?";
    image.src = `${image.src}${separator}retry=${Date.now()}`;
    return;
  }
  if (!image.classList.contains("asset-load-failed")) assetLoadFailures.value += 1;
  image.classList.add("asset-load-failed");
  image.alt = "原题图片暂时加载失败";
}

function handleAssetLoad(event: Event) {
  const image = event.target as HTMLImageElement;
  if (!(image instanceof HTMLImageElement) || !image.classList.contains("asset-load-failed")) return;
  image.classList.remove("asset-load-failed");
  assetLoadFailures.value = Math.max(0, assetLoadFailures.value - 1);
}

function reset() {
  session.value = null;
  paper.value = null;
  result.value = null;
  choices.value = {};
  questionDurations.value = {};
  files.value = {};
  previews.value = {};
  grades.value = {};
  currentIndex.value = 0;
  resultPage.value = 1;
  knowledgePage.value = 1;
  assetLoadFailures.value = 0;
  error.value = "";
}
</script>

<template>
  <div class="exam-diagnosis">
    <div v-if="error" class="exam-error"><AlertTriangle :size="17" />{{ error }}</div>

    <section v-if="loading" class="exam-loading"><LoaderCircle class="spin" :size="28" /><span>正在核验 100 套高考真题诊断卷…</span></section>

    <template v-else-if="!paper && catalog">
      <section class="exam-hero">
        <div><span><BookOpenCheck :size="16" /> 高考真题专业诊断</span><h2>选一套真题，完成一次有出处的学情测量。</h2><p>10 个科目，每科 10 套；每套 12 道 A/B/C/D 选择题和 8 道拍照作答题。题面、答案与原卷 SHA-256 一一对应。</p></div>
        <aside><ShieldCheck :size="24" /><strong>答案安全隔离</strong><small>学生接口不下发标准答案<br />主观题由真实多模态模型阅卷</small></aside>
      </section>

      <section class="exam-picker">
        <header><div><small>STEP 01</small><h3>选择科目</h3></div><span>{{ catalog.paper_count }} 套真题诊断卷</span></header>
        <div class="subject-tabs"><button v-for="item in catalog.subjects" :key="item.subject" :class="{ active: selectedSubject === item.subject }" @click="changeSubject(item.subject)">{{ item.subject_label }}<small>{{ item.paper_count }} 套</small></button></div>
      </section>

      <section class="paper-picker">
        <header><div><small>STEP 02</small><h3>选择一套诊断卷</h3></div><span>约 100 分钟</span></header>
        <div class="paper-grid"><button v-for="(item, index) in catalogSubject?.papers" :key="item.paper_id" :class="{ active: selectedPaperId === item.paper_id }" @click="selectedPaperId = item.paper_id"><span>{{ String(index + 1).padStart(2, '0') }}</span><div><strong>第 {{ index + 1 }} 套</strong><small>{{ item.multiple_choice_count }} 道选择 · {{ item.constructed_response_count }} 道拍照题</small><i>{{ item.total_score }} 分 · {{ item.duration_minutes }} 分钟</i></div><CheckCircle2 v-if="selectedPaperId === item.paper_id" :size="18" /></button></div>
        <div class="start-strip"><div><LockKeyhole :size="18" /><span><strong>作答前说明</strong><small>选择题点击后自动进入下一题；大题请只上传本人的完整解题过程，最多 3 张清晰图片。</small></span></div><button :disabled="starting || !selectedPaperId" @click="startPaper"><LoaderCircle v-if="starting" class="spin" :size="18" /><ClipboardList v-else :size="18" />{{ starting ? '正在装载原题' : '开始这套诊断' }}</button></div>
      </section>
    </template>

    <template v-else-if="paper && session && !result">
      <section class="exam-toolbar"><div><small>{{ paper.subject_label }} · 高考真题</small><strong>{{ paper.title }}</strong></div><span class="live-time"><Clock3 :size="15" />本题 {{ formatDuration(currentElapsedSeconds) }}</span><span>{{ answeredCount }}/{{ paper.question_count }} 已完成</span><button @click="reset"><RotateCcw :size="15" />重新选卷</button></section>
      <div class="exam-progress"><i :style="{ width: `${answeredCount / paper.question_count * 100}%` }" /></div>
      <section v-if="assetLoadFailures" class="asset-warning"><AlertTriangle :size="18" /><span>有 {{ assetLoadFailures }} 个原题图形重试后仍未加载。请保持当前页面并刷新浏览器；作答记录和已累计用时不会因题间切换丢失。</span></section>

      <div class="exam-layout">
        <aside class="question-nav"><header><strong>答题卡</strong><small>蓝色已完成 · 当前题高亮</small></header><div><button v-for="question in paper.questions" :key="question.question_id" :class="{ current: currentIndex === question.sequence - 1, done: choices[question.question_id] || grades[question.question_id], subjective: question.type === 'constructed_response' }" @click="goTo(question.sequence - 1)">{{ question.sequence }}</button></div><section><span><i />选择题</span><span><i />拍照题</span></section></aside>

        <main v-if="currentQuestion" class="question-card" @error.capture="handleAssetError" @load.capture="handleAssetLoad">
          <header><div><span>第 {{ currentQuestion.sequence }} 题</span><b>{{ currentQuestion.type === 'multiple_choice' ? 'A/B/C/D 单选题' : '拍照作答题' }}</b></div><small>{{ currentQuestion.max_score }} 分 · 难度 {{ Math.round(currentQuestion.difficulty * 100) }}% · {{ currentQuestion.knowledge_tags.join('、') }}</small></header>
          <div class="question-source"><FileCheck2 :size="15" /><span>{{ currentQuestion.source.source_title }} · 原题第 {{ currentQuestion.source.original_number }} 题</span><i>已校验来源</i></div>
          <div class="question-content" v-html="currentQuestion.stem_html" />

          <div v-if="currentQuestion.type === 'multiple_choice'" class="answer-options"><button v-for="option in currentQuestion.options" :key="option.key" :class="{ selected: choices[currentQuestion.question_id] === option.key }" @click="selectOption(option.key)"><b>{{ option.key }}</b><span v-html="option.content_html" /><CheckCircle2 v-if="choices[currentQuestion.question_id] === option.key" :size="19" /></button></div>

          <section v-else class="photo-answer">
            <div class="photo-guide"><Camera :size="22" /><span><strong>请拍照上传你的完整解题过程</strong><small>保留推导、单位、图形和最终结论；模型只按图片中可核验的内容评分，不会脑补步骤。</small></span></div>
            <label class="upload-zone"><input type="file" accept="image/jpeg,image/png,image/webp" multiple @change="chooseImages" /><UploadCloud :size="28" /><strong>{{ files[currentQuestion.question_id]?.length ? `已选择 ${files[currentQuestion.question_id].length} 张图片` : '点击选择或拍摄作答图片' }}</strong><small>JPG / PNG / WebP，单张不超过 10MB，最多 3 张</small></label>
            <div v-if="previews[currentQuestion.question_id]?.length" class="image-previews"><img v-for="url in previews[currentQuestion.question_id]" :key="url" :src="url" alt="学生作答预览" /></div>
            <button class="grade-photo" :disabled="gradingId === currentQuestion.question_id || !files[currentQuestion.question_id]?.length" @click="gradeCurrent"><LoaderCircle v-if="gradingId === currentQuestion.question_id" class="spin" :size="18" /><Sparkles v-else :size="18" />{{ gradingId === currentQuestion.question_id ? '真实多模态模型正在识别与评分' : grades[currentQuestion.question_id] ? '重新识别并评分' : '提交本题给模型评分' }}</button>
            <article v-if="grades[currentQuestion.question_id]" class="grade-feedback" :class="{ review: grades[currentQuestion.question_id].requires_manual_review }"><div><CheckCircle2 :size="20" /><strong>{{ grades[currentQuestion.question_id].score ?? '待复核' }} / {{ grades[currentQuestion.question_id].max_score }} 分</strong><span>置信度 {{ Math.round(grades[currentQuestion.question_id].confidence * 100) }}%</span></div><p>{{ grades[currentQuestion.question_id].feedback }}</p><small v-if="grades[currentQuestion.question_id].review_reason">{{ grades[currentQuestion.question_id].review_reason }}</small></article>
          </section>

          <footer><button :disabled="currentIndex === 0" @click="goTo(currentIndex - 1)"><ArrowLeft :size="16" />上一题</button><button v-if="currentIndex < paper.questions.length - 1" @click="goTo(currentIndex + 1)">下一题<ArrowRight :size="16" /></button><button v-else class="submit-paper" :disabled="!canSubmit || submitting" @click="submitPaper"><LoaderCircle v-if="submitting" class="spin" :size="17" /><Send v-else :size="17" />{{ canSubmit ? '提交整套诊断卷' : `还需完成 ${paper.question_count - answeredCount} 题` }}</button></footer>
        </main>
      </div>
    </template>

    <template v-else-if="result && paper">
      <section class="result-hero"><div><span><BookOpenCheck :size="18" /> 真题诊断已完成</span><h2>{{ result.score }} <small>/ {{ result.paper_max }} 分</small></h2><p>选择题由标准答案精确判分；主观题由多模态模型按原卷答案逐项评分。</p></div><aside><strong>{{ result.objective_results.filter(item => item.is_correct).length }}/{{ result.objective_results.length }}</strong><small>选择题正确</small><b>{{ result.constructed_results.length }}/{{ paper.constructed_response_count }}</b><small>主观题已阅</small></aside></section>
      <section v-if="result.manual_review_question_ids.length" class="review-warning"><AlertTriangle :size="20" /><span><strong>有 {{ result.manual_review_question_ids.length }} 道题需要人工复核</strong><small>系统没有用低置信度猜测冒充确定分，当前总分请视为待复核成绩。</small></span></section>
      <section v-if="learningRecord" class="record-overview">
        <header><div><small>LEARNING RECORD · 自动生成</small><h3>这次真题诊断就是一条完整学习记录</h3></div><span>知识点、逐题用时和成绩已同步给学情诊断 Agent</span></header>
        <div class="record-metrics">
          <article><Clock3 :size="21" /><div><strong>{{ formatDuration(learningRecord.total_duration_seconds) }}</strong><small>整卷有效作答用时</small></div></article>
          <article><Target :size="21" /><div><strong>{{ Math.round(learningRecord.objective_accuracy * 100) }}%</strong><small>选择题准确率</small></div></article>
          <article><BookOpenCheck :size="21" /><div><strong>{{ Math.round(learningRecord.score_accuracy * 100) }}%</strong><small>{{ learningRecord.is_provisional ? '当前得分率（待复核）' : '整卷得分率' }}</small></div></article>
          <article><ShieldCheck :size="21" /><div><strong>{{ learningRecord.knowledge_statistics.length }}</strong><small>已统计知识点</small></div></article>
        </div>
        <div class="knowledge-record-table">
          <div class="record-row record-head"><span>知识点</span><span>题数</span><span>累计用时</span><span>平均每题</span><span>准确率 / 得分率</span></div>
          <div v-for="item in pagedKnowledgeStatistics" :key="item.knowledge_tag" class="record-row">
            <strong>{{ item.knowledge_tag }}</strong><span>{{ item.question_count }} 题</span><span>{{ formatDuration(item.duration_seconds) }}</span><span>{{ formatDuration(item.average_duration_seconds) }}</span><b :class="{ weak: item.accuracy !== null && item.accuracy < .6 }">{{ item.accuracy === null ? '待评分' : `${Math.round(item.accuracy * 100)}%` }}</b>
          </div>
        </div>
        <PaginationControls :page="knowledgePage" :total="learningRecord.knowledge_statistics.length" :page-size="KNOWLEDGE_PAGE_SIZE" label="个知识点" @change="knowledgePage=$event" />
      </section>
      <div class="result-grid"><section><header><small>QUESTION LEARNING LOG</small><h3>逐题得分与用时</h3></header><div class="score-list"><article v-for="question in pagedResultQuestions" :key="question.question_id"><span>{{ question.sequence }}</span><div><strong>{{ question.knowledge_tags.join('、') }}</strong><small>{{ question.type === 'multiple_choice' ? '选择题' : '主观题' }} · 原题 {{ question.source.original_number }} · 用时 {{ formatDuration(learningRecord?.question_records.find(item => item.question_id === question.question_id)?.duration_seconds || 0) }}</small></div><b>{{ result.objective_results.find(item => item.question_id === question.question_id)?.score ?? result.constructed_results.find(item => item.question_id === question.question_id)?.score ?? '复核' }}/{{ question.max_score }}</b></article></div><PaginationControls :page="resultPage" :total="paper.questions.length" :page-size="RESULT_PAGE_SIZE" label="道题" @change="resultPage=$event" /></section><section><header><small>LEARNING DIAGNOSIS AGENT</small><h3>基于本卷学习记录的学情诊断</h3></header><div v-if="diagnosisState" class="diagnosis-copy"><span><ShieldCheck :size="18" />{{ diagnosisState.evidence_gate.allowed_conclusion }}</span><p>{{ diagnosisState.narrative.student_summary || '结构化状态已生成，模型叙述暂未返回。' }}</p><div><strong>下一步</strong><small>{{ diagnosisState.narrative.next_evidence_request }}</small></div></div><div v-else class="diagnosis-copy unavailable"><AlertTriangle :size="20" /><p>成绩与学习记录已保存，但学情报告未生成；没有使用固定模板替代真实模型。</p></div></section></div>
      <button class="new-paper" @click="reset"><RotateCcw :size="17" />选择另一套真题诊断卷</button>
    </template>
  </div>
</template>

<style scoped>
.exam-diagnosis{display:grid;gap:16px}.exam-error,.review-warning{display:flex;align-items:center;gap:9px;padding:13px 15px;color:#a63d48;border:1px solid #efc3c9;background:#fff3f4;border-radius:11px;font-size:10px}.exam-loading{display:grid;min-height:330px;place-items:center;align-content:center;gap:12px;color:#637b99;background:#fff;border:1px solid #e0e7f0;border-radius:16px;font-size:11px}.exam-hero{display:flex;align-items:center;justify-content:space-between;padding:31px 36px;color:#fff;background:linear-gradient(135deg,#0d3569,#165dcb 62%,#149985);border-radius:18px}.exam-hero>div{max-width:720px}.exam-hero>div>span,.result-hero>div>span{display:flex;align-items:center;gap:7px;color:#d9ecff;font-size:10px;font-weight:800}.exam-hero h2{margin:14px 0 8px;font-size:28px}.exam-hero p{margin:0;color:#d2e2f5;font-size:10px;line-height:1.8}.exam-hero aside{display:grid;justify-items:center;gap:6px;padding:18px 22px;background:#ffffff16;border:1px solid #ffffff2e;border-radius:13px}.exam-hero aside strong{font-size:11px}.exam-hero aside small{text-align:center;color:#d8e6f5;font-size:8px;line-height:1.6}.exam-picker,.paper-picker,.question-card,.question-nav,.result-grid>section{padding:21px;border:1px solid #dfe7f1;background:#fff;border-radius:15px}.exam-picker>header,.paper-picker>header,.result-grid header{display:flex;align-items:center;justify-content:space-between;padding-bottom:14px;border-bottom:1px solid #edf1f6}.exam-picker header small,.paper-picker header small,.result-grid header small{color:#5d84c3;font-size:8px;font-weight:850}.exam-picker h3,.paper-picker h3,.result-grid h3{margin:4px 0 0;color:#253f62;font-size:15px}.exam-picker header>span,.paper-picker header>span{color:#8493a7;font-size:9px}.subject-tabs{display:grid;grid-template-columns:repeat(10,1fr);gap:7px;margin-top:15px}.subject-tabs button{display:grid;gap:4px;padding:11px 5px;color:#526985;border:1px solid #e0e7f0;background:#f9fbfd;border-radius:9px;font-size:10px}.subject-tabs button small{color:#95a2b2;font-size:7px}.subject-tabs button.active{color:#fff;border-color:#1760d0;background:#1760d0}.subject-tabs button.active small{color:#dbe9ff}.paper-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:9px;margin-top:15px}.paper-grid button{display:flex;align-items:center;gap:9px;padding:13px;text-align:left;color:#4b6280;border:1px solid #e1e7ef;background:#fbfcfe;border-radius:10px}.paper-grid button>span{display:grid;width:31px;height:31px;place-items:center;color:#1760d0;background:#eaf2ff;border-radius:8px;font-size:9px;font-weight:850}.paper-grid button>div{display:grid;flex:1;gap:3px}.paper-grid strong{font-size:10px}.paper-grid small,.paper-grid i{color:#8997a9;font-size:7px;font-style:normal}.paper-grid button.active{border-color:#68a1f1;background:#f0f6ff;box-shadow:0 0 0 2px #deebff}.paper-grid button.active>svg{color:#1c9a70}.start-strip{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-top:17px;padding:15px 17px;background:#f3f7fc;border-radius:11px}.start-strip>div{display:flex;align-items:center;gap:10px;color:#45617f}.start-strip>div span{display:grid;gap:4px}.start-strip strong{font-size:9px}.start-strip small{color:#7d8da2;font-size:8px}.start-strip>button,.grade-photo,.new-paper{display:flex;align-items:center;justify-content:center;gap:7px;padding:12px 17px;color:#fff;border:0;background:linear-gradient(135deg,#155eef,#159d8c);border-radius:9px;font-size:9px;font-weight:800}.exam-toolbar{display:flex;align-items:center;gap:15px;padding:14px 18px;border:1px solid #dfe7f1;background:#fff;border-radius:13px}.exam-toolbar>div{display:grid;flex:1;gap:3px}.exam-toolbar small{color:#7d8da1;font-size:8px}.exam-toolbar strong{color:#2c4667;font-size:11px}.exam-toolbar>span{color:#1760ce;font-size:10px;font-weight:800}.exam-toolbar .live-time{display:flex;align-items:center;gap:5px;padding:7px 9px;color:#167a68;background:#eaf8f4;border-radius:7px}.exam-toolbar button{display:flex;align-items:center;gap:5px;padding:8px 10px;color:#697c93;border:1px solid #dde5ee;background:#fafbfd;border-radius:7
px;font-size:8px}.exam-progress{height:7px;overflow:hidden;background:#e4ebf4;border-radius:5px}.exam-progress i{display:block;height:100%;background:linear-gradient(90deg,#155eef,#20ab98)}
.asset-warning{display:flex;align-items:center;gap:8px;padding:11px 13px;color:#855f16;border:1px solid #f0d589;background:#fff9e9;border-radius:10px;font-size:9px}
.exam-toolbar button{border-radius:7px}
.exam-layout{display:grid;grid-template-columns:220px minmax(0,1fr);align-items:start;gap:15px}.question-nav{position:sticky;top:15px}.question-nav header{display:grid;gap:3px;padding-bottom:12px;border-bottom:1px solid #eef2f6}.question-nav>div{display:grid;grid-template-columns:repeat(5,1fr);gap:7px;margin-top:14px}.question-nav button{height:32px;border:1px solid #dfe6ee;background:#f9fbfd;border-radius:7px}.question-nav button.subjective{border-style:dashed}.question-nav button.done{color:#fff;background:#2379d5}.question-nav button.current{box-shadow:0 0 0 3px #b9d5ff}.question-nav>section{display:flex;gap:12px;margin-top:13px;color:#8997a8;font-size:8px}
.question-card{min-height:650px}.question-card>header{display:flex;justify-content:space-between;gap:12px;padding-bottom:14px;border-bottom:1px solid #edf1f6}.question-card>header span{color:#1760d0;font-weight:850}.question-card>header b{margin-left:8px;padding:5px 8px;background:#eef4fa;border-radius:6px;font-size:8px}.question-card>header small{color:#8291a4;font-size:8px}.question-source{display:flex;gap:6px;margin-top:14px;padding:9px;color:#577089;background:#f5f8fc;border-radius:8px;font-size:8px}.question-source span{flex:1}.question-source i{color:#25815f}
.question-content{margin:19px 2px;color:#263e5b;font-size:14px;line-height:2}.question-content :deep(.exam-shared-context){display:block;max-height:min(52vh,520px);overflow:auto;margin-bottom:18px;padding:17px 18px;background:#f7f9fc;border:1px solid #dce6f2;border-left:4px solid #4382d7;border-radius:0 10px 10px 0}.question-content :deep(.exam-shared-context::before){content:"题目材料 · 请阅读后作答";display:block;position:sticky;top:-17px;z-index:1;margin:-17px -18px 14px;padding:9px 16px;color:#245b9c;background:#edf4fd;border-bottom:1px solid #d6e4f4;font-size:10px;font-weight:850;letter-spacing:.04em}.question-content :deep(.exam-inline-image),.answer-options :deep(.exam-inline-image){display:inline-block;max-width:100%;max-height:180px;vertical-align:middle}.question-content :deep(.exam-formula-image),.answer-options :deep(.exam-formula-image),.question-content :deep(.exam-inline-image[src*=".svg"]),.answer-options :deep(.exam-inline-image[src*=".svg"]){width:auto;height:clamp(18px,1.6em,26px);max-width:min(100%,18em);max-height:26px;margin:0 .08em;object-fit:contain;vertical-align:-.32em}.question-content :deep(.asset-load-failed),.answer-options :deep(.asset-load-failed){min-width:150px;min-height:38px;padding:8px;color:#9b3e47;border:1px dashed #d99ca3;background:#fff3f4;font-size:9px}
.answer-options{display:grid;gap:10px}.answer-options button{display:flex;align-items:center;gap:12px;min-height:56px;padding:11px 14px;text-align:left;border:1px solid #dfe6ef;background:#fbfcfe;border-radius:11px}.answer-options button>b{display:grid;flex:0 0 34px;height:34px;place-items:center;color:#1760d0;background:#eaf2ff;border-radius:9px}.answer-options button>span{flex:1}.answer-options button.selected{border-color:#4f91e9;background:#eff6ff}.answer-options button.selected>b{color:#fff;background:#1760d0}
.photo-answer{display:grid;gap:12px}.photo-guide{display:flex;gap:10px;padding:13px;color:#315d84;background:#edf7ff;border-radius:10px}.photo-guide span{display:grid;gap:4px}.photo-guide small{font-size:8px}.upload-zone{display:grid;min-height:145px;place-items:center;align-content:center;gap:7px;border:1px dashed #9ab9dd;background:#f8fbff;border-radius:11px}.upload-zone input{display:none}.upload-zone small{font-size:8px}.image-previews{display:flex;gap:9px}.image-previews img{width:110px;height:90px;object-fit:cover;border-radius:8px}.grade-photo{width:100%}.grade-feedback{padding:14px;color:#307052;background:#f0faf5;border-radius:10px}.grade-feedback>div{display:flex;gap:8px}.grade-feedback>div span{margin-left:auto}.grade-feedback.review{color:#855f16;background:#fff9e9}
.question-card>footer{display:flex;justify-content:space-between;margin-top:25px;padding-top:15px;border-top:1px solid #edf1f6}.question-card>footer button{display:flex;align-items:center;gap:6px;padding:10px 14px;border:1px solid #dae3ed;background:#fff;border-radius:8px}.question-card>footer .submit-paper{margin-left:auto;color:#fff;background:#1760d0}.result-hero{display:flex;justify-content:space-between;padding:28px 34px;color:#fff;background:linear-gradient(135deg,#123a72,#1766d2,#149e88);border-radius:17px}.result-hero h2{font-size:38px}.record-overview{padding:21px;border:1px solid #cfe2dc;background:linear-gradient(180deg,#f7fffc,#fff);border-radius:15px}.record-overview>header{display:flex;align-items:center;justify-content:space-between;gap:15px;padding-bottom:14px;border-bottom:1px solid #deeee9}.record-overview header small{color:#16816c;font-size:8px;font-weight:850}.record-overview h3{margin:4px 0 0;color:#254d46;font-size:15px}.record-overview header>span{color:#66827d;font-size:9px}.record-metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:15px 0}.record-metrics article{display:flex;align-items:center;gap:10px;padding:14px;color:#197662;background:#eaf8f4;border-radius:10px}.record-metrics article>div{display:grid;gap:3px}.record-metrics strong{color:#195c50;font-size:16px}.record-metrics small{color:#6d8681;font-size:8px}.knowledge-record-table{overflow:hidden;border:1px solid #e0ebe8;border-radius:10px}.record-row{display:grid;grid-template-columns:minmax(180px,1.5fr) repeat(4,minmax(90px,1fr));align-items:center;gap:10px;padding:10px 13px;color:#607770;border-top:1px solid #edf2f1;font-size:9px}.record-row:first-child{border-top:0}.record-row strong{color:#2d5650}.record-row b{color:#17816b}.record-row b.weak{color:#c05a50}.record-head{color:#819690;background:#f2f8f6;font-size:8px;font-weight:800}.result-grid{display:grid;grid-template-columns:1.1fr .9fr;gap:15px}.score-list{display:grid;gap:7px;margin-top:13px}.score-list article{display:flex;align-items:center;gap:9px;padding:9px;background:#f8fafd}.score-list article>div{display:grid;flex:1}.diagnosis-copy{display:grid;gap:12px;margin-top:15px}.diagnosis-copy>p{line-height:1.9}.new-paper{justify-self:center}.spin{animation:spin 1s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}
@media(max-width:1100px){.subject-tabs{grid-template-columns:repeat(5,1fr)}.paper-grid{grid-template-columns:repeat(2,1fr)}.exam-layout{grid-template-columns:1fr}.question-nav{position:static}.result-grid{grid-template-columns:1fr}.record-metrics{grid-template-columns:repeat(2,1fr)}.record-head{display:none}.record-row{grid-template-columns:minmax(150px,1.4fr) repeat(4,minmax(72px,1fr))}}
@media(max-width:720px){.exam-hero,.result-hero,.start-strip{align-items:flex-start;flex-direction:column}.exam-hero{padding:24px}.exam-hero aside{display:none}.subject-tabs{grid-template-columns:repeat(3,1fr)}.paper-grid{grid-template-columns:1fr}.question-card>header{flex-direction:column}.exam-toolbar{flex-wrap:wrap}.exam-toolbar>div{flex-basis:70%}}
/* Exam readability: one question/page, paged results, no inner reading scrollbar. */
.exam-diagnosis{font-size:15px;line-height:1.6}.question-content{font-size:16px;line-height:2}.question-content :deep(.exam-shared-context){max-height:none;overflow:visible;font-size:15px}.question-content :deep(.exam-shared-context::before){position:static;font-size:13px}
.subject-tabs button,.paper-grid button,.question-nav button,.answer-options button,.exam-action{font-size:14px}.answer-options button{min-height:54px}.question-nav header small,.paper-grid small,.score-list small{font-size:12px}.score-list strong,.diagnosis-copy strong{font-size:14px}.diagnosis-copy p{font-size:14px}
@media(max-width:720px){.record-row{grid-template-columns:1fr 1fr;gap:8px 14px;padding:14px}.record-row strong{grid-column:1/-1;font-size:15px}.record-row span,.record-row b{font-size:13px}.record-row span:nth-of-type(1)::before{content:"题数："}.record-row span:nth-of-type(2)::before{content:"累计："}.record-row span:nth-of-type(3)::before{content:"平均："}.record-row b::before{content:"正确率："}}
</style>
