<script setup lang="ts">
import {
  BarChart3,
  BookOpenCheck,
  BrainCircuit,
  CalendarDays,
  Check,
  CheckCircle2,
  ChevronRight,
  CircleAlert,
  Clock3,
  Database,
  GraduationCap,
  LayoutDashboard,
  LoaderCircle,
  LogOut,
  Menu,
  MessageCircleQuestion,
  PanelLeftClose,
  PanelLeftOpen,
  RefreshCw,
  Send,
  ShieldCheck,
  Sparkles,
  Target,
  TrendingUp,
  UserRound,
  X,
} from "@lucide/vue";
import { computed, reactive, ref } from "vue";

import HomeworkTutorWorkspace from "@/components/HomeworkTutorWorkspace.vue";
import { callAgent } from "@/lib/agent-client";
import {
  defaultSubjects,
  editionEvidenceLabel,
  getProvinceRoute,
  isSubjectSelectionValid,
  planningSubjectKeys,
  progressGroups,
  provinceRoutes,
  provinceSubjectKeys,
  selectProvinceSubject,
  subjectEditions,
  subjectLabels,
  subjectScoreMax,
} from "@/lib/curriculum-catalog";
import type {
  AgentEnvelope,
  PlannerFormData,
  StudentLoginProfile,
  SubjectKey,
} from "@/lib/types";

type View = "workspace" | "tutor" | "plan" | "knowledge" | "feedback";

const props = defineProps<{ profile: StudentLoginProfile }>();
const emit = defineEmits<{ logout: [] }>();

const initialSubject: SubjectKey = "mathematics";
const initialEdition = subjectEditions(initialSubject)[0]?.id || "";
const initialProgress = progressGroups(initialSubject, initialEdition)[0]?.options[0]?.id || "";
const initialProvince = getProvinceRoute(props.profile.provinceCode);

const form = reactive<PlannerFormData>({
  studentId: props.profile.studentId,
  grade: props.profile.grade,
  schoolTerm: `${props.profile.grade}_term_1`,
  provinceCode: props.profile.provinceCode,
  targetExamYear: props.profile.targetExamYear,
  selectedSubjects: defaultSubjects(initialProvince),
  planningSubject: initialSubject,
  curriculumVersion: initialEdition,
  classProgress: initialProgress,
  currentScore: 92,
  targetScore: 120,
  deadline: `${props.profile.targetExamYear}-05-20`,
  weeklyMinutes: 630,
  weekdayMinutes: 70,
  weekendMinutes: 140,
  foundationMastery: 48,
  applicationMastery: 36,
});

const activeView = ref<View>("workspace");
const sidebarOpen = ref(false);
const sidebarCollapsed = ref(
  window.localStorage.getItem("ai_education_sidebar_collapsed") === "true",
);
const loading = ref(false);
const confirming = ref(false);
const feedbackLoading = ref(false);
const confirmed = ref(false);
const error = ref("");
const toast = ref("");
const response = ref<AgentEnvelope | null>(null);
const feedbackCorrect = ref(true);
const feedbackMinutes = ref(35);
const feedbackTaskId = ref("");
const feedbackResult = ref("");

const province = computed(() => getProvinceRoute(form.provinceCode));
const selectableSubjects = computed(() => provinceSubjectKeys(province.value));
const planningSubjects = computed(() => planningSubjectKeys(form.selectedSubjects));
const editions = computed(() => subjectEditions(form.planningSubject));
const chapterGroups = computed(() => progressGroups(form.planningSubject, form.curriculumVersion));
const scoreMax = computed(() => subjectScoreMax(form.planningSubject));
const planningSubjectLabel = computed(() => subjectLabels[form.planningSubject]);
const selectionValid = computed(() => isSubjectSelectionValid(province.value, form.selectedSubjects));
const selectedChapter = computed(() => chapterGroups.value
  .flatMap((group) => group.options)
  .find((item) => item.id === form.classProgress));
