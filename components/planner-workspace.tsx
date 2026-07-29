"use client";

import {
  ArrowLeft,
  ArrowRight,
  BarChart3,
  BookOpenCheck,
  BrainCircuit,
  CalendarDays,
  Check,
  CheckCircle2,
  ChevronRight,
  CircleAlert,
  Clock3,
  Cloud,
  LayoutDashboard,
  LoaderCircle,
  Menu,
  MessageSquareText,
  RefreshCw,
  Send,
  ShieldCheck,
  Sparkles,
  Target,
  TimerReset,
  TrendingUp,
  X,
} from "lucide-react";
import { FormEvent, useMemo, useState } from "react";

import { callAgent } from "@/lib/agent-client";
import {
  defaultSubjects,
  editionEvidenceLabel,
  getMathEdition,
  getProvinceRoute,
  isSubjectSelectionValid,
  mathEditions,
  progressGroups,
  provinceRoutes,
  provinceSubjectKeys,
  selectProvinceSubject,
  subjectLabels,
} from "@/lib/curriculum-catalog";
import type { AgentEnvelope, LearningPlan, PlannerFormData, SubjectKey } from "@/lib/types";
import styles from "./planner-workspace.module.css";

type View = "workspace" | "plan" | "knowledge" | "feedback";

const navItems: Array<{ key: View; label: string; icon: typeof LayoutDashboard }> = [
  { key: "workspace", label: "规划工作台", icon: LayoutDashboard },
  { key: "plan", label: "我的计划", icon: CalendarDays },
  { key: "knowledge", label: "知识画像", icon: BrainCircuit },
  { key: "feedback", label: "练习反馈", icon: BarChart3 },
];

const steps = ["学习信息", "目标与学情", "时间安排"];

const gradeLabels: Record<PlannerFormData["grade"], string> = {
  grade_10: "高一",
  grade_11: "高二",
  grade_12: "高三",
};

const taskNames: Record<string, string> = {
  concept_repair: "概念修复",
  targeted_practice: "专项训练",
  spaced_review: "间隔复习",
  timed_training: "限时训练",
  stage_assessment: "阶段测评",
};

const initialForm: PlannerFormData = {
  studentId: "student_10001",
  grade: "grade_11",
  schoolTerm: "grade_11_term_1",
  provinceCode: "43",
  targetExamYear: 2027,
  selectedSubjects: ["physics", "chemistry", "biology"],
  curriculumVersion: "people_education_a",
  classProgress: "PEA-E2-C05",
  currentScore: 92,
  targetScore: 120,
  deadline: "2027-05-20",
  weeklyMinutes: 630,
  weekdayMinutes: 70,
  weekendMinutes: 140,
  foundationMastery: 48,
  applicationMastery: 36,
};

function cn(...values: Array<string | false | undefined>) {
  return values.filter(Boolean).join(" ");
}

function formatDate(value: string, withWeekday = false) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    month: "long",
    day: "numeric",
    weekday: withWeekday ? "short" : undefined,
  }).format(date);
}

function minutesLabel(value: number) {
  if (value < 60) return `${value} 分钟`;
  const hours = Math.floor(value / 60);
  const minutes = value % 60;
  return minutes ? `${hours} 小时 ${minutes} 分` : `${hours} 小时`;
}

