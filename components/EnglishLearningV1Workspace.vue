<script setup lang="ts">
import {
  BarChart3,
  BookOpenCheck,
  BrainCircuit,
  Check,
  CheckCircle2,
  ChevronRight,
  CircleAlert,
  Clock3,
  FileText,
  GraduationCap,
  ImageUp,
  Languages,
  Lightbulb,
  LoaderCircle,
  PenLine,
  RefreshCw,
  Save,
  Send,
  ShieldCheck,
  Sparkles,
  Target,
  Trash2,
  UserRound,
} from "@lucide/vue";
import { computed, onMounted, reactive, ref } from "vue";

import {
  completeEnglishReview,
  createEnglishTraining,
  deleteEnglishLearningRecord,
  executeEnglishLanguageTask,
  extractEnglishReadingMaterial,
  fetchEnglishDashboard,
  requestEnglishReadingHint,
  submitEnglishTraining,
  updateEnglishLearnerProfile,
  type EnglishDashboard,
  type EnglishLanguageTaskResult,
  type EnglishLevel,
  type EnglishSession,
  type EnglishSubmissionResult,
  type EnglishTrainingMode,
} from "@/lib/english-learning-client";

type Page =
  "home" | "reading" | "vocabulary" | "grammar" | "writing" | "records";

const page = ref<Page>("home");
const dashboard = ref<EnglishDashboard | null>(null);
const busy = ref("");
const error = ref("");
const notice = ref("");
const readingFile = ref<HTMLInputElement | null>(null);

const reading = reactive({
  title: "我的英语阅读训练",
  text: "",
  mode: "reading_multiple_choice" as EnglishTrainingMode,
  questionCount: 4,
  fileName: "",
  warnings: [] as string[],
});
const session = ref<EnglishSession | null>(null);
const submission = ref<EnglishSubmissionResult | null>(null);
const questionIndex = ref(0);
const selections = reactive<Record<string, number>>({});
const hints = reactive<
  Record<
    string,
    Array<{ level: number; content: string; answer_exposed: boolean }>
  >
>({});
const trainingStartedAt = ref(Date.now());

const vocabularyInput = ref("");
const vocabularyRequest = ref("");
const grammarInput = ref("");
const writingInput = ref("");
const writingRequest = ref(
  "请先指出问题并引导我修改，不要直接替我重写整篇文章",
);
const taskResult = ref<EnglishLanguageTaskResult | null>(null);
const showWritingReference = ref(false);

const profileForm = reactive({
  level: "B1" as EnglishLevel,
  dailyMinutes: 30,
  goal: "新高考全国Ⅰ卷英语阅读与写作提升",
  detail: "medium" as "brief" | "medium" | "detailed",
});

const sampleReading = `Good readers do more than recognize words. They adjust their reading speed to the purpose of a text and slow down when several ideas depend on one another.

When an argument includes contrast, careful readers identify which clause carries the writer's main point. They also return to the passage to check whether an option is fully supported instead of choosing it only because it repeats a familiar word.

This evidence-based habit improves both accuracy and speed over time. It can be used when reading science reports, stories, news articles, and exam passages.`;
const sampleWriting = `Last weekend, our class take part in a volunteer activity. We went to a community library and helped organize books. This experience not only taught me how to work with others, but also make me understand the value of service.`;

const currentQuestion = computed(
  () => session.value?.questions[questionIndex.value] || null,
);
const readingParagraphs = computed(() =>
  (session.value?.display_text || "")
    .split(/\n\s*\n/)
    .filter((item) => item.trim()),
);
const answeredCount = computed(() => Object.keys(selections).length);
const canSubmitReading = computed(
  () =>
    Boolean(session.value) &&
    answeredCount.value === session.value?.questions.length,
);
const abilityCards = computed(() => [
  {
    key: "reading",
    label: "阅读能力",
    icon: BookOpenCheck,
    value: dashboard.value?.ability_profile.reading,
  },
  {
    key: "vocabulary",
    label: "词汇掌握",
    icon: Languages,
    value: dashboard.value?.ability_profile.vocabulary,
  },
  {
    key: "grammar",
    label: "语法掌握",
    icon: BrainCircuit,
    value: dashboard.value?.ability_profile.grammar,
  },
  {
    key: "writing",
    label: "写作能力",
    icon: PenLine,
    value: dashboard.value?.ability_profile.writing,
  },
]);

function scoreText(value: number | null | undefined) {
  return value == null ? "待积累" : `${Math.round(value * 100)}%`;
}

function clearFeedback() {
  error.value = "";
  notice.value = "";
}

async function loadDashboard() {
  try {
    dashboard.value = await fetchEnglishDashboard();
    const profile = dashboard.value.learner_profile;
    profileForm.level = profile.self_reported_level;
    profileForm.dailyMinutes = profile.daily_minutes || 30;
    profileForm.goal = profile.learning_goals[0] || profileForm.goal;
    profileForm.detail = profile.explanation_depth;
  } catch (cause) {
    error.value =
      cause instanceof Error ? cause.message : "英语学习档案读取失败";
  }
}

function openPage(target: Page) {
  page.value = target;
  taskResult.value = null;
  clearFeedback();
}

async function uploadReadingMaterial(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0];
  if (!file) return;
  busy.value = "upload";
  clearFeedback();
  try {
    const extracted = await extractEnglishReadingMaterial(file);
    reading.text = extracted.text;
    reading.title = extracted.filename.replace(/\.[^.]+$/, "") || reading.title;
    reading.fileName = extracted.filename;
    reading.warnings = extracted.warnings;
    notice.value = `已从${extracted.source_type.toUpperCase()}材料提取 ${extracted.character_count} 个字符，请核对后开始训练`;
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "阅读材料提取失败";
  } finally {
    busy.value = "";
    (event.target as HTMLInputElement).value = "";
  }
}

async function startReading() {
  if (reading.text.trim().length < 80) {
    error.value = "请粘贴或上传一篇完整英语材料，正文至少 80 个字符";
    return;
  }
  busy.value = "reading";
  clearFeedback();
  try {
    session.value = await createEnglishTraining({
      title: reading.title.trim() || "英语阅读训练",
      text: reading.text,
      mode: reading.mode,
      question_count:
        reading.mode === "seven_of_five" ? 5 : reading.questionCount,
    });
    submission.value = null;
    questionIndex.value = 0;
    Object.keys(selections).forEach((key) => delete selections[key]);
    Object.keys(hints).forEach((key) => delete hints[key]);
    trainingStartedAt.value = Date.now();
    notice.value = "文章分析和训练题已经生成，答案将在提交后统一显示";
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "阅读训练生成失败";
  } finally {
    busy.value = "";
  }
}

