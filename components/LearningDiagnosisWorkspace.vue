<script setup lang="ts">
import {
  Activity, AlertTriangle, BarChart3, BrainCircuit, CheckCircle2, ClipboardCheck,
  Camera, Database, FileImage, FileSearch, FlaskConical, LoaderCircle, Plus,
  RefreshCw, ShieldCheck, Sparkles, Trash2, TrendingUp, UploadCloud,
} from "@lucide/vue";
import { computed, onBeforeUnmount, reactive, ref } from "vue";

import ExamDiagnosisWorkspace from "@/components/ExamDiagnosisWorkspace.vue";
import PaginationControls from "@/components/PaginationControls.vue";
import { processLearningRecordImages, runLearningDiagnosis } from "@/lib/diagnosis-client";
import type {
  DiagnosisDimensionState, LearningDiagnosisEnvelope, LearningEvidenceDraft,
  StudentLoginProfile, SubjectKey,
} from "@/lib/types";

const props = defineProps<{
  profile: StudentLoginProfile;
  initialSubject: SubjectKey;
  initialPaperId?: string;
  curriculumVersion?: string;
  mode?: "exam" | "records";
}>();

const subject = ref<SubjectKey>(props.initialSubject || "mathematics");
const diagnosisRequest = ref("请识别我最近数学学习中有证据支持的薄弱知识、稳定错误模式和需要补充的证据。");
const records = ref<LearningEvidenceDraft[]>([]);
const result = ref<LearningDiagnosisEnvelope | null>(null);
const loading = ref(false);
const error = ref("");
const demoEvidence = ref(false);
const dimensionTab = ref<"knowledge" | "question" | "ability">("knowledge");
const reportTab = ref<"student" | "teacher">("student");
const addingEvidence = ref(false);
const questionImages = ref<File[]>([]);
const solutionImages = ref<File[]>([]);
const questionPreviews = ref<string[]>([]);
const solutionPreviews = ref<string[]>([]);
const imageWarnings = ref<string[]>([]);
const evidencePage = ref(1);
const EVIDENCE_PAGE_SIZE = 5;
const today = new Date().toISOString().slice(0, 10);

const entry = reactive({
  question_text: "", solution_text: "", knowledge: "",
  duration_minutes: 5, score: 0, max_score: 10,
});

const state = computed(() => result.value?.result.learning_state || null);
const gate = computed(() => state.value?.evidence_gate || null);
const dimensions = computed<DiagnosisDimensionState[]>(() => {
  if (!state.value) return [];
  if (dimensionTab.value === "question") return state.value.question_type_states;
  if (dimensionTab.value === "ability") return state.value.ability_states;
  return state.value.knowledge_states;
});
const pagedRecords = computed(() => {
  const start = (evidencePage.value - 1) * EVIDENCE_PAGE_SIZE;
  return records.value.slice(start, start + EVIDENCE_PAGE_SIZE);
});

const assessmentLabels: Record<LearningEvidenceDraft["assessment_type"], string> = {
  formal_exam: "正式考试", mock_exam: "模拟考试", diagnostic: "专项诊断",
  homework: "日常作业", practice: "自主练习", teacher_evaluation: "教师评价",
  agent_feedback: "辅导 Agent 反馈",
};
const levelLabels: Record<DiagnosisDimensionState["mastery_level"], string> = {
  insufficient_evidence: "证据不足", needs_support: "需要支持", developing: "发展中",
  proficient: "较熟练", strong: "稳定掌握",
};
const statusLabels = {
  insufficient_evidence: "证据不足", preliminary: "初步诊断", stable: "稳定诊断",
  review_required: "需要教师复核",
};

function setRecordImages(kind: "question" | "solution", event: Event) {
  const input = event.target as HTMLInputElement;
  const selected = Array.from(input.files || []).slice(0, 3);
  const filesRef = kind === "question" ? questionImages : solutionImages;
  const previewsRef = kind === "question" ? questionPreviews : solutionPreviews;
  previewsRef.value.forEach((url) => URL.revokeObjectURL(url));
  filesRef.value = selected;
  previewsRef.value = selected.map((file) => URL.createObjectURL(file));
  imageWarnings.value = [];
}

function clearRecordEntry() {
  [...questionPreviews.value, ...solutionPreviews.value].forEach((url) => URL.revokeObjectURL(url));
  questionImages.value = [];
  solutionImages.value = [];
  questionPreviews.value = [];
  solutionPreviews.value = [];
  entry.question_text = "";
  entry.solution_text = "";
  entry.knowledge = "";
  entry.score = 0;
}