export function PlannerWorkspace() {
  const [view, setView] = useState<View>("workspace");
  const [step, setStep] = useState(0);
  const [form, setForm] = useState<PlannerFormData>(initialForm);
  const [response, setResponse] = useState<AgentEnvelope | null>(null);
  const [loading, setLoading] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");

  const plan = response?.result?.plan;
  const knowledge = response?.result?.knowledge_profile;
  const mode = response?._meta?.mode;
  const province = getProvinceRoute(form.provinceCode);

  const progress = useMemo(() => {
    if (!plan) return 0;
    return Math.min(100, Math.round((form.currentScore / form.targetScore) * 100));
  }, [form.currentScore, form.targetScore, plan]);

  function update<K extends keyof PlannerFormData>(key: K, value: PlannerFormData[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function selectSubject(key: SubjectKey) {
    setForm((current) => {
      const route = getProvinceRoute(current.provinceCode);
      return {
        ...current,
        selectedSubjects: selectProvinceSubject(route, current.selectedSubjects, key),
      };
    });
  }

  function changeProvince(provinceCode: string) {
    const route = getProvinceRoute(provinceCode);
    setForm((current) => ({
      ...current,
      provinceCode,
      selectedSubjects: defaultSubjects(route),
    }));
  }

  function changeEdition(curriculumVersion: string) {
    const firstProgress = progressGroups(curriculumVersion)[0]?.options[0]?.id || "";
    setForm((current) => ({ ...current, curriculumVersion, classProgress: firstProgress }));
  }

  function showToast(message: string) {
    setToast(message);
    window.setTimeout(() => setToast(""), 3200);
  }

  async function generatePlan() {
    setLoading(true);
    setError("");
    try {
      const result = await callAgent({ action: "initialize", form });
      if (!result.result?.plan) throw new Error("Agent 未返回可展示的计划，请补充信息后重试");
      setResponse(result);
      setView("plan");
      setConfirmed(result.result.plan.status === "active");
      showToast("个性化学习计划已生成");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "生成失败，请稍后重试");
    } finally {
      setLoading(false);
    }
  }

  async function confirmPlan() {
    if (!plan) return;
    setConfirming(true);
    setError("");
    try {
      await callAgent({
        action: "confirm",
        planId: plan.plan_id,
        studentId: form.studentId,
        version: plan.version,
      });
      setConfirmed(true);
      showToast("计划已确认并开始执行");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "确认失败，请稍后重试");
    } finally {
      setConfirming(false);
    }
  }

  function navigate(next: View) {
    if (!plan && next !== "workspace") {
      showToast("请先完成画像并生成学习计划");
      setView("workspace");
    } else {
      setView(next);
    }
    setMenuOpen(false);
  }

  return (
    <div className={styles.shell}>
      <aside className={cn(styles.sidebar, menuOpen && styles.sidebarOpen)}>
        <div className={styles.brand}>
          <img src="/logo-mark.svg" alt="" width={38} height={38} />
          <div><strong>知途</strong><span>智能学习规划</span></div>
          <button className={styles.closeMenu} onClick={() => setMenuOpen(false)} aria-label="关闭菜单"><X size={20} /></button>
        </div>
        <nav className={styles.nav} aria-label="主导航">
          <p>学习空间</p>
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <button key={item.key} className={cn(view === item.key && styles.navActive)} onClick={() => navigate(item.key)}>
                <Icon size={19} strokeWidth={1.9} />
                <span>{item.label}</span>
                {item.key !== "workspace" && !plan && <span className={styles.lockDot} />}
              </button>
            );
          })}
        </nav>
        <div className={styles.agentCard}>
          <div className={styles.agentIcon}><Sparkles size={18} /></div>
          <div><strong>规划 Agent</strong><span>{mode === "live" ? "真实服务已连接" : mode === "demo" ? "演示模式" : "等待生成计划"}</span></div>
          <span className={cn(styles.statusDot, mode === "live" && styles.liveDot)} />
        </div>
        <div className={styles.profile}>
          <span>林</span>
          <div><strong>林同学</strong><small>{gradeLabels[form.grade]} · {province.name}</small></div>
          <ChevronRight size={17} />
        </div>
      </aside>

      {menuOpen && <button className={styles.backdrop} onClick={() => setMenuOpen(false)} aria-label="关闭菜单" />}

      <main className={styles.main}>
        <header className={styles.header}>
          <button className={styles.menuButton} onClick={() => setMenuOpen(true)} aria-label="打开菜单"><Menu size={22} /></button>
          <div>
            <span className={styles.eyebrow}>PERSONALIZED LEARNING PLANNER</span>
            <h1>{view === "workspace" ? "规划工作台" : view === "plan" ? "我的学习计划" : view === "knowledge" ? "知识画像" : "练习反馈"}</h1>
          </div>
          <div className={styles.headerActions}>
            <span className={styles.paperBadge}><ShieldCheck size={15} /> 全国新课标Ⅰ卷 · 2026依据</span>
            <button className={styles.helpButton} aria-label="帮助"><MessageSquareText size={19} /></button>
          </div>
        </header>

        <div className={styles.content}>
          {view === "workspace" && (
            <OnboardingPanel
              form={form}
              step={step}
              loading={loading}
              error={error}
              onStep={setStep}
              onUpdate={update}
              onSubject={selectSubject}
              onProvince={changeProvince}
              onEdition={changeEdition}
              onGenerate={generatePlan}
            />
          )}
          {view === "plan" && plan && (
            <PlanDashboard
              form={form}
              plan={plan}
              knowledge={knowledge}
              progress={progress}
              confirmed={confirmed}
              confirming={confirming}
              mode={mode}
              error={error}
              warnings={response?.warnings || []}
              onConfirm={confirmPlan}
              onEdit={() => { setView("workspace"); setStep(1); }}
              onFeedback={() => setView("feedback")}
            />
          )}
          {view === "knowledge" && plan && <KnowledgePanel response={response} />}
          {view === "feedback" && plan && (
            <FeedbackPanel form={form} plan={plan} onSuccess={(message) => showToast(message)} />
          )}
        </div>
      </main>

      {toast && <div className={styles.toast}><CheckCircle2 size={18} />{toast}</div>}
    </div>
  );
}

