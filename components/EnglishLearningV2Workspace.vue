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
  analyzeEnglishLanguageV2,
  assessEnglishSpeaking,
  executeEnglishLanguageTask,
  fetchEnglishDashboard,
  fetchEnglishReadingBank,
  saveEnglishReadingBankProgress,
  saveSelectedEnglishVocabulary,
  startEnglishReadingBank,
  submitEnglishReadingBank,
  type EnglishDashboard,
  type EnglishLanguageTaskResult,
  type ReadingBankItem,
  type ReadingBankPaper,
  type ReadingBankProgress,
  type WordStudyDetail,
} from "@/lib/english-learning-client";

type Page = "reading" | "language" | "speaking" | "writing" | "records";

const page = ref<Page>("reading");
const busy = ref("");
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

const languageMode = ref<"vocabulary" | "grammar">("vocabulary");
const languageText = ref("");
const languageResult = ref<Awaited<
  ReturnType<typeof analyzeEnglishLanguageV2>
> | null>(null);
const selectedWords = reactive<Record<string, boolean>>({});
const vocabularyPage = ref(1);

const speakingTopic = ref("How technology changes the way students learn");
const recording = ref(false);
const speakingSeconds = ref(0);
const browserTranscript = ref("");
const speakingResult = ref<Awaited<
  ReturnType<typeof assessEnglishSpeaking>
> | null>(null);
let recorder: MediaRecorder | null = null;
let speechRecognition: any = null;
let audioChunks: Blob[] = [];
let speakingTimer: number | undefined;

const writingText = ref("");
const writingResult = ref<EnglishLanguageTaskResult | null>(null);

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
  try {
    languageResult.value = await analyzeEnglishLanguageV2(
      languageText.value,
      languageMode.value,
    );
    Object.keys(selectedWords).forEach((key) => delete selectedWords[key]);
    vocabularyPage.value = 1;
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "语言分析失败";
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
  try {
    speakingResult.value = await assessEnglishSpeaking(
      audio,
      speakingTopic.value,
      Math.max(1, speakingSeconds.value),
      browserTranscript.value,
    );
    notice.value = "口语转写和多维评价已经完成，录音原文件未保存";
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "口语评价失败";
  } finally {
    busy.value = "";
    recorder = null;
  }
}

