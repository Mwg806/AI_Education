<script setup lang="ts">
import {
  ArrowLeft,
  ArrowRight,
  BriefcaseBusiness,
  Check,
  CheckCircle2,
  ChevronDown,
  CircleAlert,
  Clock3,
  Code2,
  Lightbulb,
  LoaderCircle,
  Play,
  RotateCcw,
  Settings2,
  Sparkles,
  Target,
  TerminalSquare,
  X,
} from "@lucide/vue";
import { computed, onMounted, reactive, ref } from "vue";

import {
  configureCareerProfile,
  createCareerCodingTask,
  createCareerDiagnostic,
  fetchCareerDashboard,
  getCareerCodingHint,
  submitCareerCode,
  submitCareerDiagnostic,
  type CareerCodingTask,
  type CareerDashboard,
  type CareerDiagnostic,
  type CareerDiagnosticResult,
  type CareerSubmission,
} from "@/lib/career-programming-client";
import type { StudentLoginProfile } from "@/lib/types";

const props = defineProps<{ profile: StudentLoginProfile }>();

const dashboard = ref<CareerDashboard | null>(null);
const diagnostic = ref<CareerDiagnostic | null>(null);
const diagnosticResult = ref<CareerDiagnosticResult | null>(null);
const task = ref<CareerCodingTask | null>(null);
const submission = ref<CareerSubmission | null>(null);
const code = ref("");
const questionIndex = ref(0);
const answers = ref<
  Array<{
    question_id: string;
    selected_option: number;
    confidence: number;
  }>
>([]);
const selectedOption = ref<number | null>(null);
const busy = ref(false);
const loading = ref(true);
const error = ref("");
const toast = ref("");
const showSkills = ref(false);
const showProfile = ref(false);

const profileForm = reactive({
  target_level: "intern" as "intern" | "junior",
  deadline_days: 90,
  weekly_hours: 10,
  current_identity: "undergraduate" as
    "vocational_student" | "undergraduate" | "career_switcher",
  python_experience: "basic" as "none" | "basic" | "project",
  project_experience: "none" as "none" | "low" | "medium",
  interview_experience: "none" as "none" | "some",
});

const configured = computed(() => Boolean(dashboard.value?.profile.configured));
const diagnosticDone = computed(() =>
  Boolean(
    dashboard.value?.progress.diagnostic_completed || diagnosticResult.value,
  ),
);
const currentQuestion = computed(
  () => diagnostic.value?.questions[questionIndex.value],
);
const diagnosticPercent = computed(() => {
  if (!diagnostic.value) return 0;
  return Math.round(
    (questionIndex.value / diagnostic.value.questions.length) * 100,
  );
});
const activeTask = computed(
  () => task.value || dashboard.value?.current_task || null,
);
const currentSkill = computed(() => {
  const skillId = activeTask.value?.skill_id;
  return dashboard.value?.skill_domains
    .flatMap((domain) => domain.skills)
    .find((skill) => skill.skill_id === skillId);
});

onMounted(loadDashboard);

async function loadDashboard() {
  loading.value = true;
  error.value = "";
  try {
    dashboard.value = await fetchCareerDashboard();
    task.value = dashboard.value.current_task;
    if (task.value) code.value = task.value.starter_code;
    Object.assign(profileForm, {
      target_level: dashboard.value.profile.target_level,
      deadline_days: dashboard.value.profile.deadline_days,
      weekly_hours: dashboard.value.profile.weekly_hours,
      current_identity: dashboard.value.profile.current_identity,
      python_experience: dashboard.value.profile.python_experience,
      project_experience: dashboard.value.profile.project_experience,
      interview_experience: dashboard.value.profile.interview_experience,
    });
  } catch (reason) {
    error.value =
      reason instanceof Error ? reason.message : "暂时无法载入职业训练空间";
  } finally {
    loading.value = false;
  }
}

function notify(message: string) {
  toast.value = message;
  window.setTimeout(() => {
    if (toast.value === message) toast.value = "";
  }, 2600);
}

async function saveProfile() {
  busy.value = true;
  error.value = "";
  try {
    await configureCareerProfile({ ...profileForm });
    showProfile.value = false;
    await loadDashboard();
    notify("职业目标已保存");
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "保存失败";
  } finally {
    busy.value = false;
  }
}

async function startDiagnostic() {
  busy.value = true;
  error.value = "";
  try {
    diagnostic.value = await createCareerDiagnostic();
    diagnosticResult.value = null;
    answers.value = [];
    questionIndex.value = 0;
    selectedOption.value = null;
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "诊断启动失败";
  } finally {
    busy.value = false;
  }
}