async function addEvidence() {
  error.value = "";
  const hasQuestion = Boolean(entry.question_text.trim() || questionImages.value.length);
  const hasSolution = Boolean(entry.solution_text.trim() || solutionImages.value.length);
  if (!hasQuestion || !hasSolution || !entry.knowledge.trim()) {
    error.value = "请填写或上传题目、填写或上传解法，并填写对应知识点";
    return;
  }
  if (entry.score < 0 || entry.score > entry.max_score || entry.max_score <= 0) {
    error.value = "得分必须在 0 与满分之间";
    return;
  }
  if (entry.duration_minutes <= 0 || entry.duration_minutes > 240) {
    error.value = "作答用时请填写 0 到 240 分钟之间的有效数值";
    return;
  }
  addingEvidence.value = true;
  try {
    const parsed = questionImages.value.length || solutionImages.value.length
      ? await processLearningRecordImages(questionImages.value, solutionImages.value)
      : null;
    imageWarnings.value = parsed?.warnings || [];
    const questionText = [entry.question_text.trim(), parsed?.question_text.trim()]
      .filter(Boolean).join("\n") || "[题目由图片上传，OCR 未提取到可靠文字]";
    const solutionText = [entry.solution_text.trim(), parsed?.solution_text.trim()]
      .filter(Boolean).join("\n") || "[解法由图片上传，OCR 未提取到可靠文字]";
    const localId = `manual_${Date.now()}_${records.value.length}`;
    const stepTrace = `题目：${questionText}\n学生解法：${solutionText}`.slice(0, 2_000);
  records.value.push({
      local_id: localId,
    assessment_id: `manual_${today}`, assessment_type: "practice",
    question_id: `question_${Date.now()}_${records.value.length + 1}`,
    knowledge_tags: entry.knowledge.split(/[，,]/).map((item) => item.trim()).filter(Boolean),
      question_type: "学生导入题目", ability_tags: [], difficulty: 0.55,
      score: entry.score, max_score: entry.max_score,
      duration_seconds: Math.max(1, Math.round(entry.duration_minutes * 60)),
      error_tags: [], step_trace: stepTrace, occurred_at: today,
      source_id: `manual-upload:${localId}`,
      question_text: questionText, solution_text: solutionText,
      question_image_names: questionImages.value.map((file) => file.name),
      solution_image_names: solutionImages.value.map((file) => file.name),
  });
  evidencePage.value = Math.ceil(records.value.length / EVIDENCE_PAGE_SIZE);
  demoEvidence.value = false;
    clearRecordEntry();
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "学习记录图片处理失败";
  } finally {
    addingEvidence.value = false;
  }
}

function loadDemoEvidence() {
  const demo = [
    ["weekly_01", "q1", "函数单调性", "选择题", "数学抽象", 0.35, 6, 10, "concept_confusion", "把端点也直接代入判断"],
    ["weekly_01", "q4", "函数单调性", "解答题", "逻辑推理", 0.55, 4, 10, "condition_omission", "求导后没有检查定义域"],
    ["mock_01", "q7", "函数单调性", "填空题", "运算求解", 0.50, 5, 10, "concept_confusion", "增区间与导数符号对应反了"],
    ["mock_01", "q12", "导数应用", "解答题", "逻辑推理", 0.72, 3, 12, "condition_omission", "没有讨论参数范围"],
    ["homework_02", "q2", "函数单调性", "选择题", "数学抽象", 0.42, 8, 10, "", "能正确利用导数符号表"],
    ["homework_02", "q5", "导数应用", "解答题", "运算求解", 0.68, 5, 12, "calculation_error", "展开后符号计算出错"],
  ] as const;
  records.value = demo.map((item, index) => ({
    local_id: `demo_${index}`, assessment_id: item[0],
    assessment_type: item[0].startsWith("mock") ? "mock_exam" : "homework",
    question_id: item[1], knowledge_tags: [item[2]], question_type: item[3],
    ability_tags: [item[4]], difficulty: item[5], score: item[6], max_score: item[7],
    duration_seconds: 240 + index * 35, error_tags: item[8] ? [item[8]] : [],
    step_trace: item[9], occurred_at: `2026-07-${15 + index}`,
    source_id: `demo:${item[0]}:${item[1]}`,
  }));
  evidencePage.value = 1;
  demoEvidence.value = true;
  result.value = null;
  error.value = "";
}

async function diagnose() {
  if (!records.value.length) {
    error.value = "请先添加真实学习记录；也可以载入明确标注的演示证据体验流程";
    return;
  }
  loading.value = true;
  error.value = "";
  try {
    result.value = await runLearningDiagnosis({
      profile: props.profile, subject: subject.value,
      curriculumVersion: props.curriculumVersion,
      diagnosisRequest: demoEvidence.value ? `[演示数据，仅用于界面验收] ${diagnosisRequest.value}` : diagnosisRequest.value,
      records: records.value,
    });
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "诊断失败";
  } finally {
    loading.value = false;
  }
}

