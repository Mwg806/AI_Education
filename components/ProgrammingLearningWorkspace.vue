<script setup lang="ts">
import {
  ArrowRight,
  BarChart3,
  BookOpenCheck,
  BrainCircuit,
  Check,
  CheckCircle2,
  ChevronRight,
  CircleAlert,
  Clock3,
  Code2,
  Compass,
  FileCheck2,
  FlaskConical,
  Gauge,
  Lightbulb,
  LoaderCircle,
  MessageSquareText,
  Play,
  Route,
  ShieldCheck,
  Sparkles,
  Target,
  TerminalSquare,
  Trophy,
} from "@lucide/vue";
import { computed, onMounted, reactive, ref } from "vue";

import {
  createProgrammingDiagnostic,
  createProgrammingInterview,
  fetchProgrammingDashboard,
  recommendProgrammingProject,
  requestProgrammingProjectHint,
  reviewProgrammingCode,
  scoreProgrammingInterviewAnswer,
  submitProgrammingDiagnostic,
  updateProgrammingProfile,
} from "@/lib/programming-learning-client";
import type {
  ProgrammingCodeReview,
  ProgrammingDashboard,
  ProgrammingDiagnostic,
  ProgrammingDiagnosticResult,
  ProgrammingDirection,
  ProgrammingInterview,
  ProgrammingInterviewScore,
  ProgrammingLearningMode,
  ProgrammingProject,
  ProgrammingProjectTask,
} from "@/lib/programming-learning-client";
import type { StudentLoginProfile } from "@/lib/types";

type WorkspaceTab =
  "overview" | "diagnostic" | "code" | "project" | "interview";

defineProps<{ profile: StudentLoginProfile }>();

const activeTab = ref<WorkspaceTab>("overview");
const dashboard = ref<ProgrammingDashboard | null>(null);
const loading = ref(true);
const actionLoading = ref(false);
const error = ref("");
const toast = ref("");

const profileForm = reactive({
  learning_mode: "beginner" as ProgrammingLearningMode,
  target_direction: "computer_science_exploration" as ProgrammingDirection,
  weekly_available_minutes: 120,
  max_session_minutes: 40,
  exam_period: false,
  programming_months: 0,
  project_count: 0,
  interestsText: "学习工具、数据分析",
});

const diagnostic = ref<ProgrammingDiagnostic | null>(null);
const diagnosticResult = ref<ProgrammingDiagnosticResult | null>(null);
const diagnosticAnswers = reactive<Record<string, number>>({});
const diagnosticConfidence = ref(0.7);

const codeForm = reactive({
  problem_statement: "找出列表中的最大值，并输出结果",
  expected_behavior: "输入 [5, 9, 3] 时输出 9",
  observed_problem: "当最大值不在最后一个位置时，输出结果不正确",
  code: `numbers = [5, 9, 3]
for number in numbers:
    max_value = number
print(max_value)`,
  hint_level: 1,
  review_stage: false,
});
const codeReview = ref<ProgrammingCodeReview | null>(null);

const projectInterest = ref("学习工具");
const projectWeeks = ref(4);
const project = ref<ProgrammingProject | null>(null);
const selectedTask = ref<ProgrammingProjectTask | null>(null);
const projectProblem = ref("我不确定应该先完成哪一个最小步骤");
const hintHistory = ref<number[]>([]);
const projectHint = ref<{
  hint_level: number;
  hint: string;
  check_questions: string[];
  verification_action: string;
} | null>(null);

const interview = ref<ProgrammingInterview | null>(null);
const interviewAnswer = ref("");
const interviewScore = ref<ProgrammingInterviewScore | null>(null);
const currentInterviewQuestion = computed(
  () => interview.value?.questions[0] || null,
);

const configured = computed(() => Boolean(dashboard.value?.profile.configured));
const roadmap = computed(() => dashboard.value?.roadmap);
const report = computed(() => dashboard.value?.weekly_report);
const evidenceCoverage = computed(() =>
  Math.round((report.value?.data_quality.coverage || 0) * 100),
);

const tabs: Array<{
  id: WorkspaceTab;
  label: string;
  note: string;
  icon: typeof BrainCircuit;
}> = [
  { id: "overview", label: "成长总览", note: "路线与证据", icon: BarChart3 },
  { id: "diagnostic", label: "基础诊断", note: "20 分钟", icon: BrainCircuit },
  { id: "code", label: "代码教练", note: "Python 静态检查", icon: Code2 },
  { id: "project", label: "项目实训", note: "原子任务", icon: FlaskConical },
  {
    id: "interview",
    label: "项目答辩",
    note: "真实表达",
    icon: MessageSquareText,
  },
];

const directionOptions: Array<{ value: ProgrammingDirection; label: string }> =
  [
    { value: "computer_science_exploration", label: "计算机科学探索" },
    { value: "artificial_intelligence", label: "人工智能体验" },
    { value: "data_science", label: "数据科学体验" },
    { value: "software_engineering", label: "软件工程与项目" },
    { value: "algorithm_advanced", label: "算法与信息学拔高" },
  ];

async function loadDashboard() {
  loading.value = true;
  error.value = "";
  try {
    dashboard.value = await fetchProgrammingDashboard();
    if (dashboard.value.profile.configured) {
      const value = dashboard.value.profile;
      profileForm.learning_mode = value.learning_mode;
      profileForm.target_direction = value.target_direction;
      profileForm.weekly_available_minutes = value.weekly_available_minutes;
      profileForm.max_session_minutes = value.max_session_minutes;
      profileForm.exam_period = value.exam_period;
      profileForm.programming_months = value.programming_months;
      profileForm.project_count = value.project_count;
      profileForm.interestsText = value.interests.join("、");
    }
  } catch (reason) {
    error.value =
      reason instanceof Error ? reason.message : "编程成长空间加载失败";
  } finally {
    loading.value = false;
  }
}

function notify(message: string) {
  toast.value = message;
  window.setTimeout(() => {
    toast.value = "";
  }, 2600);
}

async function saveProfile() {
  actionLoading.value = true;
  error.value = "";
  try {
    await updateProgrammingProfile({
      learning_mode: profileForm.learning_mode,
      target_direction: profileForm.target_direction,
      weekly_available_minutes: profileForm.weekly_available_minutes,
      max_session_minutes: profileForm.max_session_minutes,
      exam_period: profileForm.exam_period,
      programming_months: profileForm.programming_months,
      project_count: profileForm.project_count,
      interests: profileForm.interestsText
        .split(/[、,，]/)
        .map((item) => item.trim())
        .filter(Boolean),
    });
    await loadDashboard();
    activeTab.value = "diagnostic";
    notify("16 周编程成长路线已生成");
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "画像保存失败";
  } finally {
    actionLoading.value = false;
  }
}

async function startDiagnostic() {
  actionLoading.value = true;
  error.value = "";
  try {
    diagnostic.value = await createProgrammingDiagnostic();
    diagnosticResult.value = null;
    Object.keys(diagnosticAnswers).forEach(
      (key) => delete diagnosticAnswers[key],
    );
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "诊断创建失败";
  } finally {
    actionLoading.value = false;
  }
}

