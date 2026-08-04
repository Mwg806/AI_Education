<script setup lang="ts">
import {
  BookOpenCheck, BrainCircuit, Check, CheckCircle2, CircleAlert, FileText,
  Languages, LoaderCircle, RefreshCw, Send, Target, Trash2,
} from "@lucide/vue";
import { computed, onMounted, reactive, ref } from "vue";

import {
  completeEnglishReview, deleteEnglishLearningRecord, executeEnglishLanguageTask,
  fetchEnglishDashboard,
} from "@/lib/english-learning-client";
import type {
  EnglishDashboard, EnglishLanguageTaskResult, EnglishTaskType, NationalISection,
} from "@/lib/english-learning-client";

type Page = "home" | "exam" | "language" | "records";

const page = ref<Page>("home");
const dashboard = ref<EnglishDashboard | null>(null);
const result = ref<EnglishLanguageTaskResult | null>(null);
const loading = ref(false);
const error = ref("");
const notice = ref("");
const reviewing = ref("");
const deleting = ref("");
const form = reactive({
  taskType: "vocabulary_explanation" as EnglishTaskType,
  section: "reading" as NationalISection,
  source: "",
  message: "",
  detail: "medium" as "brief" | "medium" | "detailed",
});

const targetUser = computed(() => dashboard.value?.target_user || "新高考全国Ⅰ卷考生");
const blueprint = computed(() => dashboard.value?.exam_blueprint);
const sections = computed(() => blueprint.value?.sections || []);
const taskLabel: Record<string, string> = {
  vocabulary_explanation: "词汇释义与搭配",
  grammar_correction: "语法纠错",
  writing_revision: "写作批改与润色",
  translation: "翻译与术语说明",
  speaking_practice: "文本口语训练",
};

const sampleReading = `Many students believe that efficient reading means moving through a text as quickly as possible. However, experienced readers change their speed according to the purpose and difficulty of the material. They slow down when an argument depends on several connected ideas and return to the sentence to check how the evidence supports each option.`;
const sampleWriting = "This research has very important meaning for improve medical image analysis.";

async function loadDashboard() {
  try {
    dashboard.value = await fetchEnglishDashboard();
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "全国Ⅰ卷英语档案读取失败";
  }
}

function useSample(kind: "reading" | "writing") {
  form.source = kind === "reading" ? sampleReading : sampleWriting;
  if (kind === "reading") form.taskType = "exam_practice";
  notice.value = "示例材料已填入，可直接执行任务";
}

async function runTask(taskType: EnglishTaskType = form.taskType) {
  const needsSource = !["learning_plan", "progress_query"].includes(taskType);
  if (needsSource && form.source.trim().length < 1) {
    error.value = "请先输入英语材料或句子";
    return;
  }
  if ((taskType === "exam_practice" || taskType === "reading_comprehension") && form.source.trim().length < 40) {
    error.value = "全国Ⅰ卷阅读训练需要至少约40个英文字母的材料";
    return;
  }
  loading.value = true;
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
      scenario: "全国Ⅰ卷英语表达训练",
      include_exercises: true,
      include_learning_record: true,
      exam_section: form.section,
      question_count: 5,
    });
    notice.value = "任务完成，学习记录已保存到个人档案";
    await loadDashboard();
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "英语学习任务执行失败";
  } finally {
    loading.value = false;
  }
}

async function finishReview(id: string, value: "remembered" | "needs_review") {
  reviewing.value = id;
  try {
    await completeEnglishReview(id, value);
    notice.value = value === "remembered" ? "已记录为能够回忆" : "已重新安排复习";
    await loadDashboard();
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "复习结果保存失败";
  } finally {
    reviewing.value = "";
  }
}