function resetWorkspace() {
  records.value = [];
  evidencePage.value = 1;
  result.value = null;
  demoEvidence.value = false;
  error.value = "";
  clearRecordEntry();
  imageWarnings.value = [];
}

function removeEvidence(localId: string) {
  records.value = records.value.filter((item) => item.local_id !== localId);
  evidencePage.value = Math.min(
    evidencePage.value,
    Math.max(1, Math.ceil(records.value.length / EVIDENCE_PAGE_SIZE)),
  );
}

onBeforeUnmount(() => {
  [...questionPreviews.value, ...solutionPreviews.value].forEach((url) => URL.revokeObjectURL(url));
});
</script>

<template>
  <div class="diagnosis-workspace">
    <ExamDiagnosisWorkspace
      v-if="mode !== 'records'"
      :profile="profile"
      :initial-subject="initialSubject"
      :initial-paper-id="initialPaperId"
    />
    <template v-else>
    <section class="diagnosis-hero student-module-hero">
      <div><span><Activity :size="15" /> 学情诊断 Agent</span><h1>让每一个结论，都能回到证据。</h1><p>融合不同作业、考试与练习记录，识别稳定薄弱点、题型表现和待验证错因；一次作答不会被草率贴标签。</p></div>
      <div class="hero-pipeline"><span><Database :size="18" /><b>多源证据</b></span><i /><span><ShieldCheck :size="18" /><b>充分性门控</b></span><i /><span><BrainCircuit :size="18" /><b>状态诊断</b></span></div>
    </section>

    <section v-if="!state" class="diagnosis-builder">
      <div class="evidence-editor diagnosis-panel">
        <header><div><small>STEP 01</small><h2>添加一道学习记录</h2><p>题目和解法都可以直接输入文字，也可以拍照上传；其余系统字段会自动生成。</p></div></header>
        <div class="record-capture-grid">
          <section class="record-capture-card"><header><Camera :size="19" /><div><strong>1. 题目内容</strong><small>文字和图片任选一种，也可以同时提供</small></div></header><textarea v-model="entry.question_text" rows="5" placeholder="在这里粘贴或输入完整题目…" /><div class="capture-divider"><i />或者上传题目图片<i /></div><label class="record-upload"><input type="file" accept="image/jpeg,image/png,image/webp" multiple @change="setRecordImages('question', $event)" /><UploadCloud :size="20" /><span><strong>{{ questionImages.length ? `已选择 ${questionImages.length} 张题目图片` : '上传题目图片' }}</strong><small>最多 3 张，单张不超过 10MB</small></span></label><div v-if="questionPreviews.length" class="record-previews"><img v-for="url in questionPreviews" :key="url" :src="url" alt="题目预览" /></div></section>
          <section class="record-capture-card"><header><FileImage :size="19" /><div><strong>2. 你的解法</strong><small>请填写或上传你实际使用的解题过程</small></div></header><textarea v-model="entry.solution_text" rows="5" placeholder="在这里输入具体解法、步骤或思路…" /><div class="capture-divider"><i />或者上传解法图片<i /></div><label class="record-upload"><input type="file" accept="image/jpeg,image/png,image/webp" multiple @change="setRecordImages('solution', $event)" /><UploadCloud :size="20" /><span><strong>{{ solutionImages.length ? `已选择 ${solutionImages.length} 张解法图片` : '上传解法图片' }}</strong><small>支持手写过程，最多 3 张</small></span></label><div v-if="solutionPreviews.length" class="record-previews"><img v-for="url in solutionPreviews" :key="url" :src="url" alt="解法预览" /></div></section>
        </div>
        <div class="simple-record-fields">
          <label><span>科目</span><select v-model="subject"><option value="chinese">语文</option><option value="mathematics">数学</option><option value="foreign_language">英语</option><option value="physics">物理</option><option value="chemistry">化学</option><option value="biology">生物</option><option value="history">历史</option><option value="geography">地理</option><option value="ideology_politics">政治</option><option value="technology">技术</option></select></label>
          <label class="knowledge-field"><span>对应知识点</span><input v-model="entry.knowledge" placeholder="如：函数单调性、导数应用（多个用逗号分隔）" /></label>
          <label><span>用时（分钟）</span><input v-model.number="entry.duration_minutes" type="number" min="0.1" max="240" step="0.5" /></label>
          <label><span>我的得分</span><input v-model.number="entry.score" type="number" min="0" /></label>
          <label><span>题目满分</span><input v-model.number="entry.max_score" type="number" min="1" /></label>
        </div>
        <div v-if="imageWarnings.length" class="record-image-warning"><AlertTriangle :size="16" />{{ imageWarnings.join('；') }}</div>
        <button class="add-evidence" type="button" :disabled="addingEvidence" @click="addEvidence"><LoaderCircle v-if="addingEvidence" class="spin" :size="17" /><Plus v-else :size="17" />{{ addingEvidence ? '正在读取图片并生成记录' : '保存这道题的学习记录' }}</button>

        <div class="evidence-list">
          <div class="list-title"><strong>已添加的题目记录</strong><span>{{ records.length }} 道题</span></div>
          <article v-for="(item, index) in pagedRecords" :key="item.local_id"><span>{{ (evidencePage - 1) * EVIDENCE_PAGE_SIZE + index + 1 }}</span><div><strong>{{ item.knowledge_tags.join('、') }}</strong><small>{{ item.question_text?.slice(0, 55) || '图片题目' }} · 用时 {{ Math.round((item.duration_seconds || 0) / 60 * 10) / 10 }} 分钟 · 得分 {{ item.score }}/{{ item.max_score }}</small><em v-if="item.question_image_names?.length || item.solution_image_names?.length">题目图 {{ item.question_image_names?.length || 0 }} 张 · 解法图 {{ item.solution_image_names?.length || 0 }} 张</em></div><button type="button" title="删除" @click="removeEvidence(item.local_id)"><Trash2 :size="15" /></button></article>
          <p v-if="!records.length"><FileSearch :size="21" />还没有学习记录，请从上方添加一道真实题目。</p>
          <PaginationControls :page="evidencePage" :total="records.length" :page-size="EVIDENCE_PAGE_SIZE" label="道题" @change="evidencePage=$event" />
        </div>
      </div>

      <aside class="diagnosis-side">
        <section class="diagnosis-panel gate-guide"><small>STEP 02</small><h2>提出诊断问题</h2><textarea v-model="diagnosisRequest" rows="5" /><div><ShieldCheck :size="18" /><span><b>最低证据门槛</b><small>初步判断：≥3 条、≥2 个独立测次<br />稳定判断：≥5 条、≥2 种题型</small></span></div><button class="run-diagnosis" :disabled="loading || !records.length" @click="diagnose"><LoaderCircle v-if="loading" class="spin" :size="18" /><Sparkles v-else :size="18" />{{ loading ? '模型正在生成双版本报告' : '开始学情诊断' }}</button></section>
        <section class="boundary-card"><AlertTriangle :size="19" /><div><strong>诊断边界</strong><p>不做性格、心理或医学判断；不把一次失误当成稳定错因；大模型负责解释，统计状态由可复核规则产生。</p></div></section>
      </aside>
    </section>

    <div v-if="error" class="diagnosis-error"><AlertTriangle :size="17" />{{ error }}</div>

    <template v-if="state && gate">
      <section v-if="demoEvidence" class="demo-result-banner"><FlaskConical :size="17" /><strong>演示诊断结果</strong><span>以下结果来自演示证据，不写入你的真实成绩档案。</span></section>
      <div class="diagnosis-summary-cards">
        <article><span><ClipboardCheck :size="20" /></span><div><small>诊断等级</small><strong>{{ statusLabels[state.diagnosis_status] }}</strong></div></article>
        <article><span><Database :size="20" /></span><div><small>有效证据</small><strong>{{ gate.valid_evidence_count }} 条 / {{ gate.independent_assessment_count }} 个测次</strong></div></article>
        <article><span><BarChart3 :size="20" /></span><div><small>覆盖与一致性</small><strong>{{ Math.round(gate.coverage_score * 100) }}% / {{ Math.round(gate.consistency_score * 100) }}%</strong></div></article>
        <article><span><RefreshCw :size="20" /></span><div><small>状态版本</small><strong>v{{ state.state_version }} · {{ state.review_status }}</strong></div></article>
      </div>

      <section class="gate-result" :class="gate.sufficiency_level"><div><ShieldCheck :size="23" /><span><small>EVIDENCE GATE</small><strong>{{ gate.allowed_conclusion }}</strong><p>{{ gate.valid_evidence_count }} 条有效证据 · {{ gate.question_type_count }} 种题型 · {{ gate.difficulty_band_count }} 个难度层</p></span></div><button @click="resetWorkspace"><Plus :size="16" />录入新一轮证据</button></section>

      <div class="diagnosis-result-grid">
        <section class="diagnosis-panel state-panel">
          <header><div><small>STRUCTURED STATE</small><h2>多维学习状态</h2></div><div class="dimension-tabs"><button :class="{ active: dimensionTab === 'knowledge' }" @click="dimensionTab = 'knowledge'">知识点</button><button :class="{ active: dimensionTab === 'question' }" @click="dimensionTab = 'question'">题型</button><button :class="{ active: dimensionTab === 'ability' }" @click="dimensionTab = 'ability'">能力</button></div></header>
          <div class="dimension-list"><article v-for="item in dimensions" :key="item.dimension_id"><div><span><strong>{{ item.dimension_label }}</strong><small>{{ levelLabels[item.mastery_level] }} · 置信度 {{ Math.round(item.confidence * 100) }}%</small></span><b>{{ Math.round(item.mastery_probability * 100) }}%</b></div><span class="dimension-bar"><i :style="{ width: `${item.mastery_probability * 100}%` }" /></span><p><span>可信区间 {{ Math.round(item.credible_interval_low * 100) }}%—{{ Math.round(item.credible_interval_high * 100) }}%</span><span>{{ item.valid_evidence_count }} 条证据 · {{ item.independent_assessment_count }} 测次</span></p><small class="basis">{{ item.status_basis }}</small></article><p v-if="!dimensions.length" class="empty-dimension">这一维度尚无可用标签，需补充结构化证据。</p></div>
        </section>

        <section class="diagnosis-panel report-panel"><header><div><small>LLM REPORT</small><h2>双版本诊断报告</h2></div><span :class="state.narrative.generation_mode"><i />{{ state.narrative.generation_mode === 'llm' ? '真实模型生成' : '模型未生成' }}</span></header><div class="report-tabs"><button :class="{ active: reportTab === 'student' }" @click="reportTab = 'student'">学生版</button><button :class="{ active: reportTab === 'teacher' }" @click="reportTab = 'teacher'">教师版</button></div><div v-if="state.narrative.generation_mode === 'llm'" class="report-copy"><p>{{ reportTab === 'student' ? state.narrative.student_summary : state.narrative.teacher_summary }}</p><div><strong>证据边界</strong><p>{{ state.narrative.evidence_boundary }}</p></div><div><strong>下一步需要的证据</strong><p>{{ state.narrative.next_evidence_request }}</p></div></div><div v-else class="model-unavailable"><AlertTriangle :size="22" /><strong>模型报告未生成</strong><p>页面仅展示结构化状态，没有使用固定模板冒充大模型输出。</p></div></section>
      </div>

      <div class="evidence-findings">
        <section class="diagnosis-panel"><header><div><small>OBSERVED FACTS</small><h2>已观察事实</h2></div><CheckCircle2 :size="20" /></header><ul><li v-for="fact in state.observed_facts" :key="fact">{{ fact }}</li></ul></section>
        <section class="diagnosis-panel"><header><div><small>STABLE PATTERNS</small><h2>稳定错误模式</h2></div><TrendingUp :size="20" /></header><div v-if="state.stable_error_patterns.length" class="pattern-list"><article v-for="item in state.stable_error_patterns" :key="item.pattern_id"><strong>{{ item.label }}</strong><p>{{ item.description }}</p><small>{{ item.occurrence_count }} 次 / {{ item.independent_assessment_count }} 测次 · 置信度 {{ Math.round(item.confidence * 100) }}%</small></article></div><p v-else class="finding-empty">尚无跨独立测次重复出现的错误模式。</p></section>
        <section class="diagnosis-panel"><header><div><small>HYPOTHESES</small><h2>待验证原因假设</h2></div><BrainCircuit :size="20" /></header><div v-if="state.cause_hypotheses.length" class="pattern-list"><article v-for="item in state.cause_hypotheses" :key="item.hypothesis_id"><strong>{{ item.hypothesis }}</strong><p>验证方式：{{ item.verification_needed }}</p><small>支持证据 {{ item.support.length }} 条 · 置信度 {{ Math.round(item.confidence * 100) }}%</small></article></div><p v-else class="finding-empty">过程证据不足，Agent 没有臆测原因。</p></section>
      </div>
    </template>
    </template>
  </div>