async function submitDiagnostic() {
  if (!diagnostic.value) return;
  const complete = diagnostic.value.questions.every(
    (item) => diagnosticAnswers[item.question_id] !== undefined,
  );
  if (!complete) {
    error.value = "请完成全部 5 道题后再提交";
    return;
  }
  actionLoading.value = true;
  error.value = "";
  try {
    diagnosticResult.value = await submitProgrammingDiagnostic(
      diagnostic.value.diagnostic_id,
      diagnostic.value.questions.map((item) => ({
        question_id: item.question_id,
        selected_option: diagnosticAnswers[item.question_id],
        confidence: diagnosticConfidence.value,
      })),
    );
    await loadDashboard();
    notify("诊断证据已写入成长档案");
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "诊断提交失败";
  } finally {
    actionLoading.value = false;
  }
}

async function runCodeReview() {
  actionLoading.value = true;
  error.value = "";
  try {
    codeReview.value = await reviewProgrammingCode({
      ...codeForm,
      teacher_authorized: false,
    });
    await loadDashboard();
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "代码检查失败";
  } finally {
    actionLoading.value = false;
  }
}

async function createProject() {
  actionLoading.value = true;
  error.value = "";
  try {
    project.value = await recommendProgrammingProject({
      interest: projectInterest.value,
      available_weeks: projectWeeks.value,
      use_for_portfolio: true,
    });
    selectedTask.value = project.value.milestones[0]?.tasks[0] || null;
    hintHistory.value = [];
    projectHint.value = null;
    await loadDashboard();
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "项目推荐失败";
  } finally {
    actionLoading.value = false;
  }
}

async function getProjectHint() {
  if (!project.value || !selectedTask.value) return;
  actionLoading.value = true;
  error.value = "";
  try {
    projectHint.value = await requestProgrammingProjectHint(
      project.value.project_instance_id,
      {
        task_id: selectedTask.value.task_id,
        observed_problem: projectProblem.value,
        previous_hint_levels: hintHistory.value,
        max_allowed_level: 4,
        review_stage: false,
        teacher_authorized: false,
      },
    );
    hintHistory.value.push(projectHint.value.hint_level);
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "提示获取失败";
  } finally {
    actionLoading.value = false;
  }
}

async function startInterview() {
  actionLoading.value = true;
  error.value = "";
  try {
    interview.value = await createProgrammingInterview();
    interviewAnswer.value = "";
    interviewScore.value = null;
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "答辩训练创建失败";
  } finally {
    actionLoading.value = false;
  }
}

async function submitInterviewAnswer() {
  if (!interview.value || !currentInterviewQuestion.value) return;
  actionLoading.value = true;
  error.value = "";
  try {
    interviewScore.value = await scoreProgrammingInterviewAnswer(
      interview.value.session_id,
      {
        question_id: currentInterviewQuestion.value.question_id,
        answer_text: interviewAnswer.value,
      },
    );
    await loadDashboard();
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "回答评分失败";
  } finally {
    actionLoading.value = false;
  }
}

function percent(value: number) {
  return `${Math.round(value * 100)}%`;
}

function severityLabel(value: string) {
  return (
    { high: "优先修复", medium: "需要检查", low: "优化建议" }[value] || value
  );
}

onMounted(loadDashboard);
</script>

<template>
  <div class="programming-workspace">
    <section v-if="loading" class="programming-state">
      <LoaderCircle class="spin" :size="28" />
      <strong>正在恢复你的编程成长档案</strong>
      <p>读取路线、项目与学习证据…</p>
    </section>

    <template v-else-if="dashboard">
      <section class="programming-hero">
        <div class="hero-copy">
          <span class="hero-kicker"
            ><TerminalSquare :size="15" /> 第六 Agent · 学生端</span
          >
          <h1>把“想学编程”变成<br /><em>每周都能完成的小成果</em></h1>
          <p>
            面向全国一卷高中生的 Python 成长空间。先建立真实证据，再规划路线；
            考试期自动减量，不用一次失败定义能力。
          </p>
          <div class="hero-badges">
            <span><ShieldCheck :size="15" /> 默认不泄露完整作业答案</span>
            <span
              ><Clock3 :size="15" /> 单次最多
              {{ dashboard.profile.max_session_minutes }} 分钟</span
            >
            <span
              ><BookOpenCheck :size="15" /> 知识版本
              {{ dashboard.knowledge.content_version }}</span
            >
          </div>
        </div>
        <div class="hero-terminal" aria-label="Python 学习路径示意">
          <header><i /><i /><i /><span>growth.py</span></header>
          <pre><b>goal</b> = <q>"做出真实作品"</q>
