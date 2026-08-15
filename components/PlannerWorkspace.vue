<script setup lang="ts">
import {
  Bell,
  BookOpenCheck,
  BrainCircuit,
  CalendarDays,
  Check,
  CheckCircle2,
  ChevronRight,
  CircleAlert,
  ClipboardCheck,
  Clock3,
  Code2,
  Database,
  LayoutDashboard,
  Languages,
  LoaderCircle,
  LogOut,
  Menu,
  MessageCircleQuestion,
  PanelLeftClose,
  PanelLeftOpen,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Target,
  UserRound,
  X,
} from "@lucide/vue";
import { computed, onMounted, reactive, ref, watch } from "vue";

import HomeworkTutorWorkspace from "@/components/HomeworkTutorWorkspace.vue";
import AgentCollaborationWorkspace from "@/components/AgentCollaborationWorkspace.vue";
import EnglishLearningWorkspace from "@/components/EnglishLearningV2Workspace.vue";
import LearningDiagnosisWorkspace from "@/components/LearningDiagnosisWorkspace.vue";
import PaginationControls from "@/components/PaginationControls.vue";
import CareerEducationV1Workspace from "@/components/CareerEducationV1Workspace.vue";
import StudentClassroomWorkspace from "@/components/StudentClassroomWorkspace.vue";
import WenluBrandMark from "@/components/WenluBrandMark.vue";
import {
  callAgent,
  fetchLatestPlan,
  fetchPlannerHealth,
  resolveDiagnosticAssetHtml,
  startPlannerDiagnostic,
  submitPlannerDiagnostic,
} from "@/lib/agent-client";
import {
  ALL_CHAPTERS_ID,
  defaultSubjects,
  defaultProgressId,
  editionEvidenceLabel,
  getProvinceRoute,
  isSubjectSelectionValid,
  knowledgeIdLabel,
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
  DiagnosticAnswer,
  DiagnosticResult,
  DiagnosticSession,
  HomeworkHealth,
  PlannerFormData,
  PlannerSubjectPlan,
  StudentLoginProfile,
  SubjectKey,
} from "@/lib/types";
import type { CareerMode } from "@/lib/career-education-v1-client";
import {
  aiTaskNotificationsFor,
  dismissAiTaskNotification,
  pendingAiTasksFor,
  setActiveAiContext,
  type AiTaskNotification,
} from "@/lib/ai-runtime";

type View =
  | "workspace"
  | "collaboration"
  | "tutor"
  | "english"
  | "programming"
  | "diagnosis"
  | "records"
  | "classroom"
  | "plan"
  | "plan-insights";

type EnglishModule =
  "reading" | "vocabulary" | "grammar" | "speaking" | "writing" | "records";

const requestedViewParam = new URLSearchParams(window.location.search).get(
  "view",
);
const requestedView: View | null =
  requestedViewParam &&
  [
    "workspace",
    "collaboration",
    "tutor",
    "english",
    "programming",
    "diagnosis",
    "records",
    "classroom",
    "plan",
    "plan-insights",
  ].includes(requestedViewParam)
    ? (requestedViewParam as View)
    : null;
const requestedEnglishModuleParam = new URLSearchParams(
  window.location.search,
).get("module");
const requestedEnglishModule: EnglishModule =
  requestedEnglishModuleParam &&
  [
    "reading",
    "vocabulary",
    "grammar",
    "speaking",
    "writing",
    "records",
  ].includes(requestedEnglishModuleParam)
    ? (requestedEnglishModuleParam as EnglishModule)
    : "reading";
const requestedCareerModeParam = new URLSearchParams(window.location.search)
  .get("mode")
  ?.toUpperCase();
const requestedCareerMode: CareerMode =
  requestedCareerModeParam === "PROJECT" ||
  requestedCareerModeParam === "CODING" ||
  requestedCareerModeParam === "GAOKAO"
    ? requestedCareerModeParam
    : "CAREER";

const props = defineProps<{ profile: StudentLoginProfile }>();
const emit = defineEmits<{ logout: [] }>();

const initialSubject: SubjectKey = "mathematics";
const initialEdition = subjectEditions(initialSubject)[0]?.id || "";
const initialProgress = defaultProgressId(initialSubject, initialEdition);
const initialProvince = getProvinceRoute(props.profile.provinceCode);

const form = reactive<PlannerFormData>({
  studentId: props.profile.studentId,
  grade: props.profile.grade,
  schoolTerm: `${props.profile.grade}_term_1`,
  provinceCode: props.profile.provinceCode,
  targetExamYear: props.profile.targetExamYear,
  selectedSubjects: defaultSubjects(initialProvince),
  subjectPlans: [
    {
      subject: initialSubject,
      curriculumVersion: initialEdition,
      classProgress: [initialProgress],
      currentScore: 92,
      targetScore: 120,
      deadline: `${props.profile.targetExamYear}-05-20`,
      priority: 1,
    },
  ],
  weeklyMinutes: 630,
  weekdayMinutes: 70,
  weekendMinutes: 140,
});

const activeView = ref<View>(requestedView || "collaboration");
const careerMode = ref<CareerMode>(requestedCareerMode);
const englishModule = ref<EnglishModule>(requestedEnglishModule);
const planningExpanded = ref(
  ["collaboration", "workspace", "plan", "plan-insights"].includes(
    activeView.value,
  ),
);
const englishExpanded = ref(activeView.value === "english");
const careerExpanded = ref(activeView.value === "programming");
const assignedAssignmentId = ref("");
const sidebarOpen = ref(false);
const sidebarCollapsed = ref(
  window.localStorage.getItem("ai_education_sidebar_collapsed") === "true",
);
const loading = ref(false);
const confirming = ref(false);
const confirmed = ref(false);
const error = ref("");
const toast = ref("");
const aiResultNotifications = aiTaskNotificationsFor(props.profile.studentId);
const pendingAiTasks = pendingAiTasksFor(props.profile.studentId);
const pendingAiStatus = computed(() => {
  const tasks = pendingAiTasks.value;
  if (tasks.length === 1) {
    return tasks[0].pendingMessage || "问鹿AI 正在后台思考";
  }
  const generatingCount = tasks.filter((task) =>
    task.channel.endsWith("-generation"),
  ).length;
  if (generatingCount === tasks.length) {
    return `${generatingCount} 个 AI 正在出题`;
  }
  if (generatingCount) {
    return `${generatingCount} 个 AI 正在出题，${tasks.length - generatingCount} 个 AI 正在思考`;
  }
  return `${tasks.length} 个 AI 正在后台思考`;
});
const response = ref<AgentEnvelope | null>(null);
const plannerHealth = ref<HomeworkHealth | null>(null);
type SubjectDiagnosticState = {
  session: DiagnosticSession | null;
  result: DiagnosticResult | null;
  answers: DiagnosticAnswer[];
  index: number;
  selection: number | null;
  confidence: number;
  startedAt: number;
  loading: boolean;
  submitting: boolean;
};
const activePlanningSubject = ref<SubjectKey>(initialSubject);
const activeDiagnosticSubject = ref<SubjectKey>(initialSubject);
const diagnosticStates = reactive<Partial<Record<SubjectKey, SubjectDiagnosticState>>>({});

function createDiagnosticState(): SubjectDiagnosticState {
  return {
    session: null,
    result: null,
    answers: [],
    index: 0,
    selection: null,
    confidence: 0.7,
    startedAt: Date.now(),
    loading: false,
    submitting: false,
  };
}

function diagnosticState(subject: SubjectKey): SubjectDiagnosticState {
  if (!diagnosticStates[subject]) {
    diagnosticStates[subject] = createDiagnosticState();
  }
  return diagnosticStates[subject]!;
}

diagnosticState(initialSubject);
const currentDiagnosticState = computed(() =>
  diagnosticState(activeDiagnosticSubject.value),
);
const diagnosticSession = computed({
  get: () => currentDiagnosticState.value.session,
  set: (value: DiagnosticSession | null) => {
    currentDiagnosticState.value.session = value;
  },
});
const diagnosticResult = computed({
  get: () => currentDiagnosticState.value.result,
  set: (value: DiagnosticResult | null) => {
    currentDiagnosticState.value.result = value;
  },
});
const diagnosticAnswers = computed({
  get: () => currentDiagnosticState.value.answers,
  set: (value: DiagnosticAnswer[]) => {
    currentDiagnosticState.value.answers = value;
  },
});
const diagnosticIndex = computed({
  get: () => currentDiagnosticState.value.index,
  set: (value: number) => {
    currentDiagnosticState.value.index = value;
  },
});
const diagnosticSelection = computed({
  get: () => currentDiagnosticState.value.selection,
  set: (value: number | null) => {
    currentDiagnosticState.value.selection = value;
  },
});
const diagnosticConfidence = computed({
  get: () => currentDiagnosticState.value.confidence,
  set: (value: number) => {
    currentDiagnosticState.value.confidence = value;
  },
});
const diagnosticStartedAt = computed({
  get: () => currentDiagnosticState.value.startedAt,
  set: (value: number) => {
    currentDiagnosticState.value.startedAt = value;
  },
});
const diagnosticLoading = computed({
  get: () => currentDiagnosticState.value.loading,
  set: (value: boolean) => {
    currentDiagnosticState.value.loading = value;
  },
});
const diagnosticSubmitting = computed({
  get: () => currentDiagnosticState.value.submitting,
  set: (value: boolean) => {
    currentDiagnosticState.value.submitting = value;
  },
});
const diagnosticConfidenceOptions = [
  { label: "非常确定", value: 0.95, tone: "very-sure" },
  { label: "比较确定", value: 0.75, tone: "sure" },
  { label: "不太确定", value: 0.5, tone: "less-sure" },
  { label: "不确定", value: 0.25, tone: "unsure" },
];
const plannerStep = ref(1);
const planTaskPage = ref(1);
const planSubjectFilter = ref<SubjectKey | "all">("all");
const insightPage = ref(1);
const DISPLAY_PAGE_SIZE = 6;
const MAX_CHAPTER_SELECTION = 5;
const plannerSteps = [
  { id: 1, label: "基本信息", note: "地区与选科" },
  { id: 2, label: "确定范围", note: "科目与章节" },
  { id: 3, label: "学习目标", note: "成绩与日期" },
  { id: 4, label: "快速诊断", note: "逐科客观测评" },
  { id: 5, label: "学习时间", note: "生成正式计划" },
];

