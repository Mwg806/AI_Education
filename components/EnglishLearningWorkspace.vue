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
  Languages,
  LoaderCircle,
  RefreshCw,
  Send,
  ShieldCheck,
  Sparkles,
  Target,
  Trash2,
} from "@lucide/vue";
import { computed, onMounted, reactive, ref } from "vue";

import {
  completeEnglishReview,
  deleteEnglishLearningRecord,
  executeEnglishLanguageTask,
  fetchEnglishDashboard,
} from "@/lib/english-learning-client";
import type {
  EnglishDashboard,
  EnglishLanguageTaskResult,
  EnglishTaskType,
  NationalISection,
} from "@/lib/english-learning-client";

type WorkspacePage = "overview" | "exam" | "language" | "records";

const page = ref<WorkspacePage>("overview");
const dashboard = ref<EnglishDashboard | null>(null);
const result = ref<EnglishLanguageTaskResult | null>(null);
const busy = ref(false);
const reviewing = ref("");
const deleting = ref("");
const error = ref("");
const notice = ref("");

const form = reactive({
  taskType: "vocabulary_explanation" as EnglishTaskType,
  section: "reading" as NationalISection,
  source: "",
  message: "",
  detail: "medium" as "brief" | "medium" | "detailed",
});

const targetUser = computed(
  () => dashboard.value?.target_user || "新高考全国Ⅰ卷高中英语考生",
);
const blueprint = computed(() => dashboard.value?.exam_blueprint);
const readySectionCount = computed(
  () =>
    blueprint.value?.sections.filter((item) => item.status === "ready")
      .length || 0,
);
const taskLabels: Partial<Record<EnglishTaskType, string>> = {
  vocabulary_explanation: "词汇精讲",
  grammar_correction: "语法纠错",
  writing_revision: "写作批改",
  translation: "翻译训练",
  speaking_practice: "口语表达",
  exam_practice: "全国Ⅰ卷专项训练",
  learning_plan: "学习计划",
  progress_query: "学习回顾",
};

const sampleReading = `Many students believe that efficient reading means moving through a text as quickly as possible. However, experienced readers change their speed according to the purpose and difficulty of the material. They slow down when an argument depends on several connected ideas and return to the sentence to check how the evidence supports each option.`;
const sampleWriting =
  "This research has very important meaning for improve medical image analysis.";

async function loadDashboard() {
  error.value = "";
  try {
    dashboard.value = await fetchEnglishDashboard();
  } catch (cause) {
    error.value =
      cause instanceof Error ? cause.message : "英语学习档案读取失败";
  }
}

function openTask(taskType: EnglishTaskType) {
  form.taskType = taskType;
  result.value = null;
  page.value = "language";
}

function loadSample(kind: "reading" | "writing") {
  form.source = kind === "reading" ? sampleReading : sampleWriting;
  if (kind === "writing") form.taskType = "writing_revision";
  notice.value = "示例已填入，可以直接开始";
}

async function runTask(taskType: EnglishTaskType = form.taskType) {
  const needsSource = !["learning_plan", "progress_query"].includes(taskType);
  if (needsSource && !form.source.trim()) {
    error.value = "请先输入要学习的英语材料";
    return;
  }
  if (
    ["exam_practice", "reading_comprehension"].includes(taskType) &&
    form.source.trim().length < 40
  ) {
    error.value = "阅读训练材料过短，请至少输入一个完整段落";
    return;
  }
  busy.value = true;
  error.value = "";
  notice.value = "";
  try {
    result.value = await executeEnglishLanguageTask({
      task_type: taskType,
      source_text: form.source,
      user_message: form.message,
      response_mode: taskType === "exam_practice" ? "exam" : "teaching",
      detail_level: form.detail,
      revision_level: 2,
      feedback_mode: "delayed",
      scenario: "新高考全国Ⅰ卷英语学习",
      include_exercises: true,
      include_learning_record: true,
      exam_section: form.section,
      question_count: 5,
    });
    notice.value = "学习反馈已生成，并保存到个人学习记录";
    await loadDashboard();
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "任务执行失败";
  } finally {
    busy.value = false;
  }
}

