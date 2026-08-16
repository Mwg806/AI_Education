<script setup lang="ts">
import {
  BookOpenCheck,
  Check,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  CircleAlert,
  Clock3,
  FileText,
  Languages,
  LoaderCircle,
  Mic,
  MicOff,
  PenLine,
  Plus,
  RotateCcw,
  Search,
  Send,
  Sparkles,
  Square,
  Target,
  Volume2,
} from "@lucide/vue";
import { computed, onMounted, onUnmounted, reactive, ref, watch } from "vue";

import {
  aiTaskPending,
  beginAiTask,
  completeAiTask,
  failAiTask,
  usePersistentAiState,
} from "@/lib/ai-runtime";
import {
  analyzeEnglishLanguageV2,
  assessEnglishSpeaking,
  executeEnglishLanguageTask,
  fetchEnglishDashboard,
  fetchEnglishReadingBank,
  generateEnglishWritingPrompts,
  saveEnglishReadingBankProgress,
  saveSelectedEnglishVocabulary,
  startEnglishGrammarTraining,
  startEnglishReadingBank,
  submitEnglishGrammarTraining,
  submitEnglishReadingBank,
  type EnglishDashboard,
  type EnglishGrammarTrainingSession,
  type EnglishLanguageTaskResult,
  type EnglishWritingPromptSet,
  type ReadingBankItem,
  type ReadingBankPaper,
  type ReadingBankProgress,
  type WordStudyDetail,
} from "@/lib/english-learning-client";

type Page =
  "reading" | "vocabulary" | "grammar" | "speaking" | "writing" | "records";

const props = withDefaults(defineProps<{ studentId: string; activeModule?: Page }>(), {
  activeModule: "reading",
});
const page = computed(() => props.activeModule);
const busy = ref("");
const grammarAssessing = ref(false);
const writingAssessing = ref(false);
const error = ref("");
const notice = ref("");
const dashboard = ref<EnglishDashboard | null>(null);

const catalog = ref<{
  reading_count: number;
  simulation_count: number;
  completed_count: number;
  items: ReadingBankItem[];
} | null>(null);
const search = ref("");
const category = ref<"all" | "simulation" | "past_exam">("simulation");
const readingPage = ref(1);
const PAGE_SIZE = 4;
const activeReading = ref<ReadingBankPaper | null>(null);
const readingProgress = ref<ReadingBankProgress | null>(null);
const answers = reactive<Record<string, number>>({});
const currentQuestionIndex = ref(0);
const elapsedSeconds = ref(0);
let timer: number | undefined;

const languageText = usePersistentAiState(
  props.studentId,
  "english-vocabulary-text",
  "",
);
const languageResult = usePersistentAiState<Awaited<
  ReturnType<typeof analyzeEnglishLanguageV2>
> | null>(props.studentId, "english-vocabulary-result", null);
const selectedWords = reactive<Record<string, boolean>>({});
const vocabularyPage = ref(1);

const grammarFocus = usePersistentAiState(
  props.studentId,
  "english-grammar-focus",
  "新高考英语核心语法综合",
);
const grammarSession = usePersistentAiState<EnglishGrammarTrainingSession | null>(
  props.studentId,
  "english-grammar-session",
  null,
);
const grammarAnswers = usePersistentAiState<Record<string, string>>(
  props.studentId,
  "english-grammar-answers",
  {},
);
const grammarStartedAt = usePersistentAiState(
  props.studentId,
  "english-grammar-started-at",
  0,
);
const grammarGenerationPending = aiTaskPending(
  props.studentId,
  "english-grammar-generation",
);

const speakingTopic = usePersistentAiState(
  props.studentId,
  "english-speaking-topic",
  "How technology changes the way students learn",
);
const recording = ref(false);
const speakingSeconds = ref(0);
const browserTranscript = ref("");
const speakingResult = usePersistentAiState<Awaited<
  ReturnType<typeof assessEnglishSpeaking>
> | null>(props.studentId, "english-speaking-result", null);
let recorder: MediaRecorder | null = null;
let speechRecognition: any = null;
let audioChunks: Blob[] = [];
let speakingTimer: number | undefined;

const writingTaskType = usePersistentAiState<
  "mixed" | "application" | "continuation"
>(props.studentId, "english-writing-task-type", "mixed");
const writingPromptSet = usePersistentAiState<EnglishWritingPromptSet | null>(
  props.studentId,
  "english-writing-prompt-set",
  null,
);
const selectedWritingPromptId = usePersistentAiState(
  props.studentId,
  "english-writing-prompt-id",
  "",
);
const writingText = usePersistentAiState(
  props.studentId,
  "english-writing-text",
  "",
);
const writingResult = usePersistentAiState<EnglishLanguageTaskResult | null>(
  props.studentId,
  "english-writing-result",
  null,
);
const writingStartedAt = usePersistentAiState(
  props.studentId,
  "english-writing-started-at",
  0,
);
const writingGenerationPending = aiTaskPending(
  props.studentId,
  "english-writing-generation",
);

const filteredReadings = computed(() => {
  const keyword = search.value.trim().toLowerCase();
  return (catalog.value?.items || []).filter(
    (item) =>
      (category.value === "all" || item.category === category.value) &&
      (!keyword ||
        item.title.toLowerCase().includes(keyword) ||
        item.topic.toLowerCase().includes(keyword)),
  );
});
const readingPageCount = computed(() =>
  Math.max(1, Math.ceil(filteredReadings.value.length / PAGE_SIZE)),
);
const pagedReadings = computed(() => {
  const start = (readingPage.value - 1) * PAGE_SIZE;
  return filteredReadings.value.slice(start, start + PAGE_SIZE);
});
const vocabularyWords = computed(
  () => languageResult.value?.vocabulary?.words || [],
);
const vocabularyPageCount = computed(() =>
  Math.max(1, Math.ceil(vocabularyWords.value.length / PAGE_SIZE)),
);
const pagedVocabulary = computed(() => {
  const start = (vocabularyPage.value - 1) * PAGE_SIZE;
  return vocabularyWords.value.slice(start, start + PAGE_SIZE);
});
watch([search, category], () => {
  readingPage.value = 1;
});

const currentQuestion = computed(
  () => activeReading.value?.questions[currentQuestionIndex.value] || null,
);
const answeredCount = computed(() => Object.keys(answers).length);
const selectedVocabulary = computed(() =>
  (languageResult.value?.vocabulary?.words || []).filter(
    (item) => selectedWords[item.word],
  ),
);
const activeWritingPrompt = computed(() =>
  writingPromptSet.value?.prompts.find(
    (item) => item.prompt_id === selectedWritingPromptId.value,
  ),
);
const moduleMeta = computed(() => {
  const copy: Record<
    Page,
    { eyebrow: string; title: string; description: string }
  > = {
    reading: {
      eyebrow: "READING TRAINING",
      title: "在真实语篇中练出证据意识。",
      description: "使用知识库阅读材料，按题作答、自动保存进度并完成证据复盘。",
    },
    vocabulary: {
      eyebrow: "VOCABULARY TRAINING",
      title: "逐词理解语境，建立自己的词汇网络。",
      description: "分析英语句子或短文中的词汇，并将有价值的词加入个人生词本。",
    },
    grammar: {
      eyebrow: "AI GRAMMAR TRAINING",
      title: "一次三题，只给诊断，不直接给答案。",
      description:
        "问鹿AI 根据真实学情动态出题，提交后指出不足、规则方向与自查路径。",
    },
    speaking: {
      eyebrow: "SPEAKING PRACTICE",
      title: "开口表达，让反馈落到下一句话。",
      description:
        "通过麦克风完成英语表达，获取转写、多维评分和继续交流的问题。",
    },
    writing: {
      eyebrow: "AI WRITING TRAINING",
      title: "从匹配学情的题目开始，获得客观写作评价。",
      description:
        "AI 生成应用文或读后续写任务，并按五个维度评价你的真实作答。",
    },
    records: {
      eyebrow: "LEARNING PROFILE",
      title: "把每次训练沉淀为下一次个性化依据。",
      description:
        "查看阅读完成度、生词与学习记录；这些证据会被其他学生智能体共同使用。",
    },
  };
  return copy[page.value];
});

function clearMessage() {
  error.value = "";
  notice.value = "";
}

function formatTime(seconds: number) {
  const minutes = Math.floor(seconds / 60);
  return (
    String(minutes).padStart(2, "0") +
    ":" +
    String(seconds % 60).padStart(2, "0")
  );
}

function difficultyLabel(value: number) {
  if (value < 0.55) return "基础";
  if (value < 0.72) return "中等";
  return "提高";
}

function writingScoreLabel(key: string) {
  return (
    {
      task_fulfillment: "任务完成",
      content: "内容质量",
      organization: "篇章组织",
      language: "语言表达",
      mechanics: "书写规范",
    }[key] || key
  );
}

function correctionLabel(key: string) {
  return (
    {
      grammar: "语法",
      vocabulary: "词汇",
      naturalness: "表达自然度",
      style: "文体",
      punctuation: "标点",
      logic: "逻辑",
    }[key] || "表达问题"
  );
}

function formatDuration(seconds: number | undefined) {
  if (!seconds) return "未记录";
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return minutes ? `${minutes} 分 ${remainder} 秒` : `${remainder} 秒`;
}

