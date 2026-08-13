<script setup lang="ts">
import {
  ArrowRight,
  BookOpenText,
  BriefcaseBusiness,
  Check,
  CheckCircle2,
  ChevronDown,
  CircleAlert,
  ClipboardCheck,
  Clock3,
  Code2,
  Download,
  FileText,
  FlaskConical,
  Gauge,
  History,
  Lightbulb,
  LoaderCircle,
  MessageSquareText,
  Play,
  RotateCcw,
  Route,
  Send,
  ShieldCheck,
  Sparkles,
  Target,
  Upload,
  X,
} from "@lucide/vue";
import { computed, onMounted, reactive, ref, watch } from "vue";

import {
  downloadProjectDocument,
  evaluateProject,
  fetchCareerEducationDashboard,
  fetchCodingHistory,
  fetchCodingQuestionBank,
  fetchGaokaoProgrammingHistory,
  fetchProjectBank,
  nextGaokaoProgrammingQuestion,
  nextCodingQuestion,
  onboardCareerEducation,
  requestCodingHint,
  requestCodingSolution,
  resolveCareerAssetHtml,
  sendCareerChat,
  sendProjectChat,
  startProject,
  submitCodingAnswer,
  submitGaokaoProgrammingAnswer,
  submitGaokaoProgrammingImages,
  submitProjectText,
  switchCareerMode,
  uploadProjectDocument,
  type CareerChatResult,
  type CareerEducationDashboard,
  type CareerMode,
  type CodingSession,
  type CodingSubmission,
  type CodingQuestion,
  type GaokaoProgrammingFeedback,
  type GaokaoProgrammingHistory,
  type GaokaoProgrammingSession,
  type ProjectEvaluation,
  type ProjectChatResult,
  type ProjectSession,
  type ProjectTemplate,
} from "@/lib/career-education-v1-client";
import type { StudentLoginProfile } from "@/lib/types";

const props = defineProps<{
  profile: StudentLoginProfile;
  activeMode?: CareerMode;
}>();
const emit = defineEmits<{ "mode-change": [mode: CareerMode] }>();

const dashboard = ref<CareerEducationDashboard | null>(null);
const mode = ref<CareerMode>(props.activeMode || "CAREER");
const loading = ref(true);
const busy = ref(false);
const error = ref("");
const toast = ref("");
const showProfile = ref(false);
const showEvidence = ref(false);

const onboarding = reactive({
  target_job_id: "JOB_PY_BACKEND" as const,
  identity: "undergraduate" as
    | "high_school_student"
    | "vocational_student"
    | "undergraduate"
    | "career_switcher",
  education_stage: "undergraduate" as
    "high_school" | "vocational" | "undergraduate" | "graduate" | "other",
  programming_level: "basic" as "beginner" | "basic" | "project",
  known_languages: ["Python"],
  weekly_hours: 10,
  learning_goal: "internship" as
    "gaokao" | "internship" | "campus_recruitment" | "career_change",
  target_period_weeks: 16,
});

const careerMessage = ref("我目前只会 Python 基础，下一步应该学习什么？");
const careerResult = ref<CareerChatResult | null>(null);
const careerConversation = ref<
  Array<{ id: string; userMessage: string; result: CareerChatResult }>
>([]);

const projectBank = ref<ProjectTemplate[]>([]);
const projectOrder = ref<string[]>([]);
const projectSession = ref<ProjectSession | null>(null);
const activeProjectDoc = ref<"requirement" | "problems">("requirement");
const projectEvaluation = ref<ProjectEvaluation | null>(null);
const projectFile = ref<File | null>(null);
const projectMessage = ref("这个项目我应该从哪里开始？");
const projectConversation = ref<
  Array<{ id: string; userMessage?: string; result: ProjectChatResult }>
>([]);
const projectAnswer = reactive({
  development_plan: "",
  technology_selection: "",
  architecture_design: "",
  database_design: "",
  api_design: "",
  problem_solution: "",
});

const codingSession = ref<CodingSession | null>(null);
const codingSubmission = ref<CodingSubmission | null>(null);
const codingHistory = ref<CodingSubmission[]>([]);
const codingBank = ref<CodingQuestion[]>([]);
const codingDifficulty = ref(0);
const codingLanguage = ref("python");
const code = ref("");
const codingHint = ref<{ hint_level: number; hint: string } | null>(null);
const solution = ref<{
  reference_solution: string;
  solution_explanation: string;
  mastery_notice: string;
} | null>(null);
const gaokaoSession = ref<GaokaoProgrammingSession | null>(null);
const gaokaoFeedback = ref<GaokaoProgrammingFeedback | null>(null);
const gaokaoAnswer = ref("");
const gaokaoChoice = ref("");
const gaokaoSubmissionMethod = ref<"text" | "image">("text");
const gaokaoFiles = ref<File[]>([]);
const gaokaoHistory = ref<GaokaoProgrammingHistory>({
  questions: [],
  total_questions: 0,
  total_submissions: 0,
  answers_exposed: false,
});
const gaokaoStartedAt = ref(Date.now());

const configured = computed(() => Boolean(dashboard.value?.configured));
const currentJob = computed(() => dashboard.value?.jobs[0]);
const answerReady = computed(() =>
  [
    projectAnswer.development_plan,
    projectAnswer.technology_selection,
    projectAnswer.architecture_design,
    projectAnswer.database_design,
    projectAnswer.api_design,
  ].every((value) => value.trim().length >= 20),
);
const recommendedProjectDifficulty = computed(() =>
  dashboard.value?.profile.programming_level === "beginner" ? 1 : 2,
);
const projectBatch = computed(() =>
  projectOrder.value
    .slice(0, 2)
    .map((id) => projectBank.value.find((item) => item.project_id === id))
    .filter((item): item is ProjectTemplate => Boolean(item)),
);
const filteredCodingBank = computed(() =>
  codingDifficulty.value
    ? codingBank.value.filter(
        (item) => item.difficulty === codingDifficulty.value,
      )
    : codingBank.value,
);

onMounted(loadDashboard);
watch(
  () => props.activeMode,
  (next) => {
    if (next && next !== mode.value) void selectMode(next);
  },
);
watch(
  () => onboarding.identity,
  (identity) => {
    if (identity === "high_school_student") {
      onboarding.education_stage = "high_school";
      onboarding.learning_goal = "gaokao";
    }
  },
);

async function loadDashboard() {
  loading.value = true;
  error.value = "";
  try {
    dashboard.value = await fetchCareerEducationDashboard();
    mode.value = props.activeMode || dashboard.value.current_mode;
    if (dashboard.value.configured) {
      Object.assign(onboarding, {
        target_job_id: dashboard.value.profile.target_job_id,
        identity: dashboard.value.profile.identity,
        education_stage: dashboard.value.profile.education_stage,
        programming_level: dashboard.value.profile.programming_level,
        known_languages: dashboard.value.profile.known_languages,
        weekly_hours: dashboard.value.profile.weekly_hours,
        learning_goal: dashboard.value.profile.learning_goal,
        target_period_weeks: dashboard.value.profile.target_period_weeks,
      });
      if (mode.value === "PROJECT") await loadProjects();
      if (mode.value === "CODING")
        await Promise.all([loadCodingHistory(), loadCodingBank()]);
      if (mode.value === "GAOKAO") await loadGaokaoHistory();
    }
  } catch (reason) {
    error.value = messageOf(reason);
  } finally {
    loading.value = false;
  }
}

function messageOf(reason: unknown) {
  return reason instanceof Error ? reason.message : "操作失败，请稍后重试";
}

function notify(message: string) {
  toast.value = message;
  window.setTimeout(() => {
    if (toast.value === message) toast.value = "";
  }, 2600);
}

async function saveOnboarding() {
  busy.value = true;
  error.value = "";
  try {
    await onboardCareerEducation({ ...onboarding });
    showProfile.value = false;
    await loadDashboard();
    notify("岗位与学习画像已保存");
  } catch (reason) {
    error.value = messageOf(reason);
  } finally {
    busy.value = false;
  }
}

async function selectMode(next: CareerMode) {
  if (next === mode.value || busy.value) return;
  busy.value = true;
  try {
    await switchCareerMode(next);
    mode.value = next;
    emit("mode-change", next);
    if (next === "PROJECT" && !projectBank.value.length) await loadProjects();
    if (next === "CODING" && !codingBank.value.length)
      await Promise.all([loadCodingHistory(), loadCodingBank()]);
    if (next === "GAOKAO") await loadGaokaoHistory();
  } catch (reason) {
    error.value = messageOf(reason);
  } finally {
    busy.value = false;
  }
}

async function askCareer() {
  if (!careerMessage.value.trim()) return;
  const userMessage = careerMessage.value.trim();
  busy.value = true;
  error.value = "";
  try {
    const result = await sendCareerChat(userMessage);
    careerResult.value = result;
    careerConversation.value.push({
      id: result.context_used.conversation_turns + "-" + Date.now(),
      userMessage,
      result,
    });
    careerMessage.value = "";
  } catch (reason) {
    error.value = messageOf(reason);
  } finally {
    busy.value = false;
  }
}

async function loadProjects() {
  const result = await fetchProjectBank();
  projectBank.value = result.projects;
  if (!projectOrder.value.length)
    projectOrder.value = [...result.projects]
      .sort(
        (left, right) =>
          Math.abs(left.difficulty - recommendedProjectDifficulty.value) -
          Math.abs(right.difficulty - recommendedProjectDifficulty.value),
      )
      .map((item) => item.project_id);
}

function shuffleProjects() {
  if (projectOrder.value.length < 2) return;
  projectOrder.value = [...projectOrder.value.slice(1), projectOrder.value[0]];
  notify("已为你换一批实训项目");
}

async function chooseProject(project: ProjectTemplate) {
  busy.value = true;
  error.value = "";
  try {
    projectSession.value = await startProject(project.project_id);
    projectConversation.value = projectSession.value.mentor_opening
      ? [
          {
            id: projectSession.value.mentor_opening.message_id,
            result: projectSession.value.mentor_opening,
          },
        ]
      : [];
    projectEvaluation.value = null;
    Object.assign(projectAnswer, {
      development_plan: "",
      technology_selection: "",
      architecture_design: "",
      database_design: "",
      api_design: "",
      problem_solution: "",
    });
  } catch (reason) {
    error.value = messageOf(reason);
  } finally {
    busy.value = false;
  }
}

async function askProject() {
  if (!projectMessage.value.trim()) return;
  const userMessage = projectMessage.value.trim();
  busy.value = true;
  error.value = "";
  try {
    const result = await sendProjectChat(
      userMessage,
      projectSession.value?.session_id,
    );
    projectConversation.value.push({
      id: result.message_id,
      userMessage,
      result,
    });
    projectMessage.value = "";
  } catch (reason) {
    error.value = messageOf(reason);
  } finally {
    busy.value = false;
  }
}

async function downloadDocument(type: "requirement" | "problems" | "report") {
  if (!projectSession.value) return;
  try {
    await downloadProjectDocument(projectSession.value.session_id, type);
    notify("文档已开始下载");
  } catch (reason) {
    error.value = messageOf(reason);
  }
}

async function submitProject() {
  if (!projectSession.value || !answerReady.value) return;
  busy.value = true;
  error.value = "";
  try {
    await submitProjectText(projectSession.value.session_id, {
      development_plan: projectAnswer.development_plan,
      technology_selection: projectAnswer.technology_selection,
      architecture_design: projectAnswer.architecture_design,
      database_design: projectAnswer.database_design,
      api_design: projectAnswer.api_design,
      problem_solutions: {
        GENERAL:
          projectAnswer.problem_solution || "已在整体方案中说明风险处理。",
      },
    });
    projectSession.value.status = "submitted";
    notify("项目回答已保存，可以开始评价");
  } catch (reason) {
    error.value = messageOf(reason);
  } finally {
    busy.value = false;
  }
}