async function finishReview(id: string, value: "remembered" | "needs_review") {
  reviewing.value = id;
  error.value = "";
  try {
    await completeEnglishReview(id, value);
    notice.value = value === "remembered" ? "已标记为掌握" : "已安排再次复习";
    await loadDashboard();
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "复习结果保存失败";
  } finally {
    reviewing.value = "";
  }
}

async function removeEvent(id: string) {
  deleting.value = id;
  error.value = "";
  try {
    await deleteEnglishLearningRecord("event", id);
    notice.value = "学习记录已删除";
    await loadDashboard();
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "学习记录删除失败";
  } finally {
    deleting.value = "";
  }
}

onMounted(loadDashboard);
</script>

<template>
  <div class="english-agent">
    <section class="agent-hero">
      <div class="hero-copy">
        <span class="eyebrow"
          ><Sparkles :size="15" /> 阅读与语言学习 Agent</span
        >
        <h1>读懂文章，也真正学会文章里的英语。</h1>
        <p>
          为{{
            targetUser
          }}设计。围绕原文证据完成阅读、词汇、语法、写作与表达训练，
          每次学习都形成可以回看和复习的记录。
        </p>
      </div>
      <div class="hero-status">
        <span><ShieldCheck :size="20" /></span>
        <div><small>服务范围</small><strong>新高考全国Ⅰ卷</strong></div>
        <i />
        <div><small>学习反馈</small><strong>证据可追溯</strong></div>
      </div>
    </section>

    <section class="summary-row" aria-label="学习概览">
      <article>
        <span><Target :size="20" /></span>
        <div>
          <small>试卷满分</small
          ><strong>{{ blueprint?.score || 150 }} 分</strong>
        </div>
      </article>
      <article>
        <span><BookOpenCheck :size="20" /></span>
        <div>
          <small>可用专项</small><strong>{{ readySectionCount }} 个板块</strong>
        </div>
      </article>
      <article>
        <span><Clock3 :size="20" /></span>
        <div>
          <small>本周完成</small
          ><strong
            >{{ dashboard?.weekly_report.completed_tasks || 0 }} 次任务</strong
          >
        </div>
      </article>
      <article>
        <span><BrainCircuit :size="20" /></span>
        <div>
          <small>待复习</small
          ><strong>{{ dashboard?.due_reviews.length || 0 }} 项内容</strong>
        </div>
      </article>
    </section>

    <nav class="agent-nav" aria-label="阅读与语言学习功能">
      <button
        :class="{ active: page === 'overview' }"
        @click="page = 'overview'"
      >
        <span>1</span>
        <div><strong>学习首页</strong><small>了解能力与任务</small></div>
      </button>
      <button :class="{ active: page === 'exam' }" @click="page = 'exam'">
        <span>2</span>
        <div><strong>全国Ⅰ卷训练</strong><small>阅读与题型专项</small></div>
      </button>
      <button
        :class="{ active: page === 'language' }"
        @click="page = 'language'"
      >
        <span>3</span>
        <div><strong>语言学习</strong><small>词汇、语法与写作</small></div>
      </button>
      <button :class="{ active: page === 'records' }" @click="page = 'records'">
        <span>4</span>
        <div><strong>记录与复习</strong><small>巩固已经学过的内容</small></div>
      </button>
    </nav>

    <div v-if="error" class="feedback error">
      <CircleAlert :size="17" />{{ error }}
    </div>
    <div v-if="notice" class="feedback success">
      <CheckCircle2 :size="17" />{{ notice }}
    </div>

    <template v-if="page === 'overview'">
      <section class="section-card">
        <header class="section-heading">
          <div>
            <span>START HERE</span>
            <h2>今天想练什么？</h2>
            <p>选择一个任务，Agent 会自动使用适合全国Ⅰ卷考生的讲解方式。</p>
          </div>
          <button class="quiet-button" @click="loadDashboard">
            <RefreshCw :size="16" />刷新档案
          </button>
        </header>
        <div class="task-entrances">
          <button @click="page = 'exam'">
            <span><BookOpenCheck :size="22" /></span>
            <div>
              <strong>阅读与题型训练</strong
              ><small>定位证据、分析选项和干扰机制</small>
            </div>
            <ChevronRight :size="18" />
          </button>
          <button @click="openTask('vocabulary_explanation')">
            <span><Languages :size="22" /></span>
            <div>
              <strong>词汇精讲</strong><small>语境义、搭配、例句和易错点</small>
            </div>
            <ChevronRight :size="18" />
          </button>
          <button @click="openTask('grammar_correction')">
            <span><BrainCircuit :size="22" /></span>
            <div>
              <strong>语法纠错</strong
              ><small>最小修改，并解释真正的错误原因</small>
            </div>
            <ChevronRight :size="18" />
          </button>
          <button @click="openTask('writing_revision')">
            <span><FileText :size="22" /></span>
            <div>
              <strong>写作提升</strong
              ><small>保留原意，逐步提高准确性和表达</small>
            </div>
            <ChevronRight :size="18" />
          </button>
        </div>
      </section>

      <div class="dashboard-grid">
        <section class="section-card">
          <header class="mini-heading">
            <div>
              <span>WEEKLY</span>
              <h2>本周学习进展</h2>
            </div>
            <strong>{{ dashboard?.weekly_report.completed_tasks || 0 }}</strong>
          </header>
          <p class="next-step">
            {{
              dashboard?.weekly_report.next_step ||
              "完成一次学习任务后，这里会给出下一步建议。"
            }}
          </p>
          <div class="progress-facts">
            <span
              >生词记录
              <b>{{ dashboard?.weekly_report.vocabulary_count || 0 }}</b></span
            >
            <span
              >语法薄弱点
              <b>{{
                dashboard?.weekly_report.stable_grammar_weaknesses.length || 0
              }}</b></span
            >
            <span
              >有效证据
              <b>{{ dashboard?.data_sufficiency.evidence_count || 0 }}</b></span
            >
          </div>
        </section>
        <section class="section-card">
          <header class="mini-heading">
            <div>
              <span>REVIEW</span>
              <h2>今日复习</h2>
            </div>
            <strong>{{ dashboard?.due_reviews.length || 0 }}</strong>
          </header>
          <div v-if="!dashboard?.due_reviews.length" class="empty-state">
            <CheckCircle2 :size="28" />
            <div>
              <strong>今天没有到期任务</strong>
              <p>完成学习后，系统会按掌握情况安排复习。</p>
            </div>
          </div>
          <article
            v-for="item in dashboard?.due_reviews.slice(0, 2)"
            :key="item.review_id"
            class="review-item"
          >
            <div>
              <strong>{{ item.skill_label }}</strong>
              <p>{{ item.prompt }}</p>
            </div>
            <button
              :disabled="reviewing === item.review_id"
              @click="finishReview(item.review_id, 'remembered')"
            >
              <Check :size="14" />已掌握
            </button>
          </article>
        </section>
      </div>
    </template>

    <template v-else-if="page === 'exam'">
      <section class="section-card practice-shell">
        <header class="section-heading">
          <div>
            <span>EXAM PRACTICE</span>
            <h2>全国Ⅰ卷专项训练</h2>
            <p>
              选择训练板块并输入材料，反馈只依据原文，不进行虚假的成绩预测。
            </p>
          </div>
          <span class="safe-badge"><ShieldCheck :size="15" />证据优先</span>
        </header>
        <div class="practice-layout">
          <aside class="section-picker">
            <strong>选择训练板块</strong>
            <button
              v-for="item in blueprint?.sections"
              :key="item.id"
              :class="{
                selected: form.section === item.id,
                disabled: item.status !== 'ready',
              }"
              :disabled="item.status !== 'ready'"
              @click="form.section = item.id as NationalISection"
            >
              <span>{{ item.label }}</span
              ><small
                >{{ item.score }} 分 ·
                {{ item.status === "ready" ? "可训练" : "资源接入中" }}</small
              >
            </button>
          </aside>
          <div class="composer">
            <div class="field-row">
              <label
                ><span>反馈方式</span
                ><select v-model="form.detail">
                  <option value="brief">快速反馈</option>
                  <option value="medium">教学讲解</option>
                  <option value="detailed">深度分析</option>
                </select></label
              >
              <button class="sample-button" @click="loadSample('reading')">
                <FileText :size="15" />使用示例
              </button>
            </div>
            <label class="material-field"
              ><span>英语材料</span
              ><textarea
                v-model="form.source"
                rows="9"
                placeholder="粘贴阅读文章、七选五材料或写作文本……"
              />
            </label>
            <button
              class="primary-button"
              :disabled="busy"
              @click="runTask('exam_practice')"
            >
              <LoaderCircle v-if="busy" class="spin" :size="18" /><Send
                v-else
                :size="18"
              />开始全国Ⅰ卷训练
            </button>
          </div>
        </div>
      </section>
    </template>

    <template v-else-if="page === 'language'">
      <section class="section-card">
        <header class="section-heading">
          <div>
            <span>LANGUAGE COACH</span>
            <h2>语言学习工作台</h2>
            <p>
              词汇、语法、写作、翻译和口语表达，由 Agent
              自动匹配相应的教学流程。
            </p>
          </div>
          <span class="safe-badge"
            ><BrainCircuit :size="15" />智能任务路由</span
          >
        </header>
        <div class="language-types">
          <button
            v-for="(label, key) in taskLabels"
            :key="key"
            :class="{ active: form.taskType === key }"
            @click="form.taskType = key as EnglishTaskType"
          >
            {{ label }}
          </button>
        </div>
        <div class="language-form">
          <div class="field-row">
            <label
              ><span>讲解深度</span
              ><select v-model="form.detail">
                <option value="brief">简明</option>
                <option value="medium">标准</option>
                <option value="detailed">详细</option>
              </select></label
            >
            <button class="sample-button" @click="loadSample('writing')">
              <FileText :size="15" />使用写作示例
            </button>
          </div>
          <label class="material-field"
            ><span>学习内容</span
            ><textarea
              v-model="form.source"
              rows="7"
              placeholder="输入单词、句子、作文、翻译材料或想练习的表达……"
            />
          </label>
          <label class="material-field"
            ><span>补充要求（可选）</span
            ><input
              v-model="form.message"
              placeholder="例如：只修改语法，保留我的原意"
          /></label>
          <button class="primary-button" :disabled="busy" @click="runTask()">
            <LoaderCircle v-if="busy" class="spin" :size="18" /><Send
              v-else
              :size="18"
            />开始学习
          </button>
        </div>
      </section>
    </template>

    <template v-else-if="page === 'records'">
      <div class="records-grid">
        <section class="section-card">
          <header class="mini-heading">
            <div>
              <span>VOCABULARY</span>
              <h2>我的生词本</h2>
            </div>
            <strong>{{
              dashboard?.learning_records.vocabulary.length || 0
            }}</strong>
          </header>
          <div
            v-if="!dashboard?.learning_records.vocabulary.length"
            class="empty-state"
          >
            <Languages :size="27" />
            <div>
              <strong>还没有生词记录</strong>
              <p>完成词汇任务后会自动保存。</p>
            </div>
          </div>
          <article
            v-for="item in dashboard?.learning_records.vocabulary.slice(0, 8)"
            :key="item.word_key"
            class="record-item"
          >
            <div>
              <strong>{{ item.word }}</strong>
              <p>{{ item.contextual_meaning }}</p>
            </div>
            <span>{{ Math.round(item.mastery_score * 100) }}%</span>
          </article>
        </section>
        <section class="section-card">
          <header class="mini-heading">
            <div>
              <span>GRAMMAR</span>
              <h2>语法薄弱点</h2>
            </div>
            <strong>{{
              dashboard?.learning_records.grammar.length || 0
            }}</strong>
          </header>
          <div
            v-if="!dashboard?.learning_records.grammar.length"
            class="empty-state"
          >
            <BrainCircuit :size="27" />
            <div>
              <strong>暂未发现稳定薄弱点</strong>
              <p>需要多次有效学习证据才能判断。</p>
            </div>
          </div>
          <article
            v-for="item in dashboard?.learning_records.grammar.slice(0, 8)"
            :key="item.grammar_key"
            class="record-item"
          >
            <div>
              <strong>{{ item.label }}</strong>
              <p>{{ item.example_error }}</p>
            </div>
            <span>{{ item.error_count }} 次</span>
          </article>
        </section>
      </div>
      <section class="section-card">
        <header class="mini-heading">
          <div>
            <span>HISTORY</span>
            <h2>最近学习任务</h2>
          </div>
          <strong>{{ dashboard?.learning_records.events.length || 0 }}</strong>
        </header>
        <div
          v-if="!dashboard?.learning_records.events.length"
          class="empty-state"
        >
          <BarChart3 :size="27" />
          <div>
            <strong>还没有学习记录</strong>
            <p>开始一次任务后，记录会出现在这里。</p>
          </div>
        </div>
        <article
          v-for="item in dashboard?.learning_records.events.slice(0, 10)"
          :key="item.event_id"
          class="history-item"
        >
          <span><FileText :size="17" /></span>
          <div>
            <strong>{{ taskLabels[item.task_type] || item.task_type }}</strong>
            <p>{{ item.source_excerpt || "学习计划或进度回顾" }}</p>
            <small>{{
              new Date(item.created_at).toLocaleString("zh-CN")
            }}</small>
          </div>
          <button
            :disabled="deleting === item.event_id"
            title="删除记录"
            @click="removeEvent(item.event_id)"
          >
            <Trash2 :size="16" />
          </button>
        </article>
      </section>
    </template>

    <section v-if="result" class="result-card">
      <header>
        <div>
          <span>AGENT FEEDBACK</span>
          <h2>{{ result.answer.title }}</h2>
        </div>
        <button @click="result = null">关闭</button>
      </header>
      <div class="result-copy">{{ result.answer.display_markdown }}</div>
      <div
        v-if="result.answer.reading_evidence.length"
        class="result-block evidence"
      >
        <strong>原文证据</strong>
        <p
          v-for="item in result.answer.reading_evidence"
          :key="item.evidence_quote"
        >
          “{{ item.evidence_quote }}”
        </p>
      </div>
      <div v-if="result.answer.corrections.length" class="result-block">
        <strong>修改建议</strong>
        <article v-for="item in result.answer.corrections" :key="item.original">
          <b>{{ item.original }} → {{ item.corrected }}</b>
          <p>{{ item.explanation }}</p>
        </article>
      </div>
      <div v-if="result.answer.exercises.length" class="result-block exercise">
        <strong>下一步练习</strong>
        <p v-for="(item, index) in result.answer.exercises" :key="item">
          <span>{{ index + 1 }}</span
          >{{ item }}
        </p>
      </div>
    </section>
  </div>