function selectOption(index: number) {
  if (!currentQuestion.value) return;
  selections[currentQuestion.value.question_id] = index;
  error.value = "";
}

async function getHint() {
  if (!session.value || !currentQuestion.value) return;
  const questionId = currentQuestion.value.question_id;
  const level = Math.min(4, (hints[questionId]?.length || 0) + 1);
  busy.value = "hint";
  try {
    const result = await requestEnglishReadingHint(
      session.value.session_id,
      questionId,
      level,
    );
    hints[questionId] = [...(hints[questionId] || []), result];
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "提示获取失败";
  } finally {
    busy.value = "";
  }
}

async function submitReading() {
  if (!session.value || !canSubmitReading.value) {
    error.value = "请完成全部题目后再提交";
    return;
  }
  busy.value = "submit-reading";
  clearFeedback();
  const averageTime = Math.max(
    100,
    Math.round(
      (Date.now() - trainingStartedAt.value) / session.value.questions.length,
    ),
  );
  try {
    submission.value = await submitEnglishTraining(
      session.value.session_id,
      session.value.questions.map((question) => ({
        question_id: question.question_id,
        selected_option: selections[question.question_id],
        response_time_ms: averageTime,
        hint_count: hints[question.question_id]?.length || 0,
      })),
    );
    notice.value = "训练已评分，错因、证据和能力变化已经写入学习档案";
    await loadDashboard();
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "阅读训练提交失败";
  } finally {
    busy.value = "";
  }
}

function resetReading() {
  session.value = null;
  submission.value = null;
  questionIndex.value = 0;
  clearFeedback();
}

async function runLanguageTask(
  kind: "vocabulary_explanation" | "grammar_correction" | "writing_revision",
) {
  const source =
    kind === "vocabulary_explanation"
      ? vocabularyInput.value
      : kind === "grammar_correction"
        ? grammarInput.value
        : writingInput.value;
  if (!source.trim()) {
    error.value = "请先输入需要学习的内容";
    return;
  }
  busy.value = kind;
  clearFeedback();
  showWritingReference.value = false;
  try {
    taskResult.value = await executeEnglishLanguageTask({
      task_type: kind,
      source_text: source,
      user_message:
        kind === "vocabulary_explanation"
          ? vocabularyRequest.value
          : kind === "writing_revision"
            ? writingRequest.value
            : "请指出错误并引导我自行修改",
      response_mode:
        kind === "writing_revision"
          ? "guided"
          : kind === "grammar_correction"
            ? "correction"
            : "teaching",
      detail_level: profileForm.detail,
      revision_level: kind === "writing_revision" ? 1 : 2,
      include_exercises: true,
      include_learning_record: true,
      exam_section: kind === "writing_revision" ? "writing" : "integrated",
    });
    notice.value = "教学反馈已生成，并保存为本次学习记录";
    await loadDashboard();
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "语言学习任务失败";
  } finally {
    busy.value = "";
  }
}

async function saveProfile() {
  busy.value = "profile";
  clearFeedback();
  try {
    await updateEnglishLearnerProfile({
      self_reported_level: profileForm.level,
      daily_minutes: profileForm.dailyMinutes,
      preferred_mode: "teaching",
      explanation_depth: profileForm.detail,
      show_examples: true,
      show_exercises: true,
      learning_goals: [profileForm.goal],
    });
    notice.value = "学习画像已保存，后续任务会按新设置调整";
    await loadDashboard();
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "学习画像保存失败";
  } finally {
    busy.value = "";
  }
}

async function finishReview(id: string, result: "remembered" | "needs_review") {
  busy.value = id;
  try {
    await completeEnglishReview(id, result);
    await loadDashboard();
    notice.value =
      result === "remembered" ? "本项已标记为掌握" : "已安排再次复习";
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "复习结果保存失败";
  } finally {
    busy.value = "";
  }
}

async function deleteRecord(type: "event" | "vocabulary", id: string) {
  busy.value = id;
  try {
    await deleteEnglishLearningRecord(type, id);
    await loadDashboard();
    notice.value = "记录已删除";
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "记录删除失败";
  } finally {
    busy.value = "";
  }
}

onMounted(loadDashboard);
</script>