async function uploadProject() {
  if (!projectSession.value || !projectFile.value) return;
  busy.value = true;
  try {
    await uploadProjectDocument(
      projectSession.value.session_id,
      projectFile.value,
    );
    projectSession.value.status = "submitted";
    notify("回答文档已安全解析并保存");
  } catch (reason) {
    error.value = messageOf(reason);
  } finally {
    busy.value = false;
  }
}

async function scoreProject() {
  if (!projectSession.value) return;
  busy.value = true;
  try {
    projectEvaluation.value = await evaluateProject(
      projectSession.value.session_id,
    );
    projectSession.value.status = "evaluated";
    await loadDashboard();
  } catch (reason) {
    error.value = messageOf(reason);
  } finally {
    busy.value = false;
  }
}

async function loadCodingBank() {
  const result = await fetchCodingQuestionBank();
  codingBank.value = result.questions;
}

async function beginCoding(
  selectionMode: "recommended" | "random" | "selected" = "recommended",
  questionId?: string,
) {
  busy.value = true;
  error.value = "";
  try {
    codingSession.value = await nextCodingQuestion({
      language: codingLanguage.value,
      excludeQuestionId:
        selectionMode === "selected"
          ? undefined
          : codingSession.value?.question.question_id,
      difficulty:
        selectionMode === "recommended"
          ? undefined
          : codingDifficulty.value || undefined,
      selectionMode,
      questionId,
    });
    code.value = codingSession.value.question.starter_code;
    codingSubmission.value = null;
    codingHint.value = null;
    solution.value = null;
  } catch (reason) {
    error.value = messageOf(reason);
  } finally {
    busy.value = false;
  }
}

async function startGaokaoProgramming() {
  busy.value = true;
  error.value = "";
  try {
    gaokaoSession.value = await nextGaokaoProgrammingQuestion(
      gaokaoSession.value?.question.question_id,
    );
    gaokaoFeedback.value = null;
    gaokaoAnswer.value = "";
    gaokaoChoice.value = "";
    gaokaoSubmissionMethod.value = "text";
    gaokaoFiles.value = [];
    gaokaoStartedAt.value = Date.now();
  } catch (reason) {
    error.value = messageOf(reason);
  } finally {
    busy.value = false;
  }
}

async function submitGaokao() {
  if (!gaokaoSession.value) return;
  const isImageSubmission =
    gaokaoSession.value.question.type !== "multiple_choice" &&
    gaokaoSubmissionMethod.value === "image";
  const answer =
    gaokaoSession.value.question.type === "multiple_choice"
      ? gaokaoChoice.value
      : gaokaoAnswer.value.trim();
  if (isImageSubmission ? !gaokaoFiles.value.length : !answer) return;
  busy.value = true;
  error.value = "";
  try {
    const elapsed = Math.max(
      1,
      Math.round((Date.now() - gaokaoStartedAt.value) / 1000),
    );
    gaokaoFeedback.value = isImageSubmission
      ? await submitGaokaoProgrammingImages(
          gaokaoSession.value.session_id,
          gaokaoFiles.value,
          elapsed,
          gaokaoAnswer.value.trim(),
        )
      : await submitGaokaoProgrammingAnswer(
          gaokaoSession.value.session_id,
          answer,
          elapsed,
        );
    await loadGaokaoHistory();
  } catch (reason) {
    error.value = messageOf(reason);
  } finally {
    busy.value = false;
  }
}

async function loadGaokaoHistory() {
  gaokaoHistory.value = await fetchGaokaoProgrammingHistory();
}

function onGaokaoFiles(event: Event) {
  const files = Array.from(
    (event.target as HTMLInputElement).files || [],
  ).slice(0, 3);
  gaokaoFiles.value = files;
  if (files.length) notify(`已选择 ${files.length} 张作答图片`);
}

function formatRecordTime(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("zh-CN");
}

async function runCode(action: "run" | "submit") {
  if (!codingSession.value || !code.value.trim()) return;
  busy.value = true;
  error.value = "";
  try {
    codingSubmission.value = await submitCodingAnswer(
      codingSession.value.session_id,
      code.value,
      action,
    );
    if (action === "submit") {
      await Promise.all([loadDashboard(), loadCodingHistory()]);
      if (codingSubmission.value.judge_result.status === "ACCEPTED")
        notify("提交通过，技能证据已更新");
    }
  } catch (reason) {
    error.value = messageOf(reason);
  } finally {
    busy.value = false;
  }
}

async function getHint() {
  if (!codingSession.value) return;
  busy.value = true;
  try {
    codingHint.value = await requestCodingHint(codingSession.value.session_id);
  } catch (reason) {
    error.value = messageOf(reason);
  } finally {
    busy.value = false;
  }
}

async function viewSolution() {
  if (
    !codingSession.value ||
    !window.confirm("查看完整解析后，本题不会记为独立完成。继续吗？")
  )
    return;
  busy.value = true;
  try {
    solution.value = await requestCodingSolution(
      codingSession.value.session_id,
    );
    await loadCodingHistory();
  } catch (reason) {
    error.value = messageOf(reason);
  } finally {
    busy.value = false;
  }
}

async function loadCodingHistory() {
  const result = await fetchCodingHistory();
  codingHistory.value = result.submissions;
}

function onFile(event: Event) {
  projectFile.value = (event.target as HTMLInputElement).files?.[0] || null;
}
</script>