const plan = computed(() => response.value?.result?.plan);
const knowledge = computed(() => response.value?.result?.knowledge_profile);
const confidence = computed(() => Math.round((knowledge.value?.assessment_quality.confidence || 0.81) * 100));
const planValidationIssues = computed(() => plan.value?.validation?.errors || []);

const validationLabels: Record<string, string> = {
  policy_current: "考试政策有效性",
  exam_profile_match: "考试配置一致性",
  capacity_within_limit: "学习时长容量",
  subject_budgets_respected: "学科时间预算",
  buffer_reserved: "机动缓冲",
  focus_limit: "单次专注时长",
  content_available: "学习资源可用性",
  dates_valid: "任务日期范围",
  prerequisites_ordered: "前置知识顺序",
  target_gap_coverage: "薄弱知识覆盖",
  spaced_review_included: "间隔复习任务",
  timed_training_included: "限时训练任务",
  assessment_included: "阶段测评任务",
  subject_selection_legal: "地区选科规则",
};

const navItems: Array<{ id: View; label: string; icon: typeof LayoutDashboard }> = [
  { id: "workspace", label: "规划中心", icon: LayoutDashboard },
  { id: "tutor", label: "作业辅导", icon: MessageCircleQuestion },
  { id: "plan", label: "我的计划", icon: CalendarDays },
  { id: "knowledge", label: "知识画像", icon: BrainCircuit },
  { id: "feedback", label: "练习反馈", icon: BarChart3 },
];

const taskNames: Record<string, string> = {
  concept_repair: "概念修复",
  targeted_practice: "专项训练",
  spaced_review: "间隔复习",
  timed_training: "限时训练",
  stage_assessment: "阶段测评",
};

function subjectDefaults(subject: SubjectKey) {
  const version = subjectEditions(subject)[0]?.id || "";
  const progress = progressGroups(subject, version)[0]?.options[0]?.id || "";
  const max = subjectScoreMax(subject);
  return {
    planningSubject: subject,
    curriculumVersion: version,
    classProgress: progress,
    currentScore: max === 150 ? 92 : 62,
    targetScore: max === 150 ? 120 : 80,
  };
}

function changeProvince(event: Event) {
  const code = (event.target as HTMLSelectElement).value;
  const route = getProvinceRoute(code);
  form.provinceCode = code;
  form.selectedSubjects = defaultSubjects(route);
  if (!planningSubjectKeys(form.selectedSubjects).includes(form.planningSubject)) {
    Object.assign(form, subjectDefaults("mathematics"));
  }
}

function toggleSubject(key: SubjectKey) {
  form.selectedSubjects = selectProvinceSubject(province.value, form.selectedSubjects, key);
  if (!planningSubjectKeys(form.selectedSubjects).includes(form.planningSubject)) {
    Object.assign(form, subjectDefaults("mathematics"));
  }
}

function changePlanningSubject(event: Event) {
  Object.assign(form, subjectDefaults((event.target as HTMLSelectElement).value as SubjectKey));
}

function changeEdition(event: Event) {
  const version = (event.target as HTMLSelectElement).value;
  form.curriculumVersion = version;
  form.classProgress = progressGroups(form.planningSubject, version)[0]?.options[0]?.id || "";
}

function navigate(view: View) {
  sidebarOpen.value = false;
  if (!["workspace", "tutor"].includes(view) && !plan.value) {
    showToast("请先生成第一份学习计划");
    activeView.value = "workspace";
    return;
  }
  activeView.value = view;
}

function toggleSidebar() {
  sidebarCollapsed.value = !sidebarCollapsed.value;
  window.localStorage.setItem("ai_education_sidebar_collapsed", String(sidebarCollapsed.value));
}

function showToast(message: string) {
  toast.value = message;
  window.setTimeout(() => { toast.value = ""; }, 3000);
}

