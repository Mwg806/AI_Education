<script setup lang="ts">
import {
  ArrowLeft,
  ArrowRight,
  BookOpenCheck,
  BrainCircuit,
  Check,
  CheckCircle2,
  CircleAlert,
  FileSearch,
  Languages,
  LibraryBig,
  LoaderCircle,
  RefreshCw,
  RotateCcw,
  Send,
  Sparkles,
  Target,
  XCircle,
} from "@lucide/vue";
import { computed, onMounted, reactive, ref } from "vue";

import PaginationControls from "@/components/PaginationControls.vue";
import {
  analyzeEnglishText,
  completeEnglishReview,
  createEnglishTraining,
  fetchEnglishDashboard,
  submitEnglishTraining,
} from "@/lib/english-learning-client";
import type {
  EnglishAnalysis,
  EnglishDashboard,
  EnglishSession,
  EnglishSubmissionResult,
  EnglishTrainingMode,
} from "@/lib/english-learning-client";

type EnglishView = "training" | "analysis" | "profile";
type AnalysisSection = "vocabulary" | "grammar" | "sentences" | "sources";

const activeView = ref<EnglishView>("training");
const analysisSection = ref<AnalysisSection>("vocabulary");
const loading = ref(false);
const dashboardLoading = ref(true);
const error = ref("");
const message = ref("");
const dashboard = ref<EnglishDashboard | null>(null);
const analysis = ref<EnglishAnalysis | null>(null);
const session = ref<EnglishSession | null>(null);
const submission = ref<EnglishSubmissionResult | null>(null);
const questionIndex = ref(0);
const resultPage = ref(1);
const selections = ref<number[]>([]);
const responseTimes = ref<number[]>([]);
const questionStartedAt = ref(Date.now());
const articleExpanded = ref(false);
const reviewingId = ref("");
const form = reactive({
  title: "",
  text: "",
  mode: "reading_multiple_choice" as EnglishTrainingMode,
  questionCount: 4,
});

const currentQuestion = computed(
  () => session.value?.questions[questionIndex.value],
);
const currentResult = computed(
  () => submission.value?.attempt.results[resultPage.value - 1],
);
const articlePreview = computed(() => {
  const text = session.value?.display_text || "";
  return articleExpanded.value || text.length <= 900
    ? text
    : `${text.slice(0, 900)}…`;
});
const completedEvidence = computed(
  () => dashboard.value?.data_sufficiency.evidence_count || 0,
);

const sampleText = `Many students believe that efficient reading means moving through a text as quickly as possible. However, experienced readers change their speed according to the purpose and difficulty of the material. They may scan a notice for a date, but slow down when an argument depends on several connected ideas. This flexible approach also requires readers to notice words that signal contrast, cause, and result. Instead of guessing from one familiar word, they return to the sentence and check how the evidence supports each option. As this habit becomes automatic, readers can work more quickly without losing accuracy. In this way, careful evidence location and reading speed can improve together.`;

async function loadDashboard() {
  dashboardLoading.value = true;
  try {
    dashboard.value = await fetchEnglishDashboard();
  } catch (cause) {
    error.value =
      cause instanceof Error ? cause.message : "英语学习档案读取失败";
  } finally {
    dashboardLoading.value = false;
  }
}

function useSample() {
  form.title = "Evidence-based Reading（示例材料）";
  form.text = sampleText;
}

function validateMaterial() {
  if (!form.title.trim()) {
    error.value = "请填写材料标题";
    return false;
  }
  if (form.text.trim().length < 80) {
    error.value = "请粘贴一篇较完整的英语材料，至少约 80 个字符";
    return false;
  }
  return true;
}

async function runAnalysis() {
  if (!validateMaterial()) return;
  loading.value = true;
  error.value = "";
  message.value = "";
  try {
    analysis.value = await analyzeEnglishText({
      title: form.title,
      text: form.text,
    });
    analysisSection.value = "vocabulary";
    activeView.value = "analysis";
    message.value = "材料分析已完成，并保存到个人学习档案";
    await loadDashboard();
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "英语材料分析失败";
  } finally {
    loading.value = false;
  }
}