<template>
  <div class="career-v1">
    <div v-if="loading" class="loading-state">
      <LoaderCircle class="spin" :size="28" />
      <strong>正在载入职业学习空间</strong>
      <span>同步岗位、项目题库与代码记录…</span>
    </div>

    <template v-else-if="dashboard">
      <header class="topbar">
        <div class="product-logo"><Route :size="21" /></div>
        <div class="product-name">
          <strong>职业教育</strong><span>Python Backend · V1</span>
        </div>
        <div class="topbar-spacer" />
        <div v-if="configured" class="job-chip">
          <Target :size="14" />{{ currentJob?.name }}
        </div>
        <button
          v-if="configured"
          class="ghost-icon"
          title="调整画像"
          @click="showProfile = true"
        >
          <Gauge :size="18" />
        </button>
      </header>

      <div v-if="error" class="error-bar">
        <CircleAlert :size="18" /><span>{{ error }}</span
        ><button @click="error = ''"><X :size="16" /></button>
      </div>

      <main v-if="!configured || showProfile" class="onboarding-page">
        <section class="onboarding-copy">
          <span class="kicker">第一步 · 选择标准岗位</span>
          <h1>先明确岗位，<br />再进入学习模式。</h1>
          <p>
            V1 首期只开放一条完整且可验证的 Python
            后端路径。高中生也可以按高考目标建立画像；岗位技能、项目实训、代码练习和程序编程共享同一份能力画像。
          </p>
          <article class="job-preview">
            <div><BriefcaseBusiness :size="22" /></div>
            <section>
              <small>当前开放岗位</small><strong>Python 后端开发工程师</strong>
              <p>Python · FastAPI · MySQL · Redis · 测试 · 工程实践</p>
            </section>
            <CheckCircle2 :size="20" />
          </article>
        </section>

        <form class="onboarding-form" @submit.prevent="saveOnboarding">
          <div class="form-heading">
            <div>
              <small>学习画像</small>
              <h2>
                {{ configured ? "调整基础信息" : "告诉我们你的当前情况" }}
              </h2>
            </div>
            <button
              v-if="configured"
              type="button"
              class="ghost-icon"
              @click="showProfile = false"
            >
              <X :size="17" />
            </button>
          </div>
          <div class="two-col">
            <label
              >当前身份<select v-model="onboarding.identity">
                <option value="high_school_student">高中生</option>
                <option value="vocational_student">高职 / 专科学生</option>
                <option value="undergraduate">本科学生</option>
                <option value="career_switcher">转行学习者</option>
              </select></label
            >
            <label
              >学历阶段<select v-model="onboarding.education_stage">
                <option value="high_school">高中</option>
                <option value="vocational">专科</option>
                <option value="undergraduate">本科</option>
                <option value="graduate">研究生</option>
                <option value="other">其他</option>
              </select></label
            >
          </div>
          <label
            >已有编程基础
            <div class="segmented">
              <button
                v-for="item in [
                  { v: 'beginner', l: '刚开始' },
                  { v: 'basic', l: '学过基础' },
                  { v: 'project', l: '做过项目' },
                ]"
                :key="item.v"
                type="button"
                :class="{ active: onboarding.programming_level === item.v }"
                @click="
                  onboarding.programming_level =
                    item.v as typeof onboarding.programming_level
                "
              >
                {{ item.l }}
              </button>
            </div></label
          >
          <div class="two-col">
            <label
              >每周学习时间<select v-model.number="onboarding.weekly_hours">
                <option :value="5">5 小时</option>
                <option :value="10">10 小时</option>
                <option :value="14">14 小时</option>
                <option :value="20">20 小时</option>
              </select></label
            >
            <label
              >期望周期<select v-model.number="onboarding.target_period_weeks">
                <option :value="8">8 周</option>
                <option :value="12">12 周</option>
                <option :value="16">16 周</option>
                <option :value="24">24 周</option>
              </select></label
            >
          </div>
          <label
            >学习目标<select v-model="onboarding.learning_goal">
              <option value="gaokao">高考编程备考</option>
              <option value="internship">准备实习</option>
              <option value="campus_recruitment">准备校招</option>
              <option value="career_change">转行就业</option>
            </select></label
          >
          <label>已接触语言<input value="Python" disabled /></label>
          <button class="primary" :disabled="busy">
            <LoaderCircle v-if="busy" class="spin" :size="17" /><ArrowRight
              v-else
              :size="17"
            />{{ configured ? "保存画像" : "进入职业学习空间" }}
          </button>
        </form>
      </main>

      <main v-else class="workspace-page">
        <section class="overview-strip">
          <div class="readiness">
            <strong>{{ dashboard.summary.readiness.percent }}</strong
            ><span>%<small>岗位准备度</small></span>
          </div>
          <div class="overview-copy">
            <small>{{ dashboard.summary.readiness.label }}</small
            ><strong>{{ dashboard.learning_plan.next_action }}</strong>
            <p>
              当前薄弱：{{ dashboard.learning_plan.weak_skills.join(" · ") }}
            </p>
          </div>
          <div class="overview-metrics">
            <span
              ><b>{{ dashboard.summary.project_count }}</b
              >项目评价</span
            ><span
              ><b>{{ dashboard.summary.coding_solved }}</b
              >代码题完成</span
            ><span
              ><b
                >{{
                  Math.round(dashboard.summary.independent_pass_rate * 100)
                }}%</b
              >独立通过</span
            >
          </div>
          <button class="evidence-button" @click="showEvidence = !showEvidence">
            能力与路线<ChevronDown
              :size="16"
              :class="{ rotate: showEvidence }"
            />
          </button>
        </section>

        <section v-if="showEvidence" class="evidence-drawer">
          <div class="skills">
            <article
              v-for="skill in dashboard.skill_profile"
              :key="skill.skill_id"
            >
              <div>
                <strong>{{ skill.name }}</strong
                ><span>{{ Math.round(skill.mastery * 100) }}%</span>
              </div>
              <i><b :style="{ width: `${skill.mastery * 100}%` }" /></i
              ><small
                >{{ skill.evidence_count }} 条证据 · {{ skill.domain }}</small
              >
            </article>
          </div>
          <div class="weekly-plan">
            <h3>本周优先任务</h3>
            <article
              v-for="item in dashboard.learning_plan.weekly_plan"
              :key="item.skill"
            >
              <span>{{ item.estimated_hours }}h</span>
              <div>
                <strong>{{ item.skill }}</strong>
                <p>{{ item.task }}</p>
                <small>验收：{{ item.acceptance }}</small>
              </div>
            </article>
          </div>
        </section>

        <section v-if="mode === 'CAREER'" class="mode-workspace career-mode">
          <div class="mode-heading">
            <div>
              <span class="kicker">CAREER MODE</span>
              <h2>岗位技能导师</h2>
              <p>
                像真实导师一样连续交流，并结合你的岗位目标、学习基础和技能证据回答。
              </p>
            </div>
            <div class="context-badge">
              <BriefcaseBusiness :size="16" /><span>大模型导师已连接</span
              ><strong>JOB_PY_BACKEND</strong>
            </div>
          </div>
          <div class="career-layout">
            <div class="career-conversation">
              <article class="agent-welcome">
                <div><Sparkles :size="18" /></div>
                <section>
                  <strong>你想解决哪个岗位学习问题？</strong>
                  <p>
                    可以直接提问、表达困惑或继续追问。只有确实需要时，我才会建议任务和路线。
                  </p>
                </section>
              </article>
              <div class="quick-prompts">
                <button
                  @click="
                    careerMessage = '我只会 Python 基础，下一步应该学什么？'
                  "
                >
                  下一步学什么</button
                ><button
                  @click="
                    careerMessage = 'FastAPI 应该学到什么程度才适合实习？'
                  "
                >
                  FastAPI 要求</button
                ><button
                  @click="careerMessage = 'MySQL 学习路线应该如何安排？'"
                >
                  MySQL 路线
                </button>
              </div>
              <div v-if="careerConversation.length" class="conversation-feed">
                <div
                  v-for="turn in careerConversation"
                  :key="turn.id"
                  class="conversation-turn"
                >
                  <div class="user-bubble">{{ turn.userMessage }}</div>
                  <article class="career-answer">
                    <div class="answer-meta">
                      <span class="answer-label">岗位导师</span>
                      <span
                        v-if="turn.result.generation_mode === 'llm'"
                        class="model-badge"
                      >
                        大模型回答
                      </span>
                    </div>
                    <p class="mentor-analysis">{{ turn.result.analysis }}</p>
                    <div class="answer-copy">{{ turn.result.answer }}</div>
                    <p v-if="turn.result.follow_up_question" class="follow-up">
                      {{ turn.result.follow_up_question }}
                    </p>
                  </article>
                </div>
              </div>
              <div v-if="busy" class="mentor-typing">
                <LoaderCircle class="spin" :size="15" />
                岗位导师正在结合你的情况思考…
              </div>
              <div class="chat-input">
                <textarea
                  v-model="careerMessage"
                  placeholder="可以自然追问，例如：那我每天只有一小时该怎么调整？"
                  @keydown.ctrl.enter="askCareer"
                /><button
                  :disabled="busy || !careerMessage.trim()"
                  @click="askCareer"
                >
                  <LoaderCircle v-if="busy" class="spin" :size="18" /><Send
                    v-else
                    :size="18"
                  />
                </button>
              </div>
            </div>
            <aside class="career-plan">
              <template v-if="careerResult?.task_breakdown.length"
                ><div class="aside-title">
                  <ClipboardCheck :size="18" /><strong>任务拆解</strong>
                </div>
                <article
                  v-for="(item, index) in careerResult.task_breakdown"
                  :key="item.task"
                >
                  <span>0{{ index + 1 }}</span>
                  <div>
                    <strong>{{ item.task }}</strong>
                    <p>{{ item.estimated_minutes }} 分钟</p>
                    <small>验收：{{ item.acceptance }}</small>
                  </div>
                </article>
                <button
                  class="secondary"
                  @click="selectMode(careerResult.recommended_mode)"
                >
                  进入推荐模式<ArrowRight :size="16" /></button></template
              ><template v-else
                ><div class="aside-empty">
                  <Route :size="28" /><strong>需要时再拆成行动任务</strong>
                  <p>普通交流不会被强行转换成学习清单。</p>
                </div></template
              >
            </aside>
          </div>
        </section>

        <section
          v-else-if="mode === 'PROJECT'"
          class="mode-workspace project-mode"
        >
          <div class="mode-heading">
            <div>
              <span class="kicker">PROJECT MODE</span>
              <h2>项目实训</h2>
              <p>
                只训练需求理解、方案设计、问题预判和工程表达；V1
                不要求上传大型代码仓库。
              </p>
            </div>
            <button
              v-if="projectSession"
              class="secondary"
              @click="
                projectSession = null;
                projectEvaluation = null;
              "
            >
              返回项目库
            </button>
          </div>

          <section class="project-mentor-chat">
            <header>
              <span><Sparkles :size="18" /></span>
              <div>
                <strong>项目实训导师</strong>
                <small>{{
                  projectSession
                    ? `已读取《${projectSession.title}》的需求与方案资料`
                    : "可先咨询项目选择、开发顺序与技术方案"
                }}</small>
              </div>
              <b>大模型在线</b>
            </header>
            <div class="project-chat-feed">
              <article
                v-if="!projectConversation.length"
                class="project-chat-welcome"
              >
                <MessageSquareText :size="23" />
                <div>
                  <strong>把项目问题直接发给我</strong>
                  <p>
                    例如：这个项目如何拆模块？数据库先设计哪些表？第一周该完成什么？
                  </p>
                </div>
              </article>
              <div
                v-for="turn in projectConversation"
                :key="turn.id"
                class="project-chat-turn"
              >
                <p v-if="turn.userMessage" class="project-user-bubble">
                  {{ turn.userMessage }}
                </p>
                <article class="project-agent-bubble">
                  <div>
                    <strong>项目导师</strong>
                    <small v-if="turn.result.generation_mode === 'llm'"
                      >大模型回答</small
                    >
                  </div>
                  <p>{{ turn.result.answer }}</p>
                  <ul v-if="turn.result.guiding_questions.length">
                    <li
                      v-for="question in turn.result.guiding_questions"
                      :key="question"
                    >
                      {{ question }}
                    </li>
                  </ul>
                  <p
                    v-if="turn.result.follow_up_question"
                    class="project-follow-up"
                  >
                    {{ turn.result.follow_up_question }}
                  </p>
                </article>
              </div>
              <div v-if="busy" class="mentor-typing">
                <LoaderCircle
                  class="spin"
                  :size="15"
                />项目导师正在阅读方案并思考…
              </div>
            </div>
            <div class="project-chat-input">
              <textarea
                v-model="projectMessage"
                placeholder="询问开发步骤、需求理解、架构、数据库、API 或测试方案…"
                @keydown.ctrl.enter="askProject"
              />
              <button
                :disabled="busy || !projectMessage.trim()"
                @click="askProject"
              >
                <Send :size="18" /><span>发送</span>
              </button>
            </div>
          </section>

          <div v-if="!projectSession" class="project-bank-wrap">
            <header class="bank-toolbar">
              <div>
                <strong>实训项目库</strong>
                <span>根据“已有编程基础”优先展示适合你的项目</span>
              </div>
              <button class="secondary batch-button" @click="shuffleProjects">
                <RotateCcw :size="15" />换一批
              </button>
            </header>
            <div class="project-bank">
              <article
                v-for="project in projectBatch"
                :key="project.project_id"
              >
                <div class="project-card-top">
                  <span>P{{ project.difficulty }}</span
                  ><small>
                    {{ project.difficulty === 1 ? "入门" : "进阶" }}
                    <b
                      v-if="project.difficulty === recommendedProjectDifficulty"
                      >适合当前基础</b
                    >
                  </small>
                </div>
                <h3>{{ project.title }}</h3>
                <p>{{ project.background }}</p>
                <div class="project-skills">
                  <span
                    v-for="skill in project.skill_ids.slice(0, 4)"
                    :key="skill"
                    >{{ skill.replaceAll("_", " ") }}</span
                  >
                </div>
                <ul>
                  <li
                    v-for="requirement in project.requirements.slice(0, 3)"
                    :key="requirement"
                  >
                    <Check :size="14" />{{ requirement }}
                  </li>
                </ul>
                <button
                  class="primary small"
                  :disabled="busy"
                  @click="chooseProject(project)"
                >
                  开始实训<ArrowRight :size="16" />
                </button>
              </article>
            </div>
          </div>

          <div v-else-if="!projectEvaluation" class="project-session">
            <aside class="document-panel">
              <div class="document-tabs">
                <button
                  :class="{ active: activeProjectDoc === 'requirement' }"
                  @click="activeProjectDoc = 'requirement'"
                >
                  <FileText :size="15" />需求文档</button
                ><button
                  :class="{ active: activeProjectDoc === 'problems' }"
                  @click="activeProjectDoc = 'problems'"
                >
                  <CircleAlert :size="15" />问题文档
                </button>
              </div>
              <pre>{{
                activeProjectDoc === "requirement"
                  ? projectSession.requirement_doc
                  : projectSession.problem_doc
              }}</pre>
              <button
                class="download-button"
                @click="downloadDocument(activeProjectDoc)"
              >
                <Download :size="15" />下载 {{ activeProjectDoc }}.md
              </button>
            </aside>
            <div class="answer-panel">
              <div class="answer-heading">
                <div>
                  <small>{{ projectSession.title }}</small>
                  <h3>提交你的方案</h3>
                </div>
                <span :class="projectSession.status">{{
                  projectSession.status === "submitted" ? "已提交" : "待作答"
                }}</span>
              </div>
              <div class="answer-fields">
                <label
                  >1. 整体开发方案<textarea
                    v-model="projectAnswer.development_plan"
                    placeholder="说明业务流程、开发步骤和验收方式…"
                  /></label
                ><label
                  >2. 技术选型与理由<textarea
                    v-model="projectAnswer.technology_selection"
                    placeholder="说明为什么选择这些技术以及取舍…"
                  /></label
                ><label
                  >3. 架构与模块拆解<textarea
                    v-model="projectAnswer.architecture_design"
                  /></label
                ><label
                  >4. 数据库设计<textarea
                    v-model="projectAnswer.database_design"
                  /></label
                ><label
                  >5. API 设计<textarea
                    v-model="projectAnswer.api_design"
                  /></label
                ><label
                  >6. 潜在问题解决方案<textarea
                    v-model="projectAnswer.problem_solution"
                  />
                </label>
              </div>
              <div class="project-actions">
                <label class="upload-control"
                  ><Upload :size="16" /><span>{{
                    projectFile?.name || "上传 .md / .txt / .docx"
                  }}</span
                  ><input
                    type="file"
                    accept=".md,.txt,.docx"
                    @change="onFile" /></label
                ><button
                  v-if="projectFile"
                  class="secondary"
                  :disabled="busy"
                  @click="uploadProject"
                >
                  上传并解析
                </button>
                <div class="action-spacer" />
                <button
                  v-if="projectSession.status !== 'submitted'"
                  class="primary small"
                  :disabled="busy || !answerReady"
                  @click="submitProject"
                >
                  保存文本回答</button
                ><button
                  v-else
                  class="primary small"
                  :disabled="busy"
                  @click="scoreProject"
                >
                  <Sparkles :size="16" />生成评价报告
                </button>
              </div>
            </div>
          </div>

          <div v-else class="evaluation-view">
            <aside class="score-card">
              <small>PROJECT SCORE</small
              ><strong>{{ projectEvaluation.total_score }}</strong
              ><span>/ 100</span>
              <p>评分只基于项目要求和你的回答。</p>
              <button class="primary small" @click="downloadDocument('report')">
                <Download :size="16" />下载 report.md
              </button>
            </aside>
            <div class="dimension-list">
              <article
                v-for="dimension in projectEvaluation.dimensions"
                :key="dimension.key"
              >
                <div class="dimension-head">
                  <strong>{{ dimension.name }}</strong
                  ><span>{{ dimension.score }}</span>
                </div>
                <i><b :style="{ width: `${dimension.score}%` }" /></i>
                <p><b>依据：</b>{{ dimension.evidence[0] }}</p>
                <p><b>建议：</b>{{ dimension.suggestions[0] }}</p>
              </article>
            </div>
          </div>
        </section>

        <section
          v-else-if="mode === 'CODING'"
          class="mode-workspace coding-mode"
        >
          <div class="mode-heading">
            <div>
              <span class="kicker">CODING MODE</span>
              <h2>代码练习</h2>
              <p>
                题目来自 MySQL
                中已审核的原创题库。运行只看测试；提交失败后才按次数逐级提示。
              </p>
            </div>
            <div class="coding-filter">
              <label>
                <span>编程语言</span>
                <select v-model="codingLanguage">
                  <option value="python">Python</option>
                </select> </label
              ><button
                class="primary small"
                :disabled="busy"
                @click="beginCoding('random')"
              >
                {{ codingSession ? "换一道题" : "开始练习" }}
              </button>
            </div>
          </div>

          <section class="coding-bank-browser">
            <header class="bank-toolbar">
              <div>
                <strong>选择练习题</strong>
                <span>
                  当前画像推荐：{{
                    dashboard.profile.programming_level === "beginner"
                      ? "简单"
                      : dashboard.profile.programming_level === "basic"
                        ? "中等"
                        : "困难"
                  }}
                </span>
              </div>
              <div class="difficulty-tabs">
                <button
                  v-for="item in [
                    { value: 0, label: '全部' },
                    { value: 1, label: '简单' },
                    { value: 2, label: '中等' },
                    { value: 3, label: '困难' },
                  ]"
                  :key="item.value"
                  :class="{ active: codingDifficulty === item.value }"
                  @click="codingDifficulty = item.value"
                >
                  {{ item.label }}
                </button>
              </div>
            </header>
            <div class="coding-question-list">
              <button
                v-for="question in filteredCodingBank"
                :key="question.question_id"
                :class="{
                  active:
                    codingSession?.question.question_id ===
                    question.question_id,
                }"
                :disabled="busy"
                @click="beginCoding('selected', question.question_id)"
              >
                <span :class="`level-${question.difficulty}`">{{
                  question.difficulty_label
                }}</span>
                <strong>{{ question.title }}</strong>
                <small>{{ question.category }}</small>
                <CheckCircle2 v-if="question.completed" :size="15" />
              </button>
            </div>
          </section>

          <div v-if="!codingSession" class="coding-empty">
            <Code2 :size="34" />
            <h3>准备一道与岗位相关的题</h3>
            <p>
              系统会避开已完成题，并根据技能证据推荐。完整答案与隐藏测试不会出现在普通接口中。
            </p>
            <button class="primary" @click="beginCoding('recommended')">
              <Play :size="17" />获取推荐题目
            </button>
          </div>
          <div v-else class="coding-layout">
            <aside class="question-panel">
              <div class="question-meta">
                <span>{{ codingSession.question.category }}</span
                ><small>{{ codingSession.question.difficulty_label }}</small>
              </div>
              <h3>{{ codingSession.question.title }}</h3>
              <p>{{ codingSession.question.description }}</p>
              <h4>示例</h4>
              <article
                v-for="example in codingSession.question.examples"
                :key="example.input"
                class="example"
              >
                <span>输入</span><code>{{ example.input }}</code
                ><span>输出</span><code>{{ example.output }}</code>
              </article>
              <h4>约束</h4>
              <ul>
                <li
                  v-for="item in codingSession.question.constraints"
                  :key="item"
                >
                  {{ item }}
                </li>
              </ul>
            </aside>
            <div class="code-panel">
              <header>
                <span><Code2 :size="15" />solution.py</span
                ><button
                  @click="code = codingSession?.question.starter_code || ''"
                >
                  <RotateCcw :size="14" />重置
                </button>
              </header>
              <textarea v-model="code" spellcheck="false" />
              <footer>
                <button
                  class="secondary"
                  :disabled="busy"
                  @click="runCode('run')"
                >
                  <Play :size="15" />运行</button
                ><button
                  class="primary small"
                  :disabled="busy"
                  @click="runCode('submit')"
                >
                  <Send :size="15" />提交判题
                </button>
              </footer>
            </div>
            <aside class="judge-panel">
              <template v-if="codingSubmission"
                ><div
                  class="judge-title"
                  :class="{
                    accepted:
                      codingSubmission.judge_result.status === 'ACCEPTED',
                  }"
                >
                  <CheckCircle2
                    v-if="codingSubmission.judge_result.status === 'ACCEPTED'"
                    :size="23"
                  /><CircleAlert v-else :size="23" />
                  <div>
                    <small>JUDGE RESULT</small
                    ><strong>{{ codingSubmission.judge_result.status }}</strong>
                  </div>
                </div>
                <div class="judge-numbers">
                  <span
                    ><b>{{ codingSubmission.judge_result.passed }}</b
                    >/{{ codingSubmission.judge_result.total }} 测试</span
                  ><span
                    ><b>{{ codingSubmission.judge_result.runtime_ms }}</b
                    >ms</span
                  >
                </div>
                <p>{{ codingSubmission.feedback.analysis }}</p>
                <div v-if="codingSubmission.feedback.hint" class="hint">
                  <strong
                    >Hint
                    {{ codingSubmission.feedback.current_hint_level }}</strong
                  >
                  <p>{{ codingSubmission.feedback.hint }}</p>
                </div></template
              ><template v-else
                ><div class="judge-empty">
                  <Play :size="25" /><strong>等待运行</strong>
                  <p>测试结果是事实，AI 只负责解释。</p>
                </div></template
              >
              <div v-if="codingHint" class="hint manual">
                <strong>Hint {{ codingHint.hint_level }}</strong>
                <p>{{ codingHint.hint }}</p>
              </div>
              <div v-if="solution" class="solution">
                <strong>完整解析</strong>
                <pre>{{ solution.reference_solution }}</pre>
                <p>{{ solution.solution_explanation }}</p>
                <small>{{ solution.mastery_notice }}</small>
              </div>
              <div class="judge-actions">
                <button
                  class="hint-button"
                  :disabled="
                    busy ||
                    !codingSubmission ||
                    codingSubmission.judge_result.status === 'ACCEPTED' ||
                    codingSubmission.action === 'run'
                  "
                  @click="getHint"
                >
                  <Lightbulb :size="15" />{{
                    codingHint ? "更强提示" : "失败后查看提示"
                  }}</button
                ><button
                  class="solution-button"
                  :disabled="busy"
                  @click="viewSolution"
                >
                  查看完整解析
                </button>
              </div>
            </aside>
          </div>

          <details class="history-panel">
            <summary>
              <History :size="16" />提交历史（{{ codingHistory.length }}）
            </summary>
            <div>
              <article
                v-for="item in codingHistory.slice(0, 10)"
                :key="item.submission_id"
              >
                <span :class="item.status">{{ item.status }}</span
                ><strong>{{ item.judge_result.status }}</strong
                ><small
                  >第 {{ item.attempt_number }} 次 ·
                  {{ item.judge_result.passed }}/{{
                    item.judge_result.total
                  }}
                  测试</small
                >
              </article>
              <p v-if="!codingHistory.length">暂无提交记录</p>
            </div>
          </details>
        </section>

        <section v-else class="mode-workspace gaokao-mode">
          <div class="mode-heading gaokao-heading">
            <div>
              <span class="kicker">GAOKAO PROGRAMMING</span>
              <h2>程序编程</h2>
              <p>
                面向高考生的编程专项。题目仅取自知识库中的真实技术高考试题，并保留原始试卷来源。
              </p>
            </div>
            <div class="gaokao-policy">
              <ShieldCheck :size="18" />
              <span><b>引导式诊断</b>模型分析问题并给提示，不直接公布答案</span>
            </div>
          </div>

          <div v-if="!gaokaoSession" class="gaokao-start">
            <div class="gaokao-start-icon"><BookOpenText :size="30" /></div>
            <span>真实高考题 · 随机抽取</span>
            <h3>开始一轮高考编程专项练习</h3>
            <p>
              当前知识库收录的是浙江省技术选考真题。系统会如实标注年份、试卷及原题号，不会把省级试题误标为全国卷。
            </p>
            <button
              class="primary"
              :disabled="busy"
              @click="startGaokaoProgramming"
            >
              <Play :size="17" />随机抽取真题
            </button>
          </div>

          <div v-else class="gaokao-practice">
            <header class="gaokao-question-meta">
              <div>
                <span>高考真题</span>
                <b>{{ gaokaoSession.question.difficulty_label }}</b>
              </div>
              <small>
                {{ gaokaoSession.question.source.source_title }} · 原题第
                {{ gaokaoSession.question.source.original_number }} 题
              </small>
              <button
                class="secondary"
                :disabled="busy"
                @click="startGaokaoProgramming"
              >
                <RotateCcw :size="15" />换一道真题
              </button>
            </header>
            <div class="gaokao-grid">
              <article class="gaokao-question">
                <div
                  class="gaokao-stem"
                  v-html="
                    resolveCareerAssetHtml(gaokaoSession.question.stem_html)
                  "
                />
                <div
                  v-if="gaokaoSession.question.type === 'multiple_choice'"
                  class="gaokao-options"
                >
                  <button
                    v-for="option in gaokaoSession.question.options"
                    :key="option.key"
                    :class="{ active: gaokaoChoice === option.key }"
                    @click="gaokaoChoice = option.key"
                  >
                    <b>{{ option.key }}</b>
                    <span
                      v-html="resolveCareerAssetHtml(option.content_html)"
                    />
                  </button>
                </div>
                <div v-else class="gaokao-answer-area">
                  <div class="submission-method-tabs">
                    <button
                      :class="{ active: gaokaoSubmissionMethod === 'text' }"
                      @click="gaokaoSubmissionMethod = 'text'"
                    >
                      对话框输入
                    </button>
                    <button
                      :class="{ active: gaokaoSubmissionMethod === 'image' }"
                      @click="gaokaoSubmissionMethod = 'image'"
                    >
                      上传手写作答
                    </button>
                  </div>
                  <label
                    v-if="gaokaoSubmissionMethod === 'text'"
                    class="gaokao-answer"
                  >
                    <span>写下你的作答与思路</span>
                    <textarea
                      v-model="gaokaoAnswer"
                      placeholder="请说明关键步骤、变量变化或判断依据；模型会诊断思路，但不会直接给出答案。"
                    />
                  </label>
                  <div v-else class="gaokao-image-upload">
                    <label>
                      <Upload :size="24" />
                      <strong>上传题目作答图片</strong>
                      <span
                        >支持 1—3 张 JPG、PNG 或 WEBP，模型会直接阅读图片</span
                      >
                      <input
                        type="file"
                        accept="image/jpeg,image/png,image/webp"
                        multiple
                        @change="onGaokaoFiles"
                      />
                    </label>
                    <div v-if="gaokaoFiles.length" class="selected-images">
                      <span v-for="file in gaokaoFiles" :key="file.name">
                        {{ file.name }}
                      </span>
                    </div>
                    <textarea
                      v-model="gaokaoAnswer"
                      placeholder="可选：补充图片中不清楚的文字或说明答题位置…"
                    />
                  </div>
                </div>
                <button
                  class="primary gaokao-submit"
                  :disabled="
                    busy ||
                    (gaokaoSession.question.type === 'multiple_choice'
                      ? !gaokaoChoice
                      : gaokaoSubmissionMethod === 'image'
                        ? !gaokaoFiles.length
                        : !gaokaoAnswer.trim())
                  "
                  @click="submitGaokao"
                >
                  <LoaderCircle v-if="busy" class="spin" :size="17" />
                  <Send v-else :size="17" />提交并诊断
                </button>
              </article>

              <aside class="gaokao-feedback">
                <template v-if="gaokaoFeedback">
                  <div class="gaokao-score">
                    <span>本题评分</span>
                    <strong>{{ gaokaoFeedback.score }}</strong>
                    <small>/ {{ gaokaoFeedback.max_score }}</small>
                    <b>{{
                      gaokaoFeedback.submission_method === "image"
                        ? "图片作答"
                        : "文字作答"
                    }}</b>
                  </div>
                  <section>
                    <h4><Sparkles :size="15" />问题诊断</h4>
                    <p>{{ gaokaoFeedback.diagnosis }}</p>
                  </section>
                  <section v-if="gaokaoFeedback.issues.length">
                    <h4><CircleAlert :size="15" />需要关注</h4>
                    <ul>
                      <li v-for="item in gaokaoFeedback.issues" :key="item">
                        {{ item }}
                      </li>
                    </ul>
                  </section>
                  <section class="gaokao-hints">
                    <h4><Lightbulb :size="15" />思路提示</h4>
                    <ul>
                      <li v-for="item in gaokaoFeedback.hints" :key="item">
                        {{ item }}
                      </li>
                    </ul>
                  </section>
                  <p class="no-answer-note">
                    本模块不会直接展示标准答案或完整代码。
                  </p>
                </template>
                <div v-else class="gaokao-feedback-empty">
                  <Sparkles :size="27" />
                  <strong>等待你的作答</strong>
                  <p>
                    提交后，大模型会结合本题评分依据分析薄弱点，并只给方向性提示。
                  </p>
                </div>
              </aside>
            </div>
            <footer class="practice-redirect">
              <Code2 :size="19" />
              <div>
                <strong>想刷更多非高考编程题？</strong>
                <span
                  >前往代码练习，可按简单、中等、困难自由选题或随机练习。</span
                >
              </div>
              <button class="secondary" @click="selectMode('CODING')">
                前往代码练习<ArrowRight :size="15" />
              </button>
            </footer>
          </div>

          <details
            class="gaokao-history"
            :open="Boolean(gaokaoHistory.total_submissions)"
          >
            <summary>
              <History :size="18" />
              <strong>程序编程提交记录</strong>
              <span
                >{{ gaokaoHistory.total_questions }} 道题 ·
                {{ gaokaoHistory.total_submissions }} 次提交</span
              >
            </summary>
            <div
              v-if="gaokaoHistory.questions.length"
              class="gaokao-history-list"
            >
              <article
                v-for="group in gaokaoHistory.questions"
                :key="group.question_id"
                class="gaokao-history-question"
              >
                <header>
                  <div>
                    <span>高考真题</span>
                    <strong>
                      {{ group.question.source.source_title }} · 原题第
                      {{ group.question.source.original_number }} 题
                    </strong>
                  </div>
                  <small>{{ group.submissions.length }} 次作答</small>
                </header>
                <div class="history-submissions">
                  <section
                    v-for="submission in group.submissions"
                    :key="submission.submission_id"
                  >
                    <div class="history-score">
                      <b>{{ submission.score }}</b>
                      <span>/ {{ submission.max_score }}</span>
                    </div>
                    <div>
                      <strong>{{
                        submission.submission_method === "image"
                          ? `图片作答 · ${submission.image_count} 张`
                          : "文字作答"
                      }}</strong>
                      <p>{{ submission.diagnosis }}</p>
                      <small>
                        {{ formatRecordTime(submission.created_at) }} · 用时
                        {{ submission.response_time_seconds }} 秒
                      </small>
                    </div>
                  </section>
                </div>
              </article>
            </div>
            <p v-else class="gaokao-history-empty">
              完成并提交一道真题后，记录会按具体题目显示在这里。
            </p>
          </details>
        </section>
      </main>
    </template>

    <div v-if="toast" class="toast"><CheckCircle2 :size="17" />{{ toast }}</div>
  </div>