watch(
  [activeView, englishModule, careerMode],
  ([view, module, mode]) => {
    const taskView = ["collaboration", "tutor", "english", "programming"].includes(view)
      ? (view as "collaboration" | "tutor" | "english" | "programming")
      : "workspace";
    setActiveAiContext(props.profile.studentId, {
      view: taskView,
      module: taskView === "english" ? module : undefined,
      mode: taskView === "programming" ? mode : undefined,
    });
  },
  { immediate: true },
);

const province = computed(() => getProvinceRoute(form.provinceCode));
const selectableSubjects = computed(() => provinceSubjectKeys(province.value));
const planningSubjects = computed(() =>
  planningSubjectKeys(form.selectedSubjects),
);
const activeSubjectPlan = computed(() =>
  form.subjectPlans.find(
    (item) => item.subject === activePlanningSubject.value,
  ) || form.subjectPlans[0],
);
const activeDiagnosticPlan = computed(() =>
  form.subjectPlans.find(
    (item) => item.subject === activeDiagnosticSubject.value,
  ) || form.subjectPlans[0],
);
const editions = computed(() =>
  subjectEditions(activeSubjectPlan.value.subject),
);
const chapterGroups = computed(() =>
  progressGroups(
    activeSubjectPlan.value.subject,
    activeSubjectPlan.value.curriculumVersion,
  ),
);
const planningSubjectLabel = computed(
  () => subjectLabels[activeSubjectPlan.value.subject],
);
const selectionValid = computed(() =>
  isSubjectSelectionValid(province.value, form.selectedSubjects),
);
const selectableChapterGroups = computed(() =>
  chapterGroups.value
    .map((group) => ({
      ...group,
      options: group.options.filter((item) => item.id !== ALL_CHAPTERS_ID),
    }))
    .filter((group) => group.options.length),
);
const chapterOptionsById = computed(
  () =>
    new Map(
      selectableChapterGroups.value.flatMap((group) =>
        group.options.map((item) => [
          item.id,
          { ...item, groupLabel: group.label },
        ]),
      ),
    ),
);
const selectedChapters = computed(() =>
  activeSubjectPlan.value.classProgress.flatMap((id) => {
    const item = chapterOptionsById.value.get(id);
    return item ? [item] : [];
  }),
);
const allSubjectScopesValid = computed(() =>
  form.subjectPlans.every((item) => {
    const allowed = new Set(
      progressGroups(item.subject, item.curriculumVersion)
        .flatMap((group) => group.options)
        .map((option) => option.id),
    );
    return (
      item.classProgress.length >= 1 &&
      item.classProgress.length <= MAX_CHAPTER_SELECTION &&
      item.classProgress.every((chapterId) => allowed.has(chapterId))
    );
  }),
);
const allSubjectGoalsValid = computed(() =>
  form.subjectPlans.every(
    (item) =>
      item.currentScore >= 0 &&
      item.targetScore > item.currentScore &&
      item.targetScore <= subjectScoreMax(item.subject) &&
      Boolean(item.deadline),
  ),
);
const completedDiagnosticCount = computed(() =>
  form.subjectPlans.filter((item) => diagnosticStates[item.subject]?.result)
    .length,
);
const allDiagnosticsComplete = computed(
  () =>
    form.subjectPlans.length > 0 &&
    completedDiagnosticCount.value === form.subjectPlans.length,
);
const plan = computed(() => response.value?.result?.plan);
const knowledge = computed(() => response.value?.result?.knowledge_profile);
const planSubjectOptions = computed(() => {
  const goalSubjects = plan.value?.subject_goals?.map((item) => item.subject) || [];
  const subjects = goalSubjects.length
    ? goalSubjects
    : plan.value?.tasks.map((item) => item.subject as SubjectKey) || [];
  return Array.from(new Set(subjects));
});
const filteredPlanTasks = computed(() =>
  (plan.value?.tasks || []).filter(
    (item) =>
      planSubjectFilter.value === "all" ||
      item.subject === planSubjectFilter.value,
  ),
);
const pagedPlanTasks = computed(() => {
  const start = (planTaskPage.value - 1) * DISPLAY_PAGE_SIZE;
  return filteredPlanTasks.value.slice(start, start + DISPLAY_PAGE_SIZE);
});
const planningInsightMain = computed(() => {
  const explanations = plan.value?.explanations;
  const strategyItems = splitPlanningInsights(explanations?.strategy || "");
  if (strategyItems.length) return strategyItems[0];
  return (
    splitPlanningInsights(explanations?.student || "")[0] ||
    "围绕当前目标和学习证据安排本阶段任务，并根据执行结果动态调整。"
  );
});
const planningInsightItems = computed(() => {
  const source = [
    plan.value?.explanations?.strategy || "",
    plan.value?.explanations?.student || "",
  ].join("\n");
  const seen = new Set<string>();
  return splitPlanningInsights(source)
    .filter((item) => item !== planningInsightMain.value)
    .filter(
      (item) => item.length > 1 && !seen.has(item) && Boolean(seen.add(item)),
    );
});
const pagedPlanningInsights = computed(() => {
  const start = (insightPage.value - 1) * DISPLAY_PAGE_SIZE;
  return planningInsightItems.value.slice(start, start + DISPLAY_PAGE_SIZE);
});
const planValidationIssues = computed(
  () => plan.value?.validation?.errors || [],
);
const planProvisional = computed(() => plan.value?.status === "provisional");
const currentDiagnosticQuestion = computed(
  () => diagnosticSession.value?.questions[diagnosticIndex.value],
);
const diagnosticPercent = computed(() =>
  diagnosticResult.value
    ? 100
    : Math.round((diagnosticAnswers.value.length / 10) * 100),
);

function subjectScopeSignatures() {
  return Object.fromEntries(
    form.subjectPlans.map((item) => [
      item.subject,
      `${item.curriculumVersion}:${item.classProgress.join("|")}`,
    ]),
  ) as Partial<Record<SubjectKey, string>>;
}

let previousSubjectScopes = subjectScopeSignatures();
watch(subjectScopeSignatures, (current) => {
  for (const item of form.subjectPlans) {
    if (
      previousSubjectScopes[item.subject] &&
      previousSubjectScopes[item.subject] !== current[item.subject]
    ) {
      diagnosticStates[item.subject] = createDiagnosticState();
    }
  }
  previousSubjectScopes = current;
});

onMounted(async () => {
  const [healthResult, planResult] = await Promise.allSettled([
    fetchPlannerHealth(),
    fetchLatestPlan(form.studentId),
  ]);
  plannerHealth.value =
    healthResult.status === "fulfilled" ? healthResult.value : null;
  if (planResult.status === "fulfilled" && planResult.value?.result?.plan) {
    restorePlanningContext(planResult.value);
    response.value = planResult.value;
    confirmed.value = ["active", "paused"].includes(
      planResult.value.result.plan.status,
    );
    activeView.value = requestedView || "collaboration";
    showToast("已自动恢复最近一次学习规划");
  } else if (planResult.status === "rejected") {
    showToast(
      planResult.reason instanceof Error
        ? planResult.reason.message
        : "最近规划读取失败",
    );
  }
});

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
  all_goal_subjects_scheduled: "全部规划科目均已排期",
  subject_core_tasks_included: "每科复习、限时训练与阶段测评",
  subject_selection_legal: "地区选科规则",
};

const navItems: Array<{
  id: View;
  label: string;
  icon: typeof LayoutDashboard;
}> = [
  { id: "collaboration", label: "智能规划", icon: Sparkles },
  { id: "workspace", label: "计划设置", icon: LayoutDashboard },
  { id: "tutor", label: "作业辅导", icon: MessageCircleQuestion },
  { id: "english", label: "外语学习", icon: Languages },
  { id: "programming", label: "岗位技能", icon: Code2 },
  { id: "diagnosis", label: "学情诊断", icon: ClipboardCheck },
  { id: "records", label: "导入学习记录", icon: Database },
  { id: "classroom", label: "班级与通知", icon: Bell },
  { id: "plan", label: "我的计划", icon: CalendarDays },
  { id: "plan-insights", label: "规划依据", icon: BrainCircuit },
];

const standaloneBeforeCareer = navItems.filter((item) => item.id === "tutor");
const standaloneAfterCareer = navItems.filter((item) =>
  ["diagnosis", "records", "classroom"].includes(item.id),
);
const planningNavItems = navItems.filter((item) =>
  ["collaboration", "workspace", "plan", "plan-insights"].includes(item.id),
);
const englishNavItems: Array<{ id: EnglishModule; label: string }> = [
  { id: "reading", label: "阅读训练" },
  { id: "vocabulary", label: "词汇训练" },
  { id: "grammar", label: "语法训练" },
  { id: "speaking", label: "口语学习" },
  { id: "writing", label: "写作训练" },
  { id: "records", label: "学习档案" },
];
const careerNavItems: Array<{ id: CareerMode; label: string }> = [
  { id: "CAREER", label: "岗位技能" },
  { id: "PROJECT", label: "项目实训" },
  { id: "CODING", label: "代码练习" },
  { id: "GAOKAO", label: "程序编程" },
];
const activePageTitle = computed(() => {
  if (activeView.value === "programming")
    return careerNavItems.find((item) => item.id === careerMode.value)?.label;
  if (activeView.value === "english")
    return englishNavItems.find((item) => item.id === englishModule.value)
      ?.label;
  return navItems.find((item) => item.id === activeView.value)?.label;
});

const taskNames: Record<string, string> = {
  concept_learning: "概念学习",
  foundation_practice: "基础巩固",
  variant_practice: "变式训练",
  concept_repair: "概念修复",
  targeted_practice: "专项训练",
  spaced_review: "间隔复习",
  timed_training: "限时训练",
  stage_assessment: "阶段测评",
};

