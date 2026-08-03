<script setup lang="ts">
import {
  Bell, BookOpenCheck, CalendarClock, CheckCircle2, ChevronRight, ClipboardCheck,
  Copy, GraduationCap, LayoutDashboard, LoaderCircle, LogOut, Menu, Plus,
  RefreshCw, School, Search, Send, Target, UsersRound, X,
} from "@lucide/vue";
import { computed, onMounted, reactive, ref } from "vue";

import { subjectLabels } from "@/lib/curriculum-catalog";
import { fetchExamDiagnosticCatalog } from "@/lib/exam-diagnosis-client";
import {
  createClassroom, fetchClassroomDetail, fetchTeacherDashboard,
  publishAnnouncement, saveExamAssignment,
} from "@/lib/teacher-client";
import type {
  ClassroomDetail, ClassroomExamAssignment, ClassroomStudentState, TeacherDashboard,
} from "@/lib/teacher-client";
import type { ExamDiagnosticPaperSummary, SubjectKey, TeacherLoginProfile } from "@/lib/types";

type TeacherView = "overview" | "students" | "notices" | "exams";
const props = defineProps<{ profile: TeacherLoginProfile }>();
const emit = defineEmits<{ logout: [] }>();

const activeView = ref<TeacherView>("overview");
const sidebarOpen = ref(false);
const dashboard = ref<TeacherDashboard>({ classrooms: [], announcements: [], exam_assignments: [] });
const classDetail = ref<ClassroomDetail | null>(null);
const selectedClassId = ref<number | null>(null);
const loading = ref(true);
const actionLoading = ref(false);
const error = ref("");
const toast = ref("");
const search = ref("");
const createOpen = ref(false);
const catalogPapers = ref<Array<ExamDiagnosticPaperSummary & { subject: SubjectKey }>>([]);
const classForm = reactive({ className: "", grade: "grade_11", subject: props.profile.subject || "mathematics" as SubjectKey });
const noticeForm = reactive({
  classroomId: 0,
  announcementType: "homework" as "homework" | "holiday" | "notice",
  title: "",
  content: "",
  dueAt: "",
});
const examForm = reactive({
  assignmentId: "",
  classroomId: 0,
  paperId: "",
  title: "",
  dueAt: "",
  status: "published" as ClassroomExamAssignment["status"],
});

const navItems = [
  { id: "overview" as const, label: "教学总览", icon: LayoutDashboard },
  { id: "students" as const, label: "学生学情", icon: UsersRound },
  { id: "notices" as const, label: "通知与作业", icon: Bell },
  { id: "exams" as const, label: "诊断卷发布", icon: ClipboardCheck },
];
const currentClass = computed(() =>
  dashboard.value.classrooms.find((item) => item.id === selectedClassId.value),
);
const filteredStudents = computed(() => {
  const keyword = search.value.trim().toLowerCase();
  if (!keyword) return classDetail.value?.students || [];
  return (classDetail.value?.students || []).filter((item) =>
    `${item.student_name} ${item.student_id}`.toLowerCase().includes(keyword),
  );
});
const totalStudents = computed(() =>
  dashboard.value.classrooms.reduce((sum, item) => sum + Number(item.student_count), 0),
);
const activePlans = computed(() =>
  (classDetail.value?.students || []).filter((item) =>
    ["active", "waiting_for_confirmation"].includes(item.latest_plan?.status || ""),
  ).length,
);

function showToast(message: string) {
  toast.value = message;
  window.setTimeout(() => { toast.value = ""; }, 2800);
}

async function loadDashboard() {
  loading.value = true;
  error.value = "";
  try {
    dashboard.value = await fetchTeacherDashboard();
    if (!dashboard.value.classrooms.length) createOpen.value = true;
    const firstId = selectedClassId.value || dashboard.value.classrooms[0]?.id;
    if (firstId) await selectClass(firstId);
    if (!noticeForm.classroomId && firstId) noticeForm.classroomId = firstId;
    if (!examForm.classroomId && firstId) examForm.classroomId = firstId;
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "教师工作台加载失败";
  } finally {
    loading.value = false;
  }
}

async function selectClass(classroomId: number) {
  selectedClassId.value = classroomId;
  classDetail.value = await fetchClassroomDetail(classroomId);
}

async function submitClassroom() {
  if (!classForm.className.trim()) return;
  actionLoading.value = true;
  try {
    const created = await createClassroom(classForm);
    classForm.className = "";
    createOpen.value = false;
    selectedClassId.value = created.id;
    await loadDashboard();
    showToast(`班级已创建，班级码 ${created.class_code}`);
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "班级创建失败";
  } finally {
    actionLoading.value = false;
  }
}

async function submitNotice() {
  if (!noticeForm.classroomId || !noticeForm.title.trim() || !noticeForm.content.trim()) return;
  actionLoading.value = true;
  try {
    await publishAnnouncement(noticeForm.classroomId, noticeForm);
    noticeForm.title = "";
    noticeForm.content = "";
    noticeForm.dueAt = "";
    await loadDashboard();
    showToast("通知已发布到学生端");
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "通知发布失败";
  } finally {
    actionLoading.value = false;
  }
}