async function startTraining() {
  if (!validateMaterial()) return;
  loading.value = true;
  error.value = "";
  message.value = "";
  submission.value = null;
  try {
    session.value = await createEnglishTraining({
      title: form.title,
      text: form.text,
      mode: form.mode,
      question_count: form.mode === "seven_of_five" ? 5 : form.questionCount,
    });
    selections.value = session.value.questions.map(() => -1);
    responseTimes.value = session.value.questions.map(() => 0);
    questionIndex.value = 0;
    questionStartedAt.value = Date.now();
    articleExpanded.value = false;
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "英语训练生成失败";
  } finally {
    loading.value = false;
  }
}

function selectOption(index: number) {
  selections.value[questionIndex.value] = index;
}

function moveQuestion(offset: number) {
  if (selections.value[questionIndex.value] < 0) {
    error.value = "请先选择当前题目的答案";
    return;
  }
  responseTimes.value[questionIndex.value] = Math.max(
    responseTimes.value[questionIndex.value],
    Date.now() - questionStartedAt.value,
  );
  error.value = "";
  questionIndex.value = Math.max(
    0,
    Math.min(
      (session.value?.questions.length || 1) - 1,
      questionIndex.value + offset,
    ),
  );
  questionStartedAt.value = Date.now();
}

async function submitTraining() {
  if (!session.value || selections.value.some((item) => item < 0)) {
    error.value = "请完成全部题目后再提交";
    return;
  }
  responseTimes.value[questionIndex.value] = Math.max(
    responseTimes.value[questionIndex.value],
    Date.now() - questionStartedAt.value,
  );
  loading.value = true;
  error.value = "";
  try {
    submission.value = await submitEnglishTraining(
      session.value.session_id,
      session.value.questions.map((item, index) => ({
        question_id: item.question_id,
        selected_option: selections.value[index],
        response_time_ms: Math.max(100, responseTimes.value[index]),
        hint_count: 0,
      })),
    );
    session.value = submission.value.session;
    resultPage.value = 1;
    message.value = "训练已完成，错因和复习任务已经写入学习档案";
    await loadDashboard();
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "英语训练提交失败";
  } finally {
    loading.value = false;
  }
}

function resetTraining() {
  session.value = null;
  submission.value = null;
  questionIndex.value = 0;
  selections.value = [];
}

async function finishReview(
  reviewId: string,
  result: "remembered" | "needs_review",
) {
  reviewingId.value = reviewId;
  error.value = "";
  try {
    await completeEnglishReview(reviewId, result);
    message.value =
      result === "remembered"
        ? "已记录：本次能够独立回忆"
        : "已记录：仍需继续复习";
    await loadDashboard();
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "复习记录保存失败";
  } finally {
    reviewingId.value = "";
  }
}

function percent(value: number) {
  return `${Math.round(value * 100)}%`;
}

onMounted(loadDashboard);
</script>