function formatRecordTime(value: string | undefined) {
  if (!value) return "时间未记录";
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function readingImage(url: string) {
  return url.startsWith("/api/") ? "/agent-api" + url : url;
}

async function loadPageData() {
  const [bank, profile] = await Promise.all([
    fetchEnglishReadingBank(),
    fetchEnglishDashboard(),
  ]);
  catalog.value = bank;
  dashboard.value = profile;
}

async function startReading(
  item: Pick<ReadingBankItem, "reading_id" | "title">,
  restart = false,
) {
  busy.value = item.reading_id;
  clearMessage();
  try {
    const result = await startEnglishReadingBank(item.reading_id, restart);
    activeReading.value = result.reading;
    readingProgress.value = result.progress;
    elapsedSeconds.value = result.progress.elapsed_seconds;
    currentQuestionIndex.value = 0;
    Object.keys(answers).forEach((key) => delete answers[key]);
    Object.assign(answers, result.progress.answers || {});
    startTimer();
    if (restart) notice.value = `已开始重做《${item.title}》`;
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "阅读训练打开失败";
  } finally {
    busy.value = "";
  }
}

async function restartReading(
  item: Pick<ReadingBankItem, "reading_id" | "title">,
) {
  if (
    !window.confirm(
      `确认重做《${item.title}》吗？将开始新一轮答题，题库列表会以新一轮进度为准。`,
    )
  )
    return;
  await startReading(item, true);
}

function startTimer() {
  if (timer) window.clearInterval(timer);
  if (readingProgress.value?.status !== "in_progress") return;
  let checkpointTick = 0;
  timer = window.setInterval(() => {
    elapsedSeconds.value += 1;
    checkpointTick += 1;
    if (checkpointTick >= 15 && activeReading.value) {
      checkpointTick = 0;
      void saveEnglishReadingBankProgress(
        activeReading.value.reading_id,
        { ...answers },
        elapsedSeconds.value,
      );
    }
  }, 1000);
}

async function leaveReading() {
  if (activeReading.value && readingProgress.value?.status === "in_progress") {
    await saveEnglishReadingBankProgress(
      activeReading.value.reading_id,
      { ...answers },
      elapsedSeconds.value,
    ).catch(() => undefined);
  }
  if (timer) window.clearInterval(timer);
  timer = undefined;
  activeReading.value = null;
  readingProgress.value = null;
  await loadPageData();
}

async function submitReading() {
  if (
    !activeReading.value ||
    answeredCount.value !== activeReading.value.question_count
  ) {
    error.value = "请完成全部题目后再提交";
    return;
  }
  busy.value = "reading-submit";
  clearMessage();
  try {
    const result = await submitEnglishReadingBank(
      activeReading.value.reading_id,
      { ...answers },
      elapsedSeconds.value,
    );
    readingProgress.value = result.progress;
    if (timer) window.clearInterval(timer);
    notice.value = "提交完成，答案与逐题解析现已开放";
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "阅读提交失败";
  } finally {
    busy.value = "";
  }
}

async function analyzeLanguage() {
  if (!languageText.value.trim()) {
    error.value = "请先输入英语句子或短文";
    return;
  }
  busy.value = "language";
  clearMessage();
  const taskId = beginAiTask({
    studentId: props.studentId,
    channel: "english-vocabulary",
    title: "词汇分析 AI 已完成",
    destination: { view: "english", module: "vocabulary" },
  });
  try {
    languageResult.value = await analyzeEnglishLanguageV2(
      languageText.value,
      "vocabulary",
    );
    Object.keys(selectedWords).forEach((key) => delete selectedWords[key]);
    vocabularyPage.value = 1;
    completeAiTask(taskId, "词汇分析结果已经生成。");
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "语言分析失败";
    failAiTask(taskId, "词汇分析未完成，点击返回查看原因。");
  } finally {
    busy.value = "";
  }
}

async function saveWords() {
  if (!selectedVocabulary.value.length) {
    error.value = "请至少选择一个词汇";
    return;
  }
  busy.value = "save-words";
  try {
    const result = await saveSelectedEnglishVocabulary(
      languageText.value,
      selectedVocabulary.value,
    );
    notice.value = "已将 " + result.saved_count + " 个词汇加入生词本";
    await loadPageData();
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "生词保存失败";
  } finally {
    busy.value = "";
  }
}

async function startSpeaking() {
  clearMessage();
  if (!speakingTopic.value.trim()) {
    error.value = "请先输入口语主题";
    return;
  }
  if (
    !navigator.mediaDevices?.getUserMedia ||
    typeof MediaRecorder === "undefined"
  ) {
    error.value = "当前浏览器不支持麦克风录音，请使用最新版 Chrome 或 Edge";
    return;
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    audioChunks = [];
    browserTranscript.value = "";
    recorder = new MediaRecorder(stream);
    recorder.ondataavailable = (event) => {
      if (event.data.size) audioChunks.push(event.data);
    };
    recorder.start();
    const Recognition =
      (window as any).SpeechRecognition ||
      (window as any).webkitSpeechRecognition;
    if (Recognition) {
      speechRecognition = new Recognition();
      speechRecognition.lang = "en-US";
      speechRecognition.continuous = true;
      speechRecognition.interimResults = true;
      speechRecognition.onresult = (event: any) => {
        let text = "";
        for (let index = 0; index < event.results.length; index += 1) {
          text += event.results[index][0].transcript + " ";
        }
        browserTranscript.value = text.trim();
      };
      speechRecognition.start();
    }
    recording.value = true;
    speakingSeconds.value = 0;
    speakingTimer = window.setInterval(() => {
      speakingSeconds.value += 1;
      if (speakingSeconds.value >= 300) void stopSpeaking();
    }, 1000);
  } catch {
    error.value = "无法获取麦克风权限，请在浏览器地址栏允许麦克风访问";
  }
}

async function stopSpeaking() {
  if (!recorder || recorder.state === "inactive") return;
  busy.value = "speaking";
  recording.value = false;
  if (speakingTimer) window.clearInterval(speakingTimer);
  speechRecognition?.stop();
  const stopped = new Promise<void>((resolve) => {
    if (recorder) recorder.onstop = () => resolve();
  });
  recorder.stop();
  await stopped;
  recorder.stream.getTracks().forEach((track) => track.stop());
  const audio = new Blob(audioChunks, {
    type: recorder.mimeType || "audio/webm",
  });
  const taskId = beginAiTask({
    studentId: props.studentId,
    channel: "english-speaking",
    title: "口语训练 AI 已完成",
    destination: { view: "english", module: "speaking" },
  });
  try {
    speakingResult.value = await assessEnglishSpeaking(
      audio,
      speakingTopic.value,
      Math.max(1, speakingSeconds.value),
      browserTranscript.value,
    );
    notice.value = "口语转写和多维评价已经完成，录音原文件未保存";
    completeAiTask(taskId, "口语转写和多维评价已经生成。");
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "口语评价失败";
    failAiTask(taskId, "口语评价未完成，点击返回查看原因。");
  } finally {
    busy.value = "";
    recorder = null;
  }
}

async function loadGrammarBatch() {
  if (grammarGenerationPending.value) return;
  if (!grammarFocus.value.trim()) {
    error.value = "请填写本轮语法训练重点";
    return;
  }
  clearMessage();
  const taskId = beginAiTask({
    studentId: props.studentId,
    channel: "english-grammar-generation",
    title: "语法训练题已生成",
    pendingMessage: "语法训练 AI 正在出题",
    destination: { view: "english", module: "grammar" },
  });
  try {
    grammarSession.value = await startEnglishGrammarTraining(
      grammarFocus.value.trim(),
    );
    grammarAnswers.value = {};
    grammarStartedAt.value = Date.now();
    notice.value = "新一批 3 道语法题已生成，请独立完成后统一提交";
    completeAiTask(taskId, "新一批 3 道语法题已经生成，点击继续训练。");
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "语法题生成失败";
    failAiTask(taskId, "语法题生成失败，点击返回后可以重新尝试。");
  }
}

async function submitGrammarBatch() {
  if (!grammarSession.value) return;
  const submitted = grammarSession.value.questions.map((item) => ({
    question_id: item.question_id,
    answer: (grammarAnswers.value[item.question_id] || "").trim(),
  }));
  if (submitted.some((item) => !item.answer)) {
    error.value = "请完整回答 3 道语法题后再提交";
    return;
  }
  grammarAssessing.value = true;
  clearMessage();
  const taskId = beginAiTask({
    studentId: props.studentId,
    channel: "english-grammar",
    title: "语法训练 AI 已完成",
    destination: { view: "english", module: "grammar" },
  });
  try {
    grammarSession.value = await submitEnglishGrammarTraining(
      grammarSession.value.session_id,
      submitted,
      Math.max(
        1,
        Math.round((Date.now() - (grammarStartedAt.value || Date.now())) / 1000),
      ),
    );
    notice.value = "评阅完成：问鹿AI 只提供诊断与自查路径，不会直接显示答案";
    completeAiTask(taskId, "本轮 3 道题的诊断与自查路径已经生成。");
    void loadPageData().catch(() => undefined);
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "语法评阅失败";
    failAiTask(taskId, "语法评阅未完成，点击返回查看原因。");
  } finally {
    grammarAssessing.value = false;
  }
}

async function loadWritingPrompts() {
  if (writingGenerationPending.value) return;
  clearMessage();
  const taskId = beginAiTask({
    studentId: props.studentId,
    channel: "english-writing-generation",
    title: "写作训练题已生成",
    pendingMessage: "写作训练 AI 正在出题",
    destination: { view: "english", module: "writing" },
  });
  try {
    writingPromptSet.value = await generateEnglishWritingPrompts(
      writingTaskType.value,
    );
    selectedWritingPromptId.value =
      writingPromptSet.value.prompts[0]?.prompt_id || "";
    writingText.value = "";
    writingResult.value = null;
    writingStartedAt.value = Date.now();
    notice.value = "已根据当前学情生成新一批写作题";
    completeAiTask(taskId, "新一批个性化写作题已经生成，点击继续训练。");
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "写作题生成失败";
    failAiTask(taskId, "写作题生成失败，点击返回后可以重新尝试。");
  }
}

function selectWritingPrompt(promptId: string) {
  selectedWritingPromptId.value = promptId;
  writingText.value = "";
  writingResult.value = null;
  writingStartedAt.value = Date.now();
  clearMessage();
}

async function assessWriting() {
  const prompt = activeWritingPrompt.value;
  if (!prompt) {
    error.value = "请先选择一道写作题";
    return;
  }
  if (!writingText.value.trim()) {
    error.value = "请先完成这道写作题";
    return;
  }
  writingAssessing.value = true;
  clearMessage();
  const taskId = beginAiTask({
    studentId: props.studentId,
    channel: "english-writing",
    title: "写作训练 AI 已完成",
    destination: { view: "english", module: "writing" },
  });
  try {
    writingResult.value = await executeEnglishLanguageTask({
      task_type: "writing_revision",
      source_text: writingText.value,
      user_message: [
        `写作题目：${prompt.title}`,
        `任务材料：${prompt.prompt}`,
        `明确要求：${prompt.requirements.join("；")}`,
        `目标字数：${prompt.word_count}`,
        "请严格依据上述题目，对学生的真实作答进行客观评价；按任务完成度、内容、组织、语言和规范五项评分，并指出有文本证据的优势与不足。",
      ].join("\n"),
      response_mode: "guided",
      detail_level: "detailed",
      revision_level: 1,
      include_exercises: true,
      include_learning_record: true,
      exam_section: "writing",
      training_title: prompt.title,
      training_prompt: prompt.prompt,
      training_requirements: prompt.requirements,
      target_word_count: prompt.word_count,
      elapsed_seconds: Math.max(
        1,
        Math.round((Date.now() - (writingStartedAt.value || Date.now())) / 1000),
      ),
    });
    notice.value = "写作客观评价已完成，本次结果已进入共享学情档案";
    completeAiTask(taskId, `《${prompt.title}》的客观五维评价已经生成。`);
    void loadPageData().catch(() => undefined);
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "写作评价失败";
    failAiTask(taskId, "写作评价未完成，点击返回查看原因。");
  } finally {
    writingAssessing.value = false;
  }
}

watch(
  () => props.activeModule,
  (next) => {
    clearMessage();
    if (next !== "reading" && activeReading.value) void leaveReading();
    if (
      next === "grammar" &&
      !grammarSession.value &&
      !grammarGenerationPending.value
    )
      void loadGrammarBatch();
    if (
      next === "writing" &&
      !writingPromptSet.value &&
      !writingGenerationPending.value
    )
      void loadWritingPrompts();
  },
  { immediate: true },
);

onMounted(() => {
  void loadPageData().catch((cause) => {
    error.value =
      cause instanceof Error ? cause.message : "英语学习数据加载失败";
  });
});
onUnmounted(() => {
  if (timer) window.clearInterval(timer);
  if (speakingTimer) window.clearInterval(speakingTimer);
  recorder?.stream.getTracks().forEach((track) => track.stop());
});
</script>

<template>
  <div class="english-v2">
    <section class="hero student-module-hero">
      <div>
        <span><Sparkles :size="15" /> {{ moduleMeta.eyebrow }}</span>
        <h1>{{ moduleMeta.title }}</h1>
        <p>{{ moduleMeta.description }}</p>
      </div>
      <aside>
        <strong>{{ catalog?.completed_count || 0 }}</strong>
        <span>已完成阅读</span>
        <i />
        <strong>{{ dashboard?.learner_profile.evidence_count || 0 }}</strong>
        <span>有效学习证据</span>
      </aside>
    </section>

    <div v-if="error" class="message error">
      <CircleAlert :size="17" />{{ error }}
    </div>
    <div v-if="notice" class="message success">
      <CheckCircle2 :size="17" />{{ notice }}
    </div>

    <template v-if="page === 'reading'">
      <template v-if="!activeReading">
        <section class="panel bank-heading">
          <div>
            <small>READING BANK</small>
            <h2>知识库阅读题列表</h2>
            <p>
              只有点击“开始答题”后才计时；未提交的训练会保留已用时间和未完成状态。
            </p>
          </div>
          <div class="bank-tools">
            <label
              ><Search :size="16" /><input
                v-model="search"
                placeholder="搜索年份、试卷或主题"
            /></label>
            <select v-model="category">
              <option value="simulation">模拟与联考</option>
              <option value="past_exam">高考真题</option>
              <option value="all">全部阅读</option>
            </select>
          </div>
        </section>
        <section class="reading-list">
          <article
            v-for="item in pagedReadings"
            :key="item.reading_id"
            class="reading-row"
          >
            <span class="paper-letter">{{ item.section || "R" }}</span>
            <div class="reading-info">
              <div>
                <h3>{{ item.title }}</h3>
                <span :class="['status', item.status]">{{
                  item.status === "completed"
                    ? "已做完"
                    : item.status === "in_progress"
                      ? "未做完"
                      : "未开始"
                }}</span>
              </div>
              <p>
                {{ item.topic }} · {{ item.word_count }} 词 ·
                {{ item.question_count }} 题 ·
                {{ difficultyLabel(item.difficulty) }}
              </p>
              <small v-if="item.status !== 'not_started'"
                ><Clock3 :size="13" />已作答
                {{ formatTime(item.elapsed_seconds)
                }}<template v-if="item.status === 'completed'">
                  · 得分 {{ Math.round((item.score || 0) * 100) }}%</template
                ><template v-else>
                  · 已答 {{ item.answered_count }}/{{
                    item.question_count
                  }}</template
                ></small
              >
            </div>
            <div class="reading-actions">
              <button :disabled="Boolean(busy)" @click="startReading(item)">
                <LoaderCircle
                  v-if="busy === item.reading_id"
                  class="spin"
                  :size="16"
                />
                <template v-else>{{
                  item.status === "in_progress"
                    ? "继续答题"
                    : item.status === "completed"
                      ? "查看完成状态"
                      : "开始答题"
                }}</template>
                <ChevronRight :size="15" />
              </button>
              <button
                v-if="item.status === 'completed'"
                class="redo"
                :disabled="Boolean(busy)"
                @click="restartReading(item)"
              >
                <RotateCcw :size="15" />重做
              </button>
            </div>
          </article>
          <div v-if="!filteredReadings.length" class="empty">
            没有找到符合条件的阅读题。
          </div>
          <div v-if="filteredReadings.length" class="pagination">
            <button
              :disabled="readingPage === 1"
              @click="readingPage = Math.max(1, readingPage - 1)"
            >
              <ChevronLeft :size="16" />上一页
            </button>
            <span>
              第 <b>{{ readingPage }}</b> / {{ readingPageCount }} 页
              <small>共 {{ filteredReadings.length }} 套</small>
            </span>
            <button
              :disabled="readingPage === readingPageCount"
              @click="readingPage = Math.min(readingPageCount, readingPage + 1)"
            >
              下一页<ChevronRight :size="16" />
            </button>
          </div>
        </section>
      </template>

      <template v-else>
        <section class="test-toolbar">
          <button @click="leaveReading">
            <ChevronLeft :size="16" />返回题库
          </button>
          <div>
            <strong>{{ activeReading.title }}</strong
            ><span>{{ activeReading.topic }}</span>
          </div>
          <b><Clock3 :size="17" />{{ formatTime(elapsedSeconds) }}</b>
        </section>
        <div class="reading-test">
          <article class="passage">
            <header>
              <small>PASSAGE {{ activeReading.section }}</small>
              <h2>{{ activeReading.title }}</h2>
            </header>
            <img
              v-for="image in activeReading.images"
              :key="image"
              :src="readingImage(image)"
              alt="阅读题配图"
            />
            <p
              v-for="(paragraph, index) in activeReading.article.split(
                /\n\s*\n/,
              )"
              :key="index"
            >
              {{ paragraph }}
            </p>
          </article>
          <section class="questions">
            <template
              v-if="
                readingProgress?.status === 'in_progress' && currentQuestion
              "
            >
              <header>
                <span
                  >QUESTION {{ currentQuestionIndex + 1 }} /
                  {{ activeReading.question_count }}</span
                ><progress
                  :value="currentQuestionIndex + 1"
                  :max="activeReading.question_count"
                />
              </header>
              <h3>{{ currentQuestion.stem }}</h3>
              <div class="options">
                <button
                  v-for="(option, index) in currentQuestion.options"
                  :key="option"
                  :class="{
                    selected: answers[currentQuestion.question_id] === index,
                  }"
                  @click="answers[currentQuestion.question_id] = index"
                >
                  <b>{{ String.fromCharCode(65 + index) }}</b
                  ><span>{{ option }}</span
                  ><Check
                    v-if="answers[currentQuestion.question_id] === index"
                    :size="16"
                  />
                </button>
              </div>
              <footer>
                <button
                  :disabled="currentQuestionIndex === 0"
                  @click="currentQuestionIndex--"
                >
                  上一题</button
                ><button
                  v-if="currentQuestionIndex < activeReading.question_count - 1"
                  class="primary"
                  :disabled="answers[currentQuestion.question_id] == null"
                  @click="currentQuestionIndex++"
                >
                  下一题<ChevronRight :size="15" /></button
                ><button
                  v-else
                  class="primary"
                  :disabled="
                    answeredCount !== activeReading.question_count ||
                    busy === 'reading-submit'
                  "
                  @click="submitReading"
                >
                  提交并查看解析
                </button>
              </footer>
            </template>
            <template v-else>
              <header class="result-head">
                <div>
                  <small>RESULT</small>
                  <h2>本次阅读结果</h2>
                </div>
                <strong
                  >{{
                    Math.round((readingProgress?.score || 0) * 100)
                  }}%</strong
                >
              </header>
              <article
                v-for="(item, index) in readingProgress?.result"
                :key="item.question_id"
                :class="['result-item', { correct: item.is_correct }]"
              >
                <span>{{ index + 1 }}</span>
                <div>
                  <strong
                    >{{ item.is_correct ? "回答正确" : "回答错误" }} · 你的选择
                    {{ String.fromCharCode(65 + item.selected_option) }} ·
                    正确答案
                    {{ String.fromCharCode(65 + item.correct_option) }}</strong
                  >
                  <p>
                    {{
                      item.explanation || "请回到原文定位对应证据并复盘干扰项。"
                    }}
                  </p>
                </div>
              </article>
              <div class="result-actions">
                <button
                  class="redo"
                  :disabled="Boolean(busy)"
                  @click="restartReading(activeReading)"
                >
                  <RotateCcw :size="15" />重新答题
                </button>
                <button class="primary back-bank" @click="leaveReading">
                  完成复盘，返回题库
                </button>
              </div>
            </template>
          </section>
        </div>
      </template>
    </template>

    <template v-else-if="page === 'vocabulary'">
      <section class="panel language-input">
        <header>
          <div>
            <small>VOCABULARY TRAINING</small>
            <h2>语境词汇训练</h2>
            <p>
              输入英语句子或短文，AI
              会逐词解释当前语境义、搭配、句中作用与易错点。
            </p>
          </div>
          <Languages :size="25" />
        </header>
        <textarea
          v-model="languageText"
          rows="7"
          placeholder="输入一个英语句子或一段英语短文……"
        />
        <button
          class="primary analyze"
          :disabled="Boolean(busy)"
          @click="analyzeLanguage"
        >
          <LoaderCircle
            v-if="busy === 'language'"
            class="spin"
            :size="17"
          /><Sparkles v-else :size="17" />开始逐词分析
        </button>
      </section>
      <section v-if="languageResult?.vocabulary" class="word-grid">
        <header class="panel word-summary">
          <div>
            <small>WORD BY WORD</small>
            <h2>
              共分析 {{ languageResult.vocabulary.words.length }} 个不同词汇
            </h2>
            <p>{{ languageResult.vocabulary.summary }}</p>
          </div>
          <button
            class="primary"
            :disabled="!selectedVocabulary.length || busy === 'save-words'"
            @click="saveWords"
          >
            <Plus :size="16" />加入生词本（{{ selectedVocabulary.length }}）
          </button>
        </header>
        <article
          v-for="item in pagedVocabulary"
          :key="item.word"
          :class="{ picked: selectedWords[item.word] }"
        >
          <label
            ><input v-model="selectedWords[item.word]" type="checkbox" /><span
              >选择</span
            ></label
          >
          <header>
            <h3>{{ item.word }}</h3>
            <span
              >{{ item.phonetic }} ·
              {{ item.part_of_speech || "词性待结合语境" }}</span
            ><b>{{ item.difficulty }}</b>
          </header>
          <strong>{{ item.contextual_meaning }}</strong>
          <dl>
            <div>
              <dt>构词</dt>
              <dd>{{ item.morphology || "基础词形" }}</dd>
            </div>
            <div>
              <dt>句中作用</dt>
              <dd>{{ item.sentence_role }}</dd>
            </div>
            <div>
              <dt>常见搭配</dt>
              <dd>{{ item.collocations.join(" · ") || "结合原句积累" }}</dd>
            </div>
            <div>
              <dt>例句</dt>
              <dd>{{ item.example }}</dd>
            </div>
            <div>
              <dt>易错点</dt>
              <dd>{{ item.common_mistake }}</dd>
            </div>
          </dl>
        </article>
        <div v-if="vocabularyWords.length" class="pagination word-pagination">
          <button
            :disabled="vocabularyPage === 1"
            @click="vocabularyPage = Math.max(1, vocabularyPage - 1)"
          >
            <ChevronLeft :size="16" />上一页
          </button>
          <span>
            第 <b>{{ vocabularyPage }}</b> / {{ vocabularyPageCount }} 页
            <small
              >本页显示 {{ pagedVocabulary.length }} 个，共
              {{ vocabularyWords.length }} 个词</small
            >
          </span>
          <button
            :disabled="vocabularyPage === vocabularyPageCount"
            @click="
              vocabularyPage = Math.min(vocabularyPageCount, vocabularyPage + 1)
            "
          >
            下一页<ChevronRight :size="16" />
          </button>
        </div>
      </section>
    </template>

    <template v-else-if="page === 'grammar'">
      <section class="panel grammar-training-head">
        <header>
          <div>
            <small>问鹿AI · THREE QUESTIONS PER ROUND</small>
            <h2>AI 语法训练</h2>
            <p>
              每轮只生成 3
              道题。评阅会指出不足与检查路径，但不会直接给出参考答案。
            </p>
          </div>
          <Sparkles :size="25" />
        </header>
        <div class="grammar-controls">
          <label>
            <span>本轮训练重点</span>
            <input
              v-model="grammarFocus"
              :disabled="
                Boolean(busy) || grammarAssessing || grammarGenerationPending
              "
              placeholder="例如：定语从句、时态综合、语法填空"
            />
          </label>
          <button
            class="primary"
            :disabled="
              Boolean(busy) || grammarAssessing || grammarGenerationPending
            "
            @click="loadGrammarBatch"
          >
            <LoaderCircle
              v-if="grammarGenerationPending"
              class="spin"
              :size="17"
            /><RotateCcw v-else :size="17" />{{
              grammarSession ? "换一批" : "生成 3 道题"
            }}
          </button>
        </div>
        <div v-if="grammarSession" class="ai-context-strip">
          <span>问鹿AI · 个性化生成</span>
          <span>本批 3 题</span>
          <span>
            {{
              grammarSession.personalization.mode === "evidence_personalized"
                ? `已参考 ${grammarSession.personalization.evidence_count} 条真实学情证据`
                : "当前按基础画像出题"
            }}
          </span>
        </div>
      </section>

      <section
        v-if="grammarGenerationPending && !grammarSession"
        class="panel empty"
      >
        <LoaderCircle class="spin" :size="27" />问鹿AI 正在匹配学情并生成 3
        道新题……
      </section>

      <section v-else-if="grammarSession" class="grammar-question-list">
        <header class="panel grammar-round-title">
          <div>
            <small>{{
              grammarSession.status === "completed"
                ? "ROUND REVIEW"
                : "CURRENT ROUND"
            }}</small>
            <h2>{{ grammarSession.title }}</h2>
            <p>{{ grammarSession.display_text }}</p>
          </div>
          <strong v-if="grammarSession.assessment">
            {{ grammarSession.assessment.overall_score }}
            <small>综合分</small>
          </strong>
        </header>

        <article
          v-for="(item, index) in grammarSession.questions"
          :key="item.question_id"
          class="panel grammar-question-card"
        >
          <header>
            <span>{{ String(index + 1).padStart(2, "0") }}</span>
            <div>
              <small>{{ item.grammar_focus }} · {{ item.difficulty }}</small>
              <h3>{{ item.prompt }}</h3>
              <p>{{ item.instruction }}</p>
            </div>
          </header>
          <textarea
            v-model="grammarAnswers[item.question_id]"
            rows="3"
            :disabled="
              grammarSession.status === 'completed' ||
              grammarAssessing ||
              grammarGenerationPending
            "
            :placeholder="`在这里输入第 ${index + 1} 题答案……`"
          />
          <template
            v-for="feedback in grammarSession.assessment?.feedback.filter(
              (entry) => entry.question_id === item.question_id,
            ) || []"
            :key="feedback.question_id"
          >
            <div
              :class="['grammar-feedback', { correct: feedback.is_correct }]"
            >
              <header>
                <strong>{{
                  feedback.is_correct ? "作答正确" : "需要修正"
                }}</strong>
                <b>{{ feedback.score }} 分</b>
              </header>
              <p>{{ feedback.feedback }}</p>
              <dl>
                <div v-if="feedback.defect_tag">
                  <dt>问题类型</dt>
                  <dd>{{ feedback.defect_tag }}</dd>
                </div>
                <div>
                  <dt>改进步骤</dt>
                  <dd>{{ feedback.improvement_step }}</dd>
                </div>
                <div>
                  <dt>自查问题</dt>
                  <dd>{{ feedback.self_check_question }}</dd>
                </div>
              </dl>
            </div>
          </template>
        </article>

        <button
          v-if="grammarSession.status === 'in_progress'"
          class="primary grammar-submit"
          :disabled="
            Boolean(busy) || grammarAssessing || grammarGenerationPending
          "
          @click="submitGrammarBatch"
        >
          <LoaderCircle v-if="grammarAssessing" class="spin" :size="17" /><Send
            v-else
            :size="17"
          />提交 3 题并获取诊断
        </button>

        <section v-if="grammarSession.assessment" class="panel grammar-summary">
          <header>
            <div>
              <small>OBJECTIVE DIAGNOSIS</small>
              <h2>本轮学情诊断</h2>
            </div>
            <Target :size="24" />
          </header>
          <p>{{ grammarSession.assessment.summary }}</p>
          <div>
            <article>
              <strong>已经掌握</strong>
              <span
                v-for="item in grammarSession.assessment.strengths"
                :key="item"
                >{{ item }}</span
              >
            </article>
            <article>
              <strong>当前不足</strong>
              <span
                v-for="item in grammarSession.assessment.weaknesses"
                :key="item"
                >{{ item }}</span
              >
            </article>
          </div>
          <footer>
            <b>下一步：</b>{{ grammarSession.assessment.next_focus }}
            <button class="primary" @click="loadGrammarBatch">
              <RotateCcw :size="16" />按诊断换一批
            </button>
          </footer>
        </section>
      </section>
    </template>

    <template v-else-if="page === 'speaking'">
      <div class="speaking-layout">
        <section class="panel speaking-control">
          <header>
            <div>
              <small>MICROPHONE CONVERSATION</small>
              <h2>口语主题交流</h2>
              <p>
                输入主题后点击麦克风，用英语自然表达；结束后自动转写并由模型评价。
              </p>
            </div>
            <Volume2 :size="25" />
          </header>
          <label
            ><span>本轮交流主题</span
            ><input v-model="speakingTopic" :disabled="recording"
          /></label>
          <div :class="['recorder', { active: recording }]">
            <span
              ><Mic v-if="recording" :size="35" /><MicOff
                v-else
                :size="35" /></span
            ><strong>{{
              recording ? "正在倾听你的英语表达" : "准备开始口语练习"
            }}</strong
            ><b>{{ formatTime(speakingSeconds) }}</b>
            <p v-if="browserTranscript">{{ browserTranscript }}</p>
          </div>
          <button
            v-if="!recording"
            class="primary mic-button"
            :disabled="Boolean(busy)"
            @click="startSpeaking"
          >
            <Mic :size="18" />开始录音
          </button>
          <button v-else class="stop-button" @click="stopSpeaking">
            <Square :size="17" />结束并评分
          </button>
          <p class="privacy">
            录音仅用于本次转写，服务器不保存音频原文件；语音清晰度分数基于转写可识别性。
          </p>
        </section>
        <section class="panel speaking-feedback">
          <header>
            <div>
              <small>AI SPEAKING COACH</small>
              <h2>口语评价</h2>
            </div>
            <Target :size="24" />
          </header>
          <div v-if="busy === 'speaking'" class="empty">
            <LoaderCircle class="spin" :size="28" />正在转写录音并生成多维评价……
          </div>
          <div v-else-if="!speakingResult" class="empty">
            完成一次录音后，这里会显示转写、评分、修改建议和下一轮问题。
          </div>
          <template v-else>
            <div class="transcript">
              <small>语音转写</small>
              <p>{{ speakingResult.transcript }}</p>
            </div>
            <div class="score-grid">
              <article
                v-for="(score, key) in speakingResult.assessment.scores"
                :key="key"
              >
                <span>{{ key }}</span
                ><strong>{{ score }}</strong
                ><progress :value="score" max="100" />
              </article>
            </div>
            <section>
              <h3>具体改进</h3>
              <p
                v-for="item in speakingResult.assessment.improvements"
                :key="item"
              >
                {{ item }}
              </p>
            </section>
            <section class="coach-reply">
              <small>MODEL REPLY</small>
              <p>{{ speakingResult.assessment.reply }}</p>
              <strong>{{ speakingResult.assessment.next_question }}</strong>
            </section>
          </template>
        </section>
      </div>
    </template>

    <template v-else-if="page === 'writing'">
      <section class="panel writing-prompt-bank">
        <header>
          <div>
            <small>问鹿AI · WRITING PROMPTS</small>
            <h2>选择本轮写作任务</h2>
            <p>AI 会结合已验证学情生成训练题；换一批会创建全新题组。</p>
          </div>
          <div class="writing-prompt-actions">
            <select
              v-model="writingTaskType"
              :disabled="
                Boolean(busy) || writingAssessing || writingGenerationPending
              "
            >
              <option value="mixed">应用文 + 读后续写</option>
              <option value="application">只练应用文</option>
              <option value="continuation">只练读后续写</option>
            </select>
            <button
              class="primary"
              :disabled="
                Boolean(busy) || writingAssessing || writingGenerationPending
              "
              @click="loadWritingPrompts"
            >
              <LoaderCircle
                v-if="writingGenerationPending"
                class="spin"
                :size="16"
              /><RotateCcw v-else :size="16" />换一批
            </button>
          </div>
        </header>
        <div v-if="writingPromptSet" class="ai-context-strip">
          <span>问鹿AI · 个性化生成</span>
          <span>本批 {{ writingPromptSet.prompts.length }} 题</span>
          <span>
            {{
              writingPromptSet.personalization.mode === "evidence_personalized"
                ? `已参考 ${writingPromptSet.personalization.evidence_count} 条真实学情证据`
                : "当前按基础画像命题"
            }}
          </span>
        </div>
        <div
          v-if="writingGenerationPending && !writingPromptSet"
          class="empty"
        >
          <LoaderCircle class="spin" :size="27" />问鹿AI
          正在生成匹配当前学情的写作题……
        </div>
        <div v-else-if="writingPromptSet" class="writing-prompt-grid">
          <button
            v-for="(item, index) in writingPromptSet.prompts"
            :key="item.prompt_id"
            :class="{ active: selectedWritingPromptId === item.prompt_id }"
            :disabled="writingAssessing || writingGenerationPending"
            @click="selectWritingPrompt(item.prompt_id)"
          >
            <span>0{{ index + 1 }}</span>
            <small>{{
              item.task_type === "application" ? "应用文" : "读后续写"
            }}</small>
            <strong>{{ item.title }}</strong>
            <p>{{ item.prompt }}</p>
            <footer>
              {{ item.suggested_minutes }} 分钟 · {{ item.word_count }}
            </footer>
          </button>
        </div>
      </section>

      <div v-if="activeWritingPrompt" class="writing-layout">
        <section class="panel writing-answer">
          <header>
            <div>
              <small>SELECTED TASK</small>
              <h2>{{ activeWritingPrompt.title }}</h2>
            </div>
            <PenLine :size="23" />
          </header>
          <div class="writing-brief">
            <p>{{ activeWritingPrompt.prompt }}</p>
            <ul>
              <li v-for="item in activeWritingPrompt.requirements" :key="item">
                {{ item }}
              </li>
            </ul>
            <span
              >{{ activeWritingPrompt.word_count }} · 建议
              {{ activeWritingPrompt.suggested_minutes }} 分钟</span
            >
          </div>
          <textarea
            v-model="writingText"
            rows="17"
            :disabled="writingAssessing || writingGenerationPending"
            placeholder="请严格根据上方题目，用英语完成作答……"
          />
          <button
            class="primary analyze"
            :disabled="
              Boolean(busy) || writingAssessing || writingGenerationPending
            "
            @click="assessWriting"
          >
            <LoaderCircle
              v-if="writingAssessing"
              class="spin"
              :size="16"
            /><Send v-else :size="16" />提交真实作答并评价
          </button>
        </section>

        <section class="panel writing-feedback">
          <header>
            <div>
              <small>OBJECTIVE ASSESSMENT</small>
              <h2>客观五维评价</h2>
            </div>
            <Target :size="23" />
          </header>
          <div v-if="writingAssessing" class="empty">
            <LoaderCircle class="spin" :size="27" />问鹿AI
            正在核对题目要求与学生作答……
          </div>
          <div v-else-if="!writingResult" class="empty">
            完成左侧题目并提交后，这里会显示任务完成、内容、组织、语言和规范评价。
          </div>
          <template v-else>
            <section
              v-if="writingResult.answer.writing_assessment"
              class="writing-profile"
            >
              <header>
                <div>
                  <small>本次写作水平</small>
                  <strong>{{
                    writingResult.answer.writing_assessment.overall_level
                  }}</strong>
                </div>
                <span>{{
                  writingResult.answer.writing_assessment
                    .historical_comparison_basis === "compared_with_history"
                    ? "已结合近期写作档案比较"
                    : "仅依据本次作答评价"
                }}</span>
              </header>
              <h3>当前水平画像</h3>
              <p>
                {{
                  writingResult.answer.writing_assessment.current_level_summary
                }}
              </p>
              <h3>已经体现的提升与优势</h3>
              <p>{{ writingResult.answer.writing_assessment.progress_summary }}</p>
              <h3>当前不足与形成原因</h3>
              <p>{{ writingResult.answer.writing_assessment.limitation_summary }}</p>
              <h3>下一阶段目标</h3>
              <p>{{ writingResult.answer.writing_assessment.next_stage_goal }}</p>
            </section>
            <div class="score-grid">
              <article
                v-for="(score, key) in writingResult.answer.scores"
                :key="key"
              >
                <span>{{ writingScoreLabel(String(key)) }}</span>
                <strong>{{ score ?? "—" }}</strong>
                <progress :value="score || 0" max="100" />
              </article>
            </div>
            <section
              v-if="writingResult.answer.writing_assessment"
              class="writing-dimensions"
            >
              <article
                v-for="item in writingResult.answer.writing_assessment.dimensions"
                :key="item.dimension"
              >
                <header>
                  <strong>{{ writingScoreLabel(item.dimension) }}</strong>
                  <span>{{ item.performance_label }} · {{ item.score }} 分</span>
                </header>
                <blockquote>原文证据：“{{ item.evidence_quote }}”</blockquote>
                <p>{{ item.evidence_analysis }}</p>
                <footer><b>怎么提升：</b>{{ item.actionable_advice }}</footer>
              </article>
            </section>
            <section class="writing-evidence">
              <h3>有证据的优势</h3>
              <p v-for="item in writingResult.answer.strengths" :key="item">
                {{ item }}
              </p>
            </section>
            <section class="writing-evidence priority">
              <h3>优先改进</h3>
              <p
                v-for="item in writingResult.answer.priority_improvements"
                :key="item"
              >
                {{ item }}
              </p>
            </section>
            <article
              v-for="item in writingResult.answer.corrections"
              :key="item.original + item.category"
              class="grammar-issue"
            >
              <strong
                >{{ correctionLabel(item.category) }} · {{ item.original }}</strong
              >
              <p>{{ item.explanation }}</p>
            </article>
          </template>
        </section>
      </div>
    </template>

    <template v-else>
      <section class="records-grid">
        <article class="panel">
          <small>VOCABULARY BOOK</small>
          <h2>我的生词本</h2>
          <strong
            >{{
              dashboard?.learning_records.vocabulary.length || 0
            }}
            个词</strong
          >
        </article>
        <article class="panel">
          <small>READING COMPLETED</small>
          <h2>完成阅读</h2>
          <strong
            >{{ catalog?.completed_count || 0 }} /
            {{ catalog?.reading_count || 0 }}</strong
          >
        </article>
        <article class="panel">
          <small>GRAMMAR ARCHIVES</small>
          <h2>语法训练档案</h2>
          <strong
            >{{ dashboard?.training_archives.grammar.length || 0 }} 次</strong
          >
        </article>
        <article class="panel">
          <small>WRITING ARCHIVES</small>
          <h2>写作训练档案</h2>
          <strong
            >{{ dashboard?.training_archives.writing.length || 0 }} 篇</strong
          >
        </article>
      </section>
      <section class="panel archive-section">
        <header>
          <div>
            <small>GRAMMAR REVIEW</small>
            <h2>语法训练回顾</h2>
            <p>保留题目、学生原答、用时和本轮诊断，便于复盘。</p>
          </div>
        </header>
        <div
          v-if="!dashboard?.training_archives.grammar.length"
          class="empty compact-empty"
        >
          完成一次三题语法训练后，档案会显示在这里。
        </div>
        <details
          v-for="archive in dashboard?.training_archives.grammar"
          :key="archive.archive_id"
          class="training-archive"
        >
          <summary>
            <div>
              <strong>{{ archive.title }}</strong>
              <span>{{ archive.focus }}</span>
            </div>
            <small
              >{{ formatRecordTime(archive.updated_at) }} · 用时
              {{ formatDuration(archive.elapsed_seconds) }} ·
              {{ archive.assessment.overall_score }} 分</small
            >
          </summary>
          <section class="archive-overview">
            <p>{{ archive.assessment.summary }}</p>
            <div>
              <article>
                <b>已经掌握</b>
                <span
                  v-for="item in archive.assessment.strengths"
                  :key="item"
                  >{{ item }}</span
                >
              </article>
              <article>
                <b>当前不足</b>
                <span
                  v-for="item in archive.assessment.weaknesses"
                  :key="item"
                  >{{ item }}</span
                >
              </article>
            </div>
            <p><b>下一步：</b>{{ archive.assessment.next_focus }}</p>
          </section>
          <article
            v-for="(question, index) in archive.questions"
            :key="question.question_id"
            class="archive-question"
          >
            <strong>第 {{ index + 1 }} 题 · {{ question.grammar_focus }}</strong>
            <p>{{ question.prompt }}</p>
            <blockquote>
              学生原答：{{
                archive.answers.find(
                  (answer) => answer.question_id === question.question_id,
                )?.answer || "未记录"
              }}
            </blockquote>
            <p>
              <b>诊断：</b>{{ archive.assessment.feedback[index]?.feedback }}
            </p>
            <p>
              <b>改进：</b>{{
                archive.assessment.feedback[index]?.improvement_step
              }}
            </p>
          </article>
        </details>
      </section>

      <section class="panel archive-section">
        <header>
          <div>
            <small>WRITING REVIEW</small>
            <h2>写作训练回顾</h2>
            <p>保留题目、原文、五维证据评价和修改建议。</p>
          </div>
        </header>
        <div
          v-if="!dashboard?.training_archives.writing.length"
          class="empty compact-empty"
        >
          完成一次写作评价后，完整档案会显示在这里。
        </div>
        <details
          v-for="archive in dashboard?.training_archives.writing"
          :key="archive.archive_id"
          class="training-archive"
        >
          <summary>
            <div>
              <strong>{{ archive.title }}</strong>
              <span>{{ archive.prompt || "历史写作训练" }}</span>
            </div>
            <small
              >{{ formatRecordTime(archive.created_at) }} · 用时
              {{ formatDuration(archive.elapsed_seconds) }} ·
              {{ archive.writing_assessment?.overall_level || "历史评价" }}</small
            >
          </summary>
          <section v-if="archive.writing_assessment" class="archive-writing-profile">
            <h3>当前水平画像</h3>
            <p>{{ archive.writing_assessment.current_level_summary }}</p>
            <h3>提升与优势</h3>
            <p>{{ archive.writing_assessment.progress_summary }}</p>
            <h3>不足与下一步</h3>
            <p>{{ archive.writing_assessment.limitation_summary }}</p>
            <p><b>下一阶段目标：</b>{{ archive.writing_assessment.next_stage_goal }}</p>
          </section>
          <section class="archive-original">
            <h3>学生原文</h3>
            <p>{{ archive.source_text }}</p>
          </section>
          <section
            v-if="archive.writing_assessment"
            class="writing-dimensions archive-dimensions"
          >
            <article
              v-for="item in archive.writing_assessment.dimensions"
              :key="item.dimension"
            >
              <header>
                <strong>{{ writingScoreLabel(item.dimension) }}</strong>
                <span>{{ item.performance_label }} · {{ item.score }} 分</span>
              </header>
              <blockquote>原文证据：“{{ item.evidence_quote }}”</blockquote>
              <p>{{ item.evidence_analysis }}</p>
              <footer><b>怎么提升：</b>{{ item.actionable_advice }}</footer>
            </article>
          </section>
        </details>
      </section>

      <section class="panel record-list">
        <header><div><small>VOCABULARY BOOK</small><h2>生词档案</h2></div></header>
        <article
          v-for="item in dashboard?.learning_records.vocabulary"
          :key="item.word_key"
        >
          <div>
            <strong>{{ item.word }}</strong>
            <p>{{ item.contextual_meaning }}</p>
            <small>{{ item.phonetic }} · {{ item.part_of_speech }}</small>
          </div>
          <b>{{ Math.round(item.mastery_score * 100) }}%</b>
        </article>
      </section>
    </template>
  </div>