async function removeEvent(id: string) {
  deleting.value = id;
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
  <main class="english-workspace national1-workspace">
    <section class="english-hero national1-hero">
      <div>
        <span><Languages :size="18" /> 全国Ⅰ卷考生专属 · 阅读与语言学习 Agent</span>
        <h1>围绕一张卷，建立可复习的英语能力证据。</h1>
        <p>覆盖阅读、七选五、词汇、语法、写作、翻译和文本口语训练；所有反馈标注依据，不把一次练习伪装成分数预测。</p>
      </div>
      <div class="english-hero-meta"><strong>150</strong><small>全国Ⅰ卷英语满分</small><span><Target :size="15" />服务对象：{{ targetUser }}</span></div>
    </section>

    <nav class="english-tabs" aria-label="英语学习功能导航">
      <button class="english-tab-card" :class="{ active: page === 'home' }" @click="page = 'home'"><span class="tab-icon"><Target :size="19" /></span><span class="tab-copy"><b>考试蓝图</b><small>看清整张卷</small></span><span class="tab-arrow">01</span></button>
      <button class="english-tab-card" :class="{ active: page === 'exam' }" @click="page = 'exam'"><span class="tab-icon"><BookOpenCheck :size="19" /></span><span class="tab-copy"><b>全国Ⅰ卷训练</b><small>马上做一题</small></span><span class="tab-arrow">02</span></button>
      <button class="english-tab-card" :class="{ active: page === 'language' }" @click="page = 'language'"><span class="tab-icon"><Languages :size="19" /></span><span class="tab-copy"><b>语言学习任务</b><small>词汇 · 语法 · 写作</small></span><span class="tab-arrow">03</span></button>
      <button class="english-tab-card" :class="{ active: page === 'records' }" @click="page = 'records'"><span class="tab-icon"><BrainCircuit :size="19" /></span><span class="tab-copy"><b>我的记录与复习</b><small>回看你的进步</small></span><span class="tab-arrow">04</span></button>
    </nav>

    <p v-if="error" class="english-message error"><CircleAlert :size="17" />{{ error }}</p>
    <p v-if="notice" class="english-message success"><CheckCircle2 :size="17" />{{ notice }}</p>

    <template v-if="page === 'home' && dashboard">
      <section class="english-card national1-audience"><Target :size="22" /><div><strong>当前版本只服务新高考全国Ⅰ卷考生</strong><p>{{ blueprint?.notes[0] }}</p><small>{{ dashboard.exam_profile.verification_note }}</small></div><button @click="loadDashboard"><RefreshCw :size="16" />刷新</button></section>
      <section class="national1-blueprint">
        <article v-for="item in sections" :key="item.id" :class="['blueprint-item', item.status]"><span>{{ item.label }}</span><strong>{{ item.score }}分</strong><small>{{ item.question_count ? `${item.question_count}题` : '专项接口' }}</small><i>{{ item.status === 'ready' ? '当前可用' : '资源接入中' }}</i></article>
      </section>
      <section class="english-profile-grid">
        <div class="english-card"><header><div><small>WEEKLY REPORT</small><h2>本周学习报告</h2></div><span>{{ dashboard.weekly_report.completed_tasks }} 项任务</span></header><p>{{ dashboard.weekly_report.next_step }}</p><div class="report-tags"><span>词汇 {{ dashboard.weekly_report.vocabulary_count }}</span><span>稳定语法薄弱点 {{ dashboard.weekly_report.stable_grammar_weaknesses.length }}</span><span>客观证据 {{ dashboard.data_sufficiency.evidence_count }}</span></div></div>
        <div class="english-card"><header><div><small>REVIEW TODAY</small><h2>今日复习</h2></div><span>{{ dashboard.due_reviews.length }} 项</span></header><div v-if="!dashboard.due_reviews.length" class="profile-empty"><CheckCircle2 :size="28" /><p>暂无到期复习，完成任务后会自动生成。</p></div><article v-for="item in dashboard.due_reviews.slice(0,3)" :key="item.review_id" class="review-row"><strong>{{ item.skill_label }}</strong><p>{{ item.prompt }}</p><div><button :disabled="reviewing === item.review_id" @click="finishReview(item.review_id, 'needs_review')">再复习</button><button :disabled="reviewing === item.review_id" @click="finishReview(item.review_id, 'remembered')"><Check :size="14" />已掌握</button></div></article></div>
      </section>
    </template>

    <template v-else-if="page === 'exam'">
      <section class="english-card task-card"><header><div><small>NATIONAL I EXAM PRACTICE</small><h2>全国Ⅰ卷专项训练</h2><p>先选题型，再提交一段材料；系统会给出能力标签、证据句和下一步策略。</p></div><span>证据优先</span></header><div class="task-grid"><label><span>训练板块</span><select v-model="form.section"><option value="reading">阅读理解</option><option value="seven_of_five">七选五</option><option value="writing">写作</option><option value="translation">语言表达与翻译</option><option value="integrated">综合诊断</option></select></label><label><span>反馈深度</span><select v-model="form.detail"><option value="brief">快速</option><option value="medium">教学</option><option value="detailed">详细</option></select></label></div><label class="task-label"><span>材料</span><textarea v-model="form.source" rows="8" placeholder="粘贴全国Ⅰ卷阅读材料、作文或语言材料…" /></label><div class="task-actions"><button @click="useSample('reading')"><FileText :size="16" />填入阅读示例</button><button :disabled="loading" class="primary-action" @click="runTask('exam_practice')"><LoaderCircle v-if="loading" class="spin" :size="17" /><Send v-else :size="17" />生成全国Ⅰ卷训练反馈</button></div></section>
    </template>

    <template v-else-if="page === 'language'">
      <section class="english-card task-card"><header><div><small>LANGUAGE LEARNING LOOP</small><h2>语言学习任务</h2><p>每次任务都包含讲解、例子、练习和可追踪的学习记录；可选择快速或教学模式。</p></div><span>主控路由</span></header><div class="task-grid"><label><span>任务类型</span><select v-model="form.taskType"><option v-for="(label, key) in taskLabel" :key="key" :value="key">{{ label }}</option></select></label><label><span>解释深度</span><select v-model="form.detail"><option value="brief">快速</option><option value="medium">教学</option><option value="detailed">详细</option></select></label></div><label class="task-label"><span>英语内容</span><textarea v-model="form.source" rows="7" placeholder="输入单词、句子、作文或翻译材料…" /></label><label class="task-label"><span>补充要求（可选）</span><input v-model="form.message" placeholder="例如：只修改语法，不改变原意" /></label><div class="task-actions"><button @click="useSample('writing')"><FileText :size="16" />填入写作示例</button><button :disabled="loading" class="primary-action" @click="runTask()"><LoaderCircle v-if="loading" class="spin" :size="17" /><Send v-else :size="17" />执行语言学习任务</button></div></section>
    </template>

    <template v-else-if="page === 'records' && dashboard">
      <section class="english-profile-grid"><div class="english-card"><header><div><small>VOCABULARY NOTEBOOK</small><h2>生词本</h2></div><span>{{ dashboard.learning_records.vocabulary.length }} 项</span></header><article v-for="item in dashboard.learning_records.vocabulary.slice(0,8)" :key="item.word_key" class="record-row"><strong>{{ item.word }}</strong><span>{{ item.contextual_meaning }}</span><small>{{ item.status }} · 掌握度 {{ item.mastery_score.toFixed(1) }}</small></article><p v-if="!dashboard.learning_records.vocabulary.length" class="profile-empty">完成词汇任务后自动建立生词本。</p></div><div class="english-card"><header><div><small>GRAMMAR WEAKNESSES</small><h2>语法薄弱点</h2></div><span>{{ dashboard.learning_records.grammar.length }} 项</span></header><article v-for="item in dashboard.learning_records.grammar.slice(0,8)" :key="item.grammar_key" class="record-row"><strong>{{ item.label }}</strong><span>{{ item.example_error }}</span><small>错误 {{ item.error_count }} 次 · 可信度 {{ Math.round(item.confidence * 100) }}%</small></article><p v-if="!dashboard.learning_records.grammar.length" class="profile-empty">完成语法纠错后自动形成记录。</p></div></section>
      <section class="english-card"><header><div><small>LEARNING EVENTS</small><h2>最近任务</h2></div><span>{{ dashboard.learning_records.events.length }} 条</span></header><article v-for="item in dashboard.learning_records.events" :key="item.event_id" class="event-row"><div><strong>{{ taskLabel[item.task_type] || item.task_type }}</strong><p>{{ item.source_excerpt || '全国Ⅰ卷学习计划或进度查询' }}</p><small>{{ new Date(item.created_at).toLocaleString('zh-CN') }}</small></div><button :disabled="deleting === item.event_id" @click="removeEvent(item.event_id)"><Trash2 :size="15" />删除</button></article></section>
    </template>

    <section v-if="result" class="english-card task-result"><header><div><small>VERIFIED LEARNING RESULT</small><h2>{{ result.answer.title }}</h2></div><span>{{ result.generation_mode === 'llm' ? '模型生成·已质检' : '确定性降级·待核验' }}</span></header><pre>{{ result.answer.display_markdown }}</pre><div v-if="result.answer.reading_evidence.length" class="evidence-box"><strong>原文证据</strong><p v-for="item in result.answer.reading_evidence" :key="item.evidence_quote">{{ item.evidence_quote }}</p></div><div v-if="result.answer.corrections.length" class="correction-list"><article v-for="item in result.answer.corrections" :key="item.original"><strong>{{ item.original }} → {{ item.corrected }}</strong><p>{{ item.explanation }}</p><small>{{ item.category }} · {{ item.severity }}</small></article></div><div v-if="result.answer.exercises.length" class="exercise-box"><strong>下一步练习</strong><p v-for="item in result.answer.exercises" :key="item">{{ item }}</p></div><button class="close-result" @click="result = null">关闭结果</button></section>
  </main>
</template>