<template>
  <div class="rl-agent">
    <section class="rl-hero">
      <div>
        <span><Sparkles :size="15" /> Reading & Language Agent · V1</span>
        <h1>从读懂一篇文章，到形成可持续提升的语言能力。</h1>
        <p>
          面向新高考全国Ⅰ卷考生，完成阅读、词汇、语法、写作、评价、记录与推荐闭环。
        </p>
      </div>
      <aside>
        <ShieldCheck :size="23" />
        <div>
          <small>当前学习等级</small
          ><strong>{{
            dashboard?.learner_profile.estimated_level || "待评估"
          }}</strong>
        </div>
        <i />
        <div>
          <small>客观学习证据</small
          ><strong
            >{{ dashboard?.data_sufficiency.evidence_count || 0 }} 条</strong
          >
        </div>
      </aside>
    </section>

    <nav class="rl-nav">
      <button :class="{ active: page === 'home' }" @click="openPage('home')">
        <BarChart3 :size="18" /><span>学习首页</span>
      </button>
      <button
        :class="{ active: page === 'reading' }"
        @click="openPage('reading')"
      >
        <BookOpenCheck :size="18" /><span>阅读训练</span>
      </button>
      <button
        :class="{ active: page === 'vocabulary' }"
        @click="openPage('vocabulary')"
      >
        <Languages :size="18" /><span>词汇学习</span>
      </button>
      <button
        :class="{ active: page === 'grammar' }"
        @click="openPage('grammar')"
      >
        <BrainCircuit :size="18" /><span>语法训练</span>
      </button>
      <button
        :class="{ active: page === 'writing' }"
        @click="openPage('writing')"
      >
        <PenLine :size="18" /><span>写作训练</span>
      </button>
      <button
        :class="{ active: page === 'records' }"
        @click="openPage('records')"
      >
        <UserRound :size="18" /><span>档案与记录</span>
      </button>
    </nav>

    <div v-if="error" class="rl-message error">
      <CircleAlert :size="17" />{{ error }}
    </div>
    <div v-if="notice" class="rl-message success">
      <CheckCircle2 :size="17" />{{ notice }}
    </div>

    <template v-if="page === 'home'">
      <section class="ability-grid">
        <article v-for="item in abilityCards" :key="item.key">
          <span><component :is="item.icon" :size="20" /></span>
          <div>
            <small>{{ item.label }}</small
            ><strong>{{ scoreText(item.value) }}</strong>
          </div>
          <progress :value="item.value || 0" max="1" />
        </article>
      </section>
      <div class="home-grid">
        <section class="rl-card recommendation-card">
          <header>
            <div>
              <small>NEXT LEARNING</small>
              <h2>下一步学习建议</h2>
            </div>
            <Target :size="22" />
          </header>
          <strong
            >建议难度
            {{ dashboard?.recommendation.suggested_task.difficulty || 55 }} /
            100</strong
          >
          <p>
            {{
              dashboard?.recommendation.suggested_task.reason ||
              "先完成一篇阅读训练，建立客观能力证据。"
            }}
          </p>
          <ul>
            <li
              v-for="item in dashboard?.recommendation.next_learning"
              :key="item"
            >
              {{ item }}
            </li>
          </ul>
          <button class="primary" @click="openPage('reading')">
            开始阅读训练 <ChevronRight :size="16" />
          </button>
        </section>
        <section class="rl-card">
          <header>
            <div>
              <small>TODAY REVIEW</small>
              <h2>今日复习</h2>
            </div>
            <Clock3 :size="22" />
          </header>
          <div v-if="!dashboard?.due_reviews.length" class="empty">
            <CheckCircle2 :size="28" />
            <p>今天没有到期复习，完成新任务后会自动安排。</p>
          </div>
          <article
            v-for="item in dashboard?.due_reviews.slice(0, 4)"
            :key="item.review_id"
            class="review-row"
          >
            <div>
              <strong>{{ item.skill_label }}</strong>
              <p>{{ item.prompt }}</p>
            </div>
            <button
              :disabled="busy === item.review_id"
              @click="finishReview(item.review_id, 'remembered')"
            >
              <Check :size="14" />掌握
            </button>
          </article>
        </section>
      </div>
      <section class="rl-card dimension-card">
        <header>
          <div>
            <small>READING PROFILE</small>
            <h2>阅读能力画像</h2>
          </div>
          <BrainCircuit :size="22" />
        </header>
        <div
          v-if="
            !Object.keys(dashboard?.ability_profile.reading_dimensions || {})
              .length
          "
          class="empty"
        >
          <BookOpenCheck :size="28" />
          <p>完成阅读训练后，将显示主旨、细节、推断等分项能力。</p>
        </div>
        <div class="dimension-list">
          <article
            v-for="item in dashboard?.ability_profile.reading_dimensions"
            :key="item.label"
          >
            <span>{{ item.label }}</span
            ><progress :value="item.score" max="1" /><b
              >{{ Math.round(item.score * 100) }}%</b
            ><small>{{ item.evidence_count }} 条证据</small>
          </article>
        </div>
      </section>
    </template>

    <template v-else-if="page === 'reading'">
      <section v-if="!session" class="rl-card reading-setup">
        <header>
          <div>
            <small>READING INPUT</small>
            <h2>创建阅读训练</h2>
            <p>
              支持粘贴文本，或上传
              PDF、图片、TXT；上传文件只在内存中提取，不保存原文件。
            </p>
          </div>
          <BookOpenCheck :size="23" />
        </header>
        <div class="reading-settings">
          <label><span>材料标题</span><input v-model="reading.title" /></label>
          <label
            ><span>训练模式</span
            ><select v-model="reading.mode">
              <option value="reading_multiple_choice">阅读理解选择题</option>
              <option value="seven_of_five">七选五衔接训练</option>
            </select></label
          >
          <label v-if="reading.mode === 'reading_multiple_choice'"
            ><span>题目数量</span
            ><select v-model.number="reading.questionCount">
              <option :value="3">3 题</option>
              <option :value="4">4 题</option>
              <option :value="5">5 题</option>
              <option :value="6">6 题</option>
            </select></label
          >
        </div>
        <label class="large-field"
          ><span>英语正文</span
          ><textarea
            v-model="reading.text"
            rows="13"
            placeholder="在这里粘贴英语文章，或点击下方上传材料……"
          />
        </label>
        <div v-if="reading.warnings.length" class="upload-warnings">
          <p v-for="item in reading.warnings" :key="item">
            <CircleAlert :size="14" />{{ item }}
          </p>
        </div>
        <footer class="setup-actions">
          <input
            ref="readingFile"
            type="file"
            accept=".pdf,.txt,.md,image/jpeg,image/png,image/webp"
            @change="uploadReadingMaterial"
          />
          <button
            class="secondary"
            :disabled="Boolean(busy)"
            @click="readingFile?.click()"
          >
            <ImageUp :size="17" />{{
              busy === "upload" ? "正在提取" : "上传 PDF / 图片 / 文本"
            }}
          </button>
          <button
            class="secondary"
            @click="
              reading.text = sampleReading;
              reading.title = 'Evidence-based Reading';
            "
          >
            使用示例
          </button>
          <button
            class="primary"
            :disabled="Boolean(busy)"
            @click="startReading"
          >
            <LoaderCircle
              v-if="busy === 'reading'"
              class="spin"
              :size="17"
            /><Send v-else :size="17" />分析并开始训练
          </button>
        </footer>
      </section>

      <template v-else>
        <section class="reading-status">
          <div>
            <span
              >难度
              {{ Math.round(session.difficulty.absolute_score * 100) }}</span
            ><span>{{ session.analysis.statistics.word_count }} 词</span
            ><span>{{
              session.generation_mode === "llm" ? "模型命题" : "证据题库兜底"
            }}</span>
          </div>
          <button class="secondary" @click="resetReading">
            <RefreshCw :size="15" />更换材料
          </button>
        </section>
        <div v-if="!submission" class="reading-workspace">
          <article class="article-pane">
            <header>
              <small>READING</small>
              <h2>{{ session.title }}</h2>
            </header>
            <p v-for="(paragraph, index) in readingParagraphs" :key="index">
              <b>{{ index + 1 }}</b
              >{{ paragraph }}
            </p>
          </article>
          <section v-if="currentQuestion" class="question-pane">
            <header>
              <div>
                <small
                  >QUESTION {{ questionIndex + 1 }} /
                  {{ session.questions.length }}</small
                ><strong>{{ currentQuestion.skill }}</strong>
              </div>
              <progress
                :value="questionIndex + 1"
                :max="session.questions.length"
              />
            </header>
            <h3>{{ currentQuestion.stem }}</h3>
            <div class="option-list">
              <button
                v-for="(option, index) in currentQuestion.options"
                :key="option"
                :class="{
                  selected: selections[currentQuestion.question_id] === index,
                }"
                @click="selectOption(index)"
              >
                <b>{{ String.fromCharCode(65 + index) }}</b
                ><span>{{ option }}</span
                ><Check
                  v-if="selections[currentQuestion.question_id] === index"
                  :size="16"
                />
              </button>
            </div>
            <div
              v-if="hints[currentQuestion.question_id]?.length"
              class="hint-stack"
            >
              <article
                v-for="item in hints[currentQuestion.question_id]"
                :key="item.level"
              >
                <Lightbulb :size="15" />
                <div>
                  <strong>第 {{ item.level }} 级提示</strong>
                  <p>{{ item.content }}</p>
                </div>
              </article>
            </div>
            <footer>
              <button
                class="hint-button"
                :disabled="
                  busy === 'hint' ||
                  (hints[currentQuestion.question_id]?.length || 0) >= 4
                "
                @click="getHint"
              >
                <Lightbulb :size="16" />{{
                  (hints[currentQuestion.question_id]?.length || 0) < 3
                    ? "给我一点提示"
                    : "查看完整答案"
                }}
              </button>
              <div>
                <button
                  class="secondary"
                  :disabled="questionIndex === 0"
                  @click="questionIndex--"
                >
                  上一题</button
                ><button
                  v-if="questionIndex < session.questions.length - 1"
                  class="primary"
                  :disabled="selections[currentQuestion.question_id] == null"
                  @click="questionIndex++"
                >
                  下一题 <ChevronRight :size="15" /></button
                ><button
                  v-else
                  class="primary"
                  :disabled="!canSubmitReading || busy === 'submit-reading'"
                  @click="submitReading"
                >
                  <LoaderCircle
                    v-if="busy === 'submit-reading'"
                    class="spin"
                    :size="16"
                  />提交并诊断
                </button>
              </div>
            </footer>
          </section>
        </div>

        <section v-else class="rl-card reading-result">
          <header>
            <div>
              <small>READING REPORT</small>
              <h2>本次阅读诊断</h2>
            </div>
            <strong>{{ Math.round(submission.attempt.score * 100) }}%</strong>
          </header>
          <p>
            答对 {{ submission.attempt.correct_count }} /
            {{
              submission.attempt.question_count
            }}
            题。系统已按提示使用情况降低证据权重，避免把看过答案后的作答当作独立掌握。
          </p>
          <div class="review-list">
            <article
              v-for="(item, index) in submission.attempt.results"
              :key="item.question_id"
              :class="{ correct: item.is_correct }"
            >
              <span>{{ index + 1 }}</span>
              <div>
                <strong
                  >{{ item.skill_label }} ·
                  {{ item.is_correct ? "回答正确" : item.error_label }}</strong
                >
                <blockquote>“{{ item.evidence_quote }}”</blockquote>
                <p>{{ item.reasoning }}</p>
                <small>{{ item.recommended_strategy }}</small>
              </div>
            </article>
          </div>
        </section>

        <section class="rl-card article-analysis">
          <header>
            <div>
              <small>ARTICLE ANALYSIS</small>
              <h2>文章学习地图</h2>
            </div>
            <span
              >可信度 {{ Math.round(session.analysis.confidence * 100) }}%</span
            >
          </header>
          <div class="analysis-grid">
            <section>
              <h3>核心词汇</h3>
              <article
                v-for="item in session.analysis.core_vocabulary.slice(0, 8)"
                :key="item.word"
              >
                <strong>{{ item.word }}</strong>
                <p>{{ item.context }}</p>
                <small>{{ item.learning_priority }}</small>
              </article>
            </section>
            <section>
              <h3>语法与长难句</h3>
              <article
                v-for="item in session.analysis.grammar_points"
                :key="item.grammar_point"
              >
                <strong>{{ item.grammar_point }}</strong>
                <p>{{ item.evidence }}</p>
              </article>
              <article
                v-for="item in session.analysis.complex_sentences.slice(0, 3)"
                :key="item.sentence"
              >
                <strong>长难句 · {{ item.word_count }} 词</strong>
                <p>{{ item.sentence }}</p>
                <small>{{ item.guidance }}</small>
              </article>
            </section>
          </div>
        </section>
      </template>
    </template>

    <template v-else-if="page === 'vocabulary'">
      <section class="rl-card focused-task">
        <header>
          <div>
            <small>VOCABULARY</small>
            <h2>语境词汇学习</h2>
            <p>
              学习语境义、词性、音标、搭配、例句和常见误用，并自动进入生词本。
            </p>
          </div>
          <Languages :size="23" />
        </header>
        <label class="large-field"
          ><span>单词、短语或包含目标词的句子</span
          ><textarea
            v-model="vocabularyInput"
            rows="5"
            placeholder="例如：The policy had a significant impact on local communities."
          />
        </label>
        <label
          ><span>想重点了解什么（可选）</span
          ><input
            v-model="vocabularyRequest"
            placeholder="例如：解释 significant 在这里的含义和常见搭配"
        /></label>
        <button
          class="primary task-submit"
          :disabled="Boolean(busy)"
          @click="runLanguageTask('vocabulary_explanation')"
        >
          <LoaderCircle
            v-if="busy === 'vocabulary_explanation'"
            class="spin"
            :size="17"
          /><Sparkles v-else :size="17" />开始词汇学习
        </button>
      </section>
      <section
        v-if="taskResult?.answer.vocabulary.length"
        class="vocabulary-cards"
      >
        <article v-for="item in taskResult.answer.vocabulary" :key="item.word">
          <header>
            <strong>{{ item.word }}</strong
            ><span>{{ item.phonetic }} · {{ item.part_of_speech }}</span>
          </header>
          <h3>{{ item.contextual_meaning }}</h3>
          <p>{{ item.example }}</p>
          <div>
            <span v-for="tag in item.collocations" :key="tag">{{ tag }}</span>
          </div>
          <small v-if="item.common_mistake"
            >易错：{{ item.common_mistake }}</small
          >
        </article>
      </section>
    </template>

    <template v-else-if="page === 'grammar'">
      <section class="rl-card focused-task">
        <header>
          <div>
            <small>GRAMMAR</small>
            <h2>语法诊断与自我修正</h2>
            <p>
              Agent 采用最小修改原则，指出错误依据并给出练习，而不是只替你改完。
            </p>
          </div>
          <BrainCircuit :size="23" />
        </header>
        <label class="large-field"
          ><span>输入需要检查的句子或短文</span
          ><textarea
            v-model="grammarInput"
            rows="7"
            placeholder="例如：I have went to Beijing last year."
          />
        </label>
        <button
          class="primary task-submit"
          :disabled="Boolean(busy)"
          @click="runLanguageTask('grammar_correction')"
        >
          <LoaderCircle
            v-if="busy === 'grammar_correction'"
            class="spin"
            :size="17"
          /><Send v-else :size="17" />检查语法
        </button>
      </section>
      <section
        v-if="taskResult?.answer.corrections.length"
        class="rl-card correction-panel"
      >
        <header>
          <div>
            <small>GUIDED FEEDBACK</small>
            <h2>逐项修正建议</h2>
          </div>
          <ShieldCheck :size="21" />
        </header>
        <article
          v-for="item in taskResult.answer.corrections"
          :key="`${item.original}-${item.category}`"
        >
          <span>{{ item.category }}</span>
          <div>
            <del>{{ item.original }}</del
            ><strong>{{ item.corrected }}</strong>
            <p>{{ item.explanation }}</p>
          </div>
        </article>
        <div class="exercise-box">
          <h3>巩固练习</h3>
          <p v-for="(item, index) in taskResult.answer.exercises" :key="item">
            <b>{{ index + 1 }}</b
            >{{ item }}
          </p>
        </div>
      </section>
    </template>

    <template v-else-if="page === 'writing'">
      <div class="writing-workspace">
        <section class="rl-card writing-editor">
          <header>
            <div>
              <small>STUDENT DRAFT</small>
              <h2>学生作文</h2>
            </div>
            <PenLine :size="22" />
          </header>
          <label class="large-field"
            ><span>作文正文</span
            ><textarea
              v-model="writingInput"
              rows="16"
              placeholder="在这里输入你的英语作文……"
            /></label
          ><label
            ><span>本次要求</span><input v-model="writingRequest"
          /></label>
          <div>
            <button class="secondary" @click="writingInput = sampleWriting">
              使用示例</button
            ><button
              class="primary"
              :disabled="Boolean(busy)"
              @click="runLanguageTask('writing_revision')"
            >
              <LoaderCircle
                v-if="busy === 'writing_revision'"
                class="spin"
                :size="17"
              /><Send v-else :size="17" />提交评价
            </button>
          </div>
        </section>
        <section class="rl-card writing-feedback">
          <header>
            <div>
              <small>TEACHER FEEDBACK</small>
              <h2>写作评价与修改引导</h2>
            </div>
            <GraduationCap :size="22" />
          </header>
          <div
            v-if="
              !taskResult ||
              taskResult.task.primary_intent !== 'writing_revision'
            "
            class="empty tall"
          >
            <FileText :size="32" />
            <p>提交作文后，这里会显示优势、优先改进项、错误定位与练习。</p>
          </div>
          <template v-else
            ><div class="score-grid">
              <span v-for="(value, key) in taskResult.answer.scores" :key="key"
                ><small>{{ key }}</small
                ><strong>{{ value == null ? "—" : value }}</strong></span
              >
            </div>
            <section>
              <h3>优先改进</h3>
              <p
                v-for="item in taskResult.answer.priority_improvements"
                :key="item"
              >
                {{ item }}
              </p>
            </section>
            <article
              v-for="item in taskResult.answer.corrections"
              :key="item.original"
              class="writing-correction"
            >
              <strong>{{ item.category }} · {{ item.severity }}</strong>
              <p>{{ item.original }}</p>
              <small>{{ item.explanation }}</small>
            </article>
            <button
              v-if="taskResult.answer.revised_text"
              class="secondary"
              @click="showWritingReference = !showWritingReference"
            >
              {{ showWritingReference ? "收起" : "完成自改后查看" }}参考版本
            </button>
            <div v-if="showWritingReference" class="reference-draft">
              {{ taskResult.answer.revised_text }}
            </div></template
          >
        </section>
      </div>
    </template>

    <template v-else-if="page === 'records'">
      <div class="records-layout">
        <section class="rl-card profile-card">
          <header>
            <div>
              <small>STUDENT PROFILE</small>
              <h2>我的语言学习画像</h2>
            </div>
            <UserRound :size="22" />
          </header>
          <label
            ><span>当前自评等级</span
            ><select v-model="profileForm.level">
              <option
                v-for="item in ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']"
                :key="item"
              >
                {{ item }}
              </option>
            </select></label
          ><label
            ><span>每日学习时间</span
            ><input
              v-model.number="profileForm.dailyMinutes"
              type="number"
              min="10"
              max="180" /></label
          ><label
            ><span>学习目标</span><input v-model="profileForm.goal" /></label
          ><label
            ><span>讲解深度</span
            ><select v-model="profileForm.detail">
              <option value="brief">简明</option>
              <option value="medium">标准</option>
              <option value="detailed">详细</option>
            </select></label
          ><button
            class="primary"
            :disabled="busy === 'profile'"
            @click="saveProfile"
          >
            <Save :size="16" />保存画像
          </button>
        </section>
        <section class="rl-card">
          <header>
            <div>
              <small>VOCABULARY BOOK</small>
              <h2>我的生词本</h2>
            </div>
            <strong>{{
              dashboard?.learning_records.vocabulary.length || 0
            }}</strong>
          </header>
          <div class="record-scroll">
            <article
              v-for="item in dashboard?.learning_records.vocabulary"
              :key="item.word_key"
              class="record-row"
            >
              <div>
                <strong>{{ item.word }}</strong>
                <p>{{ item.contextual_meaning }}</p>
                <small
                  >遇到 {{ item.contexts_seen }} 次 · 下次复习
                  {{
                    new Date(item.next_review_at).toLocaleDateString("zh-CN")
                  }}</small
                >
              </div>
              <span>{{ Math.round(item.mastery_score * 100) }}%</span
              ><button @click="deleteRecord('vocabulary', item.word_key)">
                <Trash2 :size="14" />
              </button>
            </article>
            <div
              v-if="!dashboard?.learning_records.vocabulary.length"
              class="empty"
            >
              <Languages :size="27" />
              <p>完成词汇学习后会自动保存。</p>
            </div>
          </div>
        </section>
        <section class="rl-card">
          <header>
            <div>
              <small>ERROR PROFILE</small>
              <h2>语法薄弱点</h2>
            </div>
            <strong>{{
              dashboard?.learning_records.grammar.length || 0
            }}</strong>
          </header>
          <div class="record-scroll">
            <article
              v-for="item in dashboard?.learning_records.grammar"
              :key="item.grammar_key"
              class="record-row"
            >
              <div>
                <strong>{{ item.label }}</strong>
                <p>{{ item.example_error }}</p>
                <small
                  >{{ item.stable_weakness ? "稳定薄弱点" : "继续观察" }} · 错误
                  {{ item.error_count }} 次</small
                >
              </div>
              <span>{{ Math.round(item.mastery_score * 100) }}%</span>
            </article>
            <div
              v-if="!dashboard?.learning_records.grammar.length"
              class="empty"
            >
              <BrainCircuit :size="27" />
              <p>需要多次客观证据后才会形成稳定判断。</p>
            </div>
          </div>
        </section>
      </div>
      <section class="rl-card history-card">
        <header>
          <div>
            <small>LEARNING EVENTS</small>
            <h2>学习记录</h2>
          </div>
          <strong>{{ dashboard?.learning_records.events.length || 0 }}</strong>
        </header>
        <article
          v-for="item in dashboard?.learning_records.events"
          :key="item.event_id"
        >
          <span><FileText :size="16" /></span>
          <div>
            <strong>{{ item.task_type }}</strong>
            <p>{{ item.source_excerpt || "学习计划与进度回顾" }}</p>
            <small>{{
              new Date(item.created_at).toLocaleString("zh-CN")
            }}</small>
          </div>
          <button @click="deleteRecord('event', item.event_id)">
            <Trash2 :size="15" />
          </button>
        </article>
      </section>
    </template>
  </div>