<template>
  <div class="english-workspace">
    <section class="english-hero">
      <div>
        <span><Languages :size="17" /> 新高考全国Ⅰ卷英语 Agent</span>
        <h1>从原文证据出发，读懂、诊断、再复习。</h1>
        <p>
          支持英语材料分析、阅读理解、七选五、干扰项诊断和间隔复习。系统不会根据一次练习直接预测高考分数。
        </p>
      </div>
      <div class="english-hero-meta">
        <strong>{{ completedEvidence }}</strong
        ><small>条客观学习证据</small
        ><span><CheckCircle2 :size="15" /> MySQL 私有档案</span>
      </div>
    </section>

    <nav class="english-tabs">
      <button
        :class="{ active: activeView === 'training' }"
        @click="activeView = 'training'"
      >
        <BookOpenCheck :size="18" />阅读与七选五
      </button>
      <button
        :class="{ active: activeView === 'analysis' }"
        @click="activeView = 'analysis'"
      >
        <FileSearch :size="18" />语言材料分析
      </button>
      <button
        :class="{ active: activeView === 'profile' }"
        @click="activeView = 'profile'"
      >
        <BrainCircuit :size="18" />能力与复习
      </button>
    </nav>

    <p v-if="error" class="english-message error">
      <CircleAlert :size="17" />{{ error }}
    </p>
    <p v-if="message" class="english-message success">
      <CheckCircle2 :size="17" />{{ message }}
    </p>

    <template v-if="activeView === 'training'">
      <section v-if="!session" class="english-card material-form">
        <header>
          <div>
            <small>TRAINING MATERIAL</small>
            <h2>导入英语阅读材料</h2>
            <p>
              可以粘贴教材文章、课堂材料或合法获取的训练文本；正式命题只使用原文证据。
            </p>
          </div>
          <button @click="useSample">
            <Sparkles :size="16" />填入示例材料
          </button>
        </header>
        <div class="material-fields">
          <label
            ><span>材料标题</span
            ><input
              v-model="form.title"
              placeholder="例如：The Value of Careful Reading" /></label
          ><label
            ><span>英语原文</span
            ><textarea
              v-model="form.text"
              rows="9"
              placeholder="Paste the English article here…"
            />
          </label>
        </div>
        <div class="training-settings">
          <label
            ><span>训练类型</span>
            <div>
              <button
                :class="{ active: form.mode === 'reading_multiple_choice' }"
                @click="form.mode = 'reading_multiple_choice'"
              >
                阅读理解</button
              ><button
                :class="{ active: form.mode === 'seven_of_five' }"
                @click="form.mode = 'seven_of_five'"
              >
                七选五
              </button>
            </div></label
          ><label v-if="form.mode === 'reading_multiple_choice'"
            ><span>题目数量</span
            ><select v-model.number="form.questionCount">
              <option :value="3">3 题</option>
              <option :value="4">4 题</option>
              <option :value="5">5 题</option>
              <option :value="6">6 题</option>
            </select></label
          >
          <div class="material-actions">
            <button @click="runAnalysis">
              <FileSearch :size="17" />先分析材料</button
            ><button :disabled="loading" @click="startTraining">
              <LoaderCircle v-if="loading" class="spin" :size="18" /><Sparkles
                v-else
                :size="18"
              />{{ loading ? "正在生成并校验" : "生成训练" }}
            </button>
          </div>
        </div>
      </section>

      <template v-else-if="!submission && currentQuestion">
        <section class="english-card article-panel">
          <header>
            <div>
              <small>{{
                session.mode === "seven_of_five"
                  ? "SEVEN OF FIVE"
                  : "READING PASSAGE"
              }}</small>
              <h2>{{ session.title }}</h2>
            </div>
            <span>难度 {{ percent(session.difficulty.absolute_score) }}</span>
          </header>
          <p>{{ articlePreview }}</p>
          <button
            v-if="session.display_text.length > 900"
            @click="articleExpanded = !articleExpanded"
          >
            {{ articleExpanded ? "收起原文" : "展开完整原文" }}
          </button>
        </section>
        <section class="english-card question-panel">
          <header>
            <div>
              <small
                >QUESTION {{ questionIndex + 1 }} /
                {{ session.questions.length }}</small
              >
              <h2>{{ currentQuestion.stem }}</h2>
            </div>
            <span>{{ currentQuestion.skill }}</span>
          </header>
          <div class="english-options">
            <button
              v-for="(option, index) in currentQuestion.options"
              :key="index"
              :class="{ selected: selections[questionIndex] === index }"
              @click="selectOption(index)"
            >
              <b>{{ String.fromCharCode(65 + index) }}</b
              ><span>{{ option }}</span
              ><i v-if="selections[questionIndex] === index"
                ><Check :size="16"
              /></i>
            </button>
          </div>
          <footer>
            <button :disabled="questionIndex === 0" @click="moveQuestion(-1)">
              <ArrowLeft :size="17" />上一题</button
            ><span
              >{{ selections.filter((item) => item >= 0).length }} /
              {{ session.questions.length }} 已作答</span
            ><button
              v-if="questionIndex < session.questions.length - 1"
              @click="moveQuestion(1)"
            >
              下一题<ArrowRight :size="17" /></button
            ><button
              v-else
              :disabled="loading"
              class="submit-training"
              @click="submitTraining"
            >
              <LoaderCircle v-if="loading" class="spin" :size="17" /><Send
                v-else
                :size="17"
              />提交并诊断
            </button>
          </footer>
        </section>
      </template>

      <section
        v-else-if="submission && currentResult"
        class="english-card result-panel"
      >
        <header>
          <div>
            <small>TRAINING RESULT</small>
            <h2>训练结果与文本证据</h2>
          </div>
          <strong
            >{{ submission.attempt.correct_count }} /
            {{ submission.attempt.question_count }}</strong
          >
        </header>
        <div class="result-summary">
          <span :class="currentResult.is_correct ? 'correct' : 'wrong'"
            ><CheckCircle2 v-if="currentResult.is_correct" :size="25" /><XCircle
              v-else
              :size="25"
          /></span>
          <div>
            <small
              >第 {{ resultPage }} 题 · {{ currentResult.skill_label }}</small
            >
            <h3>{{ currentResult.is_correct ? "回答正确" : "需要复盘" }}</h3>
            <p v-if="!currentResult.is_correct">
              错因：{{ currentResult.error_label }}
            </p>
          </div>
        </div>
        <blockquote>
          <small>原文证据</small>
          <p>{{ currentResult.evidence_quote }}</p>
        </blockquote>
        <div class="reasoning-box">
          <strong>为什么</strong>
          <p>{{ currentResult.reasoning }}</p>
          <strong>下次策略</strong>
          <p>{{ currentResult.recommended_strategy }}</p>
        </div>
        <PaginationControls
          :page="resultPage"
          :total="submission.attempt.results.length"
          :page-size="1"
          label="题结果"
          @change="resultPage = $event"
        />
        <footer>
          <button @click="resetTraining">
            <RotateCcw :size="17" />开始新训练</button
          ><button @click="activeView = 'profile'">
            <BrainCircuit :size="17" />查看能力与复习
          </button>
        </footer>
      </section>
    </template>

    <template v-else-if="activeView === 'analysis'">
      <section v-if="!analysis" class="english-card analysis-empty">
        <FileSearch :size="38" />
        <h2>还没有本次材料分析</h2>
        <p>返回“阅读与七选五”，粘贴英语材料后点击“先分析材料”。</p>
        <button @click="activeView = 'training'">
          <ArrowLeft :size="17" />去导入材料
        </button>
      </section>
      <template v-else>
        <section class="analysis-metrics">
          <article>
            <small>总词数</small
            ><strong>{{ analysis.statistics.word_count }}</strong>
          </article>
          <article>
            <small>句子数</small
            ><strong>{{ analysis.statistics.sentence_count }}</strong>
          </article>
          <article>
            <small>平均句长</small
            ><strong>{{ analysis.statistics.average_sentence_words }}</strong>
          </article>
          <article>
            <small>相对负荷</small
            ><strong
              >{{ analysis.difficulty.relative_load > 0 ? "+" : ""
              }}{{ analysis.difficulty.relative_load }}</strong
            >
          </article>
        </section>
        <section class="english-card analysis-overview">
          <header>
            <div>
              <small>LANGUAGE ANALYSIS</small>
              <h2>{{ analysis.title }}</h2>
            </div>
            <span>可信度 {{ percent(analysis.confidence) }}</span>
          </header>
          <p>{{ analysis.difficulty.recommendation }}</p>
          <div class="skill-mapping">
            <span v-for="item in analysis.exam_skill_mapping" :key="item.skill"
              >{{ item.label }} · {{ percent(item.suitability) }}</span
            >
          </div>
        </section>
        <nav class="analysis-tabs">
          <button
            :class="{ active: analysisSection === 'vocabulary' }"
            @click="analysisSection = 'vocabulary'"
          >
            核心词汇</button
          ><button
            :class="{ active: analysisSection === 'grammar' }"
            @click="analysisSection = 'grammar'"
          >
            语法点</button
          ><button
            :class="{ active: analysisSection === 'sentences' }"
            @click="analysisSection = 'sentences'"
          >
            长难句</button
          ><button
            :class="{ active: analysisSection === 'sources' }"
            @click="analysisSection = 'sources'"
          >
            知识依据
          </button>
        </nav>
        <section class="english-card analysis-detail">
          <div v-if="analysisSection === 'vocabulary'" class="vocabulary-grid">
            <article v-for="item in analysis.core_vocabulary" :key="item.word">
              <header>
                <strong>{{ item.word }}</strong
                ><span>{{ item.learning_priority }}</span>
              </header>
              <p>{{ item.context }}</p>
              <small>原文出现 {{ item.occurrences }} 次</small>
            </article>
            <p v-if="!analysis.core_vocabulary.length">
              当前材料没有需要优先提取的长词。
            </p>
          </div>
          <div v-else-if="analysisSection === 'grammar'" class="analysis-list">
            <article
              v-for="item in analysis.grammar_points"
              :key="item.grammar_point"
            >
              <span><Languages :size="18" /></span>
              <div>
                <strong>{{ item.grammar_point }}</strong>
                <p>原文证据：{{ item.evidence }}</p>
                <small>{{ item.gaokao_relevance }}</small>
              </div>
            </article>
            <p v-if="!analysis.grammar_points.length">
              未发现需要优先讲解的目标语法结构。
            </p>
          </div>
          <div
            v-else-if="analysisSection === 'sentences'"
            class="sentence-list"
          >
            <article
              v-for="item in analysis.complex_sentences"
              :key="item.sentence"
            >
              <header>
                <strong>{{ item.word_count }} 词长句</strong
                ><span>{{ item.gaokao_risks.join(" · ") }}</span>
              </header>
              <p>{{ item.sentence }}</p>
              <ol>
                <li v-for="segment in item.segments" :key="segment">
                  {{ segment }}
                </li>
              </ol>
              <small>{{ item.guidance }}</small>
            </article>
            <p v-if="!analysis.complex_sentences.length">
              当前材料没有超过阈值的长难句。
            </p>
          </div>
          <div v-else class="analysis-list">
            <article
              v-for="item in analysis.source_references"
              :key="item.source_id"
            >
              <span><LibraryBig :size="18" /></span>
              <div>
                <strong>{{ item.title }}</strong>
                <p>
                  {{
                    item.document_type === "CURRICULUM_STANDARD"
                      ? "教育部官方课程标准"
                      : "英语教材目录或课程知识索引"
                  }}
                </p>
                <small
                  >权威等级 {{ item.authority_level
                  }}<template v-if="item.page_start">
                    · 第 {{ item.page_start }} 页起</template
                  ></small
                >
              </div>
            </article>
          </div>
        </section>
      </template>
    </template>

    <template v-else>
      <div v-if="dashboardLoading" class="english-loading">
        <LoaderCircle class="spin" :size="25" />正在读取英语学习档案…
      </div>
      <template v-else-if="dashboard">
        <section class="english-card profile-notice">
          <Target :size="23" />
          <div>
            <strong
              >{{
                dashboard.exam_profile.exam_year
              }}
              年新高考全国Ⅰ卷英语</strong
            >
            <p>{{ dashboard.data_sufficiency.message }}</p>
            <small>{{ dashboard.exam_profile.verification_note }}</small>
          </div>
          <button @click="loadDashboard"><RefreshCw :size="16" />刷新</button>
        </section>
        <section class="english-profile-grid">
          <div class="english-card mastery-panel">
            <header>
              <div>
                <small>ABILITY EVIDENCE</small>
                <h2>阅读能力证据</h2>
              </div>
              <span>{{ dashboard.mastery_states.length }} 项</span>
            </header>
            <article
              v-for="item in dashboard.mastery_states"
              :key="item.skill_id"
            >
              <div>
                <strong>{{ item.skill_label }}</strong
                ><small
                  >{{ item.evidence_count }} 条证据 · 可信度
                  {{ percent(item.confidence) }}</small
                >
              </div>
              <b>{{ percent(item.mastery_probability) }}</b
              ><span
                ><i :style="{ width: percent(item.mastery_probability) }"
              /></span>
            </article>
            <div v-if="!dashboard.mastery_states.length" class="profile-empty">
              <BrainCircuit :size="31" /><strong>尚无客观能力证据</strong>
              <p>完成一次阅读或七选五训练后再形成状态。</p>
            </div>
          </div>
          <div class="english-card review-panel">
            <header>
              <div>
                <small>SPACED REVIEW</small>
                <h2>到期复习</h2>
              </div>
              <span>{{ dashboard.due_reviews.length }} 项</span>
            </header>
            <article
              v-for="item in dashboard.due_reviews"
              :key="item.review_id"
            >
              <strong>{{ item.skill_label }}</strong>
              <p>{{ item.prompt }}</p>
              <blockquote>{{ item.evidence_quote }}</blockquote>
              <small
                >建议复习：{{
                  new Date(item.due_at).toLocaleDateString("zh-CN")
                }}</small
              >
              <div>
                <button
                  :disabled="reviewingId === item.review_id"
                  @click="finishReview(item.review_id, 'needs_review')"
                >
                  仍需复习</button
                ><button
                  :disabled="reviewingId === item.review_id"
                  @click="finishReview(item.review_id, 'remembered')"
                >
                  <Check :size="15" />能够回忆
                </button>
              </div>
            </article>
            <div v-if="!dashboard.due_reviews.length" class="profile-empty">
              <CheckCircle2 :size="31" /><strong>当前没有待完成复习</strong>
              <p>错题会按能力标签和遗忘风险进入这里。</p>
            </div>
          </div>
        </section>
      </template>
    </template>
  </div>
</template>

<style scoped src="./EnglishLearningWorkspace.css"></style>