async function generatePlan() {
  if (!selectionValid.value || !form.classProgress) {
    error.value = "请先完成合法选科并确认教材章节";
    return;
  }
  loading.value = true;
  error.value = "";
  try {
    const result = await callAgent({ action: "initialize", form: { ...form } });
    if (!result.result?.plan) throw new Error("Agent 未返回可展示的学习计划");
    response.value = result;
    confirmed.value = result.result.plan.status === "active";
    feedbackTaskId.value = result.result.plan.tasks[0]?.task_id || "";
    activeView.value = "plan";
    showToast("个性化学习计划已生成");
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "生成失败，请稍后重试";
  } finally {
    loading.value = false;
  }
}

async function confirmPlan() {
  if (!plan.value) return;
  if (!plan.value.validation?.valid) {
    error.value = `计划暂不能发布：${planValidationIssues.value
      .map((item) => validationLabels[item] || item)
      .join("、")}`;
    return;
  }
  confirming.value = true;
  error.value = "";
  try {
    await callAgent({
      action: "confirm",
      planId: plan.value.plan_id,
      studentId: form.studentId,
      version: plan.value.version,
    });
    confirmed.value = true;
    showToast("计划已确认并开始执行");
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "确认失败";
  } finally {
    confirming.value = false;
  }
}

async function submitFeedback() {
  if (!plan.value) return;
  feedbackLoading.value = true;
  error.value = "";
  feedbackResult.value = "";
  try {
    const now = Date.now();
    const result = await callAgent({
      action: "practice",
      studentId: form.studentId,
      event: {
        event_id: `evt_${now}`,
        student_id: form.studentId,
        session_id: `practice_${now}`,
        task_id: feedbackTaskId.value,
        item_id: `item_${now}`,
        subject: form.planningSubject,
        knowledge_ids: [`${form.classProgress}_foundation`],
        event_type: "answer_submitted",
        timestamp: new Date().toISOString(),
        response: {
          correct: feedbackCorrect.value,
          score: feedbackCorrect.value ? 5 : 0,
          max_score: 5,
          difficulty: 0.6,
        },
        behavior: {
          response_time_seconds: feedbackMinutes.value * 60,
          hint_count: feedbackCorrect.value ? 0 : 1,
          attempt_count: 1,
        },
      },
    });
    const quality = result.result?.practice_update?.quality_score;
    feedbackResult.value = typeof quality === "number"
      ? `反馈已入库，本次证据质量 ${Math.round(quality * 100)}%`
      : "反馈已入库，Agent 已完成调整规则检查";
    showToast("练习证据已提交");
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "提交失败";
  } finally {
    feedbackLoading.value = false;
  }
}

function extractionLabel(method?: string) {
  if (method === "PDF_OCR_TOC") return "扫描目录 OCR";
  if (method === "PDF_TEXT_TOC") return "PDF 目录文本";
  return "目录待人工复核";
}

function formatDate(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat("zh-CN", { month: "short", day: "numeric" }).format(date);
}

function minutesLabel(value: number) {
  const hours = Math.floor(value / 60);
  const minutes = value % 60;
  return hours ? `${hours} 小时${minutes ? ` ${minutes} 分` : ""}` : `${minutes} 分钟`;
}
</script>