async function nextQuestion() {
  if (
    !diagnostic.value ||
    !currentQuestion.value ||
    selectedOption.value === null
  )
    return;
  answers.value.push({
    question_id: currentQuestion.value.question_id,
    selected_option: selectedOption.value,
    confidence: 0.75,
  });
  if (questionIndex.value < diagnostic.value.questions.length - 1) {
    questionIndex.value += 1;
    selectedOption.value = null;
    return;
  }
  busy.value = true;
  try {
    diagnosticResult.value = await submitCareerDiagnostic(
      diagnostic.value.diagnostic_id,
      answers.value,
    );
    await loadDashboard();
  } catch (reason) {
    answers.value.pop();
    error.value = reason instanceof Error ? reason.message : "诊断提交失败";
  } finally {
    busy.value = false;
  }
}

function previousQuestion() {
  if (questionIndex.value === 0) return;
  questionIndex.value -= 1;
  selectedOption.value = answers.value.pop()?.selected_option ?? null;
}

async function beginTask() {
  busy.value = true;
  error.value = "";
  try {
    task.value = await createCareerCodingTask();
    code.value = task.value.starter_code;
    submission.value = null;
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "任务创建失败";
  } finally {
    busy.value = false;
  }
}

async function runTests() {
  if (!activeTask.value || !code.value.trim()) return;
  busy.value = true;
  error.value = "";
  try {
    submission.value = await submitCareerCode(
      activeTask.value.task_id,
      code.value,
    );
    await loadDashboard();
    if (submission.value.passed) notify("测试通过，能力证据已更新");
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "代码提交失败";
  } finally {
    busy.value = false;
  }
}

async function askHint() {
  if (!activeTask.value) return;
  busy.value = true;
  try {
    const hint = await getCareerCodingHint(activeTask.value.task_id);
    submission.value = {
      ...(submission.value || {
        submission_id: "preview",
        task_id: activeTask.value.task_id,
        attempt: 0,
        passed: false,
        execution: {
          execution_status: "not_run",
          tests_passed: 0,
          tests_failed: 0,
          runtime_ms: 0,
          runner_mode: dashboard.value?.runner.mode || "",
          safety_notice: dashboard.value?.runner.notice || "",
          message: "尚未运行",
          console: "",
        },
        diagnosis: {
          error_type: null,
          message: "尚未运行",
          related_skill_id: activeTask.value.skill_id,
        },
        mastery_update: { previous_mastery: 0, mastery: 0, change: 0 },
        next_action: "先独立尝试",
      }),
      feedback: {
        hint_level: hint.hint_level,
        hint: hint.hint,
        solution_unlocked: false,
      },
    };
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "提示获取失败";
  } finally {
    busy.value = false;
  }
}

function resetCode() {
  if (!activeTask.value) return;
  code.value = activeTask.value.starter_code;
  submission.value = null;
}
</script>