const taskDescriptions: Record<string, string> = {
  concept_learning: "先理解核心概念、条件与基本表示，再进入例题练习。",
  foundation_practice:
    "通过基础题巩固定义、公式和基本方法，补齐当前掌握薄弱点。",
  variant_practice: "围绕同一知识点改变条件或问法，训练方法迁移。",
  spaced_review: "按遗忘风险回顾关键知识，检查能否脱离提示独立完成。",
  timed_training: "在限定时间内完成小组训练，建立时间分配和解题稳定性证据。",
  stage_assessment:
    "完成本阶段小型测评，用独立证据检验学习效果并决定后续安排。",
};

const technicalTermLabels: Record<string, string> = {
  agent: "智能规划助手",
  llm: "大语言模型",
  "cp-sat": "约束规划算法",
  foundation: "基础掌握",
  application: "综合应用",
  mathematics: "数学",
  math: "数学",
  function: "函数",
  derivative: "导数",
  sequence: "数列",
  analytic: "解析",
  geometry: "几何",
  probability: "概率",
  mechanics: "力学",
  electric: "电学",
  concept: "概念",
  learning: "学习",
  practice: "练习",
  review: "复习",
  training: "训练",
  assessment: "测评",
};

function readableTechnicalToken(token: string): string {
  const catalogLabel = knowledgeIdLabel(token);
  if (
    catalogLabel !== token &&
    !/[A-Z]{2,}(?:-[A-Z0-9]+)+/.test(catalogLabel)
  ) {
    return catalogLabel;
  }
  const dimensionMatch = token.match(/^(.*)_(foundation|application)$/i);
  const base = dimensionMatch?.[1] || token;
  const dimension = dimensionMatch
    ? technicalTermLabels[dimensionMatch[2].toLowerCase()]
    : "";
  const translated = base
    .split(/[_-]+/)
    .map((part) => technicalTermLabels[part.toLowerCase()] || "")
    .filter(Boolean);
  if (translated.length)
    return [...new Set(translated), dimension].filter(Boolean).join(" · ");
  return dimension || "相关学习内容";
}

function localizePlanningText(value: string): string {
  return value
    .replace(/\\r\\n|\\n|\\r/g, "\n")
    .replace(/\r\n?/g, "\n")
    .replace(/^[ \t]*(?:[-*•]|\d+[.)、])[ \t]*/gm, "")
    .replace(
      /\b(?:TB-[A-Z0-9-]+|[A-Z]{2,8}(?:-[A-Z0-9]+)+)(?:_(?:foundation|application))?\b/g,
      readableTechnicalToken,
    )
    .replace(/\b[a-z]+(?:_[a-z0-9]+)+\b/gi, readableTechnicalToken)
    .replace(/\bCP-SAT\b/gi, technicalTermLabels["cp-sat"])
    .replace(/\bLLM\b/gi, technicalTermLabels.llm)
    .replace(/\bAgent\b/gi, technicalTermLabels.agent)
    .replace(/\bfoundation\b/gi, technicalTermLabels.foundation)
    .replace(/\bapplication\b/gi, technicalTermLabels.application);
}

function splitPlanningInsights(value: string): string[] {
  const normalized = localizePlanningText(value);
  return (normalized.match(/[^。！？；\n]+[。！？；]?/g) || [])
    .map((item) => item.trim().replace(/^(?:[-*•]|\d+[.)、])\s*/, ""))
    .filter((item) => item.length > 1);
}

function insightDetailLabel(value: string): string {
  if (/风险|调整|变化|未完成|连续|复核/.test(value)) return "风险与调整";
  if (/时间|分钟|小时|本周|排期|缓冲|节奏/.test(value)) return "时间与节奏";
  if (/任务|训练|复习|测评|练习|顺序/.test(value)) return "任务安排";
  if (/证据|诊断|掌握|依据|置信/.test(value)) return "学习依据";
  if (/目标|分数|截止|优先|补齐|重点/.test(value)) return "目标与重点";
  return "具体说明";
}

function taskTitle(task: {
  subject: string;
  task_type: string;
  knowledge_ids: string[];
}) {
  const knowledge = task.knowledge_ids[0]
    ? knowledgeIdLabel(task.knowledge_ids[0])
    : subjectLabels[task.subject as SubjectKey] || "相关学习内容";
  return `${knowledge} · ${taskNames[task.task_type] || "学习任务"}`;
}

function taskDescription(task: { task_type: string; rationale: string }) {
  return localizePlanningText(
    task.rationale ||
      taskDescriptions[task.task_type] ||
      "根据当前目标与学习证据安排。",
  );
}

function subjectDefaults(subject: SubjectKey): PlannerSubjectPlan {
  const version = subjectEditions(subject)[0]?.id || "";
  const progress = defaultProgressId(subject, version);
  const max = subjectScoreMax(subject);
  return {
    subject,
    curriculumVersion: version,
    classProgress: [progress],
    currentScore: max === 150 ? 92 : 62,
    targetScore: max === 150 ? 120 : 80,
    deadline: `${form.targetExamYear}-05-20`,
    priority: 2,
  };
}

function normalizedProgress(
  subject: SubjectKey,
  curriculumVersion: string,
  value: unknown,
): string[] {
  const restored = (
    Array.isArray(value) ? value : typeof value === "string" ? [value] : []
  )
    .filter(
      (item): item is string =>
        typeof item === "string" && item !== ALL_CHAPTERS_ID,
    )
    .slice(0, MAX_CHAPTER_SELECTION);
  const allowed = new Set(
    progressGroups(subject, curriculumVersion)
      .flatMap((group) => group.options)
      .map((item) => item.id),
  );
  const valid = restored.filter((item) => allowed.has(item));
  return valid.length
    ? valid
    : [defaultProgressId(subject, curriculumVersion)];
}

function restorePlanningContext(envelope: AgentEnvelope) {
  const restoredPlan = envelope.result?.plan;
  if (!restoredPlan) return;
  const academic = envelope.result?.student_profile;
  if (academic) {
    form.schoolTerm = academic.school_term;
    form.provinceCode = academic.province_code;
    form.targetExamYear = academic.target_exam_year;
    if (academic.selected_subjects?.length)
      form.selectedSubjects = academic.selected_subjects;
  }
  const restoredGoals = restoredPlan.subject_goals?.length
    ? restoredPlan.subject_goals
    : [
        {
          subject: (restoredPlan.generation_basis?.goal_subject ||
            restoredPlan.tasks[0]?.subject) as SubjectKey,
          current_value: Number(
            restoredPlan.generation_basis?.goal_current_value,
          ),
          target_value: Number(
            restoredPlan.generation_basis?.goal_target_value,
          ),
          deadline:
            restoredPlan.generation_basis?.goal_deadline ||
            restoredPlan.plan_end,
          priority: 1,
        },
      ];
  const restoredSubjectPlans = restoredGoals.flatMap((goal) => {
    if (!goal.subject || !(goal.subject in subjectLabels)) return [];
    const defaults = subjectDefaults(goal.subject);
    const curriculumVersion =
      goal.curriculum_version ||
      academic?.curriculum_versions?.[goal.subject] ||
      defaults.curriculumVersion;
    const sourceProgress =
      goal.class_progress?.length
        ? goal.class_progress
        : academic?.class_progress?.[goal.subject];
    const currentScore = Number(goal.current_value);
    const targetScore = Number(goal.target_value);
    return [
      {
        ...defaults,
        curriculumVersion,
        classProgress: normalizedProgress(
          goal.subject,
          curriculumVersion,
          sourceProgress,
        ),
        currentScore: Number.isFinite(currentScore)
          ? currentScore
          : defaults.currentScore,
        targetScore: Number.isFinite(targetScore)
          ? targetScore
          : defaults.targetScore,
        deadline: goal.deadline || defaults.deadline,
        priority: [1, 2, 3].includes(goal.priority)
          ? (goal.priority as 1 | 2 | 3)
          : defaults.priority,
      },
    ];
  });
  if (restoredSubjectPlans.length) {
    form.subjectPlans = restoredSubjectPlans.slice(0, 6);
    activePlanningSubject.value = form.subjectPlans[0].subject;
    activeDiagnosticSubject.value = form.subjectPlans[0].subject;
    for (const item of form.subjectPlans) diagnosticState(item.subject);
    previousSubjectScopes = subjectScopeSignatures();
  }
  form.weeklyMinutes = restoredPlan.weekly_capacity_minutes;
}

function keepAllowedPlanningSubjects() {
  const allowed = new Set(planningSubjectKeys(form.selectedSubjects));
  form.subjectPlans = form.subjectPlans.filter((item) => allowed.has(item.subject));
  if (!form.subjectPlans.length) form.subjectPlans = [subjectDefaults("mathematics")];
  if (!form.subjectPlans.some((item) => item.subject === activePlanningSubject.value)) {
    activePlanningSubject.value = form.subjectPlans[0].subject;
  }
  if (!form.subjectPlans.some((item) => item.subject === activeDiagnosticSubject.value)) {
    activeDiagnosticSubject.value = form.subjectPlans[0].subject;
  }
}

function changeProvince(event: Event) {
  const code = (event.target as HTMLSelectElement).value;
  const route = getProvinceRoute(code);
  form.provinceCode = code;
  form.selectedSubjects = defaultSubjects(route);
  keepAllowedPlanningSubjects();
}

function toggleSubject(key: SubjectKey) {
  form.selectedSubjects = selectProvinceSubject(
    province.value,
    form.selectedSubjects,
    key,
  );
  keepAllowedPlanningSubjects();
}

function selectOrAddPlanningSubject(subject: SubjectKey) {
  const existing = form.subjectPlans.findIndex((item) => item.subject === subject);
  if (existing >= 0) {
    activePlanningSubject.value = subject;
    activeDiagnosticSubject.value = subject;
    return;
  }
  if (form.subjectPlans.length >= 6) {
    showToast("一次最多规划 6 个科目");
    return;
  }
  form.subjectPlans.push(subjectDefaults(subject));
  diagnosticState(subject);
  activePlanningSubject.value = subject;
  activeDiagnosticSubject.value = subject;
}