async function assessWriting() {
  if (!writingText.value.trim()) {
    error.value = "请先输入英语作文";
    return;
  }
  busy.value = "writing";
  clearMessage();
  try {
    writingResult.value = await executeEnglishLanguageTask({
      task_type: "writing_revision",
      source_text: writingText.value,
      user_message: "请按新高考写作要求评价，并用步骤引导我自行修改",
      response_mode: "guided",
      detail_level: "detailed",
      revision_level: 1,
      include_exercises: true,
      include_learning_record: true,
      exam_section: "writing",
    });
    await loadPageData();
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "写作评价失败";
  } finally {
    busy.value = "";
  }
}

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
        <span><Sparkles :size="15" /> FOREIGN LANGUAGE LEARNING</span>
        <h1>用真实题库训练，用语言交流成长。</h1>
        <p>117 篇知识库阅读、逐词语境学习、引导式语法修正与麦克风口语陪练。</p>
      </div>
      <aside>
        <strong>{{ catalog?.completed_count || 0 }}</strong>
        <span>已完成阅读</span>
        <i />
        <strong>{{ catalog?.simulation_count || 0 }}</strong>
        <span>模拟与联考</span>
      </aside>
    </section>

    <nav>
      <button :class="{ active: page === 'reading' }" @click="page = 'reading'">
        <BookOpenCheck :size="18" />阅读训练
      </button>
      <button
        :class="{ active: page === 'language' }"
        @click="page = 'language'"
      >
        <Languages :size="18" />词汇与语法
      </button>
      <button
        :class="{ active: page === 'speaking' }"
        @click="page = 'speaking'"
      >
        <Mic :size="18" />口语学习
      </button>
      <button :class="{ active: page === 'writing' }" @click="page = 'writing'">
        <PenLine :size="18" />写作训练
      </button>
      <button :class="{ active: page === 'records' }" @click="page = 'records'">
        <FileText :size="18" />学习档案
      </button>
    </nav>

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
              <button
                :disabled="Boolean(busy)"
                @click="startReading(item)"
              >
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

    <template v-else-if="page === 'language'">
      <section class="panel language-input">
        <header>
          <div>
            <small>VOCABULARY & GRAMMAR</small>
            <h2>词汇与语法学习</h2>
            <p>
              默认逐词学习；切换语法判断后，Agent
              会先判断是否为完整句，再逐步辅助修改。
            </p>
          </div>
          <Languages :size="25" />
        </header>
        <div class="mode-switch">
          <button
            :class="{ active: languageMode === 'vocabulary' }"
            @click="
              languageMode = 'vocabulary';
              languageResult = null;
            "
          >
            词汇学习（默认）</button
          ><button
            :class="{ active: languageMode === 'grammar' }"
            @click="
              languageMode = 'grammar';
              languageResult = null;
            "
          >
            语法判断
          </button>
        </div>
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
          /><Sparkles v-else :size="17" />开始{{
            languageMode === "vocabulary" ? "逐词分析" : "语法判断"
          }}
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
      <section v-if="languageResult?.grammar" class="panel grammar-result">
        <header>
          <div>
            <small>GRAMMAR GUIDANCE</small>
            <h2>
              {{
                languageResult.grammar.is_complete_sentence
                  ? "这是一个完整句子"
                  : "当前输入不是完整句子"
              }}
            </h2>
            <p>
              {{ languageResult.grammar.sentence_type }} ·
              {{ languageResult.grammar.overall_feedback }}
            </p>
          </div>
          <CheckCircle2
            v-if="languageResult.grammar.is_complete_sentence"
            :size="26"
          /><CircleAlert v-else :size="26" />
        </header>
        <div class="steps">
          <article
            v-for="(step, index) in languageResult.grammar.correction_steps"
            :key="step"
          >
            <b>{{ index + 1 }}</b
            ><span>{{ step }}</span>
          </article>
        </div>
        <article
          v-for="item in languageResult.grammar.issues"
          :key="item.original + item.issue_type"
          class="grammar-issue"
        >
          <strong>{{ item.issue_type }} · {{ item.original }}</strong>
          <p>{{ item.explanation }}</p>
          <small>提示：{{ item.hint }}</small>
        </article>
        <div class="reference">
          <small>完成自改后核对参考表达</small>
          <p>{{ languageResult.grammar.corrected_sentence }}</p>
        </div>
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
      <div class="writing-layout">
        <section class="panel">
          <header>
            <div>
              <small>WRITING</small>
              <h2>新高考英语写作训练</h2>
            </div>
            <PenLine :size="23" />
          </header>
          <textarea
            v-model="writingText"
            rows="17"
            placeholder="输入应用文或读后续写段落……"
          /><button
            class="primary analyze"
            :disabled="Boolean(busy)"
            @click="assessWriting"
          >
            <Send :size="16" />提交评价
          </button>
        </section>
        <section class="panel">
          <header>
            <div>
              <small>GUIDED REVISION</small>
              <h2>引导式反馈</h2>
            </div>
            <Sparkles :size="23" />
          </header>
          <div v-if="!writingResult" class="empty">
            提交作文后显示优势、重点问题与修改步骤。
          </div>
          <template v-else
            ><div class="score-grid">
              <article
                v-for="(score, key) in writingResult.answer.scores"
                :key="key"
              >
                <span>{{ key }}</span
                ><strong>{{ score ?? "—" }}</strong>
              </article>
            </div>
            <h3>优先改进</h3>
            <p
              v-for="item in writingResult.answer.priority_improvements"
              :key="item"
            >
              {{ item }}
            </p>
            <article
              v-for="item in writingResult.answer.corrections"
              :key="item.original"
              class="grammar-issue"
            >
              <strong>{{ item.category }} · {{ item.original }}</strong>
              <p>{{ item.explanation }}</p>
            </article></template
          >
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
          <small>LEARNING EVENTS</small>
          <h2>学习记录</h2>
          <strong
            >{{ dashboard?.learning_records.events.length || 0 }} 条</strong
          >
        </article>
      </section>
      <section class="panel record-list">
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
  grid-template-columns: repeat(3, 1fr);
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
  .word-grid {
    grid-template-columns: 1fr;
  }
  .score-grid {
    grid-template-columns: repeat(3, 1fr);
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
  .word-summary {
    align-items: stretch;
    flex-direction: column;
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