<template>
  <div class="career-shell">
    <div v-if="loading" class="center-state">
      <LoaderCircle class="spin" :size="26" />
      <strong>正在整理你的职业训练进度</strong>
    </div>

    <template v-else-if="dashboard">
      <header class="career-header">
        <div class="brand-mark"><Code2 :size="20" /></div>
        <div class="brand-copy">
          <strong>Python 后端职业导师</strong>
          <span>Agent 6 · 训练闭环 V2</span>
        </div>
        <div class="header-spacer" />
        <span class="student-name">{{ props.profile.studentName }}</span>
        <button
          v-if="configured"
          class="icon-button"
          title="调整目标"
          @click="showProfile = true"
        >
          <Settings2 :size="18" />
        </button>
      </header>

      <div v-if="error" class="error-banner">
        <CircleAlert :size="18" /><span>{{ error }}</span>
        <button @click="error = ''"><X :size="16" /></button>
      </div>

      <main v-if="!configured || showProfile" class="onboarding-wrap">
        <section class="onboarding-intro">
          <span class="eyebrow"><BriefcaseBusiness :size="15" /> 职业目标</span>
          <h1>先确定方向，<br />再开始训练。</h1>
          <p>
            首期专注 Python
            后端实习与初级岗位。你只需要提供时间和当前基础，后续能力结论全部由测评与代码证据更新。
          </p>
          <div class="promise-list">
            <span><Check :size="16" /> 不靠自评直接判定“已掌握”</span>
            <span><Check :size="16" /> 每次只推荐一个最重要的任务</span>
            <span><Check :size="16" /> 失败先给提示，不直接泄露答案</span>
          </div>
        </section>

        <form class="profile-card" @submit.prevent="saveProfile">
          <div class="form-title">
            <div>
              <small>预计 1 分钟</small>
              <h2>{{ configured ? "调整职业目标" : "建立学习画像" }}</h2>
            </div>
            <button
              v-if="configured"
              type="button"
              class="icon-button"
              @click="showProfile = false"
            >
              <X :size="18" />
            </button>
          </div>
          <label
            >目标阶段
            <select v-model="profileForm.target_level">
              <option value="intern">实习岗位</option>
              <option value="junior">初级工程师</option>
            </select>
          </label>
          <div class="form-row">
            <label
              >目标周期
              <select v-model.number="profileForm.deadline_days">
                <option :value="60">60 天</option>
                <option :value="90">90 天</option>
                <option :value="120">120 天</option>
                <option :value="180">180 天</option>
              </select>
            </label>
            <label
              >每周时间
              <select v-model.number="profileForm.weekly_hours">
                <option :value="5">5 小时</option>
                <option :value="10">10 小时</option>
                <option :value="14">14 小时</option>
                <option :value="20">20 小时</option>
              </select>
            </label>
          </div>
          <label
            >当前身份
            <select v-model="profileForm.current_identity">
              <option value="vocational_student">高职 / 专科学生</option>
              <option value="undergraduate">本科在读</option>
              <option value="career_switcher">转行学习者</option>
            </select>
          </label>
          <label
            >Python 基础
            <div class="choice-row">
              <button
                v-for="item in [
                  { v: 'none', l: '刚开始' },
                  { v: 'basic', l: '学过语法' },
                  { v: 'project', l: '做过项目' },
                ]"
                :key="item.v"
                type="button"
                :class="{ selected: profileForm.python_experience === item.v }"
                @click="
                  profileForm.python_experience =
                    item.v as typeof profileForm.python_experience
                "
              >
                {{ item.l }}
              </button>
            </div>
          </label>
          <div class="form-row">
            <label
              >项目经验
              <select v-model="profileForm.project_experience">
                <option value="none">暂无</option>
                <option value="low">有小练习</option>
                <option value="medium">有完整项目</option>
              </select>
            </label>
            <label
              >面试经验
              <select v-model="profileForm.interview_experience">
                <option value="none">暂无</option>
                <option value="some">有过面试</option>
              </select>
            </label>
          </div>
          <button class="primary-button" :disabled="busy">
            <LoaderCircle v-if="busy" class="spin" :size="18" /><Target
              v-else
              :size="18"
            />
            {{ configured ? "保存调整" : "确定目标，开始诊断" }}
          </button>
        </form>
      </main>

      <main v-else class="career-main">
        <section class="status-strip">
          <div
            class="readiness-ring"
            :style="{ '--score': `${dashboard.readiness.percent * 3.6}deg` }"
          >
            <div>
              <strong>{{ dashboard.readiness.percent }}</strong
              ><small>%</small>
            </div>
          </div>
          <div class="status-copy">
            <span class="eyebrow"><Target :size="14" /> 岗位准备度</span>
            <h1>{{ dashboard.readiness.label }}</h1>
            <p>{{ dashboard.next_action }}</p>
          </div>
          <div class="mini-progress">
            <span :class="{ done: configured }"
              ><i><Check :size="13" /></i>目标</span
            >
            <b />
            <span :class="{ done: diagnosticDone }"
              ><i><Check :size="13" /></i>诊断</span
            >
            <b />
            <span :class="{ done: dashboard.progress.completed_tasks > 0 }"
              ><i><Check :size="13" /></i>训练</span
            >
          </div>
        </section>

        <section v-if="!diagnosticDone" class="focus-card diagnostic-card">
          <template v-if="!diagnostic">
            <div class="focus-icon"><Sparkles :size="25" /></div>
            <span class="eyebrow">下一步 · 基础诊断</span>
            <h2>用 6 道题找到真正的起点</h2>
            <p>
              覆盖 Python、HTTP、FastAPI、MySQL
              与测试。结果只作为初始证据，不会一次测评就给你贴标签。
            </p>
            <button
              class="primary-button compact"
              :disabled="busy"
              @click="startDiagnostic"
            >
              <LoaderCircle v-if="busy" class="spin" :size="18" /><ArrowRight
                v-else
                :size="18"
              />开始诊断
            </button>
          </template>
          <template v-else-if="currentQuestion">
            <div class="question-top">
              <span
                >{{ questionIndex + 1 }} /
                {{ diagnostic.questions.length }}</span
              >
              <strong>{{ currentQuestion.dimension }}</strong>
              <span>约 {{ diagnostic.estimated_minutes }} 分钟</span>
            </div>
            <div class="progress-track">
              <i :style="{ width: `${diagnosticPercent}%` }" />
            </div>
            <h2 class="question-prompt">{{ currentQuestion.prompt }}</h2>
            <div class="option-list">
              <button
                v-for="(option, index) in currentQuestion.options"
                :key="option"
                :class="{ selected: selectedOption === index }"
                @click="selectedOption = index"
              >
                <span>{{ String.fromCharCode(65 + index) }}</span
                >{{ option }}
              </button>
            </div>
            <div class="question-actions">
              <button
                class="text-button"
                :disabled="questionIndex === 0"
                @click="previousQuestion"
              >
                <ArrowLeft :size="17" />上一题
              </button>
              <button
                class="primary-button compact"
                :disabled="selectedOption === null || busy"
                @click="nextQuestion"
              >
                {{
                  questionIndex === diagnostic.questions.length - 1
                    ? "查看结果"
                    : "下一题"
                }}<ArrowRight :size="17" />
              </button>
            </div>
          </template>
        </section>

        <section v-else-if="!activeTask" class="focus-card next-task-card">
          <span class="eyebrow">下一步 · 针对性训练</span>
          <h2>
            {{
              diagnosticResult
                ? `诊断完成，优先补强 ${diagnosticResult.priority_gaps[0]}`
                : "开始当前最需要的训练"
            }}
          </h2>
          <p>
            Agent 会根据岗位重要度和已有证据选择一个 15—20
            分钟的任务。一次只做一件事。
          </p>
          <div class="gap-pills">
            <span
              v-for="gap in dashboard.priority_gaps.slice(0, 3)"
              :key="gap.skill_id"
              >{{ gap.name }} · {{ Math.round(gap.mastery * 100) }}%</span
            >
          </div>
          <button
            class="primary-button compact"
            :disabled="busy"
            @click="beginTask"
          >
            <Play :size="17" />生成推荐任务
          </button>
        </section>

        <section v-else class="coding-workspace">
          <aside class="task-panel">
            <span class="eyebrow"
              >当前任务 · {{ currentSkill?.name || activeTask.skill_id }}</span
            >
            <h2>{{ activeTask.title }}</h2>
            <p>{{ activeTask.description }}</p>
            <div class="task-meta">
              <span
                ><Clock3 :size="15" />{{
                  activeTask.estimated_minutes
                }}
                分钟</span
              ><span>难度 {{ activeTask.difficulty }}/3</span>
            </div>
            <h3>验收条件</h3>
            <ul>
              <li v-for="item in activeTask.acceptance" :key="item">
                <CheckCircle2 :size="15" />{{ item }}
              </li>
            </ul>
          </aside>

          <div class="editor-panel">
            <div class="editor-toolbar">
              <span><TerminalSquare :size="16" />main.py</span>
              <button @click="resetCode"><RotateCcw :size="15" />重置</button>
            </div>
            <textarea
              v-model="code"
              spellcheck="false"
              aria-label="Python 代码编辑器"
            />
            <div class="editor-actions">
              <small>代码会执行隐藏测试，完整答案不会直接展示</small>
              <button
                class="primary-button compact"
                :disabled="busy || !code.trim()"
                @click="runTests"
              >
                <LoaderCircle v-if="busy" class="spin" :size="17" /><Play
                  v-else
                  :size="17"
                />运行测试
              </button>
            </div>
          </div>

          <aside
            class="feedback-panel"
            :class="{
              passed: submission?.passed,
              failed: submission && !submission.passed,
            }"
          >
            <template v-if="submission">
              <div class="feedback-status">
                <CheckCircle2 v-if="submission.passed" :size="25" />
                <CircleAlert v-else :size="25" />
                <div>
                  <small>第 {{ submission.attempt || "—" }} 次结果</small
                  ><strong>{{
                    submission.passed
                      ? "测试通过"
                      : submission.execution.execution_status === "not_run"
                        ? "提示已准备"
                        : "还差一点"
                  }}</strong>
                </div>
              </div>
              <div
                v-if="submission.execution.execution_status !== 'not_run'"
                class="test-summary"
              >
                <span
                  ><b>{{ submission.execution.tests_passed }}</b> 通过</span
                ><span
                  ><b>{{ submission.execution.tests_failed }}</b> 未通过</span
                ><span
                  ><b>{{ submission.execution.runtime_ms }}</b> ms</span
                >
              </div>
              <p class="diagnosis-text">{{ submission.diagnosis.message }}</p>
              <div v-if="!submission.passed" class="hint-box">
                <span
                  ><Lightbulb :size="15" />Hint
                  {{ submission.feedback.hint_level }}</span
                >
                <p>{{ submission.feedback.hint }}</p>
              </div>
              <div v-else class="mastery-change">
                <span>技能掌握度</span
                ><strong
                  >{{
                    Math.round(
                      submission.mastery_update.previous_mastery * 100,
                    )
                  }}% →
                  {{
                    Math.round(submission.mastery_update.mastery * 100)
                  }}%</strong
                >
              </div>
              <button
                v-if="submission.passed"
                class="primary-button compact"
                @click="
                  task = null;
                  submission = null;
                  code = '';
                "
              >
                继续下一项<ArrowRight :size="16" />
              </button>
            </template>
            <template v-else>
              <div class="empty-feedback">
                <Play :size="25" /><strong>运行后在这里看结果</strong>
                <p>先看失败用例和错误方向，再决定是否查看提示。</p>
              </div>
              <button class="hint-button" :disabled="busy" @click="askHint">
                <Lightbulb :size="16" />我需要一个方向
              </button>
            </template>
          </aside>
        </section>

        <section class="evidence-section">
          <button class="evidence-toggle" @click="showSkills = !showSkills">
            <div>
              <span>能力证据</span
              ><strong
                >{{
                  dashboard.priority_gaps[0]?.name || "等待诊断"
                }}
                是当前优先项</strong
              >
            </div>
            <ChevronDown :size="20" :class="{ rotated: showSkills }" />
          </button>
          <div v-if="showSkills" class="evidence-content">
            <div class="skill-grid">
              <article
                v-for="domain in dashboard.skill_domains"
                :key="domain.domain"
              >
                <div>
                  <strong>{{ domain.domain }}</strong
                  ><span>{{ Math.round(domain.mastery * 100) }}%</span>
                </div>
                <i
                  ><b
                    :style="{ width: `${Math.round(domain.mastery * 100)}%` }"
                /></i>
                <small>{{
                  domain.skills.map((item) => item.name).join(" · ")
                }}</small>
              </article>
            </div>
            <div class="plan-list">
              <article
                v-for="phase in dashboard.learning_plan"
                :key="phase.phase"
                :class="{ current: phase.priority === 'current' }"
              >
                <span>0{{ phase.phase }}</span>
                <div>
                  <small>{{
                    phase.priority === "current" ? "当前阶段" : "后续阶段"
                  }}</small
                  ><strong>{{ phase.title }}</strong>
                  <p>{{ phase.objective }}</p>
                </div>
                <em>{{ phase.estimated_hours }}h</em>
              </article>
            </div>
          </div>
        </section>

        <p class="runner-notice">执行环境：{{ dashboard.runner.notice }}</p>
      </main>
    </template>

    <div v-if="toast" class="toast"><CheckCircle2 :size="17" />{{ toast }}</div>
  </div>