interface OnboardingProps {
  form: PlannerFormData;
  step: number;
  loading: boolean;
  error: string;
  onStep: (step: number) => void;
  onUpdate: <K extends keyof PlannerFormData>(key: K, value: PlannerFormData[K]) => void;
  onSubject: (key: SubjectKey) => void;
  onProvince: (provinceCode: string) => void;
  onEdition: (editionId: string) => void;
  onGenerate: () => void;
}

function OnboardingPanel({ form, step, loading, error, onStep, onUpdate, onSubject, onProvince, onEdition, onGenerate }: OnboardingProps) {
  const province = getProvinceRoute(form.provinceCode);
  const selectableSubjects = provinceSubjectKeys(province);
  const selectionValid = isSubjectSelectionValid(province, form.selectedSubjects);
  const edition = getMathEdition(form.curriculumVersion);
  const chapterGroups = progressGroups(form.curriculumVersion);
  const firstChoice = new Set(province.first_choice_subjects || []);
  const subjectHint = province.exam_mode === "3+1+2"
    ? "请选择 1 门首选科目和 2 门再选科目"
    : `请选择 3 科（${province.selection_rule}）`;
  return (
    <div className={styles.onboardingLayout}>
      <section className={styles.introPanel}>
        <span className={styles.mintTag}><Sparkles size={15} /> AI 个性化规划</span>
        <h2>把目标，变成<br /><em>每天可执行的路径</em></h2>
        <p>告诉我你的目标、学情和可用时间。规划 Agent 会结合考试政策、知识掌握度与学习负荷，为你生成可解释、可调整的长期计划。</p>
        <div className={styles.introPoints}>
          <div><span><Target size={20} /></span><div><strong>目标结构化</strong><small>从分数目标拆解阶段里程碑</small></div></div>
          <div><span><BrainCircuit size={20} /></span><div><strong>学情诊断</strong><small>以证据识别薄弱点与前置缺口</small></div></div>
          <div><span><TimerReset size={20} /></span><div><strong>动态调整</strong><small>根据练习反馈做最小必要调整</small></div></div>
        </div>
        <div className={styles.privacyNote}><ShieldCheck size={17} /><span>你的学习数据仅用于生成和优化个人计划</span></div>
      </section>

      <section className={styles.formCard}>
        <div className={styles.stepper}>
          {steps.map((label, index) => (
            <button key={label} className={cn(index === step && styles.stepActive, index < step && styles.stepDone)} onClick={() => index <= step && onStep(index)}>
              <span>{index < step ? <Check size={15} /> : index + 1}</span>
              <small>{label}</small>
            </button>
          ))}
          <div className={styles.stepLine}><i style={{ width: `${step * 50}%` }} /></div>
        </div>

        <div className={styles.formHeading}>
          <span>步骤 {step + 1} / 3</span>
          <h3>{step === 0 ? "先认识一下你" : step === 1 ? "明确目标与当前学情" : "安排可持续的学习时间"}</h3>
          <p>{step === 0 ? "基础信息将用于匹配适用的考试政策和课程进度。" : step === 1 ? "真实信息越充分，计划越贴近你的实际情况。" : "系统会自动保留缓冲，不把每一分钟都排满。"}</p>
        </div>

        {step === 0 && (
          <div className={styles.formBody}>
            <div className={styles.fieldGrid}>
              <label><span>当前年级</span><select value={form.grade} onChange={(event) => onUpdate("grade", event.target.value as PlannerFormData["grade"])}><option value="grade_10">高一</option><option value="grade_11">高二</option><option value="grade_12">高三</option></select></label>
              <label><span>所在地区（全国Ⅰ卷知识库范围）</span><select value={form.provinceCode} onChange={(event) => onProvince(event.target.value)}>{provinceRoutes.map((item) => <option key={item.code} value={item.code}>{item.name}省 · {item.exam_mode}</option>)}</select></label>
              <label><span>预计参加高考年份</span><select value={form.targetExamYear} onChange={(event) => onUpdate("targetExamYear", Number(event.target.value))}>{[2027, 2028, 2029, 2030].map((year) => <option key={year} value={year}>{year} 年（须按当年官方政策复核）</option>)}</select></label>
              <label><span>数学教材版本</span><select value={form.curriculumVersion} onChange={(event) => onEdition(event.target.value)}>{mathEditions.map((item) => <option key={item.id} value={item.id}>{item.label}{item.catalog_status === "VERIFIED_OFFICIAL" ? " · 官方章序已核验" : " · 章序待确认"}</option>)}</select></label>
              <label><span>{edition.catalog_status === "VERIFIED_OFFICIAL" ? "数学教材当前章节" : "数学课程标准当前主题"}</span><select value={form.classProgress} onChange={(event) => onUpdate("classProgress", event.target.value)}>{chapterGroups.map((group) => <optgroup key={group.id} label={group.label}>{group.options.map((item) => <option key={item.id} value={item.id}>{item.number ? `${item.number} ` : ""}{item.title}</option>)}</optgroup>)}</select></label>
            </div>
            <div className={styles.catalogNote}><ShieldCheck size={16} /><span><strong>{editionEvidenceLabel(form.curriculumVersion)}</strong><small>地区依据：{province.official_authority}；目标考试年份仍须按当年官方通知复核。</small></span></div>
            <fieldset className={styles.subjectField}>
              <legend>你的选科 <small>{subjectHint}</small></legend>
              <div>{selectableSubjects.map((key) => {
                const sourceKey = key === "ideology_politics" ? "politics" : key;
                const group = province.exam_mode === "3+1+2" ? (firstChoice.has(sourceKey) ? "首选" : "再选") : "选考";
                return <button type="button" key={key} className={cn(form.selectedSubjects.includes(key) && styles.subjectActive)} onClick={() => onSubject(key)}><span>{form.selectedSubjects.includes(key) && <Check size={13} />}</span>{subjectLabels[key]}<small>{group}</small></button>;
              })}</div>
            </fieldset>
            {!selectionValid && <div className={styles.selectionWarning}><CircleAlert size={14} />当前选科组合不符合 {province.selection_rule} 规则</div>}
          </div>
        )}

        {step === 1 && (
          <div className={styles.formBody}>
            <div className={styles.scoreGoal}>
              <div><label htmlFor="current-score">当前数学成绩</label><span><input id="current-score" type="number" min="0" max="150" value={form.currentScore} onChange={(event) => onUpdate("currentScore", Number(event.target.value))} /><small>分</small></span></div>
              <ArrowRight size={23} />
              <div><label htmlFor="target-score">目标成绩</label><span className={styles.targetInput}><input id="target-score" type="number" min="0" max="150" value={form.targetScore} onChange={(event) => onUpdate("targetScore", Number(event.target.value))} /><small>分</small></span></div>
            </div>
            <label className={styles.fullField}><span>目标日期</span><input type="date" value={form.deadline} min="2026-07-30" onChange={(event) => onUpdate("deadline", event.target.value)} /></label>
            <div className={styles.sliderBlock}>
              <div><span>函数与导数基础掌握度</span><strong>{form.foundationMastery}%</strong></div>
              <input aria-label="函数与导数基础掌握度" type="range" min="10" max="95" value={form.foundationMastery} onChange={(event) => onUpdate("foundationMastery", Number(event.target.value))} style={{ "--range": `${form.foundationMastery}%` } as React.CSSProperties} />
              <small><span>需要系统复习</span><span>掌握扎实</span></small>
            </div>
            <div className={styles.sliderBlock}>
              <div><span>综合题独立完成度</span><strong>{form.applicationMastery}%</strong></div>
              <input aria-label="综合题独立完成度" type="range" min="10" max="95" value={form.applicationMastery} onChange={(event) => onUpdate("applicationMastery", Number(event.target.value))} style={{ "--range": `${form.applicationMastery}%` } as React.CSSProperties} />
              <small><span>常需提示</span><span>可独立完成</span></small>
            </div>
          </div>
        )}

        {step === 2 && (
          <div className={styles.formBody}>
            <div className={styles.weeklyCard}>
              <div><span><Clock3 size={19} /></span><div><small>每周可用时间</small><strong>{minutesLabel(form.weeklyMinutes)}</strong></div></div>
              <input aria-label="每周可用时间" type="range" min="210" max="1050" step="35" value={form.weeklyMinutes} onChange={(event) => onUpdate("weeklyMinutes", Number(event.target.value))} style={{ "--range": `${((form.weeklyMinutes - 210) / 840) * 100}%` } as React.CSSProperties} />
              <p>Agent 建议排期约 {minutesLabel(Math.round(form.weeklyMinutes * 0.82))}，其余作为机动缓冲。</p>
            </div>
            <div className={styles.fieldGrid}>
              <label><span>工作日每天</span><select value={form.weekdayMinutes} onChange={(event) => onUpdate("weekdayMinutes", Number(event.target.value))}><option value="45">45 分钟</option><option value="70">70 分钟</option><option value="90">90 分钟</option></select></label>
              <label><span>周末每天</span><select value={form.weekendMinutes} onChange={(event) => onUpdate("weekendMinutes", Number(event.target.value))}><option value="90">90 分钟</option><option value="140">140 分钟</option><option value="180">180 分钟</option></select></label>
            </div>
            <div className={styles.summaryStrip}>
              <Sparkles size={19} />
              <p><strong>画像已准备好</strong><span>{gradeLabels[form.grade]} · {province.name} · {form.targetExamYear} 高考 · 数学 {form.currentScore} → {form.targetScore} 分 · 每周 {Math.round(form.weeklyMinutes / 60 * 10) / 10} 小时</span></p>
              <CheckCircle2 size={20} />
            </div>
          </div>
        )}

        {error && <div className={styles.errorBox}><CircleAlert size={17} />{error}</div>}
        <div className={styles.formFooter}>
          <button className={styles.secondaryButton} disabled={step === 0 || loading} onClick={() => onStep(step - 1)}><ArrowLeft size={17} />上一步</button>
          {step < 2 ? (
            <button className={styles.primaryButton} disabled={step === 0 && (!selectionValid || !form.classProgress)} onClick={() => onStep(step + 1)}>继续填写<ArrowRight size={17} /></button>
          ) : (
            <button className={styles.primaryButton} disabled={loading} onClick={onGenerate}>{loading ? <><LoaderCircle className={styles.spin} size={18} />Agent 正在规划</> : <><Sparkles size={18} />生成我的学习计划</>}</button>
          )}
        </div>
      </section>
    </div>
  );
}