function paperChanged() {
  const paper = catalogPapers.value.find((item) => item.paper_id === examForm.paperId);
  if (paper && !examForm.title) examForm.title = paper.title;
}

async function submitExam() {
  if (!examForm.classroomId || !examForm.paperId || !examForm.title.trim()) return;
  actionLoading.value = true;
  try {
    await saveExamAssignment(examForm.classroomId, examForm);
    examForm.assignmentId = "";
    examForm.paperId = "";
    examForm.title = "";
    examForm.dueAt = "";
    examForm.status = "published";
    await loadDashboard();
    showToast("学情诊断卷已更新并同步到学生端");
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "诊断卷发布失败";
  } finally {
    actionLoading.value = false;
  }
}

function editAssignment(item: ClassroomExamAssignment) {
  examForm.assignmentId = item.assignment_id;
  examForm.classroomId = item.classroom_id;
  examForm.paperId = item.paper_id;
  examForm.title = item.title;
  examForm.dueAt = item.due_at?.slice(0, 16) || "";
  examForm.status = item.status;
  activeView.value = "exams";
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function copyCode(code: string) {
  void navigator.clipboard.writeText(code);
  showToast(`班级码 ${code} 已复制`);
}

function gradeLabel(grade: string) {
  return grade === "grade_10" ? "高一" : grade === "grade_11" ? "高二" : "高三";
}

function planGoal(student: ClassroomStudentState) {
  const basis = student.latest_plan?.generation_basis;
  if (!student.latest_plan) return "尚未生成规划";
  const subject = basis?.goal_subject as SubjectKey | undefined;
  const score = basis?.goal_target_value;
  return subject && score ? `${subjectLabels[subject]}目标 ${score} 分` : "已生成个性化规划";
}

function diagnosisLabel(student: ClassroomStudentState) {
  const diagnosis = student.latest_diagnosis;
  if (!diagnosis) return "暂无学情诊断";
  const status = String(diagnosis.diagnosis_status || "");
  const states = (diagnosis.knowledge_states || []) as Array<Record<string, any>>;
  const weak = states.filter((item) =>
    ["needs_support", "developing"].includes(String(item.mastery_level)),
  ).slice(0, 2).map((item) => item.dimension_label || item.dimension_id);
  return weak.length ? `需关注：${weak.join("、")}` : status === "stable" ? "学情状态稳定" : "证据仍在积累";
}

onMounted(async () => {
  await loadDashboard();
  try {
    const catalog = await fetchExamDiagnosticCatalog();
    catalogPapers.value = catalog.subjects.flatMap((group) =>
      group.papers.map((paper) => ({ ...paper, subject: group.subject })),
    );
  } catch {
    catalogPapers.value = [];
  }
});
</script>

<template>
  <div class="teacher-shell">
    <div v-if="sidebarOpen" class="teacher-mask" @click="sidebarOpen=false" />
    <aside :class="{open:sidebarOpen}">
      <div class="teacher-workspace-brand"><span><GraduationCap :size="24" /></span><div><strong>知途教师平台</strong><small>TEACHER HUB</small></div><button @click="sidebarOpen=false"><X :size="18" /></button></div>
      <nav><small>教学工作台</small><button v-for="item in navItems" :key="item.id" :class="{active:activeView===item.id}" @click="activeView=item.id;sidebarOpen=false"><component :is="item.icon" :size="18" /><span>{{ item.label }}</span><ChevronRight :size="14" /></button></nav>
      <div class="teacher-class-shortcuts"><small>我的班级</small><button v-for="item in dashboard.classrooms.slice(0,4)" :key="item.id" :class="{active:selectedClassId===item.id}" @click="selectClass(item.id);activeView='students'"><span>{{ item.class_name.slice(0,1) }}</span><div><strong>{{ item.class_name }}</strong><small>{{ item.student_count }} 名学生</small></div></button></div>
      <div class="teacher-profile"><span>{{ profile.teacherName.slice(0,1) }}</span><div><strong>{{ profile.teacherName }}老师</strong><small>{{ profile.schoolName }}</small></div><button title="退出登录" @click="emit('logout')"><LogOut :size="17" /></button></div>
    </aside>

    <main>
      <header class="teacher-topbar"><button @click="sidebarOpen=true"><Menu :size="20" /></button><div><small>TEACHER INTELLIGENCE</small><strong>{{ navItems.find(item=>item.id===activeView)?.label }}</strong></div><span><i /> MySQL 教学数据已连接</span><button class="refresh-teacher" @click="loadDashboard"><RefreshCw :size="16" />刷新</button></header>
      <div class="teacher-content">
        <p v-if="error" class="teacher-error">{{ error }}</p>
        <div v-if="loading" class="teacher-loading"><LoaderCircle class="spin" :size="25" />正在读取班级教学数据…</div>

        <template v-else-if="activeView==='overview'">
          <section class="teacher-hero"><div><small>GOOD DAY, TEACHER</small><h1>{{ profile.teacherName }}老师，掌握班级真实进展。</h1><p>从规划目标、学习证据到诊断结果，把每一位学生放回具体的学习过程里观察。</p><button @click="createOpen=true"><Plus :size="17" />创建新班级</button></div><div class="hero-school"><School :size="28" /><span><strong>{{ profile.schoolName }}</strong><small>{{ profile.subject ? `${subjectLabels[profile.subject]}教师` : '教师账号' }}</small></span></div></section>
          <section class="teacher-metrics"><article><span><School :size="21" /></span><div><small>管理班级</small><strong>{{ dashboard.classrooms.length }}</strong></div></article><article><span><UsersRound :size="21" /></span><div><small>班级学生</small><strong>{{ totalStudents }}</strong></div></article><article><span><Bell :size="21" /></span><div><small>已发布通知</small><strong>{{ dashboard.announcements.length }}</strong></div></article><article><span><ClipboardCheck :size="21" /></span><div><small>诊断卷任务</small><strong>{{ dashboard.exam_assignments.length }}</strong></div></article></section>
          <section class="teacher-section"><header><div><small>MY CLASSROOMS</small><h2>班级与班级码</h2></div><button @click="createOpen=true"><Plus :size="16" />创建班级</button></header><div v-if="dashboard.classrooms.length" class="teacher-class-grid"><article v-for="item in dashboard.classrooms" :key="item.id"><div><span>{{ item.class_name.slice(0,1) }}</span><button title="复制班级码" @click="copyCode(item.class_code)"><Copy :size="15" /></button></div><h3>{{ item.class_name }}</h3><p>{{ gradeLabel(item.grade) }} · {{ item.subject ? subjectLabels[item.subject] : '综合班级' }}</p><strong>{{ item.class_code }}</strong><footer><span><UsersRound :size="14" />{{ item.student_count }} 名学生</span><button @click="selectClass(item.id);activeView='students'">查看学情 <ChevronRight :size="14" /></button></footer></article></div><div v-else class="teacher-empty"><School :size="35" /><strong>还没有班级</strong><p>创建班级后，把 8 位班级码发给学生即可加入。</p></div></section>
          <div class="teacher-overview-grid"><section class="teacher-section compact"><header><div><small>RECENT NOTICES</small><h2>最近通知</h2></div><button @click="activeView='notices'">发布通知</button></header><div class="notice-mini"><article v-for="item in dashboard.announcements.slice(0,4)" :key="item.announcement_id"><span :class="item.announcement_type"><Bell :size="15" /></span><div><strong>{{ item.title }}</strong><small>{{ item.class_name }} · {{ new Date(item.created_at).toLocaleDateString('zh-CN') }}</small></div></article><p v-if="!dashboard.announcements.length">暂无通知</p></div></section><section class="teacher-section compact"><header><div><small>DIAGNOSTIC TASKS</small><h2>诊断卷发布</h2></div><button @click="activeView='exams'">发布试卷</button></header><div class="notice-mini"><article v-for="item in dashboard.exam_assignments.slice(0,4)" :key="item.assignment_id"><span class="exam"><ClipboardCheck :size="15" /></span><div><strong>{{ item.title }}</strong><small>{{ item.class_name }} · {{ item.status==='published'?'进行中':'已关闭' }}</small></div><button @click="editAssignment(item)">更新</button></article><p v-if="!dashboard.exam_assignments.length">暂无诊断卷任务</p></div></section></div>
        </template>

        <template v-else-if="activeView==='students'">
          <section class="teacher-subhero"><div><small>STUDENT LEARNING STATES</small><h1>学生学情与规划目标</h1><p>查看班级成员最近一次可核验的规划、学情诊断和高考真题诊断记录。</p></div><label><span>当前班级</span><select :value="selectedClassId||''" @change="selectClass(Number(($event.target as HTMLSelectElement).value))"><option v-for="item in dashboard.classrooms" :key="item.id" :value="item.id">{{ item.class_name }}</option></select></label></section>
          <section v-if="currentClass" class="student-state-metrics"><article><small>班级码</small><strong>{{ currentClass.class_code }}</strong><button @click="copyCode(currentClass.class_code)"><Copy :size="14" /></button></article><article><small>学生人数</small><strong>{{ classDetail?.students.length || 0 }}</strong></article><article><small>已有规划</small><strong>{{ activePlans }}</strong></article><article><small>已发布诊断卷</small><strong>{{ classDetail?.exam_assignments.length || 0 }}</strong></article></section>
          <section class="teacher-section student-table-section"><header><div><small>CLASS MEMBERS</small><h2>{{ currentClass?.class_name || '请选择班级' }}</h2></div><label class="student-search"><Search :size="16" /><input v-model="search" placeholder="搜索姓名或账号" /></label></header><div class="student-table"><div class="student-table-head"><span>学生</span><span>规划目标</span><span>最近学情诊断</span><span>真题诊断</span></div><article v-for="student in filteredStudents" :key="student.student_id"><div><span>{{ student.student_name.slice(0,1) }}</span><strong>{{ student.student_name }}<small>{{ student.student_id }} · {{ gradeLabel(student.grade) }}</small></strong></div><p><Target :size="15" />{{ planGoal(student) }}<small>{{ student.latest_plan ? `计划状态：${student.latest_plan.status}` : '等待学生完成首次规划' }}</small></p><p><BookOpenCheck :size="15" />{{ diagnosisLabel(student) }}<small>{{ student.latest_diagnosis ? `状态版本 v${student.latest_diagnosis.state_version || 1}` : '暂无可展示证据' }}</small></p><p><ClipboardCheck :size="15" />{{ student.latest_exam ? `${student.latest_exam.score ?? '待评分'} / ${student.latest_exam.paper_max ?? '--'} 分` : '尚未测试' }}<small>{{ student.latest_exam?.subject ? subjectLabels[student.latest_exam.subject as SubjectKey] : '暂无真题诊断记录' }}</small></p></article><div v-if="!filteredStudents.length" class="teacher-empty"><UsersRound :size="32" /><strong>班级暂无学生</strong><p>请把班级码发给学生，学生加入后会显示在这里。</p></div></div></section>
        </template>

        <template v-else-if="activeView==='notices'">
          <section class="teacher-subhero notice-hero"><div><small>CLASS COMMUNICATION</small><h1>发布通知与作业</h1><p>学生加入班级后，会在自己的“班级与通知”页面实时看到发布内容。</p></div><Bell :size="42" /></section>
          <div class="teacher-editor-grid"><form class="teacher-section teacher-publish-form" @submit.prevent="submitNotice"><header><div><small>NEW ANNOUNCEMENT</small><h2>新建班级通知</h2></div><Send :size="20" /></header><label><span>发布班级</span><select v-model.number="noticeForm.classroomId"><option v-for="item in dashboard.classrooms" :key="item.id" :value="item.id">{{ item.class_name }}</option></select></label><label><span>通知类型</span><div class="type-buttons"><button type="button" :class="{active:noticeForm.announcementType==='homework'}" @click="noticeForm.announcementType='homework'">作业</button><button type="button" :class="{active:noticeForm.announcementType==='holiday'}" @click="noticeForm.announcementType='holiday'">放假</button><button type="button" :class="{active:noticeForm.announcementType==='notice'}" @click="noticeForm.announcementType='notice'">普通通知</button></div></label><label><span>标题</span><input v-model="noticeForm.title" placeholder="例如：周末数学作业" /></label><label><span>详细内容</span><textarea v-model="noticeForm.content" rows="6" placeholder="填写作业要求、放假安排或其他通知…" /></label><label><span>截止/提醒时间（选填）</span><input v-model="noticeForm.dueAt" type="datetime-local" /></label><button class="green-submit" :disabled="actionLoading"><LoaderCircle v-if="actionLoading" class="spin" :size="17" /><Send v-else :size="17" />发布到学生端</button></form><section class="teacher-section publish-history"><header><div><small>PUBLISHED</small><h2>已发布内容</h2></div><span>{{ dashboard.announcements.length }} 条</span></header><article v-for="item in dashboard.announcements" :key="item.announcement_id"><span :class="item.announcement_type"><Bell :size="16" /></span><div><small>{{ item.class_name }} · {{ item.announcement_type==='homework'?'作业':item.announcement_type==='holiday'?'放假通知':'班级通知' }}</small><strong>{{ item.title }}</strong><p>{{ item.content }}</p><time>{{ new Date(item.created_at).toLocaleString('zh-CN') }}</time></div></article><div v-if="!dashboard.announcements.length" class="teacher-empty"><Bell :size="31" /><strong>暂无通知</strong></div></section></div>
        </template>

        <template v-else>
          <section class="teacher-subhero exam-hero"><div><small>DIAGNOSTIC PAPER ASSIGNMENT</small><h1>发布与更新学情诊断卷</h1><p>从现有高考真题诊断卷中选卷。更新任务时可更换试卷、截止时间与发布状态。</p></div><ClipboardCheck :size="45" /></section>
          <div class="teacher-editor-grid"><form class="teacher-section teacher-publish-form" @submit.prevent="submitExam"><header><div><small>{{ examForm.assignmentId?'UPDATE TASK':'NEW TASK' }}</small><h2>{{ examForm.assignmentId?'更新诊断任务':'发布诊断试卷' }}</h2></div><ClipboardCheck :size="21" /></header><label><span>发布班级</span><select v-model.number="examForm.classroomId"><option v-for="item in dashboard.classrooms" :key="item.id" :value="item.id">{{ item.class_name }}</option></select></label><label><span>选择真题诊断卷</span><select v-model="examForm.paperId" @change="paperChanged"><option value="">请选择试卷</option><optgroup v-for="[key,label] in Object.entries(subjectLabels)" :key="key" :label="label"><option v-for="paper in catalogPapers.filter(item=>item.subject===key)" :key="paper.paper_id" :value="paper.paper_id">{{ paper.title }}</option></optgroup></select></label><label><span>任务标题</span><input v-model="examForm.title" placeholder="学生端显示的任务名称" /></label><label><span>截止时间（选填）</span><input v-model="examForm.dueAt" type="datetime-local" /></label><label><span>任务状态</span><select v-model="examForm.status"><option value="published">发布中</option><option value="closed">已关闭</option><option value="archived">归档</option></select></label><button class="green-submit" :disabled="actionLoading"><LoaderCircle v-if="actionLoading" class="spin" :size="17" /><CheckCircle2 v-else :size="17" />{{ examForm.assignmentId?'保存更新':'发布诊断卷' }}</button></form><section class="teacher-section publish-history exam-history"><header><div><small>ASSIGNMENTS</small><h2>已发布诊断卷</h2></div><span>{{ dashboard.exam_assignments.length }} 份</span></header><article v-for="item in dashboard.exam_assignments" :key="item.assignment_id"><span class="exam"><ClipboardCheck :size="17" /></span><div><small>{{ item.class_name }} · {{ item.status==='published'?'发布中':'已关闭' }}</small><strong>{{ item.title }}</strong><p>试卷 ID：{{ item.paper_id }}</p><time>{{ item.due_at ? `截止 ${new Date(item.due_at).toLocaleString('zh-CN')}` : '未设置截止时间' }}</time></div><button @click="editAssignment(item)">更新</button></article><div v-if="!dashboard.exam_assignments.length" class="teacher-empty"><ClipboardCheck :size="31" /><strong>暂无诊断卷任务</strong></div></section></div>
        </template>
      </div>
    </main>

    <div v-if="createOpen" class="teacher-modal-mask" @click.self="createOpen=false"><form class="teacher-modal" @submit.prevent="submitClassroom"><header><div><small>CREATE CLASSROOM</small><h2>创建新班级</h2></div><button type="button" @click="createOpen=false"><X :size="18" /></button></header><label><span>班级名称</span><input v-model="classForm.className" placeholder="例如：高二 3 班数学" /></label><label><span>年级</span><select v-model="classForm.grade"><option value="grade_10">高一</option><option value="grade_11">高二</option><option value="grade_12">高三</option></select></label><label><span>主要学科</span><select v-model="classForm.subject"><option v-for="[key,label] in Object.entries(subjectLabels)" :key="key" :value="key">{{ label }}</option></select></label><p>创建后会生成唯一的 8 位班级码，学生使用班级码加入。</p><button class="green-submit" :disabled="actionLoading"><LoaderCircle v-if="actionLoading" class="spin" :size="17" /><Plus v-else :size="17" />创建并生成班级码</button></form></div>
    <Transition name="toast"><div v-if="toast" class="teacher-toast"><CheckCircle2 :size="17" />{{ toast }}</div></Transition>
  </div>
</template>

<style scoped>
.teacher-shell{--green:#168363;--green-dark:#124d3e;--green-soft:#e7f6f0;min-height:100vh;color:#24483d;background:#f4f8f6}.teacher-shell>aside{position:fixed;z-index:30;inset:0 auto 0 0;display:flex;width:248px;flex-direction:column;padding:24px 17px 18px;color:#dff3ec;background:linear-gradient(180deg,#103e34,#17694f)}.teacher-workspace-brand{display:flex;align-items:center;gap:10px}.teacher-workspace-brand>span{display:grid;width:40px;height:40px;place-items:center;color:#0f5d45;background:#dff5ec;border-radius:11px}.teacher-workspace-brand>div{display:grid;gap:3px}.teacher-workspace-brand strong{font-size:14px}.teacher-workspace-brand small{color:#9bcdbb;font-size:7px;letter-spacing:.15em}.teacher-workspace-brand>button{display:none;margin-left:auto;color:#dff3ec;border:0;background:transparent}.teacher-shell aside nav{display:grid;gap:7px;margin-top:38px}.teacher-shell aside nav>small,.teacher-class-shortcuts>small{margin:0 9px 5px;color:#81bca7;font-size:7px;font-weight:800;letter-spacing:.15em}.teacher-shell aside nav button{display:flex;height:43px;align-items:center;gap:10px;padding:0 12px;color:#b9ddcf;border:0;background:transparent;border-radius:9px;font-size:10px;text-align:left}.teacher-shell aside nav button span{flex:1}.teacher-shell aside nav button.active{color:#155c47;background:#e3f4ed;box-shadow:0 7px 17px rgba(5,43,31,.2)}.teacher-class-shortcuts{display:grid;gap:6px;margin-top:28px;padding-top:20px;border-top:1px solid rgba(255,255,255,.09)}.teacher-class-shortcuts>button{display:flex;align-items:center;gap:9px;padding:8px;color:#c0dfd3;border:0;background:transparent;border-radius:8px;text-align:left}.teacher-class-shortcuts>button:hover,.teacher-class-shortcuts>button.active{background:rgba(255,255,255,.08)}.teacher-class-shortcuts>button>span{display:grid;width:29px;height:29px;place-items:center;color:#174e3e;background:#bfe8d9;border-radius:8px;font-size:9px;font-weight:850}.teacher-class-shortcuts>button>div{display:grid;gap:2px}.teacher-class-shortcuts strong{font-size:8px}.teacher-class-shortcuts small{color:#8fc1af;font-size:7px}.teacher-profile{display:flex;align-items:center;gap:9px;margin-top:auto;padding:12px 9px;border:1px solid rgba(255,255,255,.09);background:rgba(255,255,255,.05);border-radius:11px}.teacher-profile>span{display:grid;width:34px;height:34px;place-items:center;color:#165741;background:#d9f2e9;border-radius:9px;font-size:11px;font-weight:850}.teacher-profile>div{display:grid;min-width:0;flex:1;gap:3px}.teacher-profile strong{font-size:9px}.teacher-profile small{overflow:hidden;color:#8fc1af;font-size:7px;text-overflow:ellipsis;white-space:nowrap}.teacher-profile button{color:#aad3c4;border:0;background:transparent}.teacher-shell>main{min-height:100vh;margin-left:248px}.teacher-topbar{position:sticky;z-index:20;top:0;display:flex;height:68px;align-items:center;padding:0 30px;border-bottom:1px solid #dfe9e5;background:rgba(255,255,255,.92);backdrop-filter:blur(12px)}.teacher-topbar>button:first-child{display:none;color:#2b6554;border:0;background:transparent}.teacher-topbar>div{display:grid;gap:2px}.teacher-topbar>div small{color:#78a093;font-size:7px;letter-spacing:.15em}.teacher-topbar>div strong{font-size:13px}.teacher-topbar>span{display:flex;align-items:center;gap:6px;margin-left:auto;color:#728d84;font-size:8px}.teacher-topbar>span i{width:7px;height:7px;background:#27af7f;border-radius:50%;box-shadow:0 0 0 4px #e2f5ee}.refresh-teacher{display:flex;align-items:center;gap:5px;margin-left:17px;padding:8px 10px;color:#426b5e;border:1px solid #d7e5df;background:#fff;border-radius:8px;font-size:8px}.teacher-content{width:min(100%,1440px);margin:auto;padding:28px 32px 60px}.teacher-error{padding:11px 13px;color:#a43b3b;background:#fff0ef;border-radius:9px;font-size:9px}.teacher-loading{display:grid;min-height:65vh;place-content:center;justify-items:center;gap:12px;color:#67847a;font-size:10px}.teacher-hero,.teacher-subhero{display:flex;min-height:215px;align-items:center;justify-content:space-between;overflow:hidden;padding:35px 39px;color:#fff;background:radial-gradient(circle at 85% 30%,rgba(255,255,255,.16),transparent 27%),linear-gradient(135deg,#11523f,#188465 70%,#3eae86);border-radius:18px;box-shadow:0 19px 40px rgba(22,117,88,.15)}.teacher-hero>div:first-child,.teacher-subhero>div:first-child{max-width:790px}.teacher-hero small,.teacher-subhero small{color:#bde9da;font-size:8px;font-weight:850;letter-spacing:.17em}.teacher-hero h1,.teacher-subhero h1{margin:13px 0 9px;font-size:clamp(27px,3.2vw,42px);letter-spacing:-.045em}.teacher-hero p,.teacher-subhero p{margin:0;color:#cceade;font-size:10px;line-height:1.8}.teacher-hero>div:first-child>button{display:inline-flex;align-items:center;gap:6px;margin-top:20px;padding:10px 14px;color:#145c47;border:0;background:#fff;border-radius:8px;font-size:9px;font-weight:750}.hero-school{display:flex;max-width:300px;align-items:center;gap:13px;padding:18px;border:1px solid rgba(255,255,255,.18);background:rgba(255,255,255,.09);border-radius:13px}.hero-school span{display:grid;gap:5px}.hero-school strong{font-size:11px}.hero-school small{color:#bce5d6;font-size:8px}.teacher-metrics,.student-state-metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:13px;margin:16px 0}.teacher-metrics article{display:flex;align-items:center;gap:11px;padding:16px;border:1px solid #dfe9e5;background:#fff;border-radius:12px;box-shadow:0 5px 16px rgba(25,76,60,.04)}.teacher-metrics article>span{display:grid;width:38px;height:38px;place-items:center;color:#168363;background:#e7f6f0;border-radius:10px}.teacher-metrics article>div{display:grid;gap:3px}.teacher-metrics small,.student-state-metrics small{color:#81968f;font-size:8px}.teacher-metrics strong{font-size:20px}.teacher-section{margin-top:16px;padding:23px;border:1px solid #dfe9e5;background:#fff;border-radius:15px;box-shadow:0 6px 20px rgba(29,75,61,.045)}.teacher-section>header{display:flex;align-items:center;justify-content:space-between;gap:15px;padding-bottom:16px;border-bottom:1px solid #edf2f0}.teacher-section>header small{color:#4b947e;font-size:7px;font-weight:850;letter-spacing:.14em}.teacher-section>header h2{margin:5px 0 0;font-size:16px}.teacher-section>header>button,.teacher-section>header>span{display:flex;align-items:center;gap:5px;padding:8px 10px;color:#157254;border:1px solid #bcded2;background:#f5fbf8;border-radius:8px;font-size:8px}.teacher-class-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:13px;margin-top:17px}.teacher-class-grid>article{padding:18px;border:1px solid #dfebe6;background:linear-gradient(145deg,#fff,#f8fcfa);border-radius:13px}.teacher-class-grid>article>div{display:flex;align-items:center;justify-content:space-between}.teacher-class-grid>article>div>span{display:grid;width:39px;height:39px;place-items:center;color:#fff;background:#188363;border-radius:10px;font-size:12px;font-weight:850}.teacher-class-grid>article>div>button{color:#72958a;border:0;background:transparent}.teacher-class-grid h3{margin:15px 0 5px;font-size:13px}.teacher-class-grid p{margin:0;color:#7c918a;font-size:8px}.teacher-class-grid>article>strong{display:block;margin-top:15px;color:#176f54;font-size:19px;letter-spacing:.15em}.teacher-class-grid footer{display:flex;align-items:center;justify-content:space-between;margin-top:16px;padding-top:13px;border-top:1px solid #e8f0ed}.teacher-class-grid footer span,.teacher-class-grid footer button{display:flex;align-items:center;gap:5px;color:#758d85;border:0;background:transparent;font-size:8px}.teacher-class-grid footer button{color:#167758}.teacher-empty{display:grid;min-height:190px;place-content:center;justify-items:center;gap:8px;color:#7f9990;text-align:center}.teacher-empty strong{color:#3e6659;font-size:11px}.teacher-empty p{margin:0;font-size:8px}.teacher-overview-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}.teacher-section.compact{min-height:320px}.notice-mini{display:grid;margin-top:10px}.notice-mini article{display:flex;align-items:center;gap:9px;padding:12px 2px;border-bottom:1px solid #edf2f0}.notice-mini article>span,.publish-history article>span{display:grid;width:34px;height:34px;place-items:center;color:#7c651a;background:#fff3cf;border-radius:9px}.notice-mini article>span.homework,.publish-history article>span.homework{color:#176f54;background:#e4f5ed}.notice-mini article>span.exam,.publish-history article>span.exam{color:#426ca8;background:#eaf1fb}.notice-mini article>div{display:grid;flex:1;gap:4px}.notice-mini strong{font-size:9px}.notice-mini small{color:#83988f;font-size:7px}.notice-mini article>button{color:#167758;border:0;background:transparent;font-size:8px}.notice-mini>p{color:#899c95;font-size:9px}.teacher-subhero{min-height:180px}.teacher-subhero>label{display:grid;min-width:220px;gap:7px}.teacher-subhero>label span{font-size:8px}.teacher-subhero select{height:42px;padding:0 12px;color:#245346;border:1px solid rgba(255,255,255,.3);background:#fff;border-radius:8px;font-size:9px}.student-state-metrics article{position:relative;display:grid;gap:5px;padding:15px;border:1px solid #dfe9e5;background:#fff;border-radius:11px}.student-state-metrics strong{color:#185c49;font-size:15px}.student-state-metrics button{position:absolute;right:12px;top:18px;color:#67877c;border:0;background:transparent}.student-table-section{padding-bottom:8px}.student-search{display:flex;height:38px;align-items:center;gap:7px;padding:0 10px;border:1px solid #dbe7e2;background:#f9fcfb;border-radius:8px}.student-search input{width:180px;border:0;outline:0;background:transparent;font-size:8px}.student-table{margin-top:7px}.student-table-head,.student-table>article{display:grid;grid-template-columns:1.1fr 1fr 1.4fr 1fr;gap:13px;align-items:center}.student-table-head{padding:10px 12px;color:#82978f;font-size:7px;font-weight:800}.student-table>article{padding:14px 12px;border-top:1px solid #edf2f0}.student-table>article>div{display:flex;align-items:center;gap:9px}.student-table>article>div>span{display:grid;width:35px;height:35px;place-items:center;color:#17684f;background:#e1f3ec;border-radius:9px;font-size:10px;font-weight:850}.student-table>article>div strong{display:grid;gap:4px;font-size:9px}.student-table small{display:block;color:#899b95;font-size:7px;font-weight:400}.student-table p{display:grid;grid-template-columns:auto 1fr;gap:4px 6px;align-items:center;margin:0;color:#47685d;font-size:8px}.student-table p svg{color:#17805f}.student-table p small{grid-column:2}.notice-hero{background:linear-gradient(135deg,#125441,#198563)}.exam-hero{background:linear-gradient(135deg,#174e43,#2b8e73)}.teacher-editor-grid{display:grid;grid-template-columns:.86fr 1.14fr;gap:16px}.teacher-publish-form{display:grid;align-content:start;gap:15px}.teacher-publish-form>header{margin-bottom:2px}.teacher-publish-form>label,.teacher-modal>label{display:grid;gap:7px}.teacher-publish-form>label>span,.teacher-modal>label>span{color:#42685d;font-size:8px;font-weight:750}.teacher-publish-form input,.teacher-publish-form select,.teacher-publish-form textarea,.teacher-modal input,.teacher-modal select{width:100%;padding:0 11px;color:#264c41;border:1px solid #d8e6e1;outline:0;background:#fbfdfc;border-radius:8px;font:inherit;font-size:9px}.teacher-publish-form input,.teacher-publish-form select,.teacher-modal input,.teacher-modal select{height:42px}.teacher-publish-form textarea{padding-block:10px;line-height:1.6;resize:vertical}.type-buttons{display:grid;grid-template-columns:repeat(3,1fr);gap:7px}.type-buttons button{height:37px;color:#68847a;border:1px solid #dbe7e2;background:#fff;border-radius:8px;font-size:8px}.type-buttons button.active{color:#fff;border-color:#168363;background:#168363}.green-submit{display:flex;min-height:44px;align-items:center;justify-content:center;gap:6px;color:#fff;border:0;background:linear-gradient(135deg,#157457,#1b9972);border-radius:9px;font-size:9px;font-weight:800;box-shadow:0 9px 20px rgba(22,131,99,.16)}.publish-history{max-height:760px;overflow:auto}.publish-history>article{display:flex;align-items:flex-start;gap:11px;padding:15px 2px;border-bottom:1px solid #edf2f0}.publish-history>article>div{display:grid;flex:1;gap:5px}.publish-history article small{color:#41816d;font-size:7px}.publish-history article strong{font-size:10px}.publish-history article p{margin:0;color:#70887f;font-size:8px;line-height:1.65}.publish-history article time{color:#96a69f;font-size:7px}.publish-history article>button{padding:7px 9px;color:#167758;border:1px solid #c9e1d8;background:#f5fbf8;border-radius:7px;font-size:8px}.teacher-modal-mask{position:fixed;z-index:60;inset:0;display:grid;place-items:center;padding:20px;background:rgba(14,47,38,.48);backdrop-filter:blur(4px)}.teacher-modal{display:grid;width:min(100%,470px);gap:15px;padding:27px;border:1px solid #dce8e3;background:#fff;border-radius:17px;box-shadow:0 24px 65px rgba(9,46,35,.22)}.teacher-modal header{display:flex;align-items:center;justify-content:space-between}.teacher-modal header small{color:#4c907b;font-size:7px;letter-spacing:.14em}.teacher-modal h2{margin:5px 0 0;font-size:18px}.teacher-modal header button{color:#6d877e;border:0;background:transparent}.teacher-modal>p{margin:0;color:#7b9189;font-size:8px}.teacher-toast{position:fixed;z-index:80;right:24px;bottom:24px;display:flex;align-items:center;gap:7px;padding:12px 15px;color:#fff;background:#155f49;border-radius:9px;box-shadow:0 13px 30px rgba(16,75,57,.25);font-size:9px}.teacher-mask{display:none}@media(max-width:1050px){.teacher-class-grid{grid-template-columns:1fr 1fr}.teacher-overview-grid,.teacher-editor-grid{grid-template-columns:1fr}.student-table-head{display:none}.student-table>article{grid-template-columns:1fr 1fr}}@media(max-width:780px){.teacher-shell>aside{transform:translateX(-100%);transition:.25s ease}.teacher-shell>aside.open{transform:translateX(0)}.teacher-workspace-brand>button{display:block}.teacher-mask{position:fixed;z-index:25;inset:0;display:block;background:rgba(9,43,33,.4)}.teacher-shell>main{margin-left:0}.teacher-topbar{padding:0 16px}.teacher-topbar>button:first-child{display:block;margin-right:10px}.teacher-topbar>span{display:none}.teacher-content{padding:18px 16px 45px}.teacher-hero,.teacher-subhero{align-items:flex-start;flex-direction:column;gap:20px;padding:27px 23px}.hero-school{display:none}.teacher-metrics,.student-state-metrics{grid-template-columns:1fr 1fr}.teacher-class-grid{grid-template-columns:1fr}.student-table>article{grid-template-columns:1fr}.teacher-subhero>label{width:100%}}@media(max-width:480px){.teacher-metrics,.student-state-metrics{grid-template-columns:1fr}.teacher-overview-grid{display:block}}
</style>