</template>

<style scoped>
.rl-agent {
  display: grid;
  gap: 18px;
  color: #263d5f;
  font-size: 15px;
}
.rl-agent * {
  box-sizing: border-box;
}
.rl-agent button,
.rl-agent input,
.rl-agent select,
.rl-agent textarea {
  font: inherit;
}
.rl-agent button {
  cursor: pointer;
}
.rl-agent button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}
.rl-hero {
  display: flex;
  min-height: 210px;
  align-items: center;
  justify-content: space-between;
  gap: 28px;
  padding: 35px 39px;
  overflow: hidden;
  color: #fff;
  background: linear-gradient(135deg, #0e397e, #155eef 65%, #4c93ff);
  border-radius: 19px;
  box-shadow: 0 18px 38px rgba(21, 94, 239, 0.18);
}
.rl-hero > div {
  max-width: 760px;
}
.rl-hero > div > span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #dce9ff;
  font-size: 13px;
  font-weight: 800;
}
.rl-hero h1 {
  margin: 15px 0 10px;
  font-size: clamp(28px, 3vw, 41px);
  line-height: 1.22;
  letter-spacing: -0.035em;
}
.rl-hero p {
  margin: 0;
  color: rgba(255, 255, 255, 0.8);
  line-height: 1.8;
}
.rl-hero aside {
  display: grid;
  grid-template-columns: auto auto 1px auto;
  align-items: center;
  gap: 14px;
  padding: 18px 20px;
  border: 1px solid rgba(255, 255, 255, 0.22);
  background: rgba(255, 255, 255, 0.1);
  border-radius: 14px;
}
.rl-hero aside div {
  display: grid;
  gap: 4px;
}
.rl-hero aside small {
  color: rgba(255, 255, 255, 0.68);
  font-size: 11px;
}
.rl-hero aside i {
  width: 1px;
  height: 40px;
  background: rgba(255, 255, 255, 0.24);
}
.rl-nav {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  padding: 7px;
  border: 1px solid #dce6f4;
  background: #fff;
  border-radius: 14px;
  box-shadow: 0 7px 22px rgba(32, 68, 117, 0.06);
}
.rl-nav button {
  display: flex;
  min-height: 48px;
  align-items: center;
  justify-content: center;
  gap: 7px;
  color: #71829b;
  border: 0;
  background: transparent;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 750;
}
.rl-nav button.active {
  color: #fff;
  background: #155eef;
  box-shadow: 0 6px 15px rgba(21, 94, 239, 0.22);
}
.rl-message {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 15px;
  border-radius: 10px;
}
.rl-message.error {
  color: #ad3e38;
  background: #fff0ef;
}
.rl-message.success {
  color: #176b52;
  background: #eaf8f3;
}
.ability-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 13px;
}
.ability-grid article {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 11px;
  padding: 18px;
  border: 1px solid #dee7f3;
  background: #fff;
  border-radius: 14px;
}
.ability-grid article > span {
  display: grid;
  width: 42px;
  height: 42px;
  place-items: center;
  color: #155eef;
  background: #eaf2ff;
  border-radius: 11px;
}
.ability-grid article div {
  display: grid;
}
.ability-grid small {
  color: #8494aa;
  font-size: 11px;
}
.ability-grid strong {
  font-size: 20px;
}
.ability-grid progress {
  grid-column: 1/-1;
  width: 100%;
  height: 7px;
  accent-color: #155eef;
}
.home-grid {
  display: grid;
  grid-template-columns: 1.05fr 0.95fr;
  gap: 15px;
}
.rl-card {
  padding: 23px;
  border: 1px solid #dfe7f2;
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 8px 25px rgba(31, 65, 111, 0.055);
}
.rl-card > header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 15px;
  margin-bottom: 19px;
}
.rl-card header small {
  color: #155eef;
  font-size: 10px;
  font-weight: 850;
  letter-spacing: 0.08em;
}
.rl-card h2 {
  margin: 3px 0 0;
  color: #203a5d;
  font-size: 20px;
}
.rl-card header p {
  margin: 6px 0 0;
  color: #7b8ca3;
  line-height: 1.65;
}
.recommendation-card > strong {
  font-size: 17px;
}
.recommendation-card > p {
  color: #6f829d;
}
.recommendation-card li {
  margin: 7px 0;
}
.primary,
.secondary,
.hint-button {
  display: inline-flex;
  min-height: 40px;
  align-items: center;
  justify-content: center;
  gap: 7px;
  padding: 0 15px;
  border-radius: 9px;
  font-weight: 750;
}
.primary {
  color: #fff;
  border: 1px solid #155eef;
  background: #155eef;
}
.secondary {
  color: #315d98;
  border: 1px solid #cedcf0;
  background: #f7faff;
}
.hint-button {
  color: #8a5914;
  border: 1px solid #f0d6aa;
  background: #fff9ed;
}
.review-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 11px 0;
  border-top: 1px solid #edf1f6;
}
.review-row p {
  margin: 3px 0;
  color: #7b8da5;
}
.review-row button {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 7px 9px;
  color: #176b52;
  border: 0;
  background: #e9f8f2;
  border-radius: 7px;
}
.empty {
  display: flex;
  min-height: 120px;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: #8292a8;
  text-align: center;
}
.empty.tall {
  min-height: 380px;
  flex-direction: column;
}
.dimension-list article {
  display: grid;
  grid-template-columns: 150px 1fr 48px 90px;
  align-items: center;
  gap: 12px;
  padding: 9px 0;
}
.dimension-list progress {
  width: 100%;
  accent-color: #155eef;
}
.reading {
  display: block;
}
.reading-setup input,
.reading-setup select,
.records-layout input,
.records-layout select,
.large-field textarea {
  width: 100%;
  color: #29425f;
  border: 1px solid #ccd9e9;
  background: #fbfdff;
  border-radius: 9px;
  outline: none;
}
.reading-setup input,
.reading-setup select,
.records-layout input,
.records-layout select {
  height: 43px;
  padding: 0 12px;
}
.large-field {
  display: grid;
  gap: 7px;
}
.large-field > span,
.reading-settings label > span,
.records-layout label > span {
  color: #526982;
  font-size: 13px;
  font-weight: 750;
}
.large-field textarea {
  padding: 14px;
  resize: vertical;
  line-height: 1.75;
}
.reading-settings {
  display: grid;
  grid-template-columns: 1.3fr 1fr 0.6fr;
  gap: 13px;
  margin-bottom: 15px;
}
.reading-settings label,
.records-layout label {
  display: grid;
  gap: 7px;
}
.reading-setup footer {
  margin-top: 16px;
}
.setup-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 9px;
}
.setup-actions input[type="file"] {
  display: none;
}
.upload-warnings {
  margin-top: 10px;
  padding: 9px 12px;
  color: #99610f;
  background: #fff8e9;
  border-radius: 8px;
}
.upload-warnings p {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 3px;
}
.reading-status {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}
.reading-status > div {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.reading-status span {
  padding: 7px 11px;
  color: #386292;
  background: #eaf3ff;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 750;
}
.reading-workspace {
  display: grid;
  grid-template-columns: minmax(0, 1.12fr) minmax(390px, 0.88fr);
  min-height: 680px;
  overflow: hidden;
  border: 1px solid #d9e4f1;
  background: #fff;
  border-radius: 17px;
  box-shadow: 0 10px 30px rgba(32, 66, 113, 0.07);
}
.article-pane {
  max-height: 760px;
  padding: 32px 38px;
  overflow: auto;
  border-right: 1px solid #e3eaf3;
  background: #fcfdff;
}
.article-pane header {
  padding-bottom: 20px;
  border-bottom: 1px solid #e4eaf2;
}
.article-pane header small {
  color: #155eef;
  font-weight: 850;
  letter-spacing: 0.12em;
}
.article-pane h2 {
  margin: 6px 0 0;
  color: #203a5d;
  font-family: Georgia, serif;
  font-size: 26px;
}
.article-pane p {
  position: relative;
  margin: 25px 0;
  color: #273c57;
  font-family: Georgia, "Times New Roman", serif;
  font-size: 18px;
  line-height: 1.95;
}
.article-pane p b {
  position: absolute;
  left: -24px;
  color: #9caabd;
  font: 700 11px sans-serif;
}
.question-pane {
  display: flex;
  min-height: 680px;
  flex-direction: column;
  padding: 29px;
  background: #fff;
}
.question-pane > header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}
.question-pane > header div {
  display: grid;
  gap: 5px;
}
.question-pane > header small {
  color: #758aa6;
  font-size: 11px;
  font-weight: 800;
}
.question-pane > header strong {
  color: #155eef;
}
.question-pane > header progress {
  width: 110px;
  accent-color: #155eef;
}
.question-pane h3 {
  margin: 34px 0 23px;
  color: #233c5d;
  font-size: 19px;
  line-height: 1.65;
}
.option-list {
  display: grid;
  gap: 11px;
}
.option-list button {
  display: grid;
  grid-template-columns: 35px 1fr auto;
  align-items: center;
  gap: 11px;
  min-height: 58px;
  padding: 10px 13px;
  color: #344c69;
  text-align: left;
  border: 1px solid #d8e2ee;
  background: #fff;
  border-radius: 11px;
}
.option-list button:hover {
  border-color: #8db5f7;
  background: #f7faff;
}
.option-list button.selected {
  color: #164e9b;
  border-color: #155eef;
  background: #edf4ff;
}
.option-list button b {
  display: grid;
  width: 32px;
  height: 32px;
  place-items: center;
  color: #4d6685;
  background: #f0f4f8;
  border-radius: 8px;
}
.option-list button.selected b {
  color: #fff;
  background: #155eef;
}
.hint-stack {
  display: grid;
  gap: 7px;
  margin-top: 17px;
}
.hint-stack article {
  display: flex;
  gap: 9px;
  padding: 10px 12px;
  color: #71501f;
  background: #fff9ed;
  border-radius: 9px;
}
.hint-stack article svg {
  flex: none;
  margin-top: 2px;
}
.hint-stack strong {
  font-size: 12px;
}
.hint-stack p {
  margin: 3px 0 0;
  font-size: 13px;
  line-height: 1.55;
}
.question-pane > footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 9px;
  margin-top: auto;
  padding-top: 24px;
}
.question-pane > footer > div {
  display: flex;
  gap: 8px;
}
.reading-result > header > strong {
  color: #155eef;
  font-size: 35px;
}
.reading-result > p {
  color: #6e819a;
}
.review-list {
  display: grid;
  gap: 10px;
}
.review-list article {
  display: grid;
  grid-template-columns: 35px 1fr;
  gap: 12px;
  padding: 14px;
  color: #8e4541;
  border-left: 4px solid #e6685e;
  background: #fff5f4;
  border-radius: 9px;
}
.review-list article.correct {
  color: #27705b;
  border-color: #35a67d;
  background: #f0faf6;
}
.review-list article > span {
  display: grid;
  width: 31px;
  height: 31px;
  place-items: center;
  color: #fff;
  background: #de655d;
  border-radius: 50%;
  font-weight: 800;
}
.review-list article.correct > span {
  background: #35a67d;
}
.review-list blockquote {
  margin: 8px 0;
  padding-left: 10px;
  color: #4d637d;
  border-left: 2px solid #b9c8d9;
}
.review-list p {
  margin: 5px 0;
  line-height: 1.6;
}
.review-list small {
  font-weight: 700;
}
.analysis-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 15px;
}
.analysis-grid section {
  padding: 18px;
  background: #f7faff;
  border-radius: 11px;
}
.analysis-grid h3 {
  margin: 0 0 10px;
  color: #294968;
}
.analysis-grid p {
  color: #5d718b;
  line-height: 1.7;
}
.analysis-grid li {
  margin: 7px 0;
}
.vocab-chip-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.vocab-chip-list span {
  padding: 6px 9px;
  color: #315e99;
  background: #e9f2ff;
  border-radius: 7px;
}
.complex-sentence {
  margin-top: 10px !important;
  padding: 10px;
  border-left: 3px solid #78aaf7;
  background: #fff !important;
}
.task-intro {
  display: grid;
  grid-template-columns: 1fr auto;
  align-items: center;
  gap: 25px;
}
.task-intro > div:last-child {
  display: grid;
  width: 72px;
  height: 72px;
  place-items: center;
  color: #155eef;
  background: #eaf3ff;
  border-radius: 17px;
}
.task-submit {
  margin-top: 15px;
}
.vocabulary-cards {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 13px;
  margin-top: 15px;
}
.vocabulary-cards article {
  padding: 17px;
  border: 1px solid #dce6f2;
  background: #fff;
  border-radius: 12px;
}
.vocabulary-cards header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.vocabulary-cards h3 {
  margin: 0;
  color: #1f4d86;
  font-size: 20px;
}
.vocabulary-cards header span {
  color: #788ca6;
}
.vocabulary-cards > article > strong {
  display: block;
  margin: 9px 0;
  color: #334d6d;
}
.vocabulary-cards p {
  color: #607590;
  line-height: 1.6;
}
.vocabulary-cards footer {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.vocabulary-cards footer span,
.correction-panel article > span {
  padding: 5px 8px;
  color: #356191;
  background: #edf4ff;
  border-radius: 6px;
  font-size: 12px;
}
.correction-panel > article {
  display: grid;
  grid-template-columns: 120px 1fr;
  gap: 14px;
  padding: 14px 0;
  border-top: 1px solid #e9eef5;
}
.correction-panel article div {
  display: grid;
  gap: 5px;
}
.correction-panel del {
  color: #af5d59;
}
.correction-panel strong {
  color: #28715b;
}
.correction-panel p {
  margin: 0;
  color: #657993;
}
.exercise-box {
  margin-top: 14px;
  padding: 16px;
  background: #f6f9fd;
  border-radius: 10px;
}
.exercise-box h3 {
  margin-top: 0;
}
.exercise-box p {
  display: flex;
  gap: 8px;
}
.exercise-box b {
  display: grid;
  width: 22px;
  height: 22px;
  flex: none;
  place-items: center;
  color: #fff;
  background: #155eef;
  border-radius: 50%;
  font-size: 11px;
}
.writing-workspace {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 15px;
}
.writing-editor > div {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 15px;
}
.writing-editor label + label {
  display: grid;
  gap: 7px;
  margin-top: 13px;
}
.writing-editor input {
  height: 43px;
  padding: 0 12px;
  border: 1px solid #ccd9e9;
  border-radius: 9px;
}
.score-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  margin-bottom: 18px;
}
.score-grid span {
  display: grid;
  padding: 10px;
  color: #526981;
  background: #f3f7fc;
  border-radius: 8px;
}
.score-grid strong {
  margin-top: 4px;
  color: #155eef;
  font-size: 19px;
}
.writing-feedback section {
  padding: 12px 0;
}
.writing-feedback section p {
  margin: 7px 0;
  color: #5d728d;
}
.writing-correction {
  padding: 12px 0;
  border-top: 1px solid #e7edf4;
}
.writing-correction strong {
  color: #a6514c;
}
.writing-correction p {
  margin: 6px 0;
  color: #354e6d;
}
.writing-correction small {
  color: #71849b;
}
.reference-draft {
  margin-top: 12px;
  padding: 15px;
  white-space: pre-wrap;
  color: #315679;
  background: #eef5ff;
  border-radius: 9px;
  line-height: 1.75;
}
.records-layout {
  display: grid;
  grid-template-columns: 0.82fr 1fr 1fr;
  gap: 15px;
}
.profile-card {
  display: grid;
  gap: 13px;
}
.profile-card > header {
  margin-bottom: 2px;
}
.profile-card button {
  margin-top: 4px;
}
.record-scroll {
  max-height: 420px;
  overflow: auto;
}
.record-row {
  display: grid;
  grid-template-columns: 1fr auto auto;
  align-items: center;
  gap: 9px;
  padding: 12px 0;
  border-top: 1px solid #e9eef4;
}
.record-row p {
  margin: 4px 0;
  color: #607590;
}
.record-row small {
  color: #8292a7;
}
.record-row > span {
  color: #155eef;
  font-weight: 800;
}
.record-row button,
.history-card article button {
  display: grid;
  width: 31px;
  height: 31px;
  place-items: center;
  color: #9a6b68;
  border: 0;
  background: #fff1f0;
  border-radius: 7px;
}
.history-card > article {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 12px;
  padding: 12px 0;
  border-top: 1px solid #e9eef4;
}
.history-card > article > span {
  display: grid;
  width: 37px;
  height: 37px;
  place-items: center;
  color: #155eef;
  background: #eaf3ff;
  border-radius: 9px;
}
.history-card p {
  margin: 4px 0;
  color: #627792;
}
.history-card small {
  color: #8394a9;
}
.spin {
  animation: spin 1s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
@media (max-width: 1150px) {
  .rl-hero aside {
    display: none;
  }
  .rl-nav {
    grid-template-columns: repeat(3, 1fr);
  }
  .ability-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  .reading-workspace {
    grid-template-columns: 1fr;
  }
  .article-pane {
    max-height: 520px;
    border-right: 0;
    border-bottom: 1px solid #e4eaf2;
  }
  .records-layout {
    grid-template-columns: 1fr 1fr;
  }
  .profile-card {
    grid-column: 1/-1;
  }
}
@media (max-width: 760px) {
  .rl-hero {
    padding: 27px 23px;
  }
  .rl-nav {
    grid-template-columns: repeat(2, 1fr);
  }
  .ability-grid,
  .home-grid,
  .analysis-grid,
  .vocabulary-cards,
  .writing-workspace,
  .records-layout {
    grid-template-columns: 1fr;
  }
  .reading-settings {
    grid-template-columns: 1fr;
  }
  .reading-workspace {
    display: block;
  }
  .question-pane {
    min-height: 620px;
  }
  .setup-actions,
  .question-pane > footer {
    align-items: stretch;
    flex-direction: column;
  }
  .question-pane > footer > div {
    display: grid;
    grid-template-columns: 1fr 1fr;
  }
  .dimension-list article {
    grid-template-columns: 110px 1fr 45px;
  }
  .dimension-list article small {
    display: none;
  }
  .records-layout .profile-card {
    grid-column: auto;
  }
}
</style>