<b>path</b> = [
  <q>"理解问题"</q>,
  <q>"写出最小步骤"</q>,
  <q>"测试边界"</q>,
  <q>"解释与复盘"</q>,
]
<span>print</span>(<q>"今天只推进一步 ✓"</q>)</pre>
          <footer>
            <i /><span>Python · 静态检查模式</span><CheckCircle2 :size="15" />
          </footer>
        </div>
      </section>

      <div v-if="error" class="programming-alert">
        <CircleAlert :size="18" /><span>{{ error }}</span>
        <button @click="error = ''">关闭</button>
      </div>

      <section v-if="!configured" class="onboarding-card">
        <div class="section-heading">
          <span><Compass :size="22" /></span>
          <div>
            <small>最少必要信息</small>
            <h2>先定一个不挤占主科学习的起点</h2>
            <p>这些信息只用于编程学习路线和负荷控制，不做智力或前途判断。</p>
          </div>
        </div>
        <div class="profile-grid">
          <label>
            <span>当前模式</span>
            <select v-model="profileForm.learning_mode">
              <option value="beginner">零基础入门</option>
              <option value="advanced">有基础拔高</option>
            </select>
          </label>
          <label>
            <span>探索方向</span>
            <select v-model="profileForm.target_direction">
              <option
                v-for="item in directionOptions"
                :key="item.value"
                :value="item.value"
              >
                {{ item.label }}
              </option>
            </select>
          </label>
          <label>
            <span>每周可用时间</span>
            <div class="range-value">
              {{ profileForm.weekly_available_minutes }} 分钟
            </div>
            <input
              v-model.number="profileForm.weekly_available_minutes"
              type="range"
              min="30"
              max="360"
              step="30"
            />
          </label>
          <label>
            <span>单次最长时间</span>
            <select v-model.number="profileForm.max_session_minutes">
              <option :value="20">20 分钟</option>
              <option :value="30">30 分钟</option>
              <option :value="40">40 分钟</option>
              <option :value="60">60 分钟</option>
            </select>
          </label>
          <label>
            <span>接触编程（月）</span>
            <input
              v-model.number="profileForm.programming_months"
              type="number"
              min="0"
              max="120"
            />
          </label>
          <label>
            <span>已完成项目数</span>
            <input
              v-model.number="profileForm.project_count"
              type="number"
              min="0"
              max="50"
            />
          </label>
          <label class="wide">
            <span>兴趣方向（用顿号分隔）</span>
            <input
              v-model="profileForm.interestsText"
              placeholder="学习工具、数据分析、英语"
            />
          </label>
          <label class="exam-toggle wide">
            <input v-model="profileForm.exam_period" type="checkbox" />
            <span
              ><b>当前处于考试密集期</b
              ><small
                >开启后每周自动降至不超过 90 分钟，新知识比例降至 20%</small
              ></span
            >
          </label>
        </div>
        <button
          class="primary-action"
          :disabled="actionLoading"
          @click="saveProfile"
        >
          <LoaderCircle v-if="actionLoading" class="spin" :size="18" />
          <Route v-else :size="18" />
          生成 16 周成长路线
        </button>
      </section>

      <template v-else>
        <nav class="programming-tabs">
          <button
            v-for="item in tabs"
            :key="item.id"
            :class="{ active: activeTab === item.id }"
            @click="activeTab = item.id"
          >
            <component :is="item.icon" :size="19" />
            <span
              ><b>{{ item.label }}</b
              ><small>{{ item.note }}</small></span
            >
          </button>
        </nav>

        <template v-if="activeTab === 'overview'">
          <div class="metric-grid">
            <article>
              <span><Target :size="20" /></span>
              <div>
                <small>探索方向</small
                ><strong>{{ dashboard.major_direction.label }}</strong>
              </div>
            </article>
            <article>
              <span><Clock3 :size="20" /></span>
              <div>
                <small>本周建议</small
                ><strong
                  >{{ dashboard.profile.effective_weekly_minutes }} 分钟</strong
                >
              </div>
            </article>
            <article>
              <span><FileCheck2 :size="20" /></span>
              <div>
                <small>有效证据</small
                ><strong>{{ report?.evidence_count || 0 }} 条</strong>
              </div>
            </article>
            <article>
              <span><Gauge :size="20" /></span>
              <div>
                <small>证据覆盖</small><strong>{{ evidenceCoverage }}%</strong>
              </div>
            </article>
          </div>

          <section
            v-if="dashboard.profile.exam_period"
            class="exam-load-banner"
          >
            <ShieldCheck :size="22" />
            <div>
              <strong>考试期降载已开启</strong>
              <p>
                {{
                  roadmap?.exam_period_adjustment.reason
                }}；恢复条件：考试结束且连续一周负荷正常。
              </p>
            </div>
            <span
              >新知识
              {{
                percent(
                  roadmap?.exam_period_adjustment.new_knowledge_ratio || 0,
                )
              }}</span
            >
          </section>

          <div class="overview-layout">
            <section class="content-card roadmap-card">
              <div class="card-title">
                <div>
                  <small>12—20 周范围内</small>
                  <h2>你的 16 周成长路线</h2>
                </div>
                <span><Route :size="16" /> 每 4 周复盘</span>
              </div>
              <div class="roadmap-list">
                <article
                  v-for="stage in roadmap?.stages || []"
                  :key="stage.stage"
                >
                  <span class="stage-index">0{{ stage.stage }}</span>
                  <div>
                    <small>{{ stage.weeks }}</small>
                    <h3>{{ stage.title }}</h3>
                    <p>{{ stage.focus.join(" · ") }}</p>
                    <footer>
                      <Check :size="14" />{{ stage.weekly_output }}
                    </footer>
                  </div>
                </article>
              </div>
            </section>

            <aside class="overview-side">
              <section class="content-card next-card">
                <span><Sparkles :size="20" /></span>
                <small>Agent 建议下一步</small>
                <h3>{{ report?.next_step }}</h3>
                <button
                  @click="
                    activeTab = dashboard.skill_states.length
                      ? 'code'
                      : 'diagnostic'
                  "
                >
                  现在开始 <ArrowRight :size="15" />
                </button>
              </section>
              <section class="content-card evidence-card">
                <div class="card-title">
                  <div>
                    <small>基于学习证据</small>
                    <h2>能力节点</h2>
                  </div>
                </div>
                <div v-if="dashboard.skill_states.length" class="skill-list">
                  <article
                    v-for="skill in dashboard.skill_states.slice(0, 6)"
                    :key="skill.skill_id"
                  >
                    <div>
                      <strong>{{ skill.label }}</strong
                      ><span
                        >{{ skill.level }} ·
                        {{ skill.evidence_count }} 条证据</span
                      >
                    </div>
                    <i><b :style="{ width: percent(skill.mastery) }" /></i>
                  </article>
                </div>
                <div v-else class="empty-mini">
                  <BrainCircuit :size="28" />
                  <p>
                    完成基础诊断后显示第一批能力证据，不用自评分冒充掌握度。
                  </p>
                </div>
              </section>
            </aside>
          </div>
        </template>

        <template v-else-if="activeTab === 'diagnostic'">
          <section class="tool-header">
            <div>
              <span class="tool-icon violet"><BrainCircuit :size="24" /></span>
              <div>
                <small>低门槛诊断</small>
                <h2>用 5 个微任务找到合适起点</h2>
                <p>
                  覆盖规则推理、流程、代码阅读、循环与验证；单次结果不决定能力。
                </p>
              </div>
            </div>
            <button
              v-if="!diagnostic || diagnosticResult"
              class="primary-action compact"
              :disabled="actionLoading"
              @click="startDiagnostic"
            >
              <Play :size="17" />{{
                diagnosticResult ? "重新诊断" : "开始诊断"
              }}
            </button>
          </section>
          <section v-if="!diagnostic" class="diagnostic-intro content-card">
            <div>
              <strong>约 20 分钟</strong><small>不会要求先配置开发环境</small>
            </div>
            <div>
              <strong>5 个维度</strong
              ><small>错误会变成学习任务，不是负面标签</small>
            </div>
            <div>
              <strong>答案保护</strong><small>提交前不暴露正确选项</small>
            </div>
          </section>
          <section v-else-if="!diagnosticResult" class="question-stack">
            <article
              v-for="(question, index) in diagnostic.questions"
              :key="question.question_id"
              class="question-card"
            >
              <header>
                <span>0{{ index + 1 }}</span>
                <div>
                  <small>{{ question.dimension }}</small>
                  <h3>{{ question.prompt }}</h3>
                </div>
              </header>
              <div class="option-grid">
                <label
                  v-for="(option, optionIndex) in question.options"
                  :key="option"
                >
                  <input
                    v-model="diagnosticAnswers[question.question_id]"
                    type="radio"
                    :name="question.question_id"
                    :value="optionIndex"
                  />
                  <span
                    ><b>{{ String.fromCharCode(65 + optionIndex) }}</b
                    >{{ option }}</span
                  >
                </label>
              </div>
            </article>
            <div class="submit-strip">
              <label
                >作答把握
                <select v-model.number="diagnosticConfidence">
                  <option :value="0.9">比较确定</option>
                  <option :value="0.7">一般</option>
                  <option :value="0.45">不太确定</option>
                </select>
              </label>
              <button
                class="primary-action compact"
                :disabled="actionLoading"
                @click="submitDiagnostic"
              >
                <LoaderCircle
                  v-if="actionLoading"
                  class="spin"
                  :size="17"
                /><CheckCircle2 v-else :size="17" />提交并生成起点
              </button>
            </div>
          </section>
          <section v-else class="result-card">
            <div class="result-score">
              <span>{{ Math.round(diagnosticResult.score * 100) }}</span
              ><small>本次诊断分</small>
            </div>
            <div>
              <small>建议起点</small>
              <h2>{{ diagnosticResult.conclusion.starting_point }}</h2>
              <p>{{ diagnosticResult.conclusion.next }}</p>
              <em>仅用于安排下一步，不是专业适配或潜力结论。</em>
            </div>
          </section>
        </template>

        <template v-else-if="activeTab === 'code'">
          <section class="tool-header">
            <div>
              <span class="tool-icon cyan"><Code2 :size="24" /></span>
              <div>
                <small>Python 代码教练</small>
                <h2>先定位根因，再给最小必要提示</h2>
                <p>
                  首期只做静态分析；没有进入隔离沙箱时，绝不会声称代码运行成功。
                </p>
              </div>
            </div>
          </section>
          <div class="code-layout">
            <section class="content-card code-editor-card">
              <label
                ><span>题目要求</span
                ><input v-model="codeForm.problem_statement"
              /></label>
              <div class="two-fields">
                <label
                  ><span>预期结果</span
                  ><input v-model="codeForm.expected_behavior"
                /></label>
                <label
                  ><span>观察到的问题</span
                  ><input v-model="codeForm.observed_problem"
                /></label>
              </div>
              <label
                ><span>Python 代码</span
                ><textarea v-model="codeForm.code" spellcheck="false" />
              </label>
              <footer>
                <label class="hint-select"
                  >提示等级
                  <select v-model.number="codeForm.hint_level">
                    <option
                      v-for="level in 5"
                      :key="level - 1"
                      :value="level - 1"
                    >
                      H{{ level - 1 }}
                    </option>
                    <option :value="5">H5（仅复盘）</option>
                  </select>
                </label>
                <label class="review-check"
                  ><input v-model="codeForm.review_stage" type="checkbox" />
                  已进入复盘阶段</label
                >
                <button
                  class="primary-action compact"
                  :disabled="actionLoading"
                  @click="runCodeReview"
                >
                  <LoaderCircle
                    v-if="actionLoading"
                    class="spin"
                    :size="17"
                  /><TerminalSquare v-else :size="17" />开始静态检查
                </button>
              </footer>
            </section>
            <section class="content-card review-panel">
              <template v-if="codeReview">
                <div class="execution-note">
                  <ShieldCheck :size="17" /><span
                    ><strong>未执行代码</strong
                    >{{ codeReview.execution.reason }}</span
                  >
                </div>
                <div class="finding-list">
                  <article
                    v-for="finding in codeReview.findings"
                    :key="finding.finding_id"
                    :class="finding.severity"
                  >
                    <span>第 {{ finding.line_start }} 行</span>
                    <div>
                      <small>{{ severityLabel(finding.severity) }}</small>
                      <p>{{ finding.message }}</p>
                    </div>
                  </article>
                  <article v-if="!codeReview.findings.length" class="clear">
                    <CheckCircle2 :size="20" />
                    <div>
                      <small>未发现明显静态问题</small>
                      <p>仍需用普通、边界和异常样例验证实际行为。</p>
                    </div>
                  </article>
                </div>
                <div class="hint-box">
                  <span>H{{ codeReview.next_hint.hint_level }}</span>
                  <div>
                    <small>下一步提示</small>
                    <p>{{ codeReview.next_hint.content }}</p>
                  </div>
                </div>
                <div class="validation-list">
                  <strong>验证清单</strong>
                  <p v-for="item in codeReview.validation_plan" :key="item">
                    <Check :size="14" />{{ item }}
                  </p>
                </div>
              </template>
              <div v-else class="panel-empty">
                <Lightbulb :size="34" />
                <h3>分析结果会出现在这里</h3>
                <p>系统优先解释“为什么”，不会只贴一份修改后的完整代码。</p>
              </div>
            </section>
          </div>
        </template>

        <template v-else-if="activeTab === 'project'">
          <section class="tool-header">
            <div>
              <span class="tool-icon amber"><FlaskConical :size="24" /></span>
              <div>
                <small>项目实训</small>
                <h2>每个任务 20—90 分钟，并且可以独立验收</h2>
                <p>
                  项目包含问题分析、代码、验证、说明和展示，不用企业项目复杂度要求高中生。
                </p>
              </div>
            </div>
          </section>
          <section class="project-picker content-card">
            <label
              ><span>我感兴趣的场景</span
              ><select v-model="projectInterest">
                <option>学习工具</option>
                <option>英语</option>
                <option>数据分析</option>
                <option>物理</option>
                <option>网页</option>
                <option>校园</option>
              </select></label
            >
            <label
              ><span>可用周期</span
              ><select v-model.number="projectWeeks">
                <option :value="3">3 周</option>
                <option :value="4">4 周</option>
                <option :value="5">5 周</option>
                <option :value="6">6 周</option>
              </select></label
            >
            <button
              class="primary-action compact"
              :disabled="actionLoading"
              @click="createProject"
            >
              <Sparkles :size="17" />推荐并拆解项目
            </button>
          </section>
          <div v-if="project" class="project-layout">
            <section class="content-card milestones-card">
              <div class="project-title">
                <div>
                  <small
                    >{{ project.duration_weeks }} 周 ·
                    {{ project.estimated_total_minutes }} 分钟</small
                  >
                  <h2>{{ project.title }}</h2>
                  <p>{{ project.cross_subject_links.join(" × ") }}</p>
                </div>
                <span>难度 {{ project.difficulty }}</span>
              </div>
              <article
                v-for="(milestone, index) in project.milestones"
                :key="milestone.milestone_id"
                class="milestone"
              >
                <header>
                  <span>M{{ index + 1 }}</span>
                  <div>
                    <h3>{{ milestone.title }}</h3>
                    <small>{{ milestone.acceptance }}</small>
                  </div>
                </header>
                <button
                  v-for="task in milestone.tasks"
                  :key="task.task_id"
                  :class="{ selected: selectedTask?.task_id === task.task_id }"
                  @click="selectedTask = task"
                >
                  <CheckCircle2 :size="16" /><span
                    ><b>{{ task.title }}</b
                    ><small
                      >{{ task.estimated_minutes }} 分钟 ·
                      {{ task.acceptance_criteria[0] }}</small
                    ></span
                  ><ChevronRight :size="16" />
                </button>
              </article>
            </section>
            <aside class="content-card task-coach">
              <template v-if="selectedTask">
                <small>当前原子任务</small>
                <h2>{{ selectedTask.title }}</h2>
                <div class="task-meta">
                  <span
                    ><Clock3 :size="14" />{{
                      selectedTask.estimated_minutes
                    }}
                    分钟</span
                  ><span
                    ><Target :size="14" />{{
                      selectedTask.required_skills.length
                    }}
                    个能力节点</span
                  >
                </div>
                <strong>验收标准</strong>
                <p v-for="item in selectedTask.acceptance_criteria" :key="item">
                  <Check :size="14" />{{ item }}
                </p>
                <label
                  ><span>你卡在哪里？</span
                  ><textarea v-model="projectProblem" />
                </label>
                <button
                  class="secondary-action"
                  :disabled="actionLoading"
                  @click="getProjectHint"
                >
                  <Lightbulb :size="16" />获取下一层最小提示
                </button>
                <div v-if="projectHint" class="project-hint">
                  <span>H{{ projectHint.hint_level }}</span>
                  <p>{{ projectHint.hint }}</p>
                  <small>{{ projectHint.verification_action }}</small>
                </div>
              </template>
            </aside>
          </div>
          <section v-else class="project-empty content-card">
            <Route :size="34" />
            <h3>从一个真实、可完成的问题开始</h3>
            <p>选择兴趣与周期，Agent 会生成有验收标准的里程碑和原子任务。</p>
          </section>
        </template>

        <template v-else>
          <section class="tool-header">
            <div>
              <span class="tool-icon rose"
                ><MessageSquareText :size="24"
              /></span>
              <div>
                <small>项目陈述与高校专业探索</small>
                <h2>练习真实表达，不背诵虚构模板</h2>
                <p>
                  从切题、逻辑、准确、证据、反思、表达和时间控制七个维度给反馈。
                </p>
              </div>
            </div>
            <button
              v-if="!interview"
              class="primary-action compact"
              :disabled="actionLoading"
              @click="startInterview"
            >
              <Play :size="17" />开始 15 分钟模拟
            </button>
          </section>
          <section v-if="!interview" class="interview-intro content-card">
            <Trophy :size="38" />
            <h2>你不需要“完美经历”</h2>
            <p>
              没有获奖或完整项目也可以诚实说明当前探索；系统不会替你补写奖项、数据或个人贡献。
            </p>
          </section>
          <div v-else class="interview-layout">
            <section class="content-card interview-question">
              <span>问题 01 · {{ currentInterviewQuestion?.topic }}</span>
              <h2>{{ currentInterviewQuestion?.prompt }}</h2>
              <div class="structure-guide">
                <strong>建议结构</strong>
                <p>背景 → 问题 → 我的任务 → 解决过程 → 结果验证 → 反思改进</p>
              </div>
              <textarea
                v-model="interviewAnswer"
                placeholder="请只写自己的真实经历。如果尚未做过项目，可以说明你准备从什么问题开始，以及如何验证。"
              />
              <button
                class="primary-action compact"
                :disabled="actionLoading || interviewAnswer.length < 5"
                @click="submitInterviewAnswer"
              >
                <MessageSquareText :size="17" />提交回答并获得反馈
              </button>
            </section>
            <aside class="content-card interview-feedback">
              <template v-if="interviewScore">
                <div class="interview-score">
                  <span>{{
                    Math.round(interviewScore.overall_score * 100)
                  }}</span
                  ><small>训练评分</small>
                </div>
                <div class="dimension-list">
                  <p
                    v-for="(value, key) in interviewScore.dimension_scores"
                    :key="key"
                  >
                    <span>{{ key }}</span
                    ><i><b :style="{ width: percent(value) }" /></i
                    ><em>{{ Math.round(value * 100) }}</em>
                  </p>
                </div>
                <strong>下一轮追问</strong>
                <p>{{ interviewScore.recommended_followup }}</p>
                <div class="authenticity">
                  <ShieldCheck :size="16" />{{
                    interviewScore.authenticity_notice
                  }}
                </div>
              </template>
              <div v-else class="panel-empty">
                <BarChart3 :size="32" />
                <h3>七维反馈</h3>
                <p>
                  提交后会显示维度分、证据缺口与相关追问；单次训练不决定专业适配。
                </p>
              </div>
            </aside>
          </div>
        </template>
      </template>
    </template>

    <Transition name="toast">
      <div v-if="toast" class="programming-toast">
        <CheckCircle2 :size="17" />{{ toast }}
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.programming-workspace {
  --ink: #182334;
  --muted: #6e7b8e;
  --line: #e4e9f0;
  --paper: #fff;
  --blue: #2357d7;
  --blue-dark: #17398d;
  min-height: 100%;
  color: var(--ink);
}
.programming-state {
  min-height: 520px;
  display: grid;
  place-content: center;
  justify-items: center;
  gap: 8px;
  color: var(--muted);
}
.programming-state strong {
  color: var(--ink);
  font-size: 18px;
}
.programming-state p {
  margin: 0;
}
.spin {
  animation: spin 0.9s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
.programming-hero {
  position: relative;
  overflow: hidden;
  display: grid;
  grid-template-columns: minmax(0, 1.22fr) minmax(340px, 0.78fr);
  gap: 42px;
  padding: 48px;
  border-radius: 26px;
  background: linear-gradient(128deg, #11295f, #1c4bbd 58%, #3775ef);
  color: white;
  box-shadow: 0 18px 48px rgba(25, 64, 150, 0.2);
}
.programming-hero::before {
  content: "";
  position: absolute;
  width: 420px;
  height: 420px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 50%;
  right: -140px;
  top: -230px;
}
.hero-copy {
  position: relative;
  z-index: 1;
}
.hero-kicker {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 7px 11px;
  border: 1px solid rgba(255, 255, 255, 0.24);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.1);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.05em;
}
.hero-copy h1 {
  margin: 20px 0 14px;
  font-size: clamp(30px, 3vw, 47px);
  line-height: 1.14;
  letter-spacing: -0.04em;
}
.hero-copy h1 em {
  color: #a9d4ff;
  font-style: normal;
}
.hero-copy > p {
  max-width: 720px;
  margin: 0;
  color: rgba(255, 255, 255, 0.78);
  line-height: 1.85;
}
.hero-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 9px;
  margin-top: 24px;
}
.hero-badges span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 10px;
  border-radius: 9px;
  background: rgba(8, 20, 52, 0.28);
  color: rgba(255, 255, 255, 0.86);
  font-size: 12px;
}
.hero-terminal {
  align-self: center;
  position: relative;
  z-index: 1;
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.16);
  border-radius: 15px;
  background: #0c1830;
  box-shadow: 0 22px 45px rgba(4, 12, 30, 0.34);
  transform: rotate(1.2deg);
}
.hero-terminal header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 11px 14px;
  background: #152542;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}