</template>

<style scoped>
.diagnosis-workspace{display:grid;gap:17px}
.diagnosis-hero{position:relative;display:flex;min-height:210px;align-items:center;justify-content:space-between;overflow:hidden;padding:34px 38px;color:#fff;background:linear-gradient(135deg,#123873,#1767d8 64%,#19a5a0);border-radius:18px;box-shadow:0 20px 42px rgba(21,94,239,.16)}
.diagnosis-hero>div:first-child{z-index:1;max-width:720px}
.diagnosis-hero>div:first-child>span{display:inline-flex;align-items:center;gap:6px;color:#d9ecff;font-size:10px;font-weight:800}
.diagnosis-hero h1{margin:16px 0 10px;font-size:clamp(26px,3vw,39px);letter-spacing:-.04em}
.diagnosis-hero p{max-width:690px;margin:0;color:rgba(255,255,255,.77);font-size:11px;line-height:1.85}
.hero-pipeline{z-index:1;display:flex;align-items:center;gap:9px;padding:19px;border:1px solid rgba(255,255,255,.2);background:rgba(255,255,255,.09);border-radius:13px}
.hero-pipeline span{display:grid;justify-items:center;gap:7px;min-width:72px}
.hero-pipeline b{font-size:9px}
.hero-pipeline i{width:18px;height:1px;background:rgba(255,255,255,.35)}
.diagnosis-builder{display:grid;grid-template-columns:minmax(0,1.65fr) minmax(280px,.75fr);gap:17px}
.diagnosis-panel{padding:23px;border:1px solid #dfe7f2;background:#fff;border-radius:15px;box-shadow:0 5px 18px rgba(27,55,96,.055)}
.diagnosis-panel header{display:flex;align-items:flex-start;justify-content:space-between;gap:14px;padding-bottom:17px;border-bottom:1px solid #edf1f7}
.diagnosis-panel header small,.gate-guide>small{color:#5e87c6;font-size:8px;font-weight:850;letter-spacing:.13em}
.diagnosis-panel h2,.gate-guide h2{margin:5px 0 0;color:#1e385e;font-size:16px}
.diagnosis-panel header p{margin:5px 0 0;color:#8291a6;font-size:9px}
.demo-load{display:flex;align-items:center;gap:6px;min-height:36px;padding:0 11px;color:#486582;border:1px solid #d8e2ef;background:#f8fbff;border-radius:8px;font-size:9px;font-weight:700}
.demo-evidence-note,.demo-result-banner{display:flex;align-items:center;gap:8px;margin-top:14px;padding:11px 13px;color:#8a6414;border:1px solid #f0d99e;background:#fff9e9;border-radius:9px;font-size:9px}
.diagnosis-form-grid{display:grid;gap:12px;margin-top:16px}
.diagnosis-form-grid.three{grid-template-columns:repeat(3,1fr)}
.diagnosis-form-grid label,.score-entry label,.trace-field{display:grid;gap:6px}
.diagnosis-form-grid span,.score-entry span,.trace-field>span{color:#405878;font-size:9px;font-weight:750}
.diagnosis-form-grid input,.diagnosis-form-grid select,.score-entry input[type=number],.trace-field textarea,.gate-guide textarea{width:100%;border:1px solid #d9e3ef;background:#fbfcff;border-radius:8px;color:#2d4463;font-size:10px}
.diagnosis-form-grid input,.diagnosis-form-grid select,.score-entry input[type=number]{height:40px;padding:0 10px}
.record-capture-grid{display:grid;grid-template-columns:1fr 1fr;gap:13px;margin-top:16px}.record-capture-card{padding:15px;border:1px solid #dce6f1;background:#f9fbfe;border-radius:12px}.record-capture-card>header{display:flex;align-items:center;justify-content:flex-start;gap:9px;padding:0 0 11px;color:#1764ca;border-bottom:0}.record-capture-card>header>div{display:grid;gap:3px}.record-capture-card>header strong{color:#304c6f;font-size:10px}.record-capture-card>header small{color:#8797aa;font-size:8px}.record-capture-card>textarea{width:100%;padding:11px;color:#2f4868;border:1px solid #d9e3ee;background:#fff;border-radius:9px;font-size:10px;line-height:1.7;resize:vertical}.capture-divider{display:flex;align-items:center;gap:8px;margin:10px 0;color:#98a5b5;font-size:8px}.capture-divider i{height:1px;flex:1;background:#e2e8ef}.record-upload{display:flex;align-items:center;gap:9px;padding:11px;color:#326a9e;border:1px dashed #9abadd;background:#f3f8ff;border-radius:9px;cursor:pointer}.record-upload input{display:none}.record-upload>span{display:grid;gap:3px}.record-upload strong{font-size:9px}.record-upload small{color:#8295a9;font-size:7px}.record-previews{display:flex;gap:7px;margin-top:9px}.record-previews img{width:72px;height:62px;object-fit:cover;border:1px solid #dce5ef;border-radius:7px}.simple-record-fields{display:grid;grid-template-columns:120px minmax(220px,1fr) 120px 100px 100px;gap:10px;margin-top:13px;padding:14px;background:#f3f7fc;border-radius:11px}.simple-record-fields label{display:grid;gap:6px}.simple-record-fields span{color:#405878;font-size:9px;font-weight:750}.simple-record-fields input,.simple-record-fields select{width:100%;height:40px;padding:0 10px;color:#2d4463;border:1px solid #d9e3ef;background:#fff;border-radius:8px;font-size:10px}.record-image-warning{display:flex;align-items:center;gap:7px;margin-top:10px;padding:10px;color:#8a6414;background:#fff9e9;border-radius:8px;font-size:8px}
.score-entry{display:grid;grid-template-columns:1fr 90px auto 90px;align-items:end;gap:11px;margin-top:14px;padding:14px;background:#f7faff;border-radius:10px}
.score-entry>b{padding-bottom:11px;color:#95a3b5}
.trace-field{margin-top:13px}
.trace-field textarea,.gate-guide textarea{padding:10px;line-height:1.6;resize:vertical}
.add-evidence,.run-diagnosis{display:flex;min-height:42px;align-items:center;justify-content:center;gap:7px;margin-top:13px;color:#fff;border:0;background:linear-gradient(135deg,#155eef,#198fbe);border-radius:9px;font-size:10px;font-weight:800}
.add-evidence{width:100%}
.add-evidence:disabled{opacity:.55}
.evidence-list{margin-top:18px}
.list-title{display:flex;align-items:center;justify-content:space-between;padding-bottom:10px;color:#3b526f;font-size:10px}
.list-title span{color:#8494a9;font-size:9px}
.evidence-list article{display:flex;align-items:center;gap:10px;padding:11px 7px;border-top:1px solid #edf1f6}
.evidence-list article>span{display:grid;width:27px;height:27px;place-items:center;color:#155eef;background:#eaf2ff;border-radius:8px;font-size:9px;font-weight:800}
.evidence-list article>div{display:grid;flex:1;gap:4px}
.evidence-list article strong{color:#344b6b;font-size:10px}
.evidence-list article small{color:#8998ab;font-size:8px}
.evidence-list article em{color:#4786a8;font-size:8px;font-style:normal}
.evidence-list article button{display:grid;width:30px;height:30px;place-items:center;color:#9a6670;border:0;background:transparent}
.evidence-list>p{display:grid;justify-items:center;gap:8px;padding:28px;color:#91a0b2;font-size:9px}
.diagnosis-side{display:grid;align-content:start;gap:14px}
.gate-guide>textarea{margin-top:15px}
.gate-guide>div{display:flex;gap:9px;margin-top:15px;padding:13px;color:#285f90;background:#edf7ff;border-radius:9px}
.gate-guide>div span{display:grid;gap:4px}
.gate-guide>div b{font-size:10px}
.gate-guide>div small{color:#69839b;font-size:8px;line-height:1.65}
.run-diagnosis{width:100%;min-height:48px}
.run-diagnosis:disabled{opacity:.5}
.boundary-card{display:flex;gap:10px;padding:17px;color:#805d17;border:1px solid #eed89f;background:#fffaf0;border-radius:12px}
.boundary-card div{display:grid;gap:6px}
.boundary-card strong{font-size:10px}
.boundary-card p{margin:0;color:#7d7055;font-size:9px;line-height:1.65}
.diagnosis-error{display:flex;align-items:center;gap:8px;padding:13px 15px;color:#b43b48;border:1px solid #f0c4ca;background:#fff3f4;border-radius:10px;font-size:10px}
.demo-result-banner{margin:0}
.demo-result-banner span{color:#8b7850}
.diagnosis-summary-cards{display:grid;grid-template-columns:repeat(4,1fr);gap:13px}
.diagnosis-summary-cards article{display:flex;align-items:center;gap:11px;padding:15px 17px;border:1px solid #dfe7f2;background:#fff;border-radius:12px}
.diagnosis-summary-cards article>span{display:grid;width:38px;height:38px;place-items:center;color:#1761cf;background:#eaf2ff;border-radius:10px}
.diagnosis-summary-cards article>div{display:grid;gap:4px}
.diagnosis-summary-cards small{color:#8b98aa;font-size:8px}
.diagnosis-summary-cards strong{color:#2c4464;font-size:10px}
.gate-result{display:flex;align-items:center;justify-content:space-between;padding:17px 20px;border:1px solid #bedecf;background:#effaf5;border-radius:12px}
.gate-result>div{display:flex;align-items:center;gap:12px;color:#21805c}
.gate-result>div span{display:grid;gap:4px}
.gate-result small{font-size:8px;font-weight:850}
.gate-result strong{color:#315c4b;font-size:11px}
.gate-result p{margin:0;color:#739184;font-size:8px}
.gate-result.insufficient{border-color:#ecd498;background:#fff9e9}
.gate-result.insufficient>div{color:#a87310}
.gate-result button{display:flex;align-items:center;gap:6px;padding:9px 12px;color:#3b6171;border:1px solid #cfe1de;background:#fff;border-radius:8px;font-size:9px}
.diagnosis-result-grid{display:grid;grid-template-columns:1.18fr .82fr;gap:16px}
.dimension-tabs,.report-tabs{display:flex;gap:4px;padding:3px;background:#f0f4f9;border-radius:8px}
.dimension-tabs button,.report-tabs button{padding:7px 10px;color:#75859a;border:0;background:transparent;border-radius:6px;font-size:8px}
.dimension-tabs button.active,.report-tabs button.active{color:#155eef;background:#fff;box-shadow:0 2px 7px rgba(31,65,110,.1)}
.dimension-list{display:grid;gap:11px;margin-top:15px}
.dimension-list article{padding:14px;border:1px solid #e4eaf3;background:#fbfcff;border-radius:10px}
.dimension-list article>div{display:flex;justify-content:space-between}
.dimension-list article>div span{display:grid;gap:3px}
.dimension-list strong{color:#334b69;font-size:10px}
.dimension-list small{color:#8594a8;font-size:8px}
.dimension-list b{color:#1761cf;font-size:15px}
.dimension-bar{display:block;height:6px;margin:12px 0 8px;overflow:hidden;background:#e5ecf5;border-radius:4px}
.dimension-bar i{display:block;height:100%;background:linear-gradient(90deg,#155eef,#2bb6a3)}
.dimension-list article>p{display:flex;justify-content:space-between;margin:0;color:#7789a0;font-size:8px}
.basis{display:block;margin-top:8px;padding-top:7px;border-top:1px solid #edf1f6}
.empty-dimension,.finding-empty{color:#8998ab;font-size:9px}
.report-panel header>span{display:flex;align-items:center;gap:5px;color:#277759;font-size:8px}
.report-panel header>span i{width:6px;height:6px;background:#28a778;border-radius:50%}
.report-panel header>span.unavailable{color:#aa7016}
.report-panel header>span.unavailable i{background:#d19b3b}
.report-tabs{width:max-content;margin-top:15px}
.report-copy{display:grid;gap:13px;margin-top:14px}
.report-copy>p{min-height:105px;margin:0;color:#49617f;font-size:10px;line-height:1.9;white-space:pre-wrap}
.report-copy>div{padding:12px;background:#f5f8fc;border-radius:9px}
.report-copy strong{color:#38516e;font-size:9px}
.report-copy>div p{margin:5px 0 0;color:#70829a;font-size:9px;line-height:1.7}
.model-unavailable{display:grid;justify-items:center;gap:8px;margin-top:35px;padding:25px;color:#a66f19;text-align:center;background:#fff9e9;border-radius:10px}
.model-unavailable strong{font-size:10px}
.model-unavailable p{margin:0;color:#8d7b5b;font-size:9px}
.evidence-findings{display:grid;grid-template-columns:repeat(3,1fr);gap:15px}
.evidence-findings header svg{color:#4f7fb8}
.evidence-findings ul{display:grid;gap:9px;margin:14px 0 0;padding-left:17px;color:#526981;font-size:9px;line-height:1.65}
.pattern-list{display:grid;gap:9px;margin-top:13px}
.pattern-list article{padding:12px;background:#f7faff;border-radius:9px}
.pattern-list strong{color:#38506e;font-size:10px}
.pattern-list p{margin:5px 0;color:#6f8198;font-size:9px;line-height:1.55}
.pattern-list small{color:#8897aa;font-size:8px}
@media(max-width:1100px){
  .diagnosis-builder,.diagnosis-result-grid{grid-template-columns:1fr}
  .simple-record-fields{grid-template-columns:1fr 2fr 1fr 1fr 1fr}
  .diagnosis-summary-cards{grid-template-columns:repeat(2,1fr)}
  .evidence-findings{grid-template-columns:1fr 1fr}
  .hero-pipeline{display:none}
}
@media(max-width:720px){
  .diagnosis-hero{padding:27px 23px}
  .diagnosis-form-grid.three,.evidence-findings{grid-template-columns:1fr}
  .record-capture-grid,.simple-record-fields{grid-template-columns:1fr}
  .score-entry{grid-template-columns:1fr 1fr}
  .score-entry>b{display:none}
  .diagnosis-summary-cards{grid-template-columns:1fr}
  .gate-result{align-items:flex-start;flex-direction:column;gap:12px}
  .diagnosis-panel{padding:18px}
}
/* Readable evidence entry and diagnosis reports. */
.learning-diagnosis-page{font-size:15px;line-height:1.55}.diagnosis-panel header p{font-size:13px}.diagnosis-form-grid span,.score-entry span,.trace-field>span,.simple-record-fields span{font-size:14px}.diagnosis-form-grid input,.diagnosis-form-grid select,.score-entry input[type=number],.trace-field textarea,.gate-guide textarea,.simple-record-fields input,.simple-record-fields select,.record-capture-card>textarea{font-size:15px}
.record-capture-card>header strong,.record-upload strong,.list-title,.evidence-list article strong,.gate-guide>div b,.boundary-card strong,.diagnosis-summary-cards strong,.dimension-list strong,.report-copy strong,.pattern-list strong{font-size:14px}.record-capture-card>header small,.record-upload small,.evidence-list article small,.evidence-list article em,.gate-guide>div small,.boundary-card p,.diagnosis-summary-cards small,.dimension-list small,.dimension-list article>p,.report-copy>div p,.pattern-list p,.pattern-list small{font-size:12px}.report-copy>p,.evidence-findings ul{font-size:14px}
.add-evidence,.run-diagnosis,.demo-load,.dimension-tabs button,.report-tabs button{min-height:42px;font-size:14px}
.diagnosis-workspace{font-size:15px;line-height:1.55}
</style>