<template>
  <div class="app-shell" :class="{ 'sidebar-collapsed': sidebarCollapsed }">
    <div v-if="sidebarOpen" class="sidebar-mask" @click="sidebarOpen = false" />
    <aside class="app-sidebar" :class="{ open: sidebarOpen }">
      <div class="workspace-brand">
        <span><GraduationCap :size="25" /></span>
        <div><strong>知途 AI</strong><small>双智能体学习中心</small></div>
        <button class="sidebar-collapse" :title="sidebarCollapsed ? '展开侧栏' : '收起侧栏'" @click="toggleSidebar"><PanelLeftOpen v-if="sidebarCollapsed" :size="18" /><PanelLeftClose v-else :size="18" /></button>
        <button class="sidebar-close" aria-label="关闭菜单" @click="sidebarOpen = false"><X :size="19" /></button>
      </div>

      <nav class="workspace-nav">
        <small>学习空间</small>
        <button v-for="item in navItems" :key="item.id" :class="{ active: activeView === item.id }" @click="navigate(item.id)">
          <component :is="item.icon" :size="19" />
          <span>{{ item.label }}</span>
          <i v-if="!['workspace', 'tutor'].includes(item.id) && !plan" />
        </button>
      </nav>

      <div class="sidebar-profile">
        <span class="avatar">{{ profile.studentName.slice(0, 1) }}</span>
        <div><strong>{{ profile.studentName }}</strong><small>{{ profile.studentId }}</small></div>
        <button title="退出登录" @click="emit('logout')"><LogOut :size="17" /></button>
      </div>
    </aside>

    <main class="app-main">
      <header class="topbar">
        <button class="mobile-menu" aria-label="打开菜单" @click="sidebarOpen = true"><Menu :size="21" /></button>
        <button class="desktop-sidebar-toggle" :title="sidebarCollapsed ? '展开侧栏' : '收起侧栏'" @click="toggleSidebar"><PanelLeftOpen v-if="sidebarCollapsed" :size="19" /><PanelLeftClose v-else :size="19" /></button>
        <div><small>AI EDUCATION</small><strong>{{ activeView === 'workspace' ? '个性化学习规划' : navItems.find((item) => item.id === activeView)?.label }}</strong></div>
        <span class="service-state"><i /> 2 个 Agent 服务可用</span>
      </header>

      <div class="page-content">
        <template v-if="activeView === 'workspace'">
          <section class="welcome-hero">
            <div>
              <span class="eyebrow light"><Sparkles :size="15" /> 学习规划 Agent</span>
              <h1>{{ profile.studentName }}，今天也向目标靠近一步。</h1>
              <p>确认教材进度、当前学情和可用时间，系统会生成一份有证据、能执行、可持续调整的学习路径。</p>
            </div>
            <div class="hero-database"><Database :size="24" /><span><strong>329 册</strong><small>本地教材 PDF</small></span><span><strong>1,336</strong><small>章节选项</small></span></div>
          </section>

          <div class="overview-cards">
            <article><span><UserRound :size="20" /></span><div><small>当前档案</small><strong>{{ profile.grade === 'grade_10' ? '高一' : profile.grade === 'grade_11' ? '高二' : '高三' }} · {{ province.name }}</strong></div></article>
            <article><span><Target :size="20" /></span><div><small>目标年份</small><strong>{{ form.targetExamYear }} 年高考</strong></div></article>
            <article><span><Clock3 :size="20" /></span><div><small>每周可用</small><strong>{{ minutesLabel(form.weeklyMinutes) }}</strong></div></article>
            <article><span><ShieldCheck :size="20" /></span><div><small>目录证据</small><strong>50 个教材版本</strong></div></article>
          </div>

          <section class="planner-card">
            <div class="section-heading"><div><span>01</span><div><h2>确认学习范围</h2><p>地区决定选科规则，教材版本以学校实际用书为准。</p></div></div><BookOpenCheck :size="23" /></div>
            <div class="form-grid three">
              <label><span>所在地区</span><select :value="form.provinceCode" @change="changeProvince"><option v-for="item in provinceRoutes" :key="item.code" :value="item.code">{{ item.name }}省 · {{ item.exam_mode }}</option></select></label>
              <label><span>重点规划科目</span><select :value="form.planningSubject" @change="changePlanningSubject"><option v-for="key in planningSubjects" :key="key" :value="key">{{ subjectLabels[key] }}</option></select></label>
              <label><span>目标高考年份</span><select v-model.number="form.targetExamYear"><option v-for="year in [2027, 2028, 2029, 2030]" :key="year" :value="year">{{ year }} 年</option></select></label>
            </div>
            <div class="subject-picker">
              <div><strong>高考选科组合</strong><small>{{ province.selection_rule }}</small></div>
              <div class="subject-chips"><button v-for="key in selectableSubjects" :key="key" :class="{ selected: form.selectedSubjects.includes(key) }" type="button" @click="toggleSubject(key)"><Check v-if="form.selectedSubjects.includes(key)" :size="13" />{{ subjectLabels[key] }}</button></div>
              <p v-if="!selectionValid" class="inline-warning"><CircleAlert :size="15" /> 当前组合不符合地区选科规则</p>
            </div>

            <div class="form-grid two">
              <label><span>{{ planningSubjectLabel }}教材版本</span><select :value="form.curriculumVersion" @change="changeEdition"><option v-for="item in editions" :key="item.id" :value="item.id">{{ item.label }} · {{ item.pdf_count || item.volumes.length }} 册 / {{ item.chapter_count || 0 }} 项{{ item.review_required_volume_count ? ' · 含待复核' : '' }}</option></select></label>
              <label><span>当前教材章节</span><select v-model="form.classProgress"><optgroup v-for="group in chapterGroups" :key="group.id" :label="group.label"><option v-for="item in group.options" :key="item.id" :value="item.id">{{ item.number ? `${item.number} ` : '' }}{{ item.title }}</option></optgroup></select></label>
            </div>

            <div class="evidence-box"><ShieldCheck :size="19" /><div><strong>{{ editionEvidenceLabel(form.planningSubject, form.curriculumVersion) }}</strong><p v-if="selectedChapter?.evidence">当前证据：{{ selectedChapter.evidence.source_pdf.split('/').slice(-1)[0] }} · 第 {{ selectedChapter.evidence.pdf_page }} 页 · {{ extractionLabel(selectedChapter.evidence.extraction_method) }}</p><small>教材版本须按学校用书版权页确认，系统不会根据省份臆测版本。</small></div></div>
          </section>

          <section class="planner-card">
            <div class="section-heading"><div><span>02</span><div><h2>填写目标与学情</h2><p>真实自评会帮助 Agent 做出更稳健的起始计划。</p></div></div><Target :size="23" /></div>
            <div class="score-panel"><label><span>当前成绩</span><div><input v-model.number="form.currentScore" type="number" min="0" :max="scoreMax" /><small>/ {{ scoreMax }}</small></div></label><ChevronRight :size="23" /><label><span>目标成绩</span><div class="target-score"><input v-model.number="form.targetScore" type="number" min="0" :max="scoreMax" /><small>/ {{ scoreMax }}</small></div></label><label><span>目标日期</span><input v-model="form.deadline" type="date" /></label></div>
            <div class="range-grid">
              <label><span><b>章节基础掌握度</b><strong>{{ form.foundationMastery }}%</strong></span><input v-model.number="form.foundationMastery" type="range" min="10" max="95" /><small><i>需要系统复习</i><i>掌握扎实</i></small></label>
              <label><span><b>综合应用独立完成度</b><strong>{{ form.applicationMastery }}%</strong></span><input v-model.number="form.applicationMastery" type="range" min="10" max="95" /><small><i>常需提示</i><i>可以独立完成</i></small></label>
            </div>
          </section>

          <section class="planner-card">
            <div class="section-heading"><div><span>03</span><div><h2>设置可持续时间</h2><p>系统会保留机动缓冲，不会把每一分钟排满。</p></div></div><Clock3 :size="23" /></div>
            <div class="time-layout"><label class="weekly-range"><span><b>每周可用学习时间</b><strong>{{ minutesLabel(form.weeklyMinutes) }}</strong></span><input v-model.number="form.weeklyMinutes" type="range" min="210" max="1050" step="35" /><small>建议实际排期约 {{ minutesLabel(Math.round(form.weeklyMinutes * 0.82)) }}</small></label><div class="form-grid two compact"><label><span>工作日每天</span><select v-model.number="form.weekdayMinutes"><option :value="45">45 分钟</option><option :value="70">70 分钟</option><option :value="90">90 分钟</option></select></label><label><span>周末每天</span><select v-model.number="form.weekendMinutes"><option :value="90">90 分钟</option><option :value="140">140 分钟</option><option :value="180">180 分钟</option></select></label></div></div>
            <div v-if="error" class="message error"><CircleAlert :size="17" />{{ error }}</div>
            <div class="planner-actions"><div><CheckCircle2 :size="20" /><span><strong>资料已准备</strong><small>{{ province.name }} · {{ planningSubjectLabel }} {{ form.currentScore }} → {{ form.targetScore }} 分</small></span></div><button class="primary-button" :disabled="loading || !selectionValid" @click="generatePlan"><LoaderCircle v-if="loading" class="spin" :size="19" /><Sparkles v-else :size="19" />{{ loading ? 'Agent 正在规划' : '生成个性化学习计划' }}</button></div>
          </section>
        </template>

        <template v-else-if="activeView === 'tutor'">
          <HomeworkTutorWorkspace
            :profile="profile"
            :plan-tasks="plan?.tasks || []"
            :initial-subject="form.planningSubject"
          />
        </template>

        <template v-else-if="activeView === 'plan' && plan">
          <section v-if="response?._meta?.mode === 'demo'" class="demo-banner"><CircleAlert :size="17" /><span><strong>在线演示模式</strong> 当前展示完整交互与示例计划；服务器本地页面会调用真实 Agent。</span></section>
          <section class="plan-hero"><div><span class="eyebrow light"><CheckCircle2 :size="15" /> {{ confirmed ? '计划执行中' : plan.validation?.valid ? '规划已完成' : '规划需要调整' }}</span><h1>{{ confirmed ? '你的学习路径已经启动' : plan.validation?.valid ? '第一阶段计划已经准备好' : '计划暂未达到发布条件' }}</h1><p>{{ plan.stages[0]?.objective }}</p><div><button v-if="!confirmed" class="white-button" :disabled="confirming || !plan.validation?.valid" @click="confirmPlan"><LoaderCircle v-if="confirming" class="spin" :size="18" /><Check v-else :size="18" />{{ confirming ? '正在确认' : '确认并开始计划' }}</button><button class="white-button" @click="activeView = 'tutor'"><MessageCircleQuestion :size="17" />进入作业辅导</button><button class="ghost-button" @click="activeView = 'workspace'"><RefreshCw :size="17" />调整资料</button></div></div><div class="score-circle"><small>当前 → 目标</small><strong>{{ form.currentScore }} <i>→</i> {{ form.targetScore }}</strong><span>{{ planningSubjectLabel }} · {{ scoreMax }} 分制</span></div></section>
          <section v-if="!plan.validation?.valid" class="validation-alert"><CircleAlert :size="19" /><div><strong>以下约束尚未通过，计划不会被错误发布</strong><p>{{ planValidationIssues.map((item) => validationLabels[item] || item).join('、') }}</p></div><button @click="activeView = 'workspace'">返回调整</button></section>
          <div class="plan-metrics"><article><CalendarDays :size="20" /><span><small>计划周期</small><strong>{{ formatDate(plan.plan_start) }}—{{ formatDate(plan.plan_end) }}</strong></span></article><article><Clock3 :size="20" /><span><small>本周排期</small><strong>{{ minutesLabel(plan.scheduled_minutes) }}</strong></span></article><article><ShieldCheck :size="20" /><span><small>机动缓冲</small><strong>{{ minutesLabel(plan.buffer_minutes) }}</strong></span></article><article><CheckCircle2 :size="20" /><span><small>约束校验</small><strong>{{ plan.validation?.valid ? '全部通过' : '需要检查' }}</strong></span></article></div>
          <div v-if="error" class="message error"><CircleAlert :size="17" />{{ error }}</div>
          <div class="plan-grid"><section class="task-list card"><div class="card-heading"><div><small>THIS WEEK</small><h2>本周学习安排</h2></div><span>{{ plan.tasks.length }} 项任务</span></div><article v-for="(task, index) in plan.tasks" :key="task.task_id" class="task-row"><span class="task-index">{{ index + 1 }}</span><div><div><b>{{ taskNames[task.task_type] || task.task_type }}</b><small><Clock3 :size="13" />{{ task.planned_duration_minutes }} 分钟</small></div><h3>{{ task.rationale.split('：')[0] }}</h3><p>{{ task.rationale.split('：').slice(1).join('：') }}</p><span class="relevance"><i :style="{ width: `${task.exam_relevance * 100}%` }" /></span></div></article></section><aside class="insight-stack"><section class="card insight-card"><BrainCircuit :size="24" /><h3>Agent 规划思路</h3><p>{{ plan.explanations?.strategy }}</p><div><span>基础修复</span><ChevronRight :size="14" /><span>专项训练</span><ChevronRight :size="14" /><span>综合迁移</span></div></section><section class="card gap-card"><Target :size="23" /><h3>优先补齐</h3><p v-for="(gap, index) in knowledge?.priority_gaps || []" :key="gap"><span>{{ index + 1 }}</span>{{ gap }}</p></section></aside></div>
        </template>

        <template v-else-if="activeView === 'knowledge' && plan">
          <section class="subpage-hero"><div><span class="eyebrow"><BrainCircuit :size="15" /> 动态知识画像</span><h1>看见掌握度背后的学习证据</h1><p>画像只基于已经提供的证据，不会把缺失数据推断成事实。</p></div><div class="confidence-card"><small>当前置信度</small><strong>{{ confidence }}%</strong><span>练习后持续更新</span></div></section>
          <div class="knowledge-grid"><article v-for="item in knowledge?.knowledge_states || []" :key="item.knowledge_id" class="card"><div><strong>{{ item.knowledge_id }}</strong><b>{{ Math.round(item.mastery_probability * 100) }}%</b></div><span class="mastery"><i :style="{ width: `${item.mastery_probability * 100}%` }" /></span><p><span>阶段：{{ item.mastery_level === 'developing' ? '发展中' : '起步' }}</span><span>遗忘风险 {{ Math.round(item.forgetting_risk * 100) }}%</span></p></article></div>
          <section class="evidence-explain card"><ShieldCheck :size="25" /><div><h3>证据边界说明</h3><p>当前画像综合目标输入和自评证据。接入真实练习后，系统会根据答题质量、用时、提示依赖和重复证据调整掌握度。</p></div></section>
        </template>

        <template v-else-if="activeView === 'feedback' && plan">
          <div class="feedback-grid"><section class="feedback-story"><span class="eyebrow light"><TrendingUp :size="15" /> 闭环反馈</span><h1>一次练习，也能让计划更懂你。</h1><p>记录真实结果。普通错误只更新画像并检查规则，不会因为一次波动重建整周计划。</p><div><RefreshCw :size="25" /><span><strong>最小必要调整</strong><small>只有持续低完成率、关键掌握度变化或时间容量明显变化时才触发重规划。</small></span></div></section><form class="feedback-card card" @submit.prevent="submitFeedback"><div class="card-heading"><div><small>PRACTICE EVENT</small><h2>记录本次练习</h2></div><Send :size="22" /></div><label><span>对应计划任务</span><select v-model="feedbackTaskId"><option v-for="task in plan.tasks" :key="task.task_id" :value="task.task_id">{{ task.rationale.split('：')[0] }}</option></select></label><fieldset><legend>完成结果</legend><button type="button" :class="{ active: feedbackCorrect }" @click="feedbackCorrect = true"><CheckCircle2 :size="19" />独立完成</button><button type="button" :class="{ active: !feedbackCorrect }" @click="feedbackCorrect = false"><CircleAlert :size="19" />仍有困难</button></fieldset><label class="feedback-range"><span><b>实际用时</b><strong>{{ feedbackMinutes }} 分钟</strong></span><input v-model.number="feedbackMinutes" type="range" min="10" max="120" step="5" /></label><div v-if="error" class="message error"><CircleAlert :size="17" />{{ error }}</div><div v-if="feedbackResult" class="message success"><CheckCircle2 :size="17" />{{ feedbackResult }}</div><button class="primary-button full" :disabled="feedbackLoading" type="submit"><LoaderCircle v-if="feedbackLoading" class="spin" :size="18" /><Send v-else :size="18" />{{ feedbackLoading ? '正在提交' : '提交给规划 Agent' }}</button></form></div>
        </template>
      </div>
    </main>

    <Transition name="toast"><div v-if="toast" class="toast"><CheckCircle2 :size="18" />{{ toast }}</div></Transition>
  </div>
</template>