</template>

<style scoped>
.english-agent {
  display: grid;
  gap: 17px;
  color: #263b5d;
  font-size: 15px;
  line-height: 1.6;
}
button,
input,
select,
textarea {
  font: inherit;
}
button {
  cursor: pointer;
}
button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}
.agent-hero {
  position: relative;
  display: flex;
  min-height: 205px;
  align-items: center;
  justify-content: space-between;
  overflow: hidden;
  padding: 34px 38px;
  color: #fff;
  background: linear-gradient(135deg, #103d8f 0%, #155eef 66%, #438bff 100%);
  border-radius: 18px;
  box-shadow: 0 20px 40px rgba(21, 94, 239, 0.17);
}
.agent-hero:after {
  position: absolute;
  top: -105px;
  right: -55px;
  width: 330px;
  height: 330px;
  content: "";
  border: 1px solid rgba(255, 255, 255, 0.16);
  border-radius: 50%;
  box-shadow: 0 0 0 48px rgba(255, 255, 255, 0.045);
}
.hero-copy {
  position: relative;
  z-index: 1;
  max-width: 720px;
}
.eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #d9e7ff;
  font-size: 13px;
  font-weight: 800;
}
.agent-hero h1 {
  margin: 16px 0 10px;
  font-size: clamp(27px, 3vw, 40px);
  line-height: 1.25;
  letter-spacing: -0.035em;
}
.agent-hero p {
  margin: 0;
  color: rgba(255, 255, 255, 0.78);
  font-size: 15px;
  line-height: 1.8;
}
.hero-status {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: auto auto 1px auto;
  align-items: center;
  gap: 14px;
  padding: 18px 20px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  background: rgba(255, 255, 255, 0.1);
  border-radius: 14px;
}
.hero-status > span {
  display: grid;
  width: 42px;
  height: 42px;
  place-items: center;
  background: rgba(255, 255, 255, 0.12);
  border-radius: 11px;
}
.hero-status > div {
  display: grid;
  gap: 4px;
}
.hero-status small {
  color: rgba(255, 255, 255, 0.65);
  font-size: 12px;
}
.hero-status strong {
  font-size: 14px;
}
.hero-status i {
  width: 1px;
  height: 38px;
  background: rgba(255, 255, 255, 0.22);
}
.summary-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
}
.summary-row article {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 18px;
  border: 1px solid #dce5f3;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 8px 24px rgba(39, 75, 130, 0.06);
}
.summary-row article > span {
  display: grid;
  width: 39px;
  height: 39px;
  flex: 0 0 auto;
  place-items: center;
  color: #155eef;
  background: #eaf2ff;
  border-radius: 10px;
}
.summary-row article > div {
  display: grid;
  gap: 3px;
}
.summary-row small {
  color: #8494aa;
  font-size: 12px;
}
.summary-row strong {
  color: #253b5d;
  font-size: 15px;
}
.agent-nav {
  position: relative;
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  padding: 16px 18px;
  border: 1px solid #dce5f3;
  background: #fff;
  border-radius: 14px;
  box-shadow: 0 8px 24px rgba(39, 75, 130, 0.06);
}
.agent-nav:before {
  position: absolute;
  top: 34px;
  right: 12%;
  left: 12%;
  height: 2px;
  content: "";
  background: #e4ebf5;
}
.agent-nav button {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: #8190a5;
  border: 0;
  background: transparent;
  text-align: left;
}
.agent-nav button > span {
  display: grid;
  width: 36px;
  height: 36px;
  flex: 0 0 auto;
  place-items: center;
  border: 2px solid #dce5f1;
  background: #fff;
  border-radius: 50%;
  font-size: 12px;
  font-weight: 800;
}
.agent-nav button > div {
  display: grid;
  gap: 2px;
}
.agent-nav strong {
  font-size: 14px;
}
.agent-nav small {
  font-size: 12px;
}
.agent-nav button.active {
  color: #155eef;
}
.agent-nav button.active > span {
  color: #fff;
  border-color: #155eef;
  background: #155eef;
  box-shadow: 0 5px 14px rgba(21, 94, 239, 0.22);
}
.feedback {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 15px;
  border-radius: 10px;
}
.feedback.error {
  color: #b23d49;
  background: #fff0f1;
}
.feedback.success {
  color: #17745a;
  background: #eaf8f3;
}
.section-card,
.result-card {
  padding: 24px;
  border: 1px solid #dfe7f2;
  background: #fff;
  border-radius: 15px;
  box-shadow: 0 6px 20px rgba(27, 55, 96, 0.06);
}
.section-heading,
.mini-heading,
.result-card > header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding-bottom: 18px;
  border-bottom: 1px solid #edf1f7;
}
.section-heading > div > span,
.mini-heading > div > span,
.result-card > header span {
  color: #5e87c6;
  font-size: 12px;
  font-weight: 850;
  letter-spacing: 0.12em;
}
.section-heading h2,
.mini-heading h2,
.result-card h2 {
  margin: 4px 0 0;
  color: #1e385e;
  font-size: 21px;
}
.section-heading p {
  margin: 5px 0 0;
  color: #74859c;
  font-size: 14px;
}
.quiet-button,
.sample-button {
  display: inline-flex;
  min-height: 42px;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 0 12px;
  color: #486582;
  border: 1px solid #d8e2ef;
  background: #f8fbff;
  border-radius: 9px;
}
.safe-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 10px;
  color: #28765b;
  background: #eaf8f3;
  border-radius: 8px;
  font-size: 13px;
}
.task-entrances {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  margin-top: 18px;
}
.task-entrances button {
  display: grid;
  grid-template-columns: 45px 1fr auto;
  align-items: center;
  gap: 12px;
  padding: 17px;
  color: #526981;
  text-align: left;
  border: 1px solid #e0e8f2;
  background: #fbfdff;
  border-radius: 12px;
  transition: 0.2s;
}
.task-entrances button:hover {
  transform: translateY(-1px);
  border-color: #9fc0f5;
  background: #f5f9ff;
  box-shadow: 0 9px 18px rgba(30, 75, 140, 0.08);
}
.task-entrances button > span {
  display: grid;
  width: 45px;
  height: 45px;
  place-items: center;
  color: #155eef;
  background: #eaf2ff;
  border-radius: 11px;
}
.task-entrances button > div {
  display: grid;
  gap: 4px;
}
.task-entrances strong {
  color: #2c486b;
  font-size: 15px;
}
.task-entrances small {
  color: #8292a7;
  font-size: 13px;
}
.task-entrances button > svg {
  color: #91a0b2;
}
.dashboard-grid,
.records-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
.mini-heading {
  align-items: center;
}
.mini-heading > strong {
  display: grid;
  min-width: 40px;
  height: 40px;
  place-items: center;
  color: #155eef;
  background: #eaf2ff;
  border-radius: 10px;
  font-size: 17px;
}
.next-step {
  margin: 17px 0;
  color: #566d8a;
}
.progress-facts {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.progress-facts span {
  padding: 8px 10px;
  color: #607897;
  background: #f3f7fc;
  border-radius: 8px;
  font-size: 13px;
}
.progress-facts b {
  color: #155eef;
}
.empty-state {
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 94px;
  margin-top: 14px;
  padding: 15px;
  color: #7890aa;
  background: #f8fafd;
  border-radius: 10px;
}
.empty-state > div {
  display: grid;
  gap: 3px;
}
.empty-state strong {
  color: #47617f;
}
.empty-state p {
  margin: 0;
  font-size: 13px;
}
.review-item,
.record-item,
.history-item {
  display: flex;
  align-items: center;
  gap: 11px;
  margin-top: 10px;
  padding: 12px;
  border: 1px solid #e5ebf3;
  background: #fbfcff;
  border-radius: 10px;
}
.review-item > div,
.record-item > div,
.history-item > div {
  display: grid;
  min-width: 0;
  flex: 1;
  gap: 3px;
}
.review-item strong,
.record-item strong,
.history-item strong {
  color: #344d6d;
}
.review-item p,
.record-item p,
.history-item p {
  overflow: hidden;
  margin: 0;
  color: #71839a;
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.review-item button {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 7px 9px;
  color: #fff;
  border: 0;
  background: #155eef;
  border-radius: 7px;
  font-size: 12px;
}
.practice-layout {
  display: grid;
  grid-template-columns: 235px 1fr;
  gap: 20px;
  margin-top: 20px;
}
.section-picker {
  display: grid;
  align-content: start;
  gap: 8px;
  padding: 15px;
  background: #f5f8fc;
  border-radius: 11px;
}
.section-picker > strong {
  margin-bottom: 3px;
  color: #405878;
}
.section-picker button {
  display: grid;
  gap: 3px;
  padding: 11px 12px;
  color: #60738d;
  text-align: left;
  border: 1px solid transparent;
  background: transparent;
  border-radius: 8px;
}
.section-picker button:hover:not(:disabled) {
  background: #fff;
}
.section-picker button.selected {
  color: #155eef;
  border-color: #b9d0f7;
  background: #fff;
  box-shadow: 0 4px 12px rgba(32, 75, 135, 0.07);
}
.section-picker button.disabled {
  opacity: 0.48;
}
.section-picker button span {
  font-weight: 750;
}
.section-picker button small {
  font-size: 12px;
}
.composer,
.language-form {
  display: grid;
  gap: 14px;
}
.field-row {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 12px;
}
.field-row label {
  display: grid;
  min-width: 190px;
  gap: 6px;
}
.field-row label span,
.material-field > span {
  color: #405878;
  font-weight: 750;
}
.field-row select,
.material-field input,
.material-field textarea {
  width: 100%;
  color: #2d4463;
  border: 1px solid #d3dfec;
  outline: 0;
  background: #fbfcff;
  border-radius: 9px;
  font-size: 15px;
}
.field-row select,
.material-field input {
  height: 44px;
  padding: 0 11px;
}
.material-field {
  display: grid;
  gap: 7px;
}
.material-field textarea {
  min-height: 165px;
  padding: 12px 13px;
  line-height: 1.75;
  resize: vertical;
}
.field-row select:focus,
.material-field input:focus,
.material-field textarea:focus {
  border-color: #6ba1ff;
  box-shadow: 0 0 0 3px rgba(21, 94, 239, 0.09);
}
.primary-button {
  display: inline-flex;
  min-height: 48px;
  align-items: center;
  justify-content: center;
  gap: 7px;
  justify-self: end;
  padding: 0 22px;
  color: #fff;
  border: 0;
  background: linear-gradient(135deg, #103d8f, #155eef);
  border-radius: 10px;
  font-weight: 750;
  box-shadow: 0 10px 22px rgba(21, 94, 239, 0.2);
}
.language-types {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 18px 0;
}
.language-types button {
  min-height: 40px;
  padding: 0 13px;
  color: #58708e;
  border: 1px solid #d8e2ee;
  background: #fff;
  border-radius: 9px;
}
.language-types button:hover {
  color: #155eef;
  border-color: #a9c5f4;
}
.language-types button.active {
  color: #fff;
  border-color: #155eef;
  background: #155eef;
  box-shadow: 0 6px 14px rgba(21, 94, 239, 0.18);
}
.record-item > span {
  padding: 5px 8px;
  color: #246c98;
  background: #eaf5fb;
  border-radius: 7px;
  font-size: 12px;
}
.history-item > span {
  display: grid;
  width: 37px;
  height: 37px;
  flex: 0 0 auto;
  place-items: center;
  color: #155eef;
  background: #eaf2ff;
  border-radius: 9px;
}
.history-item small {
  color: #94a1b1;
  font-size: 12px;
}
.history-item > button {
  display: grid;
  width: 34px;
  height: 34px;
  place-items: center;
  color: #9b6570;
  border: 0;
  background: #fff1f2;
  border-radius: 8px;
}
.result-card {
  display: grid;
  gap: 15px;
  border-color: #b9d0f7;
}
.result-card > header button {
  padding: 7px 11px;
  color: #506985;
  border: 1px solid #d8e2ef;
  background: #fff;
  border-radius: 8px;
}
.result-copy {
  padding: 17px;
  color: #3a536f;
  background: #f7faff;
  border-radius: 10px;
  line-height: 1.85;
  white-space: pre-wrap;
}
.result-block {
  padding: 15px 17px;
  border: 1px solid #e0e8f2;
  background: #fbfcff;
  border-radius: 10px;
}
.result-block > strong {
  color: #294867;
}
.result-block p {
  margin: 7px 0 0;
  color: #526981;
}
.result-block article {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid #e7edf4;
}
.result-block article b {
  color: #31567e;
}
.result-block article p {
  margin-top: 4px;
}
.result-block.evidence {
  border-color: #cde4dd;
  background: #f2faf7;
}
.result-block.exercise p {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}
.result-block.exercise p span {
  display: grid;
  width: 22px;
  height: 22px;
  flex: 0 0 auto;
  place-items: center;
  color: #fff;
  background: #155eef;
  border-radius: 50%;
  font-size: 11px;
}
.spin {
  animation: spin 1s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
@media (max-width: 1100px) {
  .hero-status {
    display: none;
  }
  .summary-row {
    grid-template-columns: repeat(2, 1fr);
  }
  .agent-nav button {
    flex-direction: column;
    text-align: center;
  }
  .agent-nav small {
    display: none;
  }
}
@media (max-width: 760px) {
  .agent-hero {
    padding: 27px 23px;
  }
  .agent-hero h1 {
    font-size: 27px;
  }
  .summary-row,
  .dashboard-grid,
  .records-grid,
  .task-entrances {
    grid-template-columns: 1fr;
  }
  .agent-nav {
    padding: 12px 5px;
  }
  .agent-nav:before {
    right: 9%;
    left: 9%;
  }
  .agent-nav button > div {
    display: none;
  }
  .practice-layout {
    grid-template-columns: 1fr;
  }
  .section-picker {
    grid-template-columns: 1fr 1fr;
  }
  .section-picker > strong {
    grid-column: 1/-1;
  }
  .field-row {
    align-items: stretch;
    flex-direction: column;
  }
  .field-row label {
    min-width: 0;
  }
  .sample-button {
    width: 100%;
  }
  .primary-button {
    width: 100%;
    justify-self: stretch;
  }
  .section-card,
  .result-card {
    padding: 18px;
  }
  .section-heading {
    align-items: flex-start;
    flex-direction: column;
  }
}
@media (max-width: 480px) {
  .summary-row {
    grid-template-columns: 1fr 1fr;
    gap: 8px;
  }
  .summary-row article {
    padding: 12px;
  }
  .summary-row article > span {
    display: none;
  }
  .summary-row strong {
    font-size: 14px;
  }
  .agent-nav button > span {
    width: 34px;
    height: 34px;
  }
  .section-picker {
    grid-template-columns: 1fr;
  }
  .task-entrances button {
    grid-template-columns: 40px 1fr;
  }
  .task-entrances button > span {
    width: 40px;
    height: 40px;
  }
  .task-entrances button > svg {
    display: none;
  }
}
</style>