</template>

<style scoped>
.english-v2 {
  display: grid;
  gap: 18px;
  color: #263f60;
  font-size: 15px;
}
.english-v2 * {
  box-sizing: border-box;
}
.english-v2 button,
.english-v2 input,
.english-v2 select,
.english-v2 textarea {
  font: inherit;
}
.english-v2 button {
  cursor: pointer;
}
.english-v2 button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}
.hero {
  display: flex;
  min-height: 205px;
  align-items: center;
  justify-content: space-between;
  gap: 30px;
  padding: 34px 39px;
  color: #fff;
  background: linear-gradient(135deg, #0c3b83, #155eef 66%, #65a1ff);
  border-radius: 19px;
  box-shadow: 0 18px 38px rgba(21, 94, 239, 0.18);
}
.hero > div {
  max-width: 760px;
}
.hero > div > span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #dceaff;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.06em;
}
.hero h1 {
  margin: 14px 0 8px;
  font-size: clamp(27px, 3vw, 40px);
  letter-spacing: -0.035em;
}
.hero p {
  margin: 0;
  color: rgba(255, 255, 255, 0.82);
  line-height: 1.8;
}
.hero aside {
  display: grid;
  grid-template-columns: auto auto 1px auto auto;
  align-items: center;
  gap: 11px;
  padding: 17px 19px;
  border: 1px solid rgba(255, 255, 255, 0.23);
  background: rgba(255, 255, 255, 0.1);
  border-radius: 14px;
}
.hero aside strong {
  font-size: 24px;
}
.hero aside span {
  color: #d9e7ff;
  font-size: 11px;
}
.hero aside i {
  width: 1px;
  height: 38px;
  background: rgba(255, 255, 255, 0.25);
}
nav {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 5px;
  padding: 7px;
  border: 1px solid #dce6f3;
  background: #fff;
  border-radius: 14px;
}
nav button {
  display: flex;
  min-height: 49px;
  align-items: center;
  justify-content: center;
  gap: 7px;
  color: #71839c;
  border: 0;
  background: transparent;
  border-radius: 10px;
  font-weight: 750;
}
nav button.active {
  color: #fff;
  background: #155eef;
  box-shadow: 0 6px 15px rgba(21, 94, 239, 0.22);
}
.message {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 15px;
  border-radius: 10px;
}
.message.error {
  color: #ad3e38;
  background: #fff0ef;
}
.message.success {
  color: #176b52;
  background: #eaf8f3;
}
.panel {
  padding: 23px;
  border: 1px solid #dfe7f2;
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 8px 24px rgba(31, 65, 111, 0.055);
}
.panel > header,
.bank-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
}
.panel small {
  color: #155eef;
  font-size: 11px;
  font-weight: 850;
  letter-spacing: 0.08em;
}
.panel h2 {
  margin: 4px 0;
  color: #203a5d;
  font-size: 20px;
}
.panel p {
  color: #71849d;
  line-height: 1.65;
}
.bank-tools {
  display: flex;
  align-items: center;
  gap: 9px;
}
.bank-tools label {
  display: flex;
  align-items: center;
  gap: 7px;
  min-width: 285px;
  height: 42px;
  padding: 0 12px;
  border: 1px solid #d2deec;
  border-radius: 9px;
}
.bank-tools input {
  width: 100%;
  border: 0;
  outline: 0;
}
.bank-tools select {
  height: 42px;
  padding: 0 10px;
  color: #315478;
  border: 1px solid #d2deec;
  background: #fff;
  border-radius: 9px;
}
.reading-list {
  display: grid;
  gap: 9px;
}
.reading-row {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 15px;
  padding: 17px 19px;
  border: 1px solid #dfe7f2;
  background: #fff;
  border-radius: 13px;
  transition: 0.2s;
}
.reading-row:hover {
  border-color: #9abcf1;
  box-shadow: 0 8px 20px rgba(33, 78, 139, 0.07);
}
.paper-letter {
  display: grid;
  width: 45px;
  height: 45px;
  place-items: center;
  color: #155eef;
  background: #eaf3ff;
  border-radius: 11px;
  font-size: 18px;
  font-weight: 850;
}
.reading-info > div {
  display: flex;
  align-items: center;
  gap: 10px;
}
.reading-info h3 {
  margin: 0;
  color: #263f5f;
  font-size: 16px;
}
.reading-info p {
  margin: 6px 0;
  color: #72849a;
}
.reading-info small {
  display: flex;
  align-items: center;
  gap: 5px;
  color: #597495;
}
.status {
  padding: 4px 8px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 800;
}
.status.not_started {
  color: #6f8198;
  background: #eef2f6;
}
.status.in_progress {
  color: #9b6514;
  background: #fff5df;
}
.status.completed {
  color: #197157;
  background: #eaf8f2;
}
.reading-actions > button,
.test-toolbar button {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 9px 12px;
  color: #155eef;
  border: 1px solid #b9d0f4;
  background: #f4f8ff;
  border-radius: 8px;
  font-weight: 750;
}
.reading-actions,
.result-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
}
.reading-actions .redo,
.result-actions .redo {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  padding: 9px 12px;
  color: #6c5a9c;
  border: 1px solid #d8cff1;
  background: #f8f5ff;
  border-radius: 8px;
  font-weight: 750;
}
.test-toolbar {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 17px;
  padding: 15px 19px;
  border: 1px solid #dfe7f2;
  background: #fff;
  border-radius: 13px;
}
.test-toolbar > div {
  display: grid;
}
.test-toolbar span {
  color: #7d8da3;
  font-size: 12px;
}
.test-toolbar > b {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #155eef;
  font-size: 19px;
}
.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  padding: 15px 18px;
  border: 1px solid #dfe7f2;
  background: #fff;
  border-radius: 13px;
  box-shadow: 0 8px 20px rgba(33, 78, 139, 0.05);
}
.pagination button {
  display: inline-flex;
  min-height: 40px;
  align-items: center;
  justify-content: center;
  gap: 5px;
  padding: 8px 15px;
  color: #155eef;
  border: 1px solid #b9d0f4;
  background: #f4f8ff;
  border-radius: 8px;
  font-weight: 800;
}
.pagination span {
  display: flex;
  min-width: 190px;
  align-items: center;
  justify-content: center;
  gap: 5px;
  color: #536f8e;
}
.pagination span b {
  color: #155eef;
  font-size: 17px;
}
.pagination span small {
  margin-left: 7px;
  color: #8899ad;
}
.word-pagination {
  grid-column: 1 / -1;
}