function removePlanningSubject(subject: SubjectKey) {
  const existing = form.subjectPlans.findIndex((item) => item.subject === subject);
  if (existing < 0) return;
  if (form.subjectPlans.length === 1) {
    showToast("至少保留 1 个规划科目");
    return;
  }
  form.subjectPlans.splice(existing, 1);
  delete diagnosticStates[subject];
  keepAllowedPlanningSubjects();
  showToast(`${subjectLabels[subject]}已从本次规划中移除`);
}

function changeEdition(event: Event) {
  const version = (event.target as HTMLSelectElement).value;
  activeSubjectPlan.value.curriculumVersion = version;
  activeSubjectPlan.value.classProgress = [
    defaultProgressId(activeSubjectPlan.value.subject, version),
  ];
}

function toggleChapterScope(chapterId: string) {
  error.value = "";
  if (activeSubjectPlan.value.classProgress.includes(chapterId)) {
    activeSubjectPlan.value.classProgress = activeSubjectPlan.value.classProgress.filter(
      (item) => item !== chapterId,
    );
    return;
  }
  if (activeSubjectPlan.value.classProgress.length >= MAX_CHAPTER_SELECTION) {
    showToast("一次最多选择 5 个章节，请先取消一个已选章节");
    return;
  }
  activeSubjectPlan.value.classProgress = [
    ...activeSubjectPlan.value.classProgress,
    chapterId,
  ];
}

function navigate(view: View) {
  sidebarOpen.value = false;
  if (
    ![
      "workspace",
      "collaboration",
      "tutor",
      "english",
      "programming",
      "diagnosis",
      "records",
      "classroom",
    ].includes(view) &&
    !plan.value
  ) {
    showToast("请先生成第一份学习计划");
    activeView.value = "workspace";
    return;
  }
  activeView.value = view;
  const url = new URL(window.location.href);
  url.searchParams.set("view", view);
  if (view !== "programming") url.searchParams.delete("mode");
  if (view !== "english") url.searchParams.delete("module");
  window.history.replaceState({}, "", url);
}

function openPlanningCenter() {
  planningExpanded.value = !planningExpanded.value;
  if (planningExpanded.value && sidebarCollapsed.value)
    sidebarCollapsed.value = false;
}

function openEnglishCenter() {
  englishExpanded.value = !englishExpanded.value;
  if (englishExpanded.value && sidebarCollapsed.value)
    sidebarCollapsed.value = false;
}

function navigateEnglish(next: EnglishModule) {
  englishModule.value = next;
  englishExpanded.value = true;
  navigate("english");
  const url = new URL(window.location.href);
  url.searchParams.set("module", next);
  window.history.replaceState({}, "", url);
}

function dismissAiResult(id: string) {
  dismissAiTaskNotification(id);
}

function openAiResult(notification: AiTaskNotification) {
  dismissAiResult(notification.id);
  const destination = notification.destination;
  if (destination.view === "english" && destination.module) {
    navigateEnglish(destination.module);
    return;
  }
  if (destination.view === "programming" && destination.mode) {
    navigateCareer(destination.mode);
    return;
  }
  navigate(destination.view);
}

function openCareerCenter() {
  careerExpanded.value = !careerExpanded.value;
  if (careerExpanded.value && sidebarCollapsed.value)
    sidebarCollapsed.value = false;
}

function navigateCareer(next: CareerMode) {
  careerMode.value = next;
  careerExpanded.value = true;
  navigate("programming");
  const url = new URL(window.location.href);
  url.searchParams.set("mode", next.toLowerCase());
  window.history.replaceState({}, "", url);
}

function openAssignedDiagnosis(assignmentId: string) {
  assignedAssignmentId.value = assignmentId;
  activeView.value = "diagnosis";
}

function toggleSidebar() {
  sidebarCollapsed.value = !sidebarCollapsed.value;
  window.localStorage.setItem(
    "ai_education_sidebar_collapsed",
    String(sidebarCollapsed.value),
  );
}

function showToast(message: string) {
  toast.value = message;
  window.setTimeout(() => {
    toast.value = "";
  }, 3000);
}

function movePlannerStep(step: number) {
  if (step === 2 && !selectionValid.value) {
    error.value = "请先完成符合所在地区规则的高考选科组合";
    return;
  }
  if (step === 3 && !allSubjectScopesValid.value) {
    error.value = "请先完成合法选科，并为每个规划科目选择 1–5 个教材章节";
    return;
  }
  if (step === 4 && !allSubjectGoalsValid.value) {
    error.value = "请为每个规划科目填写合理的当前成绩、目标成绩和目标日期";
    return;
  }
  if (step === 5 && !allDiagnosticsComplete.value) {
    error.value = `请先完成全部科目诊断（${completedDiagnosticCount.value}/${form.subjectPlans.length}）`;
    return;
  }
  if (step === 4) {
    const firstPending = form.subjectPlans.find(
      (item) => !diagnosticStates[item.subject]?.result,
    );
    activeDiagnosticSubject.value =
      firstPending?.subject || form.subjectPlans[0].subject;
  }
  plannerStep.value = step;
  error.value = "";
  window.scrollTo({ top: 0, behavior: "smooth" });
}

async function startDiagnostic() {
  const subjectPlan = activeDiagnosticPlan.value;
  if (!subjectPlan || !selectionValid.value || !allSubjectScopesValid.value) {
    error.value = "请先确认科目、教材版本，并选择 1–5 个章节";
    return;
  }
  diagnosticLoading.value = true;
  error.value = "";
  try {
    diagnosticSession.value = await startPlannerDiagnostic(
      { ...form },
      { ...subjectPlan, classProgress: [...subjectPlan.classProgress] },
    );
    diagnosticResult.value = null;
    diagnosticAnswers.value = [];
    diagnosticIndex.value = 0;
    diagnosticSelection.value = null;
    diagnosticConfidence.value = 0.7;
    diagnosticStartedAt.value = Date.now();
    showToast(
      diagnosticSession.value.generation_mode === "llm"
        ? `已为${subjectLabels[subjectPlan.subject]}按 ${subjectPlan.classProgress.length} 个章节生成 10 道诊断题`
        : `问鹿AI暂时不可用，${subjectLabels[subjectPlan.subject]}已切换本地真题题库`,
    );
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "快速诊断生成失败";
  } finally {
    diagnosticLoading.value = false;
  }
}

function recordDiagnosticAnswer(): boolean {
  const question = currentDiagnosticQuestion.value;
  if (!question || diagnosticSelection.value === null) {
    error.value = "请先选择本题答案";
    return false;
  }
  diagnosticAnswers.value = [
    ...diagnosticAnswers.value.filter(
      (item) => item.question_id !== question.question_id,
    ),
    {
      question_id: question.question_id,
      selected_option: diagnosticSelection.value,
      response_time_seconds: Math.max(
        1,
        Math.round((Date.now() - diagnosticStartedAt.value) / 1000),
      ),
      confidence: diagnosticConfidence.value,
    },
  ];
  return true;
}

function selectDiagnosticOption(optionIndex: number) {
  diagnosticSelection.value = optionIndex;
  error.value = "";
}

async function selectDiagnosticConfidence(value: number) {
  if (diagnosticSelection.value === null) {
    error.value = "请先选择 A、B、C 或 D";
    return;
  }
  diagnosticConfidence.value = value;
  if (diagnosticIndex.value < 9) {
    nextDiagnosticQuestion();
  } else {
    await finishDiagnostic();
  }
}

function nextDiagnosticQuestion() {
  if (!recordDiagnosticAnswer()) return;
  diagnosticIndex.value += 1;
  diagnosticSelection.value = null;
  diagnosticConfidence.value = 0.7;
  diagnosticStartedAt.value = Date.now();
  error.value = "";
}

async function finishDiagnostic() {
  if (!diagnosticSession.value || !recordDiagnosticAnswer()) return;
  diagnosticSubmitting.value = true;
  error.value = "";
  try {
    diagnosticResult.value = await submitPlannerDiagnostic(
      form.studentId,
      diagnosticSession.value.diagnostic_id,
      diagnosticAnswers.value,
    );
    showToast(
      `${subjectLabels[activeDiagnosticSubject.value]}诊断完成（${completedDiagnosticCount.value}/${form.subjectPlans.length}）`,
    );
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "诊断提交失败";
  } finally {
    diagnosticSubmitting.value = false;
  }
}

async function generatePlan() {
  if (!allDiagnosticsComplete.value) {
    error.value = "请先完成所有规划科目的快速诊断，再生成正式计划";
    plannerStep.value = 4;
    return;
  }
  if (!selectionValid.value || !allSubjectScopesValid.value) {
    error.value = "请先完成合法选科，并为每科选择 1–5 个教材章节";
    return;
  }
  loading.value = true;
  error.value = "";
  try {
    const result = await callAgent({
      action: "initialize",
      form: { ...form },
      diagnosticEvidenceBySubject: Object.fromEntries(
        form.subjectPlans.map((item) => [
          item.subject,
          diagnosticStates[item.subject]?.result?.knowledge_evidence || [],
        ]),
      ),
    });
    if (!result.result?.plan) throw new Error("Agent 未返回可展示的学习计划");
    response.value = result;
    confirmed.value = result.result.plan.status === "active";
    planTaskPage.value = 1;
    planSubjectFilter.value = "all";
    insightPage.value = 1;
    activeView.value = "plan";
    showToast("个性化学习计划已生成");
  } catch (reason) {
    error.value =
      reason instanceof Error ? reason.message : "生成失败，请稍后重试";
  } finally {
    loading.value = false;
  }
}