</template>

<style scoped>
.career-shell {
  --ink: #17202a;
  --muted: #6b7280;
  --line: #e6e8eb;
  --paper: #fff;
  --accent: #17785f;
  min-height: calc(100vh - 64px);
  background: #f5f6f4;
  color: var(--ink);
  font-family: Inter, "PingFang SC", "Microsoft YaHei", sans-serif;
}
.career-header {
  height: 68px;
  padding: 0 34px;
  display: flex;
  align-items: center;
  gap: 12px;
  background: rgba(255, 255, 255, 0.94);
  border-bottom: 1px solid var(--line);
}
.brand-mark {
  width: 38px;
  height: 38px;
  display: grid;
  place-items: center;
  color: #fff;
  background: var(--ink);
  border-radius: 11px;
}
.brand-copy {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.brand-copy strong {
  font-size: 14px;
}
.brand-copy span,
.student-name {
  font-size: 12px;
  color: var(--muted);
}
.header-spacer {
  flex: 1;
}
.icon-button {
  width: 36px;
  height: 36px;
  display: grid;
  place-items: center;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: #fff;
  color: #505761;
  cursor: pointer;
}
.center-state {
  min-height: 70vh;
  display: grid;
  place-items: center;
  align-content: center;
  gap: 12px;
  color: var(--muted);
}
.spin {
  animation: spin 1s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
.error-banner {
  margin: 18px auto 0;
  max-width: 1120px;
  padding: 12px 14px;
  display: flex;
  align-items: center;
  gap: 10px;
  border: 1px solid #fed7d7;
  border-radius: 12px;
  background: #fff5f5;
  color: #a33b3b;
  font-size: 13px;
}
.error-banner span {
  flex: 1;
}
.error-banner button {
  border: 0;
  background: none;
  color: inherit;
  cursor: pointer;
}
.onboarding-wrap {
  max-width: 1080px;
  margin: 0 auto;
  padding: 64px 30px 80px;
  display: grid;
  grid-template-columns: 0.9fr 1.1fr;
  gap: 72px;
  align-items: center;
}
.onboarding-intro h1 {
  font-size: 46px;
  line-height: 1.13;
  letter-spacing: -0.04em;
  margin: 18px 0;
}
.onboarding-intro > p {
  font-size: 16px;
  line-height: 1.8;
  color: var(--muted);
  max-width: 470px;
}
.eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  color: var(--accent);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.promise-list {
  margin-top: 28px;
  display: grid;
  gap: 12px;
}
.promise-list span {
  display: flex;
  gap: 9px;
  align-items: center;
  font-size: 13px;
  color: #46505a;
}
.profile-card {
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 20px;
  padding: 28px;
  box-shadow: 0 18px 50px rgba(30, 40, 35, 0.07);
  display: grid;
  gap: 18px;
}
.form-title {
  display: flex;
  justify-content: space-between;
  align-items: start;
  margin-bottom: 4px;
}
.form-title small {
  color: var(--accent);
  font-weight: 700;
}
.form-title h2 {
  margin: 5px 0 0;
  font-size: 22px;
}
.profile-card label {
  display: grid;
  gap: 8px;
  font-size: 12px;
  font-weight: 650;
  color: #46505a;
}
.profile-card select {
  height: 42px;
  border: 1px solid #dcdfe3;
  border-radius: 10px;
  padding: 0 11px;
  background: #fff;
  color: var(--ink);
  font: inherit;
}
.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}
.choice-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}
.choice-row button {
  height: 40px;
  border: 1px solid #dfe2e5;
  border-radius: 10px;
  background: #fafafa;
  color: #5e6670;
  cursor: pointer;
}
.choice-row button.selected {
  border-color: var(--accent);
  background: #eef7f3;
  color: var(--accent);
  font-weight: 700;
}
.primary-button {
  border: 0;
  border-radius: 11px;
  background: var(--accent);
  color: #fff;
  min-height: 46px;
  padding: 0 18px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-weight: 700;
  cursor: pointer;
}
.primary-button.compact {
  min-height: 40px;
  width: max-content;
}
.primary-button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.career-main {
  max-width: 1180px;
  margin: 0 auto;
  padding: 32px 30px 70px;
}
.status-strip {
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 12px 0 28px;
}
.readiness-ring {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: conic-gradient(var(--accent) var(--score), #e1e5e2 0);
  position: relative;
}
.readiness-ring:before {
  content: "";
  position: absolute;
  inset: 7px;
  border-radius: 50%;
  background: #f5f6f4;
}
.readiness-ring div {
  z-index: 1;
}
.readiness-ring strong {
  font-size: 22px;
}
.readiness-ring small {
  font-size: 11px;
}
.status-copy h1 {
  font-size: 24px;
  margin: 5px 0 3px;
}
.status-copy p {
  margin: 0;
  color: var(--muted);
  font-size: 13px;
}
.mini-progress {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 8px;
}
.mini-progress span {
  display: grid;
  place-items: center;
  gap: 5px;
  color: #9aa0a6;
  font-size: 11px;
}
.mini-progress i {
  width: 25px;
  height: 25px;
  border-radius: 50%;
  border: 1px solid #d7dadd;
  display: grid;
  place-items: center;
  font-style: normal;
}
.mini-progress b {
  width: 38px;
  height: 1px;
  background: #d9dcde;
}
.mini-progress span.done {
  color: var(--accent);
}
.mini-progress span.done i {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
}
.focus-card {
  min-height: 390px;
  border: 1px solid var(--line);
  border-radius: 18px;
  background: var(--paper);
  padding: 52px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
}
.focus-icon {
  width: 56px;
  height: 56px;
  border-radius: 16px;
  background: #eef7f3;
  color: var(--accent);
  display: grid;
  place-items: center;
  margin-bottom: 18px;
}
.focus-card h2 {
  font-size: 28px;
  letter-spacing: -0.02em;
  margin: 10px 0;
}
.focus-card > p {
  max-width: 600px;
  color: var(--muted);
  line-height: 1.7;
  margin: 0 0 24px;
}
.gap-pills {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: center;
  margin-bottom: 24px;
}
.gap-pills span {
  padding: 7px 10px;
  border-radius: 999px;
  background: #f1f3f2;
  color: #5e6660;
  font-size: 12px;
}
.diagnostic-card {
  align-items: stretch;
  text-align: left;
  max-width: 850px;
  margin: 0 auto;
}
.diagnostic-card:not(:has(.question-top)) {
  align-items: center;
  text-align: center;
}
.question-top {
  display: flex;
  justify-content: space-between;
  color: var(--muted);
  font-size: 12px;
}
.question-top strong {
  color: var(--accent);
}
.progress-track {
  height: 4px;
  background: #eceeed;
  border-radius: 4px;
  margin: 14px 0 40px;
  overflow: hidden;
}
.progress-track i {
  display: block;
  height: 100%;
  background: var(--accent);
}
.question-prompt {
  font-size: 23px !important;
  line-height: 1.55;
  margin: 0 0 25px !important;
}
.option-list {
  display: grid;
  gap: 10px;
}
.option-list button {
  min-height: 52px;
  padding: 10px 14px;
  border: 1px solid var(--line);
  border-radius: 11px;
  background: #fff;
  display: flex;
  align-items: center;
  gap: 12px;
  text-align: left;
  color: #39424c;
  cursor: pointer;
}
.option-list button span {
  width: 27px;
  height: 27px;
  border-radius: 8px;
  background: #f0f2f1;
  display: grid;
  place-items: center;
  font-size: 12px;
}
.option-list button.selected {
  border-color: var(--accent);
  background: #f1f8f5;
}
.option-list button.selected span {
  background: var(--accent);
  color: #fff;
}
.question-actions {
  display: flex;
  justify-content: space-between;
  margin-top: 28px;
}
.text-button {
  border: 0;
  background: none;
  display: flex;
  align-items: center;
  gap: 7px;
  color: var(--muted);
  cursor: pointer;
}
.text-button:disabled {
  opacity: 0.35;
}
.coding-workspace {
  display: grid;
  grid-template-columns: 260px minmax(400px, 1fr) 280px;
  min-height: 530px;
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 17px;
  overflow: hidden;
}
.task-panel,
.feedback-panel {
  padding: 25px;
}
.task-panel {
  border-right: 1px solid var(--line);
}
.task-panel h2 {
  font-size: 20px;
  line-height: 1.4;
  margin: 12px 0;
}
.task-panel > p {
  font-size: 13px;
  line-height: 1.7;
  color: var(--muted);
}
.task-meta {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin: 18px 0;
}
.task-meta span {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 6px 8px;
  background: #f2f4f3;
  border-radius: 7px;
  font-size: 11px;
  color: #58605b;
}
.task-panel h3 {
  font-size: 12px;
  margin: 24px 0 10px;
}
.task-panel ul {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  gap: 9px;
}
.task-panel li {
  display: flex;
  align-items: flex-start;
  gap: 7px;
  font-size: 12px;
  line-height: 1.45;
  color: #545d56;
}
.task-panel li svg {
  color: var(--accent);
  flex: none;
  margin-top: 1px;
}
.editor-panel {
  min-width: 0;
  background: #19201f;
  display: flex;
  flex-direction: column;
}
.editor-toolbar {
  height: 47px;
  padding: 0 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: #bac3bf;
  border-bottom: 1px solid #303837;
  font-size: 12px;
}
.editor-toolbar span,
.editor-toolbar button {
  display: flex;
  align-items: center;
  gap: 7px;
}
.editor-toolbar button {
  border: 0;
  background: none;
  color: #96a19d;
  cursor: pointer;
}
.editor-panel textarea {
  flex: 1;
  resize: none;
  border: 0;
  outline: 0;
  background: #19201f;
  color: #dce6e1;
  padding: 21px;
  font:
    13px/1.75 "JetBrains Mono",
    "SFMono-Regular",
    Consolas,
    monospace;
  tab-size: 4;
}
.editor-actions {
  padding: 12px 15px;
  border-top: 1px solid #303837;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.editor-actions small {
  color: #86928d;
  font-size: 10px;
}
.feedback-panel {
  border-left: 1px solid var(--line);
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.feedback-panel.passed {
  background: #f5fbf8;
}
.feedback-panel.failed {
  background: #fffdf8;
}
.feedback-status {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #b17b24;
}
.feedback-panel.passed .feedback-status {
  color: var(--accent);
}
.feedback-status div {
  display: flex;
  flex-direction: column;
}
.feedback-status small {
  font-size: 10px;
  color: var(--muted);
}
.feedback-status strong {
  font-size: 18px;
}
.test-summary {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 6px;
}
.test-summary span {
  padding: 8px 3px;
  text-align: center;
  background: rgba(255, 255, 255, 0.8);
  border: 1px solid var(--line);
  border-radius: 8px;
  font-size: 9px;
  color: var(--muted);
}
.test-summary b {
  display: block;
  color: var(--ink);
  font-size: 15px;
}
.diagnosis-text {
  font-size: 12px;
  line-height: 1.6;
  color: #5c625e;
  margin: 0;
}
.hint-box {
  padding: 13px;
  border-radius: 10px;
  background: #fff7df;
  border: 1px solid #f1deb0;
}
.hint-box span {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #9a6d1e;
  font-size: 11px;
  font-weight: 700;
}
.hint-box p {
  font-size: 12px;
  line-height: 1.6;
  margin: 8px 0 0;
}
.mastery-change {
  padding: 13px;
  border: 1px solid #cfe9dd;
  background: #fff;
  border-radius: 10px;
  display: flex;
  justify-content: space-between;
  font-size: 12px;
}
.mastery-change strong {
  color: var(--accent);
}
.empty-feedback {
  margin: auto;
  text-align: center;
  color: #8c9490;
}
.empty-feedback strong {
  display: block;
  color: #4e5753;
  margin: 12px 0 5px;
}
.empty-feedback p {
  font-size: 11px;
  line-height: 1.6;
}
.hint-button {
  border: 1px solid var(--line);
  background: #fff;
  border-radius: 9px;
  min-height: 38px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  color: #59615d;
  cursor: pointer;
}
.evidence-section {
  margin-top: 18px;
  border: 1px solid var(--line);
  border-radius: 14px;
  background: #fff;
  overflow: hidden;
}
.evidence-toggle {
  width: 100%;
  padding: 17px 20px;
  border: 0;
  background: #fff;
  display: flex;
  align-items: center;
  text-align: left;
  cursor: pointer;
}
.evidence-toggle div {
  display: flex;
  flex-direction: column;
  gap: 3px;
  flex: 1;
}
.evidence-toggle span {
  font-size: 10px;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.08em;
}
.evidence-toggle strong {
  font-size: 13px;
}
.evidence-toggle svg {
  transition: 0.2s;
}
.evidence-toggle svg.rotated {
  transform: rotate(180deg);
}
.evidence-content {
  padding: 4px 20px 20px;
  border-top: 1px solid var(--line);
  display: grid;
  grid-template-columns: 1.2fr 0.8fr;
  gap: 24px;
}
.skill-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
  padding-top: 18px;
}
.skill-grid article > div {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
}
.skill-grid article > i {
  display: block;
  height: 5px;
  background: #ecefed;
  border-radius: 5px;
  margin: 8px 0;
}
.skill-grid article > i b {
  display: block;
  height: 100%;
  background: var(--accent);
  border-radius: 5px;
}
.skill-grid small {
  font-size: 9px;
  color: #8a918d;
  line-height: 1.5;
}
.plan-list {
  padding-top: 18px;
  display: grid;
  gap: 8px;
}
.plan-list article {
  padding: 10px;
  display: flex;
  gap: 10px;
  border: 1px solid var(--line);
  border-radius: 9px;
  align-items: center;
}
.plan-list article.current {
  border-color: #b9ddcf;
  background: #f4faf7;
}
.plan-list article > span {
  font-size: 11px;
  color: var(--accent);
}
.plan-list div {
  display: flex;
  flex-direction: column;
  flex: 1;
}
.plan-list small {
  font-size: 8px;
  color: var(--muted);
}
.plan-list strong {
  font-size: 11px;
}
.plan-list p {
  font-size: 9px;
  margin: 2px 0;
  color: var(--muted);
}
.plan-list em {
  font-style: normal;
  font-size: 10px;
  color: var(--muted);
}
.runner-notice {
  text-align: center;
  color: #959b98;
  font-size: 10px;
  margin: 18px;
}
.toast {
  position: fixed;
  right: 24px;
  bottom: 24px;
  padding: 12px 15px;
  border-radius: 11px;
  background: #17241f;
  color: #fff;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  box-shadow: 0 12px 30px rgba(0, 0, 0, 0.18);
}
@media (max-width: 1000px) {
  .coding-workspace {
    grid-template-columns: 220px 1fr;
  }
  .feedback-panel {
    grid-column: 1/-1;
    border-left: 0;
    border-top: 1px solid var(--line);
    min-height: 210px;
  }
  .onboarding-wrap {
    gap: 35px;
  }
  .evidence-content {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 720px) {
  .career-header {
    padding: 0 16px;
  }
  .student-name {
    display: none;
  }
  .onboarding-wrap {
    grid-template-columns: 1fr;
    padding: 34px 18px;
  }
  .onboarding-intro h1 {
    font-size: 34px;
  }
  .career-main {
    padding: 22px 14px;
  }
  .status-strip {
    align-items: flex-start;
  }
  .mini-progress {
    display: none;
  }
  .focus-card {
    padding: 28px 20px;
  }
  .coding-workspace {
    grid-template-columns: 1fr;
  }
  .task-panel {
    border-right: 0;
    border-bottom: 1px solid var(--line);
  }
  .editor-panel {
    min-height: 430px;
  }
  .feedback-panel {
    grid-column: auto;
  }
  .skill-grid {
    grid-template-columns: 1fr;
  }
  .form-row {
    grid-template-columns: 1fr;
  }
}
</style>