.hero-terminal header i {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: #ff6d68;
}
.hero-terminal header i:nth-child(2) {
  background: #ffc85a;
}
.hero-terminal header i:nth-child(3) {
  background: #52d68a;
}
.hero-terminal header span {
  margin-left: 7px;
  color: #8094b8;
  font: 11px monospace;
}
.hero-terminal pre {
  margin: 0;
  padding: 23px;
  color: #aab8d2;
  font:
    13px/1.8 ui-monospace,
    SFMono-Regular,
    Menlo,
    monospace;
  white-space: pre-wrap;
}
.hero-terminal pre b {
  color: #7cc7ff;
}
.hero-terminal pre q {
  color: #a9e2b8;
}
.hero-terminal pre span {
  color: #d6a5ff;
}
.hero-terminal footer {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 10px 14px;
  background: #101f39;
  color: #8fa3c5;
  font-size: 11px;
}
.hero-terminal footer i {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #45d27e;
  box-shadow: 0 0 0 4px rgba(69, 210, 126, 0.12);
}
.hero-terminal footer svg {
  margin-left: auto;
  color: #45d27e;
}
.programming-alert {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 16px;
  padding: 13px 16px;
  border: 1px solid #f4caca;
  border-radius: 11px;
  background: #fff5f5;
  color: #a43a3a;
  font-size: 13px;
}
.programming-alert button {
  margin-left: auto;
  border: 0;
  background: transparent;
  color: inherit;
  cursor: pointer;
}
.onboarding-card,
.content-card {
  border: 1px solid var(--line);
  border-radius: 18px;
  background: var(--paper);
  box-shadow: 0 8px 24px rgba(25, 42, 68, 0.045);
}
.onboarding-card {
  margin-top: 20px;
  padding: 30px;
}
.section-heading {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding-bottom: 23px;
  border-bottom: 1px solid var(--line);
}
.section-heading > span {
  display: grid;
  place-items: center;
  width: 46px;
  height: 46px;
  border-radius: 13px;
  color: var(--blue);
  background: #edf3ff;
}
.section-heading small,
.card-title small,
.tool-header small,
.project-title small {
  color: var(--blue);
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.section-heading h2,
.card-title h2,
.tool-header h2,
.project-title h2 {
  margin: 4px 0 5px;
  font-size: 22px;
  letter-spacing: -0.02em;
}
.section-heading p,
.tool-header p,
.project-title p {
  margin: 0;
  color: var(--muted);
  line-height: 1.6;
}
.profile-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 18px;
  margin: 24px 0;
}
.profile-grid label,
.code-editor-card label,
.project-picker label,
.task-coach label {
  display: grid;
  gap: 7px;
  color: #4f5d70;
  font-size: 12px;
  font-weight: 700;
}
.profile-grid input:not([type="checkbox"]),
.profile-grid select,
.code-editor-card input,
.code-editor-card select,
.project-picker select,
.task-coach textarea {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid #d9e0ea;
  border-radius: 9px;
  background: #fbfcfe;
  padding: 11px 12px;
  color: var(--ink);
  outline: none;
}
.profile-grid input:focus,
.profile-grid select:focus,
.code-editor-card input:focus,
.task-coach textarea:focus {
  border-color: #79a0ed;
  box-shadow: 0 0 0 3px rgba(46, 100, 214, 0.1);
}
.profile-grid .wide {
  grid-column: span 2;
}
.range-value {
  color: var(--ink);
  font-size: 14px;
}
.profile-grid input[type="range"] {
  accent-color: var(--blue);
}
.exam-toggle {
  display: flex !important;
  flex-direction: row;
  align-items: center;
  padding: 10px 13px;
  border: 1px solid #dbe5f6;
  border-radius: 10px;
  background: #f7faff;
}
.exam-toggle input {
  width: 17px;
  height: 17px;
  accent-color: var(--blue);
}
.exam-toggle span {
  display: grid;
  gap: 2px;
}
.exam-toggle small {
  color: var(--muted);
  font-weight: 500;
}
.primary-action,
.secondary-action {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border: 0;
  border-radius: 10px;
  padding: 12px 17px;
  font-weight: 750;
  cursor: pointer;
}
.primary-action {
  color: #fff;
  background: linear-gradient(135deg, #265fdc, #1947b4);
  box-shadow: 0 8px 18px rgba(31, 81, 190, 0.2);
}
.primary-action.compact {
  padding: 10px 14px;
  font-size: 13px;
}
.primary-action:disabled,
.secondary-action:disabled {
  opacity: 0.55;
  cursor: wait;
}
.secondary-action {
  width: 100%;
  color: var(--blue);
  background: #edf3ff;
}
.programming-tabs {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 10px;
  margin: 18px 0;
  padding: 7px;
  border: 1px solid var(--line);
  border-radius: 15px;
  background: #fff;
}
.programming-tabs button {
  display: flex;
  align-items: center;
  gap: 10px;
  border: 0;
  border-radius: 10px;
  padding: 11px;
  color: #657287;
  background: transparent;
  text-align: left;
  cursor: pointer;
}
.programming-tabs button span {
  display: grid;
  gap: 2px;
}
.programming-tabs button b {
  color: #354257;
  font-size: 13px;
}
.programming-tabs button small {
  font-size: 10px;
}
.programming-tabs button.active {
  color: #fff;
  background: var(--blue);
  box-shadow: 0 6px 14px rgba(35, 87, 215, 0.18);
}
.programming-tabs button.active b {
  color: #fff;
}
.programming-tabs button.active small {
  color: rgba(255, 255, 255, 0.7);
}
.metric-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}
.metric-grid article {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 17px;
  border: 1px solid var(--line);
  border-radius: 14px;
  background: #fff;
}
.metric-grid article > span {
  display: grid;
  place-items: center;
  width: 38px;
  height: 38px;
  border-radius: 10px;
  color: var(--blue);
  background: #edf3ff;
}
.metric-grid article div {
  display: grid;
  gap: 4px;
}
.metric-grid small {
  color: var(--muted);
  font-size: 11px;
}
.metric-grid strong {
  font-size: 15px;
}
.exam-load-banner {
  display: flex;
  align-items: center;
  gap: 13px;
  margin-top: 14px;
  padding: 15px 18px;
  border: 1px solid #f2ddb5;
  border-radius: 13px;
  color: #785418;
  background: #fffaf0;
}
.exam-load-banner div {
  flex: 1;
}
.exam-load-banner p {
  margin: 3px 0 0;
  font-size: 12px;
}
.exam-load-banner > span {
  padding: 7px 10px;
  border-radius: 8px;
  background: #fff1cf;
  font-size: 12px;
  font-weight: 800;
}
.overview-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.55fr) minmax(290px, 0.75fr);
  gap: 16px;
  margin-top: 16px;
}
.content-card {
  padding: 22px;
}
.card-title {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 17px;
}
.card-title h2 {
  font-size: 20px;
}
.card-title > span {
  display: inline-flex;
  gap: 6px;
  align-items: center;
  padding: 7px 9px;
  border-radius: 8px;
  color: #52647e;
  background: #f3f6fa;
  font-size: 11px;
}
.roadmap-list {
  display: grid;
}
.roadmap-list article {
  position: relative;
  display: grid;
  grid-template-columns: 44px 1fr;
  gap: 14px;
  padding: 0 0 22px;
}
.roadmap-list article:not(:last-child)::after {
  content: "";
  position: absolute;
  left: 21px;
  top: 40px;
  bottom: 2px;
  width: 1px;
  background: #dce5f4;
}
.stage-index {
  display: grid;
  place-items: center;
  width: 42px;
  height: 42px;
  border-radius: 12px;
  color: #fff;
  background: var(--blue);
  font: 700 12px monospace;
}
.roadmap-list small {
  color: var(--blue);
  font-size: 11px;
  font-weight: 700;
}
.roadmap-list h3 {
  margin: 3px 0 5px;
  font-size: 16px;
}
.roadmap-list p {
  margin: 0;
  color: var(--muted);
  font-size: 12px;
}
.roadmap-list footer {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 9px;
  color: #3d6b4a;
  font-size: 11px;
}
.overview-side {
  display: grid;
  align-content: start;
  gap: 16px;
}
.next-card {
  color: white;
  background: linear-gradient(145deg, #243d82, #265fdc);
  border-color: transparent;
}
.next-card > span {
  display: grid;
  place-items: center;
  width: 39px;
  height: 39px;
  border-radius: 11px;
  background: rgba(255, 255, 255, 0.14);
}
.next-card small {
  display: block;
  margin-top: 20px;
  color: #a9c4ff;
}
.next-card h3 {
  margin: 5px 0 18px;
  line-height: 1.55;
}
.next-card button {
  display: flex;
  align-items: center;
  gap: 6px;
  border: 0;
  padding: 0;
  color: #fff;
  background: transparent;
  font-weight: 700;
  cursor: pointer;
}
.skill-list {
  display: grid;
  gap: 14px;
}
.skill-list article div {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 7px;
}
.skill-list strong {
  font-size: 12px;
}
.skill-list span {
  color: var(--muted);
  font-size: 10px;
}
.skill-list i,
.dimension-list i {
  display: block;
  height: 5px;
  overflow: hidden;
  border-radius: 99px;
  background: #edf0f5;
}
.skill-list i b,
.dimension-list i b {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #2b62db, #6aa4ff);
}
.empty-mini,
.panel-empty,
.project-empty,
.interview-intro {
  display: grid;
  place-items: center;
  gap: 8px;
  padding: 28px 10px;
  color: #8a97a9;
  text-align: center;
}
.empty-mini p,
.panel-empty p,
.project-empty p,
.interview-intro p {
  max-width: 520px;
  margin: 0;
  line-height: 1.65;
  font-size: 12px;
}
.panel-empty h3,
.project-empty h3,
.interview-intro h2 {
  margin: 4px 0 0;
  color: var(--ink);
}
.tool-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 25px 4px 18px;
}
.tool-header > div {
  display: flex;
  align-items: center;
  gap: 14px;
}
.tool-header h2 {
  font-size: 23px;
}
.tool-icon {
  display: grid;
  place-items: center;
  width: 50px;
  height: 50px;
  border-radius: 14px;
}
.tool-icon.violet {
  color: #7155c8;
  background: #f2efff;
}
.tool-icon.cyan {
  color: #0a7599;
  background: #eaf9ff;
}
.tool-icon.amber {
  color: #a66a0b;
  background: #fff6df;
}
.tool-icon.rose {
  color: #b14965;
  background: #fff0f3;
}
.diagnostic-intro {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0;
}
.diagnostic-intro div {
  display: grid;
  gap: 5px;
  padding: 18px;
  text-align: center;
}
.diagnostic-intro div:not(:last-child) {
  border-right: 1px solid var(--line);
}
.diagnostic-intro strong {
  font-size: 19px;
}
.diagnostic-intro small {
  color: var(--muted);
}
.question-stack {
  display: grid;
  gap: 12px;
}
.question-card {
  padding: 22px;
  border: 1px solid var(--line);
  border-radius: 15px;
  background: #fff;
}
.question-card header {
  display: flex;
  gap: 13px;
}
.question-card header > span {
  display: grid;
  place-items: center;
  flex: 0 0 37px;
  height: 37px;
  border-radius: 10px;
  color: var(--blue);
  background: #edf3ff;
  font: 700 11px monospace;
}
.question-card header small {
  color: var(--blue);
  font-size: 10px;
  font-weight: 800;
}
.question-card h3 {
  margin: 4px 0 14px;
  font-size: 15px;
  line-height: 1.6;
}
.option-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
  margin-left: 50px;
}
.option-grid input {
  position: absolute;
  opacity: 0;
}
.option-grid label span {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 10px;
  border: 1px solid #e0e5ed;
  border-radius: 9px;
  color: #4e5b6e;
  font-size: 12px;
  cursor: pointer;
}
.option-grid label b {
  display: grid;
  place-items: center;
  width: 23px;
  height: 23px;
  border-radius: 7px;
  background: #f0f3f8;
}
.option-grid input:checked + span {
  border-color: #5e8ce9;
  color: #1e4da9;
  background: #f3f7ff;
}
.option-grid input:checked + span b {
  color: white;
  background: var(--blue);
}
.submit-strip {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 14px;
  padding: 15px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: #fff;
}
.submit-strip label {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--muted);
  font-size: 12px;
}
.submit-strip select {
  border: 1px solid #dbe1ea;
  border-radius: 8px;
  padding: 8px;
}
.result-card {
  display: flex;
  align-items: center;
  gap: 24px;
  padding: 30px;
  border: 1px solid #cfe0ff;
  border-radius: 18px;
  background: linear-gradient(120deg, #f8faff, #eef4ff);
}
.result-score {
  display: grid;
  place-items: center;
  flex: 0 0 120px;
  height: 120px;
  border-radius: 50%;
  color: white;
  background: var(--blue);
}
.result-score span {
  font-size: 38px;
  font-weight: 850;
}
.result-score small {
  margin-top: -15px;
  color: #cfe0ff;
}
.result-card h2 {
  margin: 4px 0;
}
.result-card p {
  color: var(--muted);
}
.result-card em {
  color: #8b641e;
  font-size: 12px;
  font-style: normal;
}
.code-layout,
.project-layout,
.interview-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(330px, 0.85fr);
  gap: 16px;
}
.code-editor-card {
  display: grid;
  gap: 15px;
}
.two-fields {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.code-editor-card textarea {
  min-height: 265px;
  resize: vertical;
  border: 1px solid #253551;
  border-radius: 11px;
  padding: 16px;
  color: #d8e6ff;
  background: #111d31;
  font:
    13px/1.7 ui-monospace,
    SFMono-Regular,
    Menlo,
    monospace;
  outline: none;
}
.code-editor-card footer {
  display: flex;
  align-items: center;
  gap: 12px;
}
.code-editor-card footer .primary-action {
  margin-left: auto;
}
.hint-select,
.review-check {
  display: flex !important;
  grid-auto-flow: column;
  align-items: center;
  gap: 7px !important;
}
.hint-select select {
  padding: 8px;
}
.review-check input {
  accent-color: var(--blue);
}
.review-panel {
  min-height: 470px;
}
.execution-note {
  display: flex;
  gap: 9px;
  padding: 11px;
  border-radius: 9px;
  color: #526174;
  background: #f4f7fb;
}
.execution-note span {
  display: grid;
  gap: 2px;
  font-size: 10px;
}
.execution-note strong {
  color: var(--ink);
  font-size: 12px;
}
.finding-list {
  display: grid;
  gap: 9px;
  margin: 14px 0;
}
.finding-list article {
  display: flex;
  gap: 10px;
  padding: 11px;
  border-left: 3px solid #e7a635;
  border-radius: 7px;
  background: #fff9ed;
}
.finding-list article.high {
  border-color: #dc5960;
  background: #fff2f2;
}
.finding-list article.low,
.finding-list article.clear {
  border-color: #4ba473;
  background: #f1fbf5;
}
.finding-list article > span {
  white-space: nowrap;
  color: #7c8796;
  font-size: 10px;
}
.finding-list small {
  font-weight: 800;
}
.finding-list p {
  margin: 3px 0 0;
  font-size: 12px;
  line-height: 1.5;
}
.hint-box {
  display: flex;
  gap: 11px;
  padding: 14px;
  border: 1px solid #d8e4ff;
  border-radius: 11px;
  background: #f4f7ff;
}
.hint-box > span,
.project-hint > span {
  display: grid;
  place-items: center;
  flex: 0 0 35px;
  height: 35px;
  border-radius: 9px;
  color: white;
  background: var(--blue);
  font: 700 11px monospace;
}
.hint-box small {
  color: var(--blue);
  font-weight: 800;
}
.hint-box p {
  margin: 4px 0 0;
  font-size: 12px;
  line-height: 1.6;
}
.validation-list {
  margin-top: 15px;
}
.validation-list > strong {
  font-size: 12px;
}
.validation-list p,
.task-coach > p {
  display: flex;
  gap: 7px;
  margin: 8px 0;
  color: #5b687b;
  font-size: 11px;
}
.project-picker {
  display: flex;
  align-items: end;
  gap: 14px;
  margin-bottom: 16px;
}
.project-picker label {
  flex: 1;
}
.project-picker button {
  margin-left: auto;
}
.milestones-card {
  padding: 0;
  overflow: hidden;
}
.project-title {
  display: flex;
  justify-content: space-between;
  padding: 23px;
  color: white;
  background: linear-gradient(135deg, #1d3978, #2f63d2);
}
.project-title small {
  color: #a9c4ff;
}
.project-title h2 {
  margin-top: 5px;
}
.project-title p {
  color: #cedbfa;
}
.project-title > span {
  align-self: start;
  padding: 7px 9px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.14);
  font-size: 11px;
}
.milestone {
  padding: 18px 22px;
  border-bottom: 1px solid var(--line);
}
.milestone header {
  display: flex;
  gap: 10px;
  margin-bottom: 11px;
}
.milestone header > span {
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  border-radius: 9px;
  color: var(--blue);
  background: #edf3ff;
  font: 700 11px monospace;
}
.milestone h3 {
  margin: 0 0 3px;
  font-size: 14px;
}
.milestone small {
  color: var(--muted);
  font-size: 10px;
}
.milestone button {
  display: flex;
  width: 100%;
  align-items: center;
  gap: 9px;
  margin: 6px 0;
  border: 1px solid transparent;
  border-radius: 9px;
  padding: 9px;
  color: #667487;
  background: #f8f9fb;
  text-align: left;
  cursor: pointer;
}
.milestone button span {
  display: grid;
  flex: 1;
  gap: 2px;
}
.milestone button b {
  color: #354257;
  font-size: 12px;
}
.milestone button.selected {
  border-color: #aac4f5;
  color: var(--blue);
  background: #f2f6ff;
}
.task-coach {
  align-self: start;
  position: sticky;
  top: 12px;
}
.task-coach > small {
  color: var(--blue);
  font-weight: 800;
}
.task-coach h2 {
  margin: 5px 0 10px;
  font-size: 20px;
}
.task-meta {
  display: flex;
  gap: 8px;
  margin-bottom: 18px;
}
.task-meta span {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 8px;
  border-radius: 7px;
  color: #5b6a7f;
  background: #f1f4f8;
  font-size: 10px;
}
.task-coach > strong {
  font-size: 12px;
}
.task-coach textarea {
  min-height: 80px;
  resize: vertical;
}
.task-coach label {
  margin: 18px 0 10px;
}
.project-hint {
  display: flex;
  gap: 10px;
  margin-top: 12px;
  padding: 12px;
  border: 1px solid #d8e3fa;
  border-radius: 10px;
  background: #f5f8ff;
}
.project-hint p {
  margin: 0;
  font-size: 11px;
  line-height: 1.55;
}
.project-hint small {
  display: none;
}
.interview-intro {
  min-height: 260px;
}
.interview-question > span {
  color: var(--blue);
  font-size: 11px;
  font-weight: 800;
}
.interview-question h2 {
  margin: 8px 0 18px;
  font-size: 22px;
  line-height: 1.5;
}
.structure-guide {
  padding: 12px;
  border-left: 3px solid var(--blue);
  border-radius: 0 9px 9px 0;
  background: #f4f7fc;
}
.structure-guide strong {
  font-size: 11px;
}
.structure-guide p {
  margin: 4px 0 0;
  color: var(--muted);
  font-size: 11px;
}
.interview-question textarea {
  width: 100%;
  min-height: 190px;
  box-sizing: border-box;
  margin: 14px 0;
  resize: vertical;
  border: 1px solid #d9e0ea;
  border-radius: 11px;
  padding: 14px;
  color: var(--ink);
  font: inherit;
  line-height: 1.65;
  outline: none;
}
.interview-question .primary-action {
  margin-left: auto;
}
.interview-feedback {
  min-height: 420px;
}
.interview-score {
  display: grid;
  place-items: center;
  width: 100px;
  height: 100px;
  margin: 0 auto 18px;
  border-radius: 50%;
  color: white;
  background: var(--blue);
}
.interview-score span {
  font-size: 31px;
  font-weight: 850;
}
.interview-score small {
  margin-top: -12px;
  color: #d1e0ff;
}
.dimension-list {
  display: grid;
  gap: 8px;
}
.dimension-list p {
  display: grid;
  grid-template-columns: 85px 1fr 28px;
  align-items: center;
  gap: 8px;
  margin: 0;
}
.dimension-list p > span {
  color: #58677b;
  font-size: 10px;
}
.dimension-list em {
  color: #536075;
  font-size: 10px;
  font-style: normal;
}
.interview-feedback > strong {
  display: block;
  margin-top: 18px;
  font-size: 12px;
}
.interview-feedback > p {
  color: #59677a;
  font-size: 12px;
  line-height: 1.6;
}
.authenticity {
  display: flex;
  gap: 7px;
  margin-top: 13px;
  padding: 10px;
  border-radius: 9px;
  color: #3e6b4b;
  background: #f0f9f3;
  font-size: 10px;
  line-height: 1.5;
}
.programming-toast {
  position: fixed;
  z-index: 20;
  right: 24px;
  bottom: 24px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 15px;
  border-radius: 10px;
  color: white;
  background: #173b89;
  box-shadow: 0 10px 30px rgba(20, 50, 110, 0.3);
  font-size: 12px;
}
.toast-enter-active,
.toast-leave-active {
  transition: 0.2s ease;
}
.toast-enter-from,
.toast-leave-to {
  transform: translateY(8px);
  opacity: 0;
}
@media (max-width: 1050px) {
  .programming-hero {
    grid-template-columns: 1fr;
  }
  .hero-terminal {
    display: none;
  }
  .programming-tabs {
    grid-template-columns: repeat(3, 1fr);
  }
  .metric-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  .overview-layout,
  .code-layout,
  .project-layout,
  .interview-layout {
    grid-template-columns: 1fr;
  }
  .task-coach {
    position: static;
  }
  .profile-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
@media (max-width: 680px) {
  .programming-hero {
    padding: 28px 22px;
    border-radius: 18px;
  }
  .hero-copy h1 {
    font-size: 30px;
  }
  .hero-badges span {
    width: 100%;
  }
  .programming-tabs {
    grid-template-columns: 1fr 1fr;
  }
  .metric-grid,
  .profile-grid,
  .diagnostic-intro,
  .option-grid {
    grid-template-columns: 1fr;
  }
  .profile-grid .wide {
    grid-column: auto;
  }
  .overview-layout {
    grid-template-columns: 1fr;
  }
  .tool-header {
    align-items: flex-start;
    flex-direction: column;
  }
  .project-picker {
    align-items: stretch;
    flex-direction: column;
  }
  .code-editor-card footer,
  .submit-strip {
    align-items: stretch;
    flex-direction: column;
  }
  .code-editor-card footer .primary-action {
    margin-left: 0;
  }
  .two-fields {
    grid-template-columns: 1fr;
  }
  .option-grid {
    margin-left: 0;
  }
  .result-card {
    align-items: flex-start;
    flex-direction: column;
  }
  .result-score {
    flex-basis: 120px;
  }
}
</style>