async function confirmPlan() {
  if (!plan.value) return;
  if (planProvisional.value) {
    error.value = "当前为暂定计划，请先完成快速诊断再生成可确认计划";
    return;
  }
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

function formatDate(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat("zh-CN", {
        month: "short",
        day: "numeric",
      }).format(date);
}

function minutesLabel(value: number) {
  const hours = Math.floor(value / 60);
  const minutes = value % 60;
  return hours
    ? `${hours} 小时${minutes ? ` ${minutes} 分` : ""}`
    : `${minutes} 分钟`;
}
</script>

<template>
  <div
    class="app-shell student-theme"
    :class="{ 'sidebar-collapsed': sidebarCollapsed }"
  >
    <div v-if="sidebarOpen" class="sidebar-mask" @click="sidebarOpen = false" />
    <aside class="app-sidebar" :class="{ open: sidebarOpen }">
      <div class="workspace-brand">
        <WenluBrandMark class="workspace-brand-mark" :size="28" />
        <div><strong>问鹿</strong><small>AI多智能体学习中心</small></div>
        <button
          class="sidebar-collapse"
          :title="sidebarCollapsed ? '展开侧栏' : '收起侧栏'"
          @click="toggleSidebar"
        >
          <PanelLeftOpen v-if="sidebarCollapsed" :size="18" /><PanelLeftClose
            v-else
            :size="18"
          />
        </button>
        <button
          class="sidebar-close"
          aria-label="关闭菜单"
          @click="sidebarOpen = false"
        >
          <X :size="19" />
        </button>
      </div>

      <nav class="workspace-nav">
        <small>学习空间</small>
        <div class="nav-group">
          <button
            class="nav-group-toggle"
            :class="{
              active: ['workspace', 'plan', 'plan-insights'].includes(
                activeView,
              ),
            }"
            @click="openPlanningCenter"
          >
            <LayoutDashboard :size="19" />
            <span>规划中心</span>
            <ChevronRight :size="16" :class="{ expanded: planningExpanded }" />
          </button>
          <div v-if="planningExpanded" class="nav-children">
            <button
              v-for="item in planningNavItems"
              :key="item.id"
              class="nav-child"
              :class="{ active: activeView === item.id }"
              @click="navigate(item.id)"
            >
              <b class="nav-bullet" /><span>{{ item.label }}</span>
              <i v-if="['plan', 'plan-insights'].includes(item.id) && !plan" />
            </button>
          </div>
        </div>
        <button
          v-for="item in standaloneBeforeCareer"
          :key="item.id"
          :class="{ active: activeView === item.id }"
          @click="navigate(item.id)"
        >
          <component :is="item.icon" :size="19" />
          <span>{{ item.label }}</span>
        </button>
        <div class="nav-group">
          <button
            class="nav-group-toggle"
            :class="{ active: activeView === 'english' }"
            @click="openEnglishCenter"
          >
            <Languages :size="19" />
            <span>外语学习</span>
            <ChevronRight :size="16" :class="{ expanded: englishExpanded }" />
          </button>
          <div v-if="englishExpanded" class="nav-children">
            <button
              v-for="item in englishNavItems"
              :key="item.id"
              class="nav-child"
              :class="{
                active: activeView === 'english' && englishModule === item.id,
              }"
              @click="navigateEnglish(item.id)"
            >
              <b class="nav-bullet" /><span>{{ item.label }}</span>
            </button>
          </div>
        </div>
        <div class="nav-group">
          <button
            class="nav-group-toggle"
            :class="{ active: activeView === 'programming' }"
            @click="openCareerCenter"
          >
            <Code2 :size="19" />
            <span>职业教育</span>
            <ChevronRight :size="16" :class="{ expanded: careerExpanded }" />
          </button>
          <div v-if="careerExpanded" class="nav-children">
            <button
              v-for="item in careerNavItems"
              :key="item.id"
              class="nav-child"
              :class="{
                active: activeView === 'programming' && careerMode === item.id,
              }"
              @click="navigateCareer(item.id)"
            >
              <b class="nav-bullet" /><span>{{ item.label }}</span>
            </button>
          </div>
        </div>
        <button
          v-for="item in standaloneAfterCareer"
          :key="item.id"
          :class="{ active: activeView === item.id }"
          @click="navigate(item.id)"
        >
          <component :is="item.icon" :size="19" />
          <span>{{ item.label }}</span>
        </button>
      </nav>

      <div class="sidebar-profile">
        <span class="avatar">{{ profile.studentName.slice(0, 1) }}</span>
        <div>
          <strong>{{ profile.studentName }}</strong
          ><small>{{ profile.studentId }}</small>
        </div>
        <button title="退出登录" @click="emit('logout')">
          <LogOut :size="17" />
        </button>
      </div>
    </aside>

    <main class="app-main">
      <header class="topbar">
        <button
          class="mobile-menu"
          aria-label="打开菜单"
          @click="sidebarOpen = true"
        >
          <Menu :size="21" />
        </button>
        <button
          class="desktop-sidebar-toggle"
          :title="sidebarCollapsed ? '展开侧栏' : '收起侧栏'"
          @click="toggleSidebar"
        >
          <PanelLeftOpen v-if="sidebarCollapsed" :size="19" /><PanelLeftClose
            v-else
            :size="19"
          />
        </button>
        <div>
          <small>AI EDUCATION</small><strong>{{ activePageTitle }}</strong>
        </div>
        <span class="service-state"
          ><i />
          {{
            plannerHealth?.planner_generation_mode === "llm"
              ? "问鹿规划模型在线"
              : "问鹿规划模型未连接"
          }}</span
        >
      </header>

      <div class="page-content">
        <EnglishLearningWorkspace
          v-show="activeView === 'english'"
          :student-id="profile.studentId"
          :active-module="englishModule"
        />

        <template v-if="activeView === 'workspace'">
          <section class="welcome-hero student-module-hero">
            <div>
              <span class="eyebrow light"
                ><Sparkles :size="15" /> 学习规划 Agent</span
              >
              <h1>{{ profile.studentName }}，今天也向目标靠近一步。</h1>
              <p>
                确认教材进度、当前学情和可用时间，系统会生成一份有证据、能执行、可持续调整的学习路径。
              </p>
            </div>
            <div class="hero-database">
              <Database :size="24" /><span
                ><strong>329 册</strong><small>本地教材 PDF</small></span
              ><span><strong>1,336</strong><small>章节选项</small></span>
            </div>
          </section>

          <div class="overview-cards">
            <article>
              <span><UserRound :size="20" /></span>
              <div>
                <small>当前档案</small
                ><strong
                  >{{
                    profile.grade === "grade_10"
                      ? "高一"
                      : profile.grade === "grade_11"
                        ? "高二"
                        : "高三"
                  }}
                  · {{ province.name }}</strong
                >
              </div>
            </article>
            <article>
              <span><Target :size="20" /></span>
              <div>
                <small>目标年份</small
                ><strong>{{ form.targetExamYear }} 年高考</strong>
              </div>
            </article>
            <article>
              <span><Clock3 :size="20" /></span>
              <div>
                <small>每周可用</small
                ><strong>{{ minutesLabel(form.weeklyMinutes) }}</strong>
              </div>
            </article>
            <article>
              <span><ShieldCheck :size="20" /></span>
              <div><small>目录证据</small><strong>50 个教材版本</strong></div>
            </article>
          </div>

          <nav class="planner-stepper" aria-label="个性化规划步骤">
            <div
              v-for="item in plannerSteps"
              :key="item.id"
              :class="{
                active: plannerStep === item.id,
                done:
                  plannerStep > item.id ||
                  (item.id === 4 && allDiagnosticsComplete),
              }"
            >
              <span
                ><Check
                  v-if="
                    plannerStep > item.id ||
                    (item.id === 4 && allDiagnosticsComplete)
                  "
                  :size="15"
                /><b v-else>{{ item.id }}</b></span
              >
              <div>
                <strong>{{ item.label }}</strong
                ><small>{{ item.note }}</small>
              </div>
            </div>
          </nav>

          <div v-if="error" class="message error wizard-message">
            <CircleAlert :size="17" />{{ error }}
          </div>

          <section
            v-if="plannerStep === 1"
            class="planner-card planner-step-page"
          >
            <div class="section-heading">
              <div>
                <span>01</span>
                <div>
                  <h2>确认基本信息</h2>
                  <p>先确认所在地区、高考年份和选科组合，下一步再设置具体规划范围。</p>
                </div>
              </div>
              <BookOpenCheck :size="23" />
            </div>
            <div class="form-grid two">
              <label
                ><span>所在地区</span
                ><select :value="form.provinceCode" @change="changeProvince">
                  <option
                    v-for="item in provinceRoutes"
                    :key="item.code"
                    :value="item.code"
                  >
                    {{ item.name }}省 · {{ item.exam_mode }}
                  </option>
                </select></label
              >
              <label
                ><span>目标高考年份</span
                ><select v-model.number="form.targetExamYear">
                  <option
                    v-for="year in [2027, 2028, 2029, 2030]"
                    :key="year"
                    :value="year"
                  >
                    {{ year }} 年
                  </option>
                </select></label
              >
            </div>
            <div class="subject-picker">
              <div>
                <strong>高考选科组合</strong
                ><small>{{ province.selection_rule }}</small>
              </div>
              <div class="subject-chips">
                <button
                  v-for="key in selectableSubjects"
                  :key="key"
                  :class="{ selected: form.selectedSubjects.includes(key) }"
                  type="button"
                  @click="toggleSubject(key)"
                >
                  <Check
                    v-if="form.selectedSubjects.includes(key)"
                    :size="13"
                  />{{ subjectLabels[key] }}
                </button>
              </div>
              <p v-if="!selectionValid" class="inline-warning">
                <CircleAlert :size="15" /> 当前组合不符合地区选科规则
              </p>
            </div>
            <div class="workflow-actions">
              <span>第 1 步，共 5 步</span>
              <button
                class="primary-button"
                type="button"
                @click="movePlannerStep(2)"
              >
                下一步：确定范围 <ChevronRight :size="18" />
              </button>
            </div>
          </section>

          <section
            v-else-if="plannerStep === 2"
            class="planner-card planner-step-page"
          >
            <div class="section-heading">
              <div>
                <span>02</span>
                <div>
                  <h2>确定规划范围</h2>
                  <p>选择本次需要规划的科目，再逐科确认教材版本和 1–5 个学习章节。</p>
                </div>
              </div>
              <BookOpenCheck :size="23" />
            </div>
            <div class="subject-picker planning-subject-picker">
              <div>
                <strong>本次规划科目（{{ form.subjectPlans.length }} / 6）</strong>
                <small>点击已选科目可切换编辑；移除请使用下方独立按钮</small>
              </div>
              <div class="subject-chips">
                <button
                  v-for="key in planningSubjects"
                  :key="key"
                  :class="{
                    selected: form.subjectPlans.some(
                      (item) => item.subject === key,
                    ),
                    editing: activePlanningSubject === key,
                  }"
                  type="button"
                  @click="selectOrAddPlanningSubject(key)"
                >
                  <Check
                    v-if="form.subjectPlans.some(
                      (item) => item.subject === key,
                    )"
                    :size="13"
                  />{{ subjectLabels[key] }}
                </button>
              </div>
              <footer class="planning-subject-actions">
                <p>
                  当前正在编辑：<strong>{{ planningSubjectLabel }}</strong>
                </p>
                <button
                  v-if="form.subjectPlans.length > 1"
                  class="remove-planning-subject"
                  type="button"
                  @click="removePlanningSubject(activeSubjectPlan.subject)"
                >
                  <X :size="13" />移除{{ planningSubjectLabel }}
                </button>
              </footer>
            </div>
            <div class="form-grid two planning-scope-grid">
              <label
                ><span>{{ planningSubjectLabel }}教材版本</span
                ><select
                  :value="activeSubjectPlan.curriculumVersion"
                  @change="changeEdition"
                >
                  <option
                    v-for="item in editions"
                    :key="item.id"
                    :value="item.id"
                  >
                    {{ item.label }} ·
                    {{ item.pdf_count || item.volumes.length }} 册 /
                    {{ item.chapter_count || 0 }} 项{{
                      item.review_required_volume_count ? " · 含待复核" : ""
                    }}
                  </option>
                </select></label
              >
              <section
                class="chapter-scope-field"
                aria-labelledby="chapter-scope-label"
              >
                <header>
                  <div>
                    <span id="chapter-scope-label">当前学习范围</span>
                    <small>可跨分册选择，快速诊断将覆盖全部已选章节</small>
                  </div>
                  <strong>{{ activeSubjectPlan.classProgress.length }} / 5</strong>
                </header>
                <div
                  v-if="selectedChapters.length"
                  class="selected-chapter-list"
                  aria-label="已选择的章节"
                >
                  <button
                    v-for="(item, index) in selectedChapters"
                    :key="item.id"
                    type="button"
                    :title="'取消选择：' + item.title"
                    @click="toggleChapterScope(item.id)"
                  >
                    <span>{{ index + 1 }}</span>
                    <b>{{ item.title }}</b>
                    <X :size="14" />
                  </button>
                </div>
                <p v-else class="chapter-selection-empty">
                  <CircleAlert :size="15" />请至少选择 1 个章节
                </p>
                <div class="chapter-option-groups">
                  <section
                    v-for="group in selectableChapterGroups"
                    :key="group.id"
                  >
                    <header>
                      <strong>{{ group.label }}</strong>
                      <small>
                        {{
                          group.options.filter((item) =>
                            activeSubjectPlan.classProgress.includes(item.id),
                          ).length
                        }}
                        / {{ group.options.length }} 已选
                      </small>
                    </header>
                    <div>
                      <button
                        v-for="(item, optionIndex) in group.options"
                        :key="item.id"
                        type="button"
                        :class="{
                          selected: activeSubjectPlan.classProgress.includes(item.id),
                          'limit-reached':
                            activeSubjectPlan.classProgress.length >=
                              MAX_CHAPTER_SELECTION &&
                            !activeSubjectPlan.classProgress.includes(item.id),
                        }"
                        :aria-pressed="activeSubjectPlan.classProgress.includes(item.id)"
                        @click="toggleChapterScope(item.id)"
                      >
                        <span>
                          <Check
                            v-if="activeSubjectPlan.classProgress.includes(item.id)"
                            :size="14"
                          />
                          <b v-else>{{ optionIndex + 1 }}</b>
                        </span>
                        <span>
                          <strong>
                            {{ item.number ? item.number + " " : ""
                            }}{{ item.title }}
                          </strong>
                          <small v-if="item.evidence">
                            PDF 第 {{ item.evidence.pdf_page }} 页可追溯
                          </small>
                        </span>
                      </button>
                    </div>
                  </section>
                </div>
                <footer>
                  <span>至少 1 个，最多 5 个</span>
                  <span>已选范围会同时用于诊断出题与正式计划</span>
                </footer>
              </section>
            </div>
            <div class="evidence-box">
              <ShieldCheck :size="19" />
              <div>
                <strong>{{
                  editionEvidenceLabel(
                    activeSubjectPlan.subject,
                    activeSubjectPlan.curriculumVersion,
                  )
                }}</strong>
                <p v-if="selectedChapters.length">
                  已选择 {{ selectedChapters.length }} 个章节；后续 10
                  道快速诊断题会覆盖全部已选范围，并把每道题归属写入客观学情证据。
                </p>
                <small>
                  {{ selectedChapters.filter((item) => item.evidence).length }}
                  个已选章节可追溯到教材 PDF
                  目录；教材版本仍须按学校用书版权页确认。
                </small>
              </div>
            </div>
            <div class="workflow-actions">
              <button
                class="workflow-back"
                type="button"
                @click="movePlannerStep(1)"
              >
                返回上一步</button
              ><button
                class="primary-button"
                type="button"
                @click="movePlannerStep(3)"
              >
                下一步：设置目标 <ChevronRight :size="18" />
              </button>
            </div>
          </section>

          <section
            v-else-if="plannerStep === 3"
            class="planner-card planner-step-page"
          >
            <div class="section-heading">
              <div>
                <span>03</span>
                <div>
                  <h2>填写学习目标</h2>
                  <p>这里只填写可核验的成绩目标，掌握程度将由快速诊断判断。</p>
                </div>
              </div>
              <Target :size="23" />
            </div>
            <div class="multi-subject-goals">
              <section
                v-for="item in form.subjectPlans"
                :key="item.subject"
                class="subject-goal-card"
              >
                <header>
                  <strong>{{ subjectLabels[item.subject] }}</strong>
                  <span>{{ subjectScoreMax(item.subject) }} 分制</span>
                </header>
                <div class="score-panel">
                  <label
                    ><span>当前成绩</span>
                    <div>
                      <input
                        v-model.number="item.currentScore"
                        type="number"
                        min="0"
                        :max="subjectScoreMax(item.subject)"
                      /><small>/ {{ subjectScoreMax(item.subject) }}</small>
                    </div></label
                  ><ChevronRight :size="23" /><label
                    ><span>目标成绩</span>
                    <div class="target-score">
                      <input
                        v-model.number="item.targetScore"
                        type="number"
                        min="0"
                        :max="subjectScoreMax(item.subject)"
                      /><small>/ {{ subjectScoreMax(item.subject) }}</small>
                    </div></label
                  ><label
                    ><span>目标日期</span
                    ><input v-model="item.deadline" type="date"
                  /></label>
                  <label
                    ><span>规划优先级</span
                    ><select v-model.number="item.priority">
                      <option :value="1">高优先级</option>
                      <option :value="2">中优先级</option>
                      <option :value="3">保持型</option>
                    </select></label
                  >
                </div>
              </section>
            </div>
            <div class="objective-note">
              <Target :size="21" />
              <div>
                <strong>目标用于确定训练强度，不等同于当前掌握度</strong>
                <p>
                  下一步的 10
                  题诊断会提供客观学情证据，系统不会要求你猜测自己的基础和综合应用水平。
                </p>
              </div>
            </div>
            <div class="workflow-actions">
              <button
                class="workflow-back"
                type="button"
                @click="movePlannerStep(1)"
              >
                返回上一步</button
              ><button
                class="primary-button"
                type="button"
                @click="movePlannerStep(4)"
              >
                下一步：快速诊断 <ChevronRight :size="18" />
              </button>
            </div>
          </section>

          <section
            v-else-if="plannerStep === 4"
            class="planner-card diagnostic-card planner-step-page"
          >
            <div class="section-heading">
              <div>
                <span>04</span>
                <div>
                  <h2>10 题快速诊断</h2>
                  <p>直接通过客观作答估计基础、应用和迁移能力。</p>
                </div>
              </div>
              <BrainCircuit :size="23" />
            </div>
            <div class="subject-picker diagnostic-subject-picker">
              <div>
                <strong>逐科诊断进度</strong>
                <small>{{ completedDiagnosticCount }} / {{ form.subjectPlans.length }} 科已完成</small>
              </div>
              <div class="subject-chips">
                <button
                  v-for="item in form.subjectPlans"
                  :key="item.subject"
                  type="button"
                  :class="{
                    selected: activeDiagnosticSubject === item.subject,
                    completed: diagnosticStates[item.subject]?.result,
                  }"
                  @click="activeDiagnosticSubject = item.subject"
                >
                  <Check
                    v-if="diagnosticStates[item.subject]?.result"
                    :size="13"
                  />{{ subjectLabels[item.subject] }}
                </button>
              </div>
            </div>
            <div
              v-if="!diagnosticSession && !diagnosticResult"
              class="diagnostic-intro"
            >
              <div>
                <strong>
                  {{ subjectLabels[activeDiagnosticSubject] }}的 10 道题将覆盖已选的
                  {{ activeDiagnosticPlan.classProgress.length }} 个章节
                </strong>
                <p>
                  问鹿AI会在全部所选章节间合理分配前置、概念、基础应用、综合应用和迁移题；
                  每个章节至少覆盖 1 题，异常时自动切换本地真题题库。
                </p>
              </div>
              <button
                class="secondary-button"
                type="button"
                :disabled="
                  diagnosticLoading || !selectionValid || !allSubjectScopesValid
                "
                @click="startDiagnostic"
              >
                <LoaderCircle
                  v-if="diagnosticLoading"
                  class="spin"
                  :size="18"
                /><BrainCircuit v-else :size="18" />{{
                  diagnosticLoading
                    ? "问鹿AI 正在按所选章节出题"
                    : "开始快速诊断"
                }}
              </button>
            </div>
            <div
              v-else-if="
                diagnosticSession &&
                currentDiagnosticQuestion &&
                !diagnosticResult
              "
              class="diagnostic-workspace"
            >
              <p
                v-if="
                  diagnosticSession.generation_mode === 'fixed_bank_fallback'
                "
                class="diagnostic-fallback-note"
              >
                <ShieldCheck :size="16" />
                当前使用本地高考真题题库兜底，答案仍只会在提交后显示。
              </p>
              <div class="diagnostic-progress">
                <div>
                  <strong>第 {{ diagnosticIndex + 1 }} / 10 题</strong
                  ><span>{{ currentDiagnosticQuestion.knowledge_focus }}</span>
                </div>
                <span><i :style="{ width: `${diagnosticPercent}%` }" /></span>
              </div>
              <article class="diagnostic-question">
                <small
                  >{{
                    currentDiagnosticQuestion.scope_label || "所选学习范围"
                  }}
                  · {{ currentDiagnosticQuestion.dimension }} · 难度
                  {{
                    Math.round(currentDiagnosticQuestion.difficulty * 100)
                  }}%</small
                >
                <h3
                  v-if="currentDiagnosticQuestion.prompt_html"
                  class="diagnostic-rich-content"
                  v-html="
                    resolveDiagnosticAssetHtml(
                      currentDiagnosticQuestion.prompt_html,
                    )
                  "
                />
                <h3 v-else>{{ currentDiagnosticQuestion.prompt }}</h3>
                <div class="diagnostic-options">
                  <button
                    v-for="(
                      option, optionIndex
                    ) in currentDiagnosticQuestion.options"
                    :key="optionIndex"
                    type="button"
                    :class="{ selected: diagnosticSelection === optionIndex }"
                    @click="selectDiagnosticOption(optionIndex)"
                  >
                    <b>{{ String.fromCharCode(65 + optionIndex) }}</b
                    ><span
                      v-if="
                        currentDiagnosticQuestion.options_html?.[optionIndex]
                      "
                      class="diagnostic-rich-content"
                      v-html="
                        resolveDiagnosticAssetHtml(
                          currentDiagnosticQuestion.options_html[optionIndex],
                        )
                      "
                    /><span v-else>{{ option }}</span
                    ><i v-if="diagnosticSelection === optionIndex"
                      ><Check :size="15"
                    /></i>
                  </button>
                </div>
              </article>
              <div class="diagnostic-confidence">
                <div>
                  <strong>你对刚才选择的答案有多确定？</strong
                  ><small>{{
                    diagnosticSelection === null
                      ? "请先选择上方 A、B、C 或 D"
                      : diagnosticIndex < 9
                        ? "点击后自动进入下一题"
                        : "点击后自动提交诊断"
                  }}</small>
                </div>
                <div class="confidence-buttons">
                  <button
                    v-for="item in diagnosticConfidenceOptions"
                    :key="item.label"
                    type="button"
                    :class="item.tone"
                    :disabled="
                      diagnosticSelection === null || diagnosticSubmitting
                    "
                    @click="selectDiagnosticConfidence(item.value)"
                  >
                    <span />{{ item.label }}
                  </button>
                </div>
              </div>
            </div>
            <div v-else-if="diagnosticResult" class="diagnostic-result">
              <div>
                <CheckCircle2 :size="24" /><span
                  ><strong>客观诊断已完成</strong
                  ><small
                    >10 条证据将用于本次学习状态评估和计划生成</small
                  ></span
                ><button type="button" @click="startDiagnostic">
                  <RefreshCw :size="15" />重新诊断
                </button>
              </div>
              <div class="diagnostic-metrics">
                <article>
                  <small>客观正确率</small
                  ><strong
                    >{{
                      Math.round(diagnosticResult.objective_score * 100)
                    }}%</strong
                  >
                </article>
                <article>
                  <small>基础能力</small
                  ><strong
                    >{{
                      Math.round(diagnosticResult.foundation_score * 100)
                    }}%</strong
                  >
                </article>
                <article>
                  <small>综合应用</small
                  ><strong
                    >{{
                      Math.round(diagnosticResult.application_score * 100)
                    }}%</strong
                  >
                </article>
                <article>
                  <small>作答信心校准</small
                  ><strong
                    >{{
                      Math.round(diagnosticResult.metacognitive_accuracy * 100)
                    }}%</strong
                  >
                </article>
              </div>
            </div>
            <div class="workflow-actions">
              <button
                class="workflow-back"
                type="button"
                @click="movePlannerStep(3)"
              >
                返回上一步</button
              ><button
                class="primary-button"
                type="button"
                :disabled="!allDiagnosticsComplete"
                @click="movePlannerStep(5)"
              >
                下一步：安排时间 <ChevronRight :size="18" />
              </button>
            </div>
          </section>

          <section v-else class="planner-card planner-step-page">
            <div class="section-heading">
              <div>
                <span>05</span>
                <div>
                  <h2>设置可持续时间</h2>
                  <p>系统会保留机动缓冲，不会把每一分钟排满。</p>
                </div>
              </div>
              <Clock3 :size="23" />
            </div>
            <div class="time-layout">
              <label class="weekly-range"
                ><span
                  ><b>每周可用学习时间</b
                  ><strong>{{ minutesLabel(form.weeklyMinutes) }}</strong></span
                ><input
                  v-model.number="form.weeklyMinutes"
                  type="range"
                  min="210"
                  max="1050"
                  step="35"
                /><small
                  >建议实际排期约
                  {{
                    minutesLabel(Math.round(form.weeklyMinutes * 0.82))
                  }}</small
                ></label
              >
              <div class="form-grid two compact">
                <label
                  ><span>工作日每天</span
                  ><select v-model.number="form.weekdayMinutes">
                    <option :value="45">45 分钟</option>
                    <option :value="70">70 分钟</option>
                    <option :value="90">90 分钟</option>
                  </select></label
                ><label
                  ><span>周末每天</span
                  ><select v-model.number="form.weekendMinutes">
                    <option :value="90">90 分钟</option>
                    <option :value="140">140 分钟</option>
                    <option :value="180">180 分钟</option>
                  </select></label
                >
              </div>
            </div>
            <div class="planner-actions">
              <button
                class="workflow-back"
                type="button"
                @click="movePlannerStep(4)"
              >
                返回上一步
              </button>
              <div>
                <CheckCircle2 :size="20" /><span
                  ><strong>客观诊断与时间资料已准备</strong
                  ><small
                    >{{ province.name }} · 已完成 {{ form.subjectPlans.length }} 科客观诊断</small
                  ></span
                >
              </div>
              <button
                class="primary-button"
                :disabled="loading || !selectionValid || !allDiagnosticsComplete"
                @click="generatePlan"
              >
                <LoaderCircle v-if="loading" class="spin" :size="19" /><Sparkles
                  v-else
                  :size="19"
                />{{ loading ? "Agent 正在规划" : "生成个性化学习计划" }}
              </button>
            </div>
          </section>
        </template>

        <template v-else-if="activeView === `collaboration`">
          <AgentCollaborationWorkspace
            :profile="profile"
            :current-plan="plan"
            v-on:open-planning-center="navigate(`workspace`)"
          />
        </template>

        <template v-else-if="activeView === `tutor`">
          <HomeworkTutorWorkspace
            :profile="profile"
            :plan-tasks="plan?.tasks || []"
            :initial-subject="form.subjectPlans[0].subject"
          />
        </template>

        <template v-else-if="activeView === 'programming'">
          <CareerEducationV1Workspace
            :profile="profile"
            :active-mode="careerMode"
            @mode-change="navigateCareer"
          />
        </template>

        <template v-else-if="activeView === 'diagnosis'">
          <LearningDiagnosisWorkspace
            :profile="profile"
            :initial-subject="form.subjectPlans[0].subject"
            :curriculum-version="form.subjectPlans[0].curriculumVersion"
            :initial-assignment-id="assignedAssignmentId"
            mode="exam"
          />
        </template>

        <template v-else-if="activeView === 'records'">
          <LearningDiagnosisWorkspace
            :profile="profile"
            :initial-subject="form.subjectPlans[0].subject"
            :curriculum-version="form.subjectPlans[0].curriculumVersion"
            mode="records"
          />
        </template>

        <template v-else-if="activeView === 'classroom'">
          <StudentClassroomWorkspace @open-diagnosis="openAssignedDiagnosis" />
        </template>

        <template v-else-if="activeView === 'plan' && plan">
          <section v-if="response?._meta?.mode === 'demo'" class="demo-banner">
            <CircleAlert :size="17" /><span
              ><strong>在线演示模式</strong>
              当前展示完整交互与示例计划；服务器本地页面会调用真实 Agent。</span
            >
          </section>
          <section class="plan-hero student-module-hero">
            <div>
              <span class="eyebrow light"
                ><CheckCircle2 :size="15" />
                {{
                  confirmed
                    ? "计划执行中"
                    : planProvisional
                      ? "客观证据不足 · 暂定计划"
                      : plan.validation?.valid
                        ? "规划已完成"
                        : "规划需要调整"
                }}</span
              >
              <h1>
                {{
                  confirmed
                    ? "你的学习路径已经启动"
                    : planProvisional
                      ? "先参考执行，完成诊断后再确认"
                      : plan.validation?.valid
                        ? "第一阶段计划已经准备好"
                        : "计划暂未达到发布条件"
                }}
              </h1>
              <p>{{ plan.stages[0]?.objective }}</p>
              <div>
                <button
                  v-if="!confirmed && !planProvisional"
                  class="white-button"
                  :disabled="confirming || !plan.validation?.valid"
                  @click="confirmPlan"
                >
                  <LoaderCircle
                    v-if="confirming"
                    class="spin"
                    :size="18"
                  /><Check v-else :size="18" />{{
                    confirming ? "正在确认" : "确认并开始计划"
                  }}</button
                ><button
                  class="white-button"
                  @click="activeView = 'plan-insights'"
                >
                  <BrainCircuit :size="17" />查看规划依据</button
                ><button class="white-button" @click="activeView = 'tutor'">
                  <MessageCircleQuestion :size="17" />进入作业辅导</button
                ><button class="ghost-button" @click="activeView = 'workspace'">
                  <RefreshCw :size="17" />调整资料
                </button>
              </div>
            </div>
            <div class="score-circle">
              <small>统一规划科目</small
              ><strong>{{ form.subjectPlans.length }} 科</strong
              ><span>{{ form.subjectPlans.map((item) => subjectLabels[item.subject]).join(' · ') }}</span>
            </div>
          </section>
          <section
            v-if="planProvisional"
            class="validation-alert provisional-alert"
          >
            <BrainCircuit :size="19" />
            <div>
              <strong>这是暂定计划，尚不能确认执行</strong>
              <p>
                当前客观证据不足。返回规划中心完成 10
                题快速诊断，再重新生成即可获得可确认计划。
              </p>
            </div>
            <button @click="activeView = 'workspace'">去完成诊断</button>
          </section>
          <section v-if="!plan.validation?.valid" class="validation-alert">
            <CircleAlert :size="19" />
            <div>
              <strong>以下约束尚未通过，计划不会被错误发布</strong>
              <p>
                {{
                  planValidationIssues
                    .map((item) => validationLabels[item] || item)
                    .join("、")
                }}
              </p>
            </div>
            <button @click="activeView = 'workspace'">返回调整</button>
          </section>
          <div class="plan-metrics">
            <article>
              <CalendarDays :size="20" /><span
                ><small>计划周期</small
                ><strong
                  >{{ formatDate(plan.plan_start) }}—{{
                    formatDate(plan.plan_end)
                  }}</strong
                ></span
              >
            </article>
            <article>
              <Clock3 :size="20" /><span
                ><small>本周排期</small
                ><strong>{{
                  minutesLabel(plan.scheduled_minutes)
                }}</strong></span
              >
            </article>
            <article>
              <ShieldCheck :size="20" /><span
                ><small>机动缓冲</small
                ><strong>{{ minutesLabel(plan.buffer_minutes) }}</strong></span
              >
            </article>
            <article>
              <CheckCircle2 :size="20" /><span
                ><small>约束校验</small
                ><strong>{{
                  plan.validation?.valid ? "全部通过" : "需要检查"
                }}</strong></span
              >
            </article>
          </div>
          <section class="plan-subject-summary">
            <article
              v-for="goal in plan.subject_goals"
              :key="goal.subject"
            >
              <header>
                <strong>{{ subjectLabels[goal.subject] }}</strong>
                <span>优先级 {{ goal.priority }}</span>
              </header>
              <p>
                {{ goal.current_value }} → {{ goal.target_value }} 分 ·
                {{ formatDate(goal.deadline) }}
              </p>
              <small>
                每周预算
                {{ minutesLabel(plan.subject_time_budgets[goal.subject] || 0) }}
              </small>
            </article>
          </section>
          <div v-if="error" class="message error">
            <CircleAlert :size="17" />{{ error }}
          </div>
          <div class="plan-stack">
            <section class="task-list card">
              <div class="card-heading">
                <div>
                  <small>本周任务</small>
                  <h2>本周学习安排</h2>
                </div>
                <span>{{ filteredPlanTasks.length }} 项任务</span>
              </div>
              <div class="plan-subject-filters">
                <button
                  type="button"
                  :class="{ active: planSubjectFilter === 'all' }"
                  @click="
                    planSubjectFilter = 'all';
                    planTaskPage = 1;
                  "
                >
                  全部
                </button>
                <button
                  v-for="subject in planSubjectOptions"
                  :key="subject"
                  type="button"
                  :class="{ active: planSubjectFilter === subject }"
                  @click="
                    planSubjectFilter = subject;
                    planTaskPage = 1;
                  "
                >
                  {{ subjectLabels[subject] }}
                </button>
              </div>
              <article
                v-for="(task, index) in pagedPlanTasks"
                :key="task.task_id"
                class="task-row"
              >
                <span class="task-index">{{
                  (planTaskPage - 1) * DISPLAY_PAGE_SIZE + index + 1
                }}</span>
                <div>
                  <div>
                    <b>{{ taskNames[task.task_type] || "学习任务" }}</b
                    ><small
                      ><Clock3 :size="13" />{{
                        task.planned_duration_minutes
                      }}
                      分钟</small
                    >
                  </div>
                  <h3>{{ taskTitle(task) }}</h3>
                  <p>{{ taskDescription(task) }}</p>
                  <span class="relevance"
                    ><i :style="{ width: `${task.exam_relevance * 100}%` }"
                  /></span>
                </div>
              </article>
              <PaginationControls
                :page="planTaskPage"
                :total="filteredPlanTasks.length"
                :page-size="DISPLAY_PAGE_SIZE"
                label="项任务"
                @change="planTaskPage = $event"
              />
            </section>
            <section class="card gap-card gap-card-wide">
              <header>
                <span><Target :size="23" /></span>
                <div>
                  <small>当前优先级</small>
                  <h2>优先补齐</h2>
                  <p>这些内容来自当前学习证据，将优先安排在本周任务中。</p>
                </div>
              </header>
              <div class="gap-list">
                <p
                  v-for="(gap, index) in knowledge?.priority_gaps || []"
                  :key="gap"
                >
                  <span>{{ index + 1 }}</span
                  >{{ knowledgeIdLabel(gap) }}
                </p>
                <p v-if="!knowledge?.priority_gaps?.length" class="gap-empty">
                  完成更多客观诊断后，这里会显示需要优先补齐的内容。
                </p>
              </div>
            </section>
          </div>
        </template>

        <template v-else-if="activeView === 'plan-insights' && plan">
          <section class="subpage-hero insight-page-hero student-module-hero">
            <div>
              <span class="eyebrow"
                ><BrainCircuit :size="15" /> 智能规划说明</span
              >
              <h1>这份计划为什么这样安排</h1>
              <p>
                按照目标、学习证据、时间预算和调整条件逐点说明，不展示系统内部编号。
              </p>
            </div>
            <button class="insight-back" @click="activeView = 'plan'">
              <CalendarDays :size="17" />返回本周计划
            </button>
          </section>
          <section class="card insight-page-card">
            <header class="card-heading">
              <div>
                <small>主次分层说明</small>
                <h2>规划依据</h2>
              </div>
              <span
                >1 个核心方向 ·
                {{ planningInsightItems.length }} 条具体说明</span
              >
            </header>
            <section class="insight-main-point">
              <span><BrainCircuit :size="25" /></span>
              <div>
                <small>核心规划方向</small>
                <h3>本阶段总纲</h3>
                <p>{{ planningInsightMain }}</p>
              </div>
            </section>
            <section class="insight-detail-section">
              <header>
                <div>
                  <small>从属说明</small>
                  <h3>围绕总纲的具体安排</h3>
                </div>
                <span>{{ planningInsightItems.length }} 条</span>
              </header>
              <div
                v-if="pagedPlanningInsights.length"
                class="insight-point-list"
              >
                <article
                  v-for="(item, index) in pagedPlanningInsights"
                  :key="`${insightPage}-${index}-${item}`"
                >
                  <span>{{
                    (insightPage - 1) * DISPLAY_PAGE_SIZE + index + 1
                  }}</span>
                  <div>
                    <strong>{{ insightDetailLabel(item) }}</strong>
                    <p>{{ item }}</p>
                  </div>
                </article>
              </div>
              <div v-else class="insight-empty compact">
                <strong>暂无更多具体说明</strong>
                <p>当前核心规划方向已经完整展示。</p>
              </div>
              <PaginationControls
                :page="insightPage"
                :total="planningInsightItems.length"
                :page-size="DISPLAY_PAGE_SIZE"
                label="条具体说明"
                @change="insightPage = $event"
              />
            </section>
          </section>
        </template>
      </div>
    </main>

    <TransitionGroup
      name="ai-result"
      tag="section"
      class="ai-result-notifications"
      aria-label="问鹿AI结果通知"
      aria-live="polite"
    >
      <article
        v-for="notification in aiResultNotifications"
        :key="notification.id"
        class="ai-result-notification"
      >
        <button
          class="ai-result-link"
          type="button"
          @click="openAiResult(notification)"
        >
          <span class="ai-result-icon"><Sparkles :size="20" /></span>
          <span class="ai-result-copy">
            <small>问鹿AI · 结果已就绪</small>
            <strong>{{ notification.title }}</strong>
            <span>{{ notification.message }}</span>
            <b>点击前往查看 <ChevronRight :size="15" /></b>
          </span>
        </button>
        <button
          class="ai-result-close"
          type="button"
          :aria-label="'关闭' + notification.title + '通知'"
          @click="dismissAiResult(notification.id)"
        >
          <X :size="15" />
        </button>
      </article>
      <article
        v-if="pendingAiTasks.length"
        key="pending-ai-status"
        class="ai-pending-notification"
      >
        <LoaderCircle class="spin" :size="18" />
        <span>
          <strong>{{ pendingAiStatus }}</strong>
          <small>可以继续使用其他页面，完成后会提醒你。</small>
        </span>
      </article>
    </TransitionGroup>
    <Transition name="toast"
      ><div v-if="toast" class="toast">
        <CheckCircle2 :size="18" />{{ toast }}
      </div></Transition
    >
  </div>
</template>

<style scoped>
.ai-pending-notification{display:flex;align-items:center;gap:11px;padding:13px 16px;color:#174ea6;border:1px solid #bdd3f7;background:rgba(244,248,255,.97);border-radius:14px;box-shadow:0 14px 38px rgba(27,63,118,.18);backdrop-filter:blur(12px)}
.ai-pending-notification>span{display:flex;flex-direction:column;gap:3px}.ai-pending-notification strong{font-size:14px}.ai-pending-notification small{color:#607a9d;font-size:12px;line-height:1.45}
</style>