.reading-test {
  display: grid;
  grid-template-columns: minmax(0, 1.12fr) minmax(400px, 0.88fr);
  min-height: 690px;
  overflow: hidden;
  border: 1px solid #dbe5f0;
  background: #fff;
  border-radius: 16px;
}
.passage {
  max-height: 760px;
  overflow: auto;
  padding: 32px 36px;
  border-right: 1px solid #e3eaf2;
}
.passage h2 {
  margin: 6px 0 25px;
  color: #203a5d;
}
.passage p {
  color: #334c6b;
  font-family: Georgia, serif;
  font-size: 17px;
  line-height: 1.9;
  white-space: pre-wrap;
}
.passage img {
  display: block;
  max-width: 100%;
  margin: 18px auto;
  object-fit: contain;
}
.questions {
  display: flex;
  min-width: 0;
  flex-direction: column;
  padding: 31px;
  background: #f8fbff;
}
.questions > header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 15px;
  color: #155eef;
  font-size: 12px;
  font-weight: 850;
}
.questions progress {
  width: 44%;
  accent-color: #155eef;
}
.questions h3 {
  margin: 30px 0 22px;
  color: #263f60;
  font-size: 19px;
  line-height: 1.65;
}
.options {
  display: grid;
  gap: 11px;
}
.options button {
  display: grid;
  grid-template-columns: 34px 1fr auto;
  align-items: center;
  gap: 11px;
  padding: 14px;
  text-align: left;
  color: #3a536f;
  border: 1px solid #d7e2ed;
  background: #fff;
  border-radius: 10px;
}
.options button b {
  display: grid;
  width: 31px;
  height: 31px;
  place-items: center;
  color: #53708f;
  background: #edf3f9;
  border-radius: 8px;
}
.options button.selected {
  color: #155eef;
  border-color: #6f9ff0;
  background: #eef5ff;
}
.options button.selected b {
  color: #fff;
  background: #155eef;
}
.questions footer {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  margin-top: auto;
  padding-top: 28px;
}
.questions footer button,
.primary,
.stop-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  min-height: 41px;
  padding: 9px 17px;
  border-radius: 9px;
  font-weight: 800;
}
.questions footer button {
  color: #55708e;
  border: 1px solid #cfdae7;
  background: #fff;
}
.primary {
  color: #fff !important;
  border: 1px solid #155eef !important;
  background: #155eef !important;
}
.result-head strong {
  color: #155eef;
  font-size: 32px;
}
.result-item {
  display: grid;
  grid-template-columns: 34px 1fr;
  gap: 12px;
  margin-top: 13px;
  padding: 15px;
  border-left: 4px solid #e06d64;
  background: #fff0ef;
  border-radius: 9px;
}
.result-item.correct {
  border-color: #35a47d;
  background: #edf9f4;
}
.result-item > span {
  display: grid;
  width: 30px;
  height: 30px;
  place-items: center;
  color: #fff;
  background: #e06d64;
  border-radius: 50%;
  font-weight: 800;
}
.result-item.correct > span {
  background: #35a47d;
}
.result-item p {
  margin-bottom: 0;
}
.result-actions {
  margin-top: 20px;
  flex-wrap: wrap;
}
.result-actions .back-bank {
  margin-top: 0;
}
.language-input textarea,
.writing-layout textarea {
  width: 100%;
  resize: vertical;
  margin-top: 16px;
  padding: 15px;
  color: #304c6d;
  border: 1px solid #cddaea;
  outline: none;
  border-radius: 10px;
  line-height: 1.75;
}
.language-input textarea:focus,
.writing-layout textarea:focus {
  border-color: #6f9ff0;
  box-shadow: 0 0 0 3px #e9f2ff;
}
.mode-switch {
  display: inline-flex;
  gap: 4px;
  margin-top: 16px;
  padding: 4px;
  background: #edf3fa;
  border-radius: 10px;
}
.mode-switch button {
  padding: 8px 14px;
  color: #657b96;
  border: 0;
  background: transparent;
  border-radius: 7px;
}
.mode-switch button.active {
  color: #155eef;
  background: #fff;
  box-shadow: 0 3px 10px rgba(41, 77, 126, 0.1);
  font-weight: 800;
}
.analyze {
  margin-top: 12px;
}
.word-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 13px;
}
.word-summary {
  grid-column: 1 / -1;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.word-grid > article:not(.word-summary) {
  position: relative;
  padding: 21px;
  border: 1px solid #dfe7f2;
  background: #fff;
  border-radius: 13px;
}
.word-grid > article.picked {
  border-color: #71a1ee;
  box-shadow: 0 0 0 2px #e5f0ff;
}
.word-grid > article > label {
  position: absolute;
  top: 17px;
  right: 18px;
  color: #6f8197;
  font-size: 12px;
}
.word-grid > article > header {
  display: flex;
  align-items: baseline;
  gap: 9px;
  padding-right: 70px;
}
.word-grid h3 {
  margin: 0;
  color: #163e73;
  font-size: 22px;
}
.word-grid header span {
  color: #74869b;
}
.word-grid header b {
  padding: 3px 7px;
  color: #155eef;
  background: #eaf3ff;
  border-radius: 6px;
  font-size: 11px;
}
.word-grid > article > strong {
  display: block;
  margin: 15px 0;
  color: #244c7d;
}
dl {
  display: grid;
  gap: 8px;
  margin: 0;
}
dl div {
  display: grid;
  grid-template-columns: 70px 1fr;
  gap: 8px;
}
dt {
  color: #8997aa;
}
dd {
  margin: 0;
  color: #536a84;
}
.grammar-result {
  border-top: 4px solid #155eef;
}
.steps {
  display: grid;
  gap: 8px;
  margin: 18px 0;
}
.steps article {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 11px 13px;
  background: #f2f7fd;
  border-radius: 8px;
}
.steps b {
  display: grid;
  width: 25px;
  height: 25px;
  place-items: center;
  color: #fff;
  background: #155eef;
  border-radius: 50%;
}
.grammar-issue {
  margin-top: 10px;
  padding: 14px 16px;
  border-left: 3px solid #e9a13d;
  background: #fff8eb;
  border-radius: 8px;
}
.grammar-issue p {
  margin: 7px 0;
}
.reference,
.transcript,
.coach-reply {
  margin-top: 16px;
  padding: 15px;
  background: #edf5ff;
  border-radius: 9px;
}
.reference p,
.transcript p,
.coach-reply p {
  margin-bottom: 0;
  color: #355577;
}
.grammar-training-head {
  border-top: 4px solid #155eef;
}
.grammar-controls {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: end;
  gap: 12px;
  margin-top: 19px;
}
.grammar-controls label {
  display: grid;
  gap: 7px;
  color: #4f6986;
  font-weight: 750;
}
.grammar-controls input,
.writing-prompt-actions select {
  min-height: 43px;
  padding: 0 12px;
  color: #315478;
  border: 1px solid #ccd9e8;
  background: #fff;
  border-radius: 9px;
  outline: none;
}
.ai-context-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 15px;
}
.ai-context-strip span {
  padding: 6px 10px;
  color: #315e96;
  background: #eaf3ff;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 750;
}
.grammar-question-list {
  display: grid;
  gap: 13px;
}
.grammar-round-title > strong {
  display: grid;
  min-width: 82px;
  color: #155eef;
  font-size: 31px;
  text-align: center;
}
.grammar-round-title > strong small {
  color: #7c8da3;
  font-size: 11px;
}
.grammar-question-card > header {
  display: grid;
  grid-template-columns: 45px 1fr;
}
.grammar-question-card > header > span {
  display: grid;
  width: 40px;
  height: 40px;
  place-items: center;
  color: #fff;
  background: #155eef;
  border-radius: 11px;
  font-weight: 850;
}
.grammar-question-card h3 {
  margin: 5px 0;
  color: #263f60;
  font-size: 17px;
  line-height: 1.6;
}
.grammar-question-card textarea {
  width: 100%;
  resize: vertical;
  margin-top: 14px;
  padding: 14px;
  color: #304c6d;
  border: 1px solid #cddaea;
  border-radius: 10px;
  outline: none;
}
.grammar-question-card textarea:focus {
  border-color: #6f9ff0;
  box-shadow: 0 0 0 3px #e9f2ff;
}
.grammar-feedback {
  margin-top: 14px;
  padding: 15px;
  border-left: 4px solid #e19a38;
  background: #fff8eb;
  border-radius: 9px;
}
.grammar-feedback.correct {
  border-color: #35a47d;
  background: #edf9f4;
}
.grammar-feedback > header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.grammar-feedback > header b {
  color: #155eef;
}
.grammar-feedback dl div {
  grid-template-columns: 82px 1fr;
}
.grammar-submit {
  justify-self: end;
}
.grammar-summary > div {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin: 16px 0;
}
.grammar-summary article {
  display: grid;
  gap: 7px;
  padding: 14px;
  background: #f2f7fd;
  border-radius: 10px;
}
.grammar-summary article span {
  color: #5c738e;
}
.grammar-summary footer {
  display: flex;
  align-items: center;
  gap: 7px;
  padding-top: 14px;
  border-top: 1px solid #e6edf5;
}
.grammar-summary footer button {
  margin-left: auto;
}
.writing-prompt-bank > header {
  align-items: center;
}
.writing-prompt-actions {
  display: flex;
  align-items: center;
  gap: 9px;
}
.writing-prompt-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 11px;
  margin-top: 16px;
}
.writing-prompt-grid > button {
  display: grid;
  min-height: 220px;
  align-content: start;
  gap: 7px;
  padding: 17px;
  text-align: left;
  color: #536c88;
  border: 1px solid #d9e4ef;
  background: #f9fbfe;
  border-radius: 12px;
}
.writing-prompt-grid > button:hover,
.writing-prompt-grid > button.active {
  border-color: #6f9ff0;
  background: #edf5ff;
  box-shadow: 0 7px 18px rgba(27, 84, 163, 0.09);
}
.writing-prompt-grid > button > span {
  color: #155eef;
  font-size: 12px;
  font-weight: 850;
}
.writing-prompt-grid small {
  color: #6d84a0;
}
.writing-prompt-grid strong {
  color: #24476f;
  font-size: 16px;
}
.writing-prompt-grid p {
  display: -webkit-box;
  overflow: hidden;
  margin: 2px 0;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 4;
}
.writing-prompt-grid footer {
  margin-top: auto;
  color: #155eef;
  font-size: 12px;
  font-weight: 750;
}
.writing-brief {
  margin-top: 16px;
  padding: 15px;
  background: #f2f7fd;
  border-radius: 10px;
}
.writing-brief p {
  margin-top: 0;
  color: #365371;
}
.writing-brief li {
  margin: 5px 0;
  color: #536d88;
}
.writing-brief > span {
  color: #155eef;
  font-size: 12px;
  font-weight: 750;
}
.writing-evidence {
  padding: 13px 15px;
  background: #edf9f4;
  border-radius: 9px;
}
.writing-evidence.priority {
  margin-top: 10px;
  background: #fff8eb;
}
.writing-evidence h3 {
  margin-top: 0;
  color: #294b70;
}
.writing-evidence p {
  margin: 6px 0;
}
.writing-profile {
  margin-top: 17px;
  padding: 17px;
  color: #365371;
  border: 1px solid #cfe0f4;
  background: linear-gradient(145deg, #f0f6ff, #fbfdff);
  border-radius: 12px;
}
.writing-profile > header,
.writing-dimensions article > header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.writing-profile > header > div {
  display: grid;
}
.writing-profile > header strong {
  color: #155eef;
  font-size: 24px;
}
.writing-profile > header span {
  padding: 5px 9px;
  color: #386696;
  background: #e3efff;
  border-radius: 999px;
  font-size: 12px;
}
.writing-profile h3,
.archive-writing-profile h3 {
  margin: 15px 0 5px;
  color: #294b70;
  font-size: 15px;
}
.writing-profile p,
.archive-writing-profile p {
  margin: 0;
  line-height: 1.75;
}
.writing-dimensions {
  display: grid;
  gap: 10px;
  margin-bottom: 13px;
}
.writing-dimensions article {
  padding: 15px;
  border: 1px solid #e0e9f3;
  background: #fbfdff;
  border-radius: 10px;
}
.writing-dimensions article > header strong {
  color: #284c75;
}
.writing-dimensions article > header span {
  color: #155eef;
  font-weight: 750;
}
.writing-dimensions blockquote,
.archive-question blockquote {
  margin: 10px 0;
  padding: 10px 12px;
  color: #486785;
  border-left: 3px solid #6f9ff0;
  background: #edf5ff;
}
.writing-dimensions p,
.writing-dimensions footer {
  margin: 8px 0 0;
  line-height: 1.7;
}
.speaking-layout,
.writing-layout {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}
.speaking-control > label {
  display: grid;
  gap: 7px;
  margin-top: 18px;
  color: #4f6986;
  font-weight: 750;
}
.speaking-control input {
  width: 100%;
  padding: 12px;
  border: 1px solid #ccdae9;
  border-radius: 9px;
  outline: none;
}
.recorder {
  display: grid;
  min-height: 270px;
  place-items: center;
  align-content: center;
  gap: 13px;
  margin: 18px 0;
  padding: 22px;
  text-align: center;
  border: 1px dashed #a9c1df;
  background: #f7fbff;
  border-radius: 15px;
}
.recorder > span {
  display: grid;
  width: 76px;
  height: 76px;
  place-items: center;
  color: #155eef;
  background: #e5f0ff;
  border-radius: 50%;
}
.recorder b {
  color: #155eef;
  font-size: 25px;
}
.recorder.active > span {
  color: #fff;
  background: #e45752;
  animation: pulse 1.5s infinite;
}
.recorder p {
  max-width: 92%;
  margin: 0;
}
.mic-button,
.stop-button {
  width: 100%;
}
.stop-button {
  color: #fff;
  border: 1px solid #d84f4b;
  background: #d84f4b;
}
.privacy {
  font-size: 12px;
}
.empty {
  display: flex;
  min-height: 180px;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: #8292a6;
  text-align: center;
}
.score-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 8px;
  margin: 18px 0;
}
.score-grid article {
  display: grid;
  gap: 5px;
  padding: 11px;
  background: #f2f7fd;
  border-radius: 8px;
}
.score-grid span {
  overflow: hidden;
  color: #71849b;
  font-size: 11px;
  text-overflow: ellipsis;
}
.score-grid strong {
  color: #155eef;
  font-size: 21px;
}
.score-grid progress {
  width: 100%;
  accent-color: #155eef;
}
.records-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 13px;
}
.records-grid strong {
  color: #155eef;
  font-size: 25px;
}
.record-list {
  display: grid;
  gap: 9px;
}
.record-list article {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 13px;
  border-bottom: 1px solid #edf1f5;
}
.record-list p {
  margin: 3px 0;
}
.record-list b {
  color: #155eef;
}
.archive-section {
  display: grid;
  gap: 11px;
}
.compact-empty {
  min-height: 90px;
}
.training-archive {
  overflow: hidden;
  border: 1px solid #dce6f0;
  background: #fff;
  border-radius: 11px;
}
.training-archive > summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 15px 17px;
  cursor: pointer;
  list-style-position: inside;
}
.training-archive > summary > div {
  display: inline-grid;
  max-width: 65%;
  gap: 4px;
}
.training-archive > summary strong {
  color: #284c75;
}
.training-archive > summary span,
.training-archive > summary small {
  overflow: hidden;
  color: #71849a;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.training-archive[open] > summary {
  border-bottom: 1px solid #e7edf4;
  background: #f8fbff;
}
.archive-overview,
.archive-writing-profile,
.archive-original {
  margin: 15px;
  padding: 15px;
  background: #f5f9fe;
  border-radius: 10px;
}
.archive-overview > div {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}
.archive-overview article {
  display: grid;
  gap: 5px;
  padding: 12px;
  background: #fff;
  border-radius: 8px;
}
.archive-question {
  margin: 12px 15px;
  padding: 14px;
  border: 1px solid #e1e9f2;
  border-radius: 9px;
}
.archive-question p,
.archive-original p {
  line-height: 1.75;
  white-space: pre-wrap;
}
.archive-dimensions {
  margin: 15px;
}
.spin {
  animation: spin 1s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
@keyframes pulse {
  50% {
    box-shadow: 0 0 0 15px rgba(228, 87, 82, 0.12);
  }
}
@media (max-width: 980px) {
  .hero {
    align-items: flex-start;
    flex-direction: column;
  }
  .reading-test,
  .speaking-layout,
  .writing-layout {
    grid-template-columns: 1fr;
  }
  .passage {
    max-height: none;
    border-right: 0;
    border-bottom: 1px solid #e3eaf2;
  }
  .questions {
    min-height: 570px;
  }
  .word-grid,
  .writing-prompt-grid {
    grid-template-columns: 1fr;
  }
  .score-grid {
    grid-template-columns: repeat(3, 1fr);
  }
  .records-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
@media (max-width: 680px) {
  .hero {
    padding: 25px;
  }
  .hero aside {
    display: none;
  }
  nav {
    grid-template-columns: repeat(2, 1fr);
  }
  .bank-heading,
  .bank-tools,
  .word-summary,
  .writing-prompt-bank > header {
    align-items: stretch;
    flex-direction: column;
  }
  .grammar-controls,
  .grammar-summary > div,
  .archive-overview > div,
  .records-grid {
    grid-template-columns: 1fr;
  }
  .training-archive > summary {
    align-items: flex-start;
    flex-direction: column;
  }
  .training-archive > summary > div {
    max-width: 100%;
  }
  .grammar-summary footer,
  .writing-prompt-actions {
    align-items: stretch;
    flex-direction: column;
  }
  .grammar-summary footer button {
    width: 100%;
    margin-left: 0;
  }
  .bank-tools label {
    min-width: 0;
  }
  .reading-row {
    grid-template-columns: auto 1fr;
  }
  .reading-actions {
    grid-column: 1 / -1;
    align-items: stretch;
  }
  .reading-actions > button {
    flex: 1;
    justify-content: center;
  }
  .test-toolbar {
    grid-template-columns: auto 1fr;
  }
  .test-toolbar > b {
    grid-column: 1 / -1;
  }
  .passage,
  .questions {
    padding: 22px;
  }
  .pagination {
    gap: 7px;
    padding: 12px 9px;
  }
  .pagination button {
    padding: 8px 10px;
  }
  .pagination span {
    min-width: 0;
    flex: 1;
    flex-wrap: wrap;
    text-align: center;
  }
  .pagination span small {
    width: 100%;
    margin-left: 0;
  }
  .records-grid {
    grid-template-columns: 1fr;
  }
}
</style>