interface DashboardProps {
  form: PlannerFormData;
  plan: LearningPlan;
  knowledge: NonNullable<AgentEnvelope["result"]>["knowledge_profile"];
  progress: number;
  confirmed: boolean;
  confirming: boolean;
  mode?: "live" | "demo";
  error: string;
  warnings: Array<{ code: string; message: string }>;
  onConfirm: () => void;
  onEdit: () => void;
  onFeedback: () => void;
}

function PlanDashboard({ form, plan, knowledge, progress, confirmed, confirming, mode, error, warnings, onConfirm, onEdit, onFeedback }: DashboardProps) {
  const capacityPercent = Math.round((plan.scheduled_minutes / plan.weekly_capacity_minutes) * 100);
  return (
    <div className={styles.dashboard}>
      {mode === "demo" && <div className={styles.demoBanner}><Cloud size={17} /><span><strong>在线演示模式</strong> 当前展示完整交互与示例计划；配置后端地址后会调用真实 LangGraph Agent。</span></div>}
      {warnings.map((warning) => <div className={styles.policyBanner} key={warning.code}><CircleAlert size={17} /><span><strong>政策版本提醒</strong>{warning.message}</span></div>)}
      <section className={styles.planHero}>
        <div>
          <span className={styles.planState}>{confirmed ? <><CheckCircle2 size={15} />计划执行中</> : <><Sparkles size={15} />Agent 已完成规划</>}</span>
          <h2>{confirmed ? "你的学习路径已启动" : "第一阶段计划已经准备好"}</h2>
          <p>{plan.stages[0]?.objective || "根据你的目标、知识证据与时间容量生成"}</p>
          <div className={styles.heroButtons}>
            {!confirmed ? <button className={styles.primaryButton} onClick={onConfirm} disabled={confirming}>{confirming ? <LoaderCircle className={styles.spin} size={18} /> : <Check size={18} />}{confirming ? "正在确认" : "确认并开始计划"}</button> : <button className={styles.primaryButton} onClick={onFeedback}><Send size={17} />记录一次练习</button>}
            <button className={styles.secondaryButton} onClick={onEdit}><RefreshCw size={16} />调整目标</button>
          </div>
        </div>
        <div className={styles.scoreArc} style={{ "--progress": `${progress * 3.6}deg` } as React.CSSProperties}>
          <div><small>当前 / 目标</small><strong>{form.currentScore}<i>→</i>{form.targetScore}</strong><span>数学 · 150 分制</span></div>
        </div>
      </section>

      {error && <div className={styles.errorBox}><CircleAlert size={17} />{error}</div>}

      <div className={styles.metricGrid}>
        <article><span className={styles.metricIcon}><CalendarDays size={20} /></span><div><small>目标日期</small><strong>{formatDate(form.deadline)}</strong><p>距目标仍有充足调整空间</p></div></article>
        <article><span className={styles.metricIcon}><Clock3 size={20} /></span><div><small>每周计划</small><strong>{minutesLabel(plan.scheduled_minutes)}</strong><p>占有效容量 {capacityPercent}%</p></div></article>
        <article><span className={styles.metricIcon}><TimerReset size={20} /></span><div><small>机动缓冲</small><strong>{minutesLabel(plan.buffer_minutes)}</strong><p>用于错题回访与临时调整</p></div></article>
        <article><span className={styles.metricIcon}><ShieldCheck size={20} /></span><div><small>方案校验</small><strong>{plan.validation?.valid ? "全部通过" : "需要检查"}</strong><p>{Object.values(plan.validation?.checks || {}).filter(Boolean).length} 项约束已验证</p></div></article>
      </div>

      <div className={styles.dashboardGrid}>
        <section className={styles.taskPanel}>
          <div className={styles.panelHeading}><div><span>THIS WEEK</span><h3>本周学习安排</h3></div><small>{plan.tasks.length} 项任务 · {minutesLabel(plan.scheduled_minutes)}</small></div>
          <div className={styles.timeline}>
            {plan.tasks.map((task, index) => (
              <article key={task.task_id} className={styles.taskItem}>
                <div className={styles.dateBox}><strong>{formatDate(task.planned_start, true).replace(/星期|周/, "周")}</strong><span>{new Date(task.planned_start).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", hour12: false })}</span></div>
                <span className={styles.timelineDot}>{index + 1}</span>
                <div className={styles.taskContent}>
                  <div><span className={styles.taskType}>{taskNames[task.task_type] || task.task_type}</span><span className={styles.duration}><Clock3 size={13} />{task.planned_duration_minutes} 分钟</span></div>
                  <h4>{task.rationale.split("：")[0]}</h4>
                  <p>{task.rationale.includes("：") ? task.rationale.split("：").slice(1).join("：") : task.rationale}</p>
                  <div className={styles.taskMeta}><span>考试相关度 {Math.round(task.exam_relevance * 100)}%</span><i><b style={{ width: `${task.exam_relevance * 100}%` }} /></i></div>
                </div>
              </article>
            ))}
          </div>
        </section>

        <aside className={styles.insightColumn}>
          <section className={styles.insightCard}>
            <div className={styles.panelHeading}><div><span>AGENT INSIGHT</span><h3>规划思路</h3></div><BrainCircuit size={21} /></div>
            <p>{plan.explanations?.strategy || "先补齐高权重薄弱点，再通过变式练习与周期测评验证迁移效果。"}</p>
            <div className={styles.route}><span>基础修复</span><ChevronRight size={14} /><span>专项训练</span><ChevronRight size={14} /><span>综合迁移</span></div>
          </section>
          <section className={styles.gapCard}>
            <div className={styles.panelHeading}><div><span>PRIORITY GAPS</span><h3>优先补齐</h3></div><Target size={21} /></div>
            {(knowledge?.priority_gaps || ["函数与图像", "导数运算", "分类讨论"]).slice(0, 3).map((gap, index) => <div key={gap}><span>{index + 1}</span><p>{gap}<small>{index === 0 ? "前置影响较高" : index === 1 ? "近期错题集中" : "高考相关度高"}</small></p></div>)}
          </section>
          <section className={styles.capacityCard}>
            <div><span>时间负荷</span><strong>{capacityPercent}%</strong></div>
            <div className={styles.capacityBar}><i style={{ width: `${capacityPercent}%` }} /><b style={{ width: `${100 - capacityPercent}%` }} /></div>
            <p><span><i />已排期 {plan.scheduled_minutes} 分钟</span><span><i />缓冲 {plan.buffer_minutes} 分钟</span></p>
          </section>
        </aside>
      </div>
    </div>
  );
}

function KnowledgePanel({ response }: { response: AgentEnvelope | null }) {
  const profile = response?.result?.knowledge_profile;
  return (
    <div className={styles.subpage}>
      <section className={styles.subpageIntro}><div><span className={styles.mintTag}><BrainCircuit size={15} /> 动态知识画像</span><h2>看见掌握度背后的学习证据</h2><p>画像只基于已提供的证据，不会把缺失数据推断成事实；练习后将持续更新。</p></div><div className={styles.confidence}><small>画像置信度</small><strong>{Math.round((profile?.assessment_quality.confidence || 0.81) * 100)}%</strong><span>当前证据质量良好</span></div></section>
      <div className={styles.knowledgeGrid}>
        {(profile?.knowledge_states || []).map((item) => (
          <article key={item.knowledge_id}>
            <div><span>{item.knowledge_id}</span><strong>{Math.round(item.mastery_probability * 100)}%</strong></div>
            <div className={styles.masteryBar}><i style={{ width: `${item.mastery_probability * 100}%` }} /></div>
            <p><span>掌握阶段：{item.mastery_level === "developing" ? "发展中" : "起步"}</span><span>遗忘风险 {Math.round(item.forgetting_risk * 100)}%</span></p>
          </article>
        ))}
      </div>
      <section className={styles.evidenceNote}><ShieldCheck size={22} /><div><strong>证据边界说明</strong><p>当前画像综合了你的自评信息与目标输入。接入真实练习记录后，系统会根据答题质量、用时、提示依赖和重复证据调整掌握度。</p></div></section>
    </div>
  );
}

function FeedbackPanel({ form, plan, onSuccess }: { form: PlannerFormData; plan: LearningPlan; onSuccess: (message: string) => void }) {
  const [taskId, setTaskId] = useState(plan.tasks[0]?.task_id || "");
  const [correct, setCorrect] = useState(true);
  const [minutes, setMinutes] = useState(35);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<string>("");
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const eventId = `evt_${Date.now()}`;
      const response = await callAgent({
        action: "practice",
        studentId: form.studentId,
        event: {
          event_id: eventId,
          student_id: form.studentId,
          session_id: `practice_${Date.now()}`,
          task_id: taskId,
          item_id: `item_${Date.now()}`,
          subject: "mathematics",
          knowledge_ids: ["math_function_foundation"],
          event_type: "answer_submitted",
          timestamp: new Date().toISOString(),
          response: { correct, score: correct ? 5 : 0, max_score: 5, difficulty: 0.6 },
          behavior: { response_time_seconds: minutes * 60, hint_count: correct ? 0 : 1, attempt_count: 1 },
        },
      });
      const quality = response.result?.practice_update?.quality_score;
      setResult(typeof quality === "number" ? `反馈已入库，本次证据质量 ${Math.round(quality * 100)}%` : "反馈已入库，Agent 已完成调整规则检查");
      onSuccess("练习证据已提交给规划 Agent");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "提交失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className={styles.feedbackLayout}>
      <section className={styles.feedbackIntro}><span className={styles.mintTag}><TrendingUp size={15} /> 闭环反馈</span><h2>一次练习，也能让计划更懂你</h2><p>记录真实结果。普通错误只更新画像并检查规则，不会因为一次波动重建整周计划。</p><div><BookOpenCheck size={24} /><p><strong>最小必要调整</strong><span>仅在持续低完成率、关键掌握度变化或时间容量明显变化时触发重新规划。</span></p></div></section>
      <form className={styles.feedbackForm} onSubmit={submit}>
        <div className={styles.formHeading}><span>PRACTICE EVENT</span><h3>记录本次练习</h3><p>所填信息将作为新的学习证据。</p></div>
        <label className={styles.fullField}><span>对应计划任务</span><select value={taskId} onChange={(event) => setTaskId(event.target.value)}>{plan.tasks.map((task) => <option key={task.task_id} value={task.task_id}>{task.rationale.split("：")[0]}</option>)}</select></label>
        <fieldset className={styles.resultChoice}><legend>完成结果</legend><button type="button" className={cn(correct && styles.correctActive)} onClick={() => setCorrect(true)}><CheckCircle2 size={20} />独立完成</button><button type="button" className={cn(!correct && styles.wrongActive)} onClick={() => setCorrect(false)}><CircleAlert size={20} />仍有困难</button></fieldset>
        <div className={styles.sliderBlock}><div><span>实际用时</span><strong>{minutes} 分钟</strong></div><input aria-label="实际用时" type="range" min="10" max="120" step="5" value={minutes} onChange={(event) => setMinutes(Number(event.target.value))} style={{ "--range": `${((minutes - 10) / 110) * 100}%` } as React.CSSProperties} /><small><span>10 分钟</span><span>120 分钟</span></small></div>
        {error && <div className={styles.errorBox}><CircleAlert size={17} />{error}</div>}
        {result && <div className={styles.successBox}><CheckCircle2 size={18} />{result}</div>}
        <button className={styles.primaryButton} type="submit" disabled={loading}>{loading ? <LoaderCircle className={styles.spin} size={18} /> : <Send size={18} />}{loading ? "正在提交" : "提交给规划 Agent"}</button>
      </form>
    </div>
  );
}