</template>

<style scoped>
.career-v1 {
  --ink: #172b4d;
  --muted: #64748b;
  --line: #dfe7f2;
  --paper: #fff;
  --green: #155eef;
  --soft: #eef4ff;
  min-height: calc(100vh - 64px);
  background: #f4f7fc;
  color: var(--ink);
  font-family: Inter, "PingFang SC", "Microsoft YaHei", sans-serif;
}
.topbar {
  height: 68px;
  padding: 0 30px;
  display: flex;
  align-items: center;
  gap: 11px;
  background: #fff;
  border-bottom: 1px solid var(--line);
}
.product-logo {
  width: 39px;
  height: 39px;
  border-radius: 11px;
  display: grid;
  place-items: center;
  background: #103d8f;
  color: #fff;
}
.product-name {
  display: flex;
  flex-direction: column;
}
.product-name strong {
  font-size: 14px;
}
.product-name span {
  font-size: 10px;
  color: var(--muted);
  letter-spacing: 0.07em;
}
.topbar-spacer {
  flex: 1;
}
.job-chip {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 10px;
  border-radius: 999px;
  background: var(--soft);
  color: var(--green);
  font-size: 11px;
}
.ghost-icon {
  width: 35px;
  height: 35px;
  display: grid;
  place-items: center;
  border: 1px solid var(--line);
  border-radius: 9px;
  background: #fff;
  color: #56605c;
  cursor: pointer;
}
.error-bar {
  max-width: 1200px;
  margin: 14px auto 0;
  padding: 11px 13px;
  border: 1px solid #f3cccc;
  border-radius: 10px;
  background: #fff6f6;
  color: #a33b3b;
  display: flex;
  align-items: center;
  gap: 9px;
  font-size: 12px;
}
.error-bar span {
  flex: 1;
}
.error-bar button {
  border: 0;
  background: none;
  color: inherit;
}
.loading-state {
  min-height: 70vh;
  display: grid;
  place-items: center;
  align-content: center;
  gap: 9px;
  color: var(--muted);
}
.loading-state span {
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
.onboarding-page {
  max-width: 1050px;
  margin: auto;
  padding: 55px 24px 80px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 65px;
  align-items: center;
}
.kicker {
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.12em;
  color: var(--green);
}
.onboarding-copy h1 {
  font-size: 43px;
  line-height: 1.17;
  letter-spacing: -0.035em;
  margin: 14px 0;
}
.onboarding-copy > p {
  font-size: 14px;
  line-height: 1.8;
  color: var(--muted);
}
.job-preview {
  margin-top: 28px;
  padding: 17px;
  border: 1px solid #d9e7e1;
  border-radius: 14px;
  background: #f8fcfa;
  display: flex;
  align-items: center;
  gap: 12px;
}
.job-preview > div {
  width: 38px;
  height: 38px;
  display: grid;
  place-items: center;
  border-radius: 10px;
  background: #e4f3ed;
  color: var(--green);
}
.job-preview section {
  display: flex;
  flex-direction: column;
  flex: 1;
}
.job-preview small {
  font-size: 9px;
  color: var(--muted);
}
.job-preview strong {
  font-size: 13px;
}
.job-preview p {
  font-size: 9px;
  color: var(--muted);
  margin: 3px 0;
}
.job-preview > svg {
  color: var(--green);
}
.onboarding-form {
  padding: 27px;
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 18px;
  box-shadow: 0 16px 45px rgba(30, 45, 39, 0.07);
  display: grid;
  gap: 16px;
}
.form-heading {
  display: flex;
  justify-content: space-between;
}
.form-heading small {
  color: var(--green);
  font-size: 9px;
}
.form-heading h2 {
  font-size: 19px;
  margin: 4px 0;
}
.onboarding-form label {
  display: grid;
  gap: 7px;
  font-size: 11px;
  font-weight: 650;
  color: #515a56;
}
.onboarding-form select,
.onboarding-form input {
  height: 41px;
  border: 1px solid #d9dddb;
  border-radius: 9px;
  background: #fff;
  padding: 0 10px;
  color: var(--ink);
}
.two-col {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 11px;
}
.segmented {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 7px;
}
.segmented button {
  height: 39px;
  border: 1px solid var(--line);
  border-radius: 9px;
  background: #fafbfa;
  color: var(--muted);
  cursor: pointer;
}
.segmented button.active {
  border-color: var(--green);
  background: #eef4ff;
  color: var(--green);
  font-weight: 700;
}
.primary,
.secondary {
  min-height: 43px;
  padding: 0 16px;
  border-radius: 9px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  font-weight: 700;
  cursor: pointer;
}
.primary {
  border: 0;
  background: var(--green);
  color: #fff;
}
.primary.small {
  min-height: 37px;
  width: max-content;
  font-size: 11px;
}
.secondary {
  border: 1px solid var(--line);
  background: #fff;
  color: #505a56;
}
.primary:disabled,
.secondary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.workspace-page {
  max-width: 1220px;
  margin: auto;
  padding: 25px 25px 70px;
}
.overview-strip {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 17px;
}
.readiness {
  display: flex;
  align-items: baseline;
  min-width: 78px;
}
.readiness strong {
  font-size: 35px;
  letter-spacing: -0.05em;
}
.readiness > span {
  font-size: 12px;
  color: var(--green);
}
.readiness small {
  display: block;
  color: var(--muted);
  font-size: 8px;
}
.overview-copy {
  display: flex;
  flex-direction: column;
}
.overview-copy small {
  color: var(--green);
  font-size: 9px;
}
.overview-copy strong {
  font-size: 14px;
}
.overview-copy p {
  margin: 3px 0 0;
  color: var(--muted);
  font-size: 10px;
}
.overview-metrics {
  display: flex;
  gap: 7px;
  margin-left: auto;
}
.overview-metrics span {
  min-width: 76px;
  padding: 8px 10px;
  border: 1px solid var(--line);
  border-radius: 9px;
  background: #fff;
  font-size: 9px;
  color: var(--muted);
}
.overview-metrics b {
  display: block;
  color: var(--ink);
  font-size: 15px;
}
.evidence-button {
  border: 0;
  background: none;
  display: flex;
  align-items: center;
  gap: 5px;
  color: var(--muted);
  font-size: 10px;
  cursor: pointer;
}
.evidence-button svg {
  transition: 0.2s;
}
.evidence-button svg.rotate {
  transform: rotate(180deg);
}
.evidence-drawer {
  margin: -3px 0 17px;
  padding: 17px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: #fff;
  display: grid;
  grid-template-columns: 1.25fr 0.75fr;
  gap: 24px;
}
.skills {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
}
.skills article > div {
  display: flex;
  justify-content: space-between;
  font-size: 10px;
}
.skills i {
  height: 4px;
  display: block;
  background: #ebeeec;
  border-radius: 4px;
  margin: 5px 0;
}
.skills i b {
  display: block;
  height: 100%;
  border-radius: 4px;
  background: var(--green);
}
.skills small {
  font-size: 8px;
  color: #909793;
}
.weekly-plan h3 {
  font-size: 11px;
  margin: 0 0 8px;
}
.weekly-plan article {
  display: flex;
  gap: 9px;
  padding: 8px 0;
  border-top: 1px solid #edf0ee;
}
.weekly-plan article > span {
  font-size: 10px;
  color: var(--green);
}
.weekly-plan article div {
  display: flex;
  flex-direction: column;
}
.weekly-plan strong {
  font-size: 10px;
}
.weekly-plan p,
.weekly-plan small {
  font-size: 8px;
  color: var(--muted);
  margin: 2px 0;
}
.mode-nav {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 9px;
  margin-bottom: 12px;
}
.mode-nav button {
  height: 64px;
  padding: 0 16px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: #fff;
  display: flex;
  align-items: center;
  gap: 10px;
  text-align: left;
  color: #65706c;
  cursor: pointer;
}
.mode-nav button > div {
  display: flex;
  flex-direction: column;
  flex: 1;
}
.mode-nav strong {
  font-size: 12px;
  color: #3f4845;
}
.mode-nav span {
  font-size: 9px;
  color: #8a928f;
}
.mode-nav button.active {
  border-color: #83bba7;
  background: #f2f9f6;
  color: var(--green);
  box-shadow: inset 0 -2px var(--green);
}
.mode-nav button.active strong {
  color: var(--green);
}
.mode-workspace {
  border: 1px solid var(--line);
  border-radius: 15px;
  background: #fff;
  overflow: hidden;
}
.mode-heading {
  min-height: 85px;
  padding: 19px 22px;
  display: flex;
  align-items: center;
  border-bottom: 1px solid var(--line);
}
.mode-heading > div:first-child {
  flex: 1;
}
.mode-heading h2 {
  font-size: 19px;
  margin: 4px 0;
}
.mode-heading p {
  margin: 0;
  color: var(--muted);
  font-size: 10px;
}
.context-badge {
  padding: 9px 11px;
  border: 1px solid #d8e5fa;
  border-radius: 9px;
  background: #f7faff;
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 1px 7px;
  align-items: center;
}
.context-badge svg {
  grid-row: 1/3;
  color: var(--green);
}
.context-badge span {
  font-size: 8px;
  color: var(--muted);
}
.context-badge strong {
  font-size: 9px;
  color: var(--green);
}
.career-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 300px;
  min-height: 650px;
}
.career-conversation {
  min-width: 0;
  padding: 24px;
  border-right: 1px solid var(--line);
  display: flex;
  flex-direction: column;
}
.agent-welcome {
  display: flex;
  gap: 11px;
}
.agent-welcome > div {
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  border-radius: 10px;
  background: #eef4ff;
  color: var(--green);
}
.agent-welcome section {
  display: flex;
  flex-direction: column;
}
.agent-welcome strong {
  font-size: 13px;
}
.agent-welcome p {
  max-width: 600px;
  font-size: 11px;
  line-height: 1.6;
  color: var(--muted);
}
.quick-prompts {
  display: flex;
  gap: 7px;
  margin: 18px 0 9px;
}
.quick-prompts button {
  padding: 7px 9px;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: #fff;
  color: #68716d;
  font-size: 9px;
  cursor: pointer;
}
.conversation-feed {
  flex: 1;
  min-height: 250px;
  max-height: 560px;
  overflow-y: auto;
  margin: 12px -5px 14px 0;
  padding-right: 7px;
}
.conversation-turn + .conversation-turn {
  margin-top: 20px;
}
.user-bubble {
  width: fit-content;
  max-width: 78%;
  margin-left: auto;
  padding: 10px 13px;
  border-radius: 12px 12px 3px 12px;
  background: var(--green);
  color: #fff;
  font-size: 11px;
  line-height: 1.6;
}
.conversation-turn .career-answer {
  margin: 8px 42px 0 0;
  border-radius: 3px 12px 12px 12px;
}
.answer-meta {
  display: flex;
  align-items: center;
  gap: 7px;
}
.model-badge {
  padding: 3px 6px;
  border-radius: 999px;
  background: #eaf1ff;
  color: var(--green);
  font-size: 7px;
}
.mentor-analysis {
  color: #77817d !important;
}
.answer-copy {
  margin-top: 10px;
  white-space: pre-wrap;
  color: #3f4945;
  font-size: 11px;
  line-height: 1.75;
}
.follow-up {
  margin-top: 12px !important;
  padding-top: 10px;
  border-top: 1px solid var(--line);
  color: var(--green) !important;
  font-weight: 650;
}
.mentor-typing {
  width: fit-content;
  margin: 10px 0;
  padding: 8px 11px;
  border-radius: 9px;
  background: #f3f7ff;
  display: flex;
  align-items: center;
  gap: 7px;
  color: var(--muted);
  font-size: 9px;
}
.chat-input {
  display: flex;
  gap: 8px;
  padding: 8px;
  border: 1px solid #d8ddda;
  border-radius: 11px;
  margin-top: auto;
  background: #fff;
  box-shadow: 0 8px 25px rgba(21, 94, 239, 0.08);
}
.chat-input textarea {
  flex: 1;
  min-height: 65px;
  border: 0;
  resize: none;
  outline: 0;
  font: inherit;
  font-size: 12px;
}
.chat-input button {
  width: 39px;
  height: 39px;
  border: 0;
  border-radius: 9px;
  background: var(--green);
  color: #fff;
  display: grid;
  place-items: center;
  align-self: end;
}
.career-answer {
  margin-top: 18px;
  padding: 17px;
  border-radius: 11px;
  background: #f7faff;
}
.answer-label {
  font-size: 8px;
  color: var(--green);
  font-weight: 800;
}
.career-answer h3 {
  font-size: 11px;
  margin: 14px 0 4px;
}
.career-answer p {
  font-size: 11px;
  line-height: 1.7;
  color: #4f5955;
  margin: 5px 0;
}
.career-plan {
  padding: 20px;
  background: #f8faff;
}
.aside-title {
  display: flex;
  align-items: center;
  gap: 7px;
  margin-bottom: 10px;
}
.aside-title strong {
  font-size: 12px;
}
.career-plan article {
  padding: 10px 0;
  display: flex;
  gap: 9px;
  border-top: 1px solid var(--line);
}
.career-plan article > span {
  font-size: 9px;
  color: var(--green);
}
.career-plan article div {
  display: flex;
  flex-direction: column;
}
.career-plan article strong {
  font-size: 10px;
}
.career-plan article p,
.career-plan article small {
  font-size: 8px;
  color: var(--muted);
  margin: 2px 0;
}
.career-plan .secondary {
  margin-top: 14px;
  width: 100%;
  font-size: 10px;
}
.aside-empty {
  height: 100%;
  display: grid;
  place-items: center;
  align-content: center;
  text-align: center;
  color: #9ba19e;
}
.aside-empty strong {
  color: #616966;
  margin: 9px 0;
}
.aside-empty p {
  font-size: 9px;
  line-height: 1.5;
  max-width: 180px;
}
.project-bank-wrap {
  padding: 20px;
}
.bank-toolbar {
  display: flex;
  align-items: center;
  gap: 14px;
  justify-content: space-between;
}
.bank-toolbar > div:first-child {
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.bank-toolbar strong {
  font-size: 12px;
}
.bank-toolbar span {
  color: var(--muted);
  font-size: 9px;
}
.batch-button {
  min-height: 35px;
  font-size: 9px;
}
.project-bank {
  padding-top: 13px;
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}
.project-mentor-chat {
  margin: 20px;
  overflow: hidden;
  border: 1px solid #cfddf4;
  border-radius: 14px;
  background: #fff;
  box-shadow: 0 12px 30px rgba(21, 94, 239, 0.07);
}
.project-mentor-chat > header {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 58px;
  padding: 10px 15px;
  border-bottom: 1px solid var(--line);
  background: #f7faff;
}
.project-mentor-chat > header > span {
  display: grid;
  width: 34px;
  height: 34px;
  place-items: center;
  color: var(--green);
  background: #e8f0ff;
  border-radius: 10px;
}
.project-mentor-chat > header > div {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  gap: 2px;
}
.project-mentor-chat > header strong {
  font-size: 12px;
}
.project-mentor-chat > header small {
  overflow: hidden;
  color: var(--muted);
  font-size: 9px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.project-mentor-chat > header > b {
  padding: 5px 8px;
  color: #155eef;
  background: #eaf1ff;
  border-radius: 999px;
  font-size: 8px;
}
.project-chat-feed {
  min-height: 235px;
  max-height: 480px;
  overflow-y: auto;
  padding: 17px;
  background: #fbfdff;
}
.project-chat-welcome {
  display: flex;
  min-height: 190px;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: #7890b5;
  text-align: left;
}
.project-chat-welcome strong {
  color: var(--ink);
  font-size: 12px;
}
.project-chat-welcome p {
  margin: 4px 0 0;
  color: var(--muted);
  font-size: 10px;
}
.project-chat-turn + .project-chat-turn {
  margin-top: 18px;
}
.project-user-bubble {
  width: fit-content;
  max-width: 76%;
  margin: 0 0 9px auto;
  padding: 10px 13px;
  color: #fff;
  background: #155eef;
  border-radius: 12px 12px 3px 12px;
  font-size: 11px;
  line-height: 1.65;
}
.project-agent-bubble {
  max-width: 88%;
  padding: 14px 16px;
  border: 1px solid #e1e9f5;
  background: #fff;
  border-radius: 3px 12px 12px;
}
.project-agent-bubble > div {
  display: flex;
  align-items: center;
  gap: 7px;
}
.project-agent-bubble > div strong {
  color: #174b9d;
  font-size: 10px;
}
.project-agent-bubble > div small {
  padding: 3px 6px;
  color: #155eef;
  background: #eaf1ff;
  border-radius: 999px;
  font-size: 7px;
}
.project-agent-bubble > p {
  margin: 9px 0 0;
  color: #334764;
  font-size: 11px;
  line-height: 1.75;
  white-space: pre-wrap;
}
.project-agent-bubble ul {
  display: grid;
  gap: 5px;
  margin: 11px 0 0;
  padding: 10px 10px 10px 27px;
  color: #475f80;
  background: #f4f8ff;
  border-radius: 8px;
  font-size: 10px;
}
.project-agent-bubble .project-follow-up {
  color: #155eef;
  font-weight: 650;
}
.project-chat-input {
  display: flex;
  gap: 9px;
  padding: 12px;
  border-top: 1px solid var(--line);
  background: #fff;
}
.project-chat-input textarea {
  min-height: 72px;
  flex: 1;
  resize: vertical;
  padding: 10px 12px;
  border: 1px solid #d6e0ee;
  border-radius: 9px;
  outline: none;
  font: inherit;
  font-size: 11px;
}
.project-chat-input textarea:focus {
  border-color: #86adf7;
  box-shadow: 0 0 0 3px rgba(21, 94, 239, 0.08);
}
.project-chat-input button {
  min-width: 88px;
  align-self: stretch;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  color: #fff;
  border: 0;
  background: #155eef;
  border-radius: 9px;
}
.project-chat-input button:disabled {
  opacity: 0.5;
}
.project-bank > article {
  padding: 17px;
  border: 1px solid var(--line);
  border-radius: 12px;
  display: flex;
  flex-direction: column;
}
.project-card-top {
  display: flex;
  justify-content: space-between;
}
.project-card-top span {
  padding: 4px 7px;
  border-radius: 6px;
  background: #eaf1ff;
  color: var(--green);
  font-size: 9px;
}
.project-card-top small {
  font-size: 9px;
  color: var(--muted);
}
.project-card-top small b {
  margin-left: 5px;
  padding: 3px 5px;
  border-radius: 999px;
  background: #eaf1ff;
  color: var(--green);
  font-size: 7px;
}
.project-bank h3 {
  font-size: 14px;
  margin: 13px 0 5px;
}
.project-bank p {
  font-size: 10px;
  line-height: 1.6;
  color: var(--muted);
  min-height: 48px;
}
.project-skills {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}
.project-skills span {
  padding: 4px 5px;
  border-radius: 5px;
  background: #f1f3f2;
  font-size: 7px;
  color: #66706c;
}
.project-bank ul {
  list-style: none;
  padding: 11px 0;
  margin: 0;
  display: grid;
  gap: 5px;
}
.project-bank li {
  display: flex;
  gap: 5px;
  font-size: 9px;
  color: #56605c;
}
.project-bank li svg {
  color: var(--green);
  flex: none;
}
.project-bank .primary {
  margin-top: auto;
}
.project-session {
  display: grid;
  grid-template-columns: 380px 1fr;
  min-height: 590px;
}
.document-panel {
  border-right: 1px solid var(--line);
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.document-tabs {
  height: 45px;
  display: flex;
  border-bottom: 1px solid var(--line);
}
.document-tabs button {
  flex: 1;
  border: 0;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  color: var(--muted);
  font-size: 9px;
}
.document-tabs button.active {
  color: var(--green);
  background: #f5f8ff;
}
.document-panel pre {
  flex: 1;
  max-height: 550px;
  overflow: auto;
  margin: 0;
  padding: 17px;
  white-space: pre-wrap;
  font:
    10px/1.65 "SFMono-Regular",
    Consolas,
    monospace;
  color: #4d5652;
}
.download-button {
  height: 39px;
  border: 0;
  border-top: 1px solid var(--line);
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  color: var(--green);
  font-size: 9px;
}
.answer-panel {
  padding: 20px;
  min-width: 0;
}
.answer-heading {
  display: flex;
  justify-content: space-between;
}
.answer-heading small {
  color: var(--muted);
  font-size: 8px;
}
.answer-heading h3 {
  font-size: 15px;
  margin: 3px 0;
}
.answer-heading > span {
  padding: 5px 7px;
  height: max-content;
  border-radius: 6px;
  background: #f1f3f2;
  color: var(--muted);
  font-size: 8px;
}
.answer-heading > span.submitted {
  background: #eaf6f1;
  color: var(--green);
}
.answer-fields {
  margin-top: 13px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 9px;
}
.answer-fields label {
  font-size: 9px;
  font-weight: 650;
  color: #515a56;
}
.answer-fields textarea {
  width: 100%;
  height: 78px;
  margin-top: 5px;
  padding: 8px;
  border: 1px solid var(--line);
  border-radius: 8px;
  resize: vertical;
  font: inherit;
  font-size: 10px;
  box-sizing: border-box;
}
.project-actions {
  margin-top: 13px;
  display: flex;
  align-items: center;
  gap: 7px;
}
.upload-control {
  height: 36px;
  padding: 0 10px;
  border: 1px dashed #bdc9c4;
  border-radius: 8px;
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--muted);
  font-size: 8px;
  cursor: pointer;
}
.upload-control input {
  display: none;
}
.action-spacer {
  flex: 1;
}
.evaluation-view {
  display: grid;
  grid-template-columns: 230px 1fr;
  min-height: 500px;
}
.score-card {
  padding: 30px;
  background: #f4f8ff;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.score-card small {
  font-size: 8px;
  color: var(--green);
}
.score-card > strong {
  font-size: 64px;
  letter-spacing: -0.07em;
  margin-top: 35px;
}
.score-card > span {
  font-size: 11px;
  color: var(--muted);
}
.score-card p {
  font-size: 9px;
  line-height: 1.5;
  color: var(--muted);
  margin: 20px 0;
}
.dimension-list {
  padding: 18px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 9px;
}
.dimension-list article {
  padding: 12px;
  border: 1px solid var(--line);
  border-radius: 9px;
}
.dimension-head {
  display: flex;
  justify-content: space-between;
  font-size: 10px;
}
.dimension-head span {
  color: var(--green);
  font-weight: 800;
}
.dimension-list i {
  height: 4px;
  display: block;
  margin: 7px 0;
  background: #edf0ee;
  border-radius: 4px;
}
.dimension-list i b {
  display: block;
  height: 100%;
  background: var(--green);
  border-radius: 4px;
}
.dimension-list p {
  font-size: 8px;
  line-height: 1.5;
  color: var(--muted);
  margin: 4px 0;
}
.dimension-list p b {
  color: #4b5551;
}
.coding-filter {
  display: flex;
  align-items: end;
  gap: 7px;
}
.coding-filter label {
  display: grid;
  gap: 3px;
  color: var(--muted);
  font-size: 8px;
}
.coding-filter select {
  height: 37px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #fff;
  padding: 0 9px;
  font-size: 9px;
}
.coding-bank-browser {
  padding: 16px 20px;
  border-bottom: 1px solid var(--line);
  background: #f9fbff;
}
.difficulty-tabs {
  display: flex !important;
  flex-direction: row !important;
  gap: 5px !important;
}
.difficulty-tabs button {
  padding: 8px 13px;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: #fff;
  color: var(--muted);
  font-size: 12px;
  cursor: pointer;
}
.difficulty-tabs button.active {
  border-color: #8eb1ef;
  background: #eaf1ff;
  color: var(--green);
  font-weight: 700;
}
.coding-question-list {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 7px;
  margin-top: 12px;
}
.coding-question-list > button {
  min-width: 0;
  padding: 14px;
  border: 1px solid var(--line);
  border-radius: 9px;
  background: #fff;
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 6px 10px;
  color: var(--ink);
  text-align: left;
  cursor: pointer;
}
.coding-question-list > button.active {
  border-color: #7ca4ef;
  box-shadow: 0 0 0 2px rgba(21, 94, 239, 0.08);
}
.coding-question-list > button > span {
  grid-row: 1 / 3;
  padding: 6px 9px;
  border-radius: 5px;
  font-size: 11px;
  font-weight: 700;
}
.coding-question-list .level-1 {
  background: #e8f7ef;
  color: #168253;
}
.coding-question-list .level-2 {
  background: #fff4d9;
  color: #a66808;
}
.coding-question-list .level-3 {
  background: #ffebed;
  color: #c24150;
}
.coding-question-list strong {
  overflow: hidden;
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.coding-question-list small {
  color: var(--muted);
  font-size: 10px;
}
.coding-question-list svg {
  grid-column: 3;
  grid-row: 1 / 3;
  color: #18a565;
}
.coding-empty {
  min-height: 410px;
  display: grid;
  place-items: center;
  align-content: center;
  text-align: center;
  color: #83908b;
}
.coding-empty h3 {
  color: #4c5753;
  margin: 12px 0 4px;
}
.coding-empty p {
  max-width: 430px;
  font-size: 10px;
  line-height: 1.6;
}
.coding-layout {
  display: grid;
  grid-template-columns: minmax(280px, 34%) minmax(0, 1fr);
  min-height: 520px;
}
.question-panel {
  padding: 18px;
  border-right: 1px solid var(--line);
}
.question-meta {
  display: flex;
  justify-content: space-between;
}
.question-meta span {
  padding: 4px 6px;
  border-radius: 5px;
  background: #eaf5f0;
  color: var(--green);
  font-size: 8px;
  text-transform: uppercase;
}
.question-meta small {
  font-size: 8px;
  color: var(--muted);
}
.question-panel h3 {
  font-size: 16px;
  line-height: 1.4;
  margin: 13px 0 7px;
}
.question-panel > p,
.question-panel li {
  font-size: 9px;
  line-height: 1.6;
  color: var(--muted);
}
.question-panel h4 {
  font-size: 9px;
  margin: 17px 0 6px;
}
.example {
  padding: 8px;
  border-radius: 7px;
  background: #f5f7f6;
  display: grid;
  grid-template-columns: 35px 1fr;
  gap: 4px;
  font-size: 8px;
}
.example span {
  color: var(--muted);
}
.example code {
  color: #39433f;
}
.question-panel ul {
  padding-left: 15px;
}
.code-panel {
  display: flex;
  flex-direction: column;
  background: #18201f;
}
.code-panel header {
  height: 43px;
  padding: 0 13px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #303a37;
  color: #aeb9b4;
  font-size: 9px;
}
.code-panel header span,
.code-panel header button {
  display: flex;
  align-items: center;
  gap: 5px;
}
.code-panel header button {
  border: 0;
  background: none;
  color: #8f9b96;
  font-size: 8px;
}
.code-panel textarea {
  flex: 1;
  padding: 17px;
  border: 0;
  outline: 0;
  resize: none;
  background: #18201f;
  color: #dce5e1;
  font:
    11px/1.7 "SFMono-Regular",
    Consolas,
    monospace;
}
.code-panel footer {
  padding: 10px;
  display: flex;
  justify-content: flex-end;
  gap: 7px;
  border-top: 1px solid #303a37;
}
.code-panel .secondary {
  background: #26302e;
  border-color: #3a4542;
  color: #c2cbc7;
  min-height: 37px;
  font-size: 9px;
}
.judge-panel {
  grid-column: 1 / -1;
  min-height: 210px;
  padding: 17px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  border-top: 1px solid var(--line);
  background: #fbfdff;
}
.judge-title {
  display: flex;
  gap: 8px;
  align-items: center;
  color: #b17826;
}
.judge-title.accepted {
  color: var(--green);
}
.judge-title div {
  display: flex;
  flex-direction: column;
}
.judge-title small {
  font-size: 7px;
  color: var(--muted);
}
.judge-title strong {
  font-size: 12px;
}
.judge-numbers {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 5px;
}
.judge-numbers span {
  padding: 7px;
  border: 1px solid var(--line);
  border-radius: 7px;
  font-size: 7px;
  color: var(--muted);
  text-align: center;
}
.judge-numbers b {
  display: block;
  font-size: 12px;
  color: var(--ink);
}
.judge-panel > p {
  font-size: 9px;
  line-height: 1.6;
  color: var(--muted);
}
.hint {
  padding: 10px;
  border: 1px solid #efdfb7;
  border-radius: 8px;
  background: #fff9e9;
}
.hint strong {
  font-size: 8px;
  color: #95691f;
}
.hint p {
  font-size: 9px;
  line-height: 1.55;
  margin: 5px 0;
}
.hint.manual {
  border-color: #d8e7e1;
  background: #f3f9f6;
}
.hint.manual strong {
  color: var(--green);
}
.solution {
  padding: 9px;
  border: 1px solid var(--line);
  border-radius: 8px;
}
.solution > strong {
  font-size: 9px;
}
.solution pre {
  padding: 7px;
  background: #1b2321;
  color: #d9e4df;
  white-space: pre-wrap;
  font-size: 8px;
}
.solution p,
.solution small {
  font-size: 8px;
  line-height: 1.5;
  color: var(--muted);
}
.judge-empty {
  margin: auto;
  text-align: center;
  color: #9ba19f;
}
.judge-empty strong {
  display: block;
  color: #606966;
  margin: 8px;
}
.judge-empty p {
  font-size: 8px;
}
.judge-actions {
  margin-top: auto;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 5px;
}
.hint-button,
.solution-button {
  height: 34px;
  border-radius: 7px;
  background: #fff;
  font-size: 8px;
  cursor: pointer;
}
.hint-button {
  border: 1px solid var(--line);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
}
.solution-button {
  border: 0;
  color: #8a918e;
}
.history-panel {
  border-top: 1px solid var(--line);
}
.history-panel summary {
  padding: 16px 18px;
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  cursor: pointer;
}
.history-panel > div {
  padding: 0 18px 17px;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 6px;
}
.history-panel article {
  padding: 12px;
  border: 1px solid var(--line);
  border-radius: 7px;
  display: flex;
  flex-direction: column;
}
.history-panel article span {
  font-size: 10px;
  color: var(--green);
}
.history-panel article strong {
  margin: 4px 0;
  font-size: 13px;
}
.history-panel article small {
  font-size: 10px;
  color: var(--muted);
}
.gaokao-heading {
  background: linear-gradient(110deg, #fff 55%, #f1f6ff);
}
.gaokao-policy {
  display: flex;
  align-items: center;
  gap: 8px;
  max-width: 240px;
  padding: 9px 11px;
  border: 1px solid #cfddf4;
  border-radius: 10px;
  background: #fff;
  color: var(--green);
}
.gaokao-policy span {
  color: var(--muted);
  font-size: 8px;
  line-height: 1.5;
}
.gaokao-policy b {
  display: block;
  color: #174b9d;
  font-size: 9px;
}
.gaokao-start {
  min-height: 510px;
  padding: 40px 20px;
  display: flex;
  align-items: center;
  flex-direction: column;
  justify-content: center;
  text-align: center;
  background: radial-gradient(circle at 50% 38%, #eef4ff, #fff 42%);
}
.gaokao-start-icon {
  width: 64px;
  height: 64px;
  display: grid;
  place-items: center;
  border-radius: 18px;
  background: #155eef;
  color: #fff;
  box-shadow: 0 14px 28px rgba(21, 94, 239, 0.2);
}
.gaokao-start > span {
  margin-top: 17px;
  color: var(--green);
  font-size: 9px;
  font-weight: 700;
}
.gaokao-start h3 {
  margin: 7px 0;
  font-size: 20px;
}
.gaokao-start p {
  max-width: 550px;
  margin: 0 0 20px;
  color: var(--muted);
  font-size: 10px;
  line-height: 1.8;
}
.gaokao-question-meta {
  min-height: 54px;
  padding: 9px 18px;
  display: flex;
  align-items: center;
  gap: 13px;
  border-bottom: 1px solid var(--line);
  background: #f8faff;
}
.gaokao-question-meta > div {
  display: flex;
  gap: 5px;
}
.gaokao-question-meta span,
.gaokao-question-meta b {
  padding: 4px 7px;
  border-radius: 999px;
  background: #eaf1ff;
  color: var(--green);
  font-size: 8px;
}
.gaokao-question-meta b {
  background: #fff3d8;
  color: #9a650f;
}
.gaokao-question-meta small {
  flex: 1;
  color: var(--muted);
  font-size: 8px;
}
.gaokao-question-meta .secondary {
  min-height: 34px;
  font-size: 8px;
}
.gaokao-grid {
  display: block;
  min-height: 520px;
}
.gaokao-question {
  padding: 28px 32px;
  border-bottom: 1px solid var(--line);
}
.gaokao-stem {
  color: #263a59;
  font-size: 13px;
  line-height: 1.85;
}
.gaokao-stem :deep(img),
.gaokao-options :deep(img) {
  display: inline-block;
  max-width: 100%;
  height: auto;
  margin: 10px auto;
  vertical-align: middle;
  object-fit: contain;
}
.gaokao-stem :deep(pre) {
  overflow-x: auto;
  padding: 13px;
  border-radius: 8px;
  background: #f4f7fb;
}
.gaokao-options {
  display: grid;
  gap: 8px;
  margin-top: 20px;
}
.gaokao-options button {
  padding: 11px 13px;
  display: flex;
  align-items: flex-start;
  gap: 10px;
  border: 1px solid var(--line);
  border-radius: 9px;
  background: #fff;
  color: #344765;
  text-align: left;
  cursor: pointer;
}
.gaokao-options button > b {
  width: 24px;
  height: 24px;
  display: grid;
  flex: none;
  place-items: center;
  border-radius: 50%;
  background: #edf2f9;
  color: #536783;
  font-size: 9px;
}
.gaokao-options button.active {
  border-color: #6897ee;
  background: #f3f7ff;
}
.gaokao-options button.active > b {
  background: var(--green);
  color: #fff;
}
.gaokao-answer {
  display: grid;
  gap: 8px;
  margin-top: 20px;
  color: #455873;
  font-size: 10px;
  font-weight: 700;
}
.gaokao-answer-area {
  margin-top: 22px;
}
.submission-method-tabs {
  display: flex;
  gap: 7px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--line);
}
.submission-method-tabs button {
  padding: 8px 13px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #fff;
  color: var(--muted);
  font-size: 11px;
  cursor: pointer;
}
.submission-method-tabs button.active {
  border-color: #7da3ec;
  background: #edf3ff;
  color: var(--green);
  font-weight: 700;
}
.gaokao-answer textarea {
  min-height: 220px;
  padding: 13px;
  resize: vertical;
  border: 1px solid #cfdbed;
  border-radius: 9px;
  outline: none;
  font: inherit;
  font-size: 13px;
  line-height: 1.7;
}
.gaokao-image-upload {
  display: grid;
  gap: 10px;
  margin-top: 13px;
}
.gaokao-image-upload > label {
  min-height: 150px;
  display: flex;
  align-items: center;
  flex-direction: column;
  justify-content: center;
  gap: 7px;
  border: 1px dashed #8eade5;
  border-radius: 11px;
  background: #f7faff;
  color: var(--green);
  cursor: pointer;
}
.gaokao-image-upload > label strong {
  color: #334b70;
  font-size: 13px;
}
.gaokao-image-upload > label span {
  color: var(--muted);
  font-size: 10px;
}
.gaokao-image-upload input[type="file"] {
  display: none;
}
.gaokao-image-upload > textarea {
  min-height: 80px;
  padding: 11px;
  resize: vertical;
  border: 1px solid var(--line);
  border-radius: 9px;
  font: inherit;
  font-size: 11px;
}
.selected-images {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.selected-images span {
  padding: 6px 8px;
  border-radius: 6px;
  background: #eaf1ff;
  color: #355e9c;
  font-size: 9px;
}
.gaokao-submit {
  margin-top: 17px;
}
.gaokao-feedback {
  padding: 22px 32px;
  background: #f8faff;
}
.gaokao-feedback-empty {
  min-height: 150px;
  display: grid;
  place-items: center;
  align-content: center;
  color: #7f98be;
  text-align: center;
}
.gaokao-feedback-empty strong {
  margin: 9px 0 4px;
  color: #3b506e;
  font-size: 12px;
}
.gaokao-feedback-empty p {
  max-width: 260px;
  color: var(--muted);
  font-size: 9px;
  line-height: 1.6;
}
.gaokao-score {
  display: flex;
  align-items: baseline;
  padding-bottom: 15px;
  border-bottom: 1px solid var(--line);
}
.gaokao-score span {
  flex: 1;
  color: var(--muted);
  font-size: 9px;
}
.gaokao-score strong {
  color: var(--green);
  font-size: 31px;
}
.gaokao-score small {
  color: var(--muted);
  font-size: 9px;
}
.gaokao-score > b {
  margin-left: 10px;
  padding: 5px 8px;
  border-radius: 999px;
  background: #eaf1ff;
  color: var(--green);
  font-size: 8px;
}
.gaokao-feedback section {
  margin-top: 16px;
}
.gaokao-feedback h4 {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 0 0 7px;
  color: #334b70;
  font-size: 10px;
}
.gaokao-feedback p,
.gaokao-feedback li {
  color: #5b6d88;
  font-size: 9px;
  line-height: 1.7;
}
.gaokao-feedback ul {
  margin: 0;
  padding-left: 18px;
}
.gaokao-hints {
  padding: 11px;
  border: 1px solid #eadcae;
  border-radius: 9px;
  background: #fffaf0;
}
.no-answer-note {
  padding-top: 11px;
  border-top: 1px dashed #cdd8e8;
  color: #7b8ba3 !important;
}
.practice-redirect {
  padding: 13px 18px;
  display: flex;
  align-items: center;
  gap: 10px;
  border-top: 1px solid var(--line);
  background: #fff;
  color: var(--green);
}
.practice-redirect > div {
  flex: 1;
  display: flex;
  flex-direction: column;
}
.practice-redirect strong {
  color: #334765;
  font-size: 10px;
}
.practice-redirect span {
  color: var(--muted);
  font-size: 8px;
}
.practice-redirect .secondary {
  min-height: 34px;
  font-size: 8px;
}
.gaokao-history {
  border-top: 1px solid var(--line);
  background: #fff;
}
.gaokao-history summary {
  min-height: 58px;
  padding: 0 22px;
  display: flex;
  align-items: center;
  gap: 9px;
  color: #395371;
  cursor: pointer;
}
.gaokao-history summary strong {
  font-size: 13px;
}
.gaokao-history summary span {
  margin-left: auto;
  color: var(--muted);
  font-size: 11px;
}
.gaokao-history-list {
  display: grid;
  gap: 11px;
  padding: 0 22px 22px;
}
.gaokao-history-question {
  overflow: hidden;
  border: 1px solid var(--line);
  border-radius: 11px;
}
.gaokao-history-question > header {
  padding: 12px 14px;
  display: flex;
  align-items: center;
  gap: 12px;
  background: #f7faff;
}
.gaokao-history-question > header > div {
  display: flex;
  flex: 1;
  align-items: center;
  gap: 9px;
}
.gaokao-history-question > header span {
  padding: 4px 7px;
  border-radius: 999px;
  background: #eaf1ff;
  color: var(--green);
  font-size: 9px;
}
.gaokao-history-question > header strong {
  font-size: 12px;
}
.gaokao-history-question > header small {
  color: var(--muted);
  font-size: 10px;
}
.history-submissions {
  display: grid;
  gap: 1px;
  background: var(--line);
}
.history-submissions > section {
  padding: 13px 14px;
  display: grid;
  grid-template-columns: 65px 1fr;
  gap: 14px;
  background: #fff;
}
.history-score {
  display: flex;
  align-items: baseline;
  justify-content: center;
  color: var(--green);
}
.history-score b {
  font-size: 23px;
}
.history-score span {
  font-size: 10px;
}
.history-submissions > section > div:last-child > strong {
  font-size: 11px;
}
.history-submissions p {
  margin: 5px 0;
  color: #586a84;
  font-size: 11px;
  line-height: 1.6;
}
.history-submissions small {
  color: var(--muted);
  font-size: 9px;
}
.gaokao-history-empty {
  margin: 0;
  padding: 0 22px 20px;
  color: var(--muted);
  font-size: 11px;
}
.toast {
  position: fixed;
  right: 22px;
  bottom: 22px;
  padding: 11px 14px;
  border-radius: 9px;
  background: #182a24;
  color: #fff;
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 10px;
  box-shadow: 0 12px 30px rgba(0, 0, 0, 0.18);
}
@media (max-width: 1000px) {
  .career-layout {
    grid-template-columns: 1fr;
  }
  .career-conversation {
    border-right: 0;
    border-bottom: 1px solid var(--line);
  }
  .project-bank {
    grid-template-columns: 1fr 1fr;
  }
  .coding-question-list {
    grid-template-columns: repeat(2, 1fr);
  }
  .gaokao-grid {
    grid-template-columns: 1fr;
  }
  .gaokao-question {
    border-right: 0;
    border-bottom: 1px solid var(--line);
  }
  .project-session {
    grid-template-columns: 320px 1fr;
  }
  .coding-layout {
    grid-template-columns: 240px 1fr;
  }
  .judge-panel {
    grid-column: 1/-1;
    min-height: 240px;
    border-left: 0;
    border-top: 1px solid var(--line);
  }
  .evidence-drawer {
    grid-template-columns: 1fr;
  }
  .overview-metrics {
    display: none;
  }
}
@media (max-width: 720px) {
  .topbar {
    padding: 0 14px;
  }
  .job-chip {
    display: none;
  }
  .onboarding-page {
    grid-template-columns: 1fr;
    padding: 35px 16px;
  }
  .onboarding-copy h1 {
    font-size: 34px;
  }
  .workspace-page {
    padding: 18px 10px;
  }
  .overview-strip {
    flex-wrap: wrap;
  }
  .overview-copy {
    flex: 1;
  }
  .mode-nav {
    gap: 5px;
  }
  .mode-nav button {
    padding: 0 9px;
  }
  .mode-nav button > svg:last-child,
  .mode-nav span {
    display: none;
  }
  .project-bank {
    grid-template-columns: 1fr;
  }
  .bank-toolbar,
  .gaokao-question-meta,
  .practice-redirect {
    align-items: stretch;
    flex-direction: column;
  }
  .difficulty-tabs {
    flex-wrap: wrap;
  }
  .coding-question-list {
    grid-template-columns: 1fr;
  }
  .gaokao-policy {
    display: none;
  }
  .project-session,
  .evaluation-view,
  .coding-layout {
    grid-template-columns: 1fr;
  }
  .document-panel {
    border-right: 0;
    border-bottom: 1px solid var(--line);
  }
  .answer-fields,
  .dimension-list,
  .skills {
    grid-template-columns: 1fr;
  }
  .coding-layout .question-panel {
    border-right: 0;
    border-bottom: 1px solid var(--line);
  }
  .code-panel {
    min-height: 430px;
  }
  .two-col {
    grid-template-columns: 1fr;
  }
}
</style>
