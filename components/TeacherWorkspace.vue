<script setup lang="ts">
import {
  Bell,
  BookOpenCheck,
  CalendarClock,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  ClipboardCheck,
  Copy,
  GraduationCap,
  LayoutDashboard,
  LoaderCircle,
  LogOut,
  Menu,
  Plus,
  RefreshCw,
  School,
  Search,
  Send,
  Sparkles,
  Target,
  UserMinus,
  UsersRound,
  X,
  XCircle,
} from "@lucide/vue";
import {
  computed,
  onBeforeUnmount,
  onMounted,
  reactive,
  ref,
  watch,
} from "vue";

import PaginationControls from "@/components/PaginationControls.vue";
import { subjectLabels } from "@/lib/curriculum-catalog";
import TeacherPreparationWorkspace from "@/components/TeacherPreparationWorkspace.vue";
import { fetchExamDiagnosticCatalog } from "@/lib/exam-diagnosis-client";
import {
  createClassroom,
  fetchClassroomDetail,
  fetchClassroomTeachers,
  joinTeacherClassroom,
  fetchTeacherDashboard,
  publishAnnouncement,
  publishAnnouncementsBatch,
  publishExamAssignmentsBatch,
  removeClassroomTeacher,
  reviewClassroomLeave,
  reviewTeacherClassroomLeave,
  reviewTeacherJoin,
  saveExamAssignment,
  transferClassroomOwner,
  updateClassroomJoinPolicy,
  leaveTeacherClassroom,
} from "@/lib/teacher-client";
import type {
  ClassroomDetail,
  ClassroomExamAssignment,
  ClassroomTeacherMember,
  ClassroomLeaveRequest,
  ClassroomStudentState,
  TeacherDashboard,
} from "@/lib/teacher-client";
import type {
  ExamDiagnosticPaperSummary,
  SubjectKey,
  TeacherLoginProfile,
} from "@/lib/types";

type TeacherView =
  | "overview"
  | "preparation-create"
  | "preparation-library"
  | "students"
  | "collaboration"
  | "leave-requests"
  | "notices"
  | "exams";
const props = defineProps<{ profile: TeacherLoginProfile }>();
const emit = defineEmits<{ logout: [] }>();

const activeView = ref<TeacherView>("overview");
const sidebarOpen = ref(false);
const preparationOpen = ref(true);
const dashboard = ref<TeacherDashboard>({
  classrooms: [],
  announcements: [],
  exam_assignments: [],
  leave_requests: [],
});
const classDetail = ref<ClassroomDetail | null>(null);
const selectedClassId = ref<number | null>(null);
const loading = ref(true);
const actionLoading = ref(false);
const error = ref("");
const toast = ref("");
const search = ref("");
const createOpen = ref(false);
const joinOpen = ref(false);
const joinCode = ref("");
const studentPage = ref(1);
const noticePage = ref(1);
const examPage = ref(1);
const leaveRequestPage = ref(1);
const reviewingRequestId = ref("");
const STUDENT_PAGE_SIZE = 6;
const CONTENT_PAGE_SIZE = 5;
const catalogPapers = ref<
  Array<ExamDiagnosticPaperSummary & { subject: SubjectKey }>
>([]);
const classForm = reactive({
  className: "",
  grade: "grade_11",
  subject: props.profile.subject || ("mathematics" as SubjectKey),
});
const noticeForm = reactive({
  classroomId: 0,
  announcementType: "homework" as "homework" | "holiday" | "notice",
  title: "",
  content: "",
  dueAt: "",
});
const collaborationMembers = ref<ClassroomTeacherMember[]>([]);
const collaborationLoading = ref(false);
const selectedBatchClassIds = ref<number[]>([]);
const batchResult = ref<{ succeeded: number; failed: number } | null>(null);
const examForm = reactive({
  assignmentId: "",
  classroomId: 0,
  paperId: "",
  title: "",
  dueAt: "",
  status: "published" as ClassroomExamAssignment["status"],
});

const baseNavItems = [
  { id: "students" as const, label: "学生学情", icon: UsersRound },
  { id: "collaboration" as const, label: "协作管理", icon: UsersRound },
  { id: "leave-requests" as const, label: "退班审批", icon: UserMinus },
  { id: "notices" as const, label: "通知与作业", icon: Bell },
  { id: "exams" as const, label: "诊断卷发布", icon: ClipboardCheck },
];
const hasOwnedClass = computed(() =>
  dashboard.value.classrooms.some(
    (item) => item.teacher_access_role === "owner",
  ),
);
const navItems = computed(() =>
  baseNavItems.filter(
    (item) => item.id !== "leave-requests" || hasOwnedClass.value,
  ),
);
const viewLabels: Record<TeacherView, string> = {
  overview: "教学总览",
  "preparation-create": "生成备课方案",
  "preparation-library": "我的备课方案",
  students: "学生学情",
  collaboration: "协作管理",
  "leave-requests": "退班审批",
  notices: "通知与作业",
  exams: "诊断卷发布",
};
const currentViewLabel = computed(() => viewLabels[activeView.value]);
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
const pagedStudents = computed(() => {
  const start = (studentPage.value - 1) * STUDENT_PAGE_SIZE;
  return filteredStudents.value.slice(start, start + STUDENT_PAGE_SIZE);
});
const pagedAnnouncements = computed(() => {
  const start = (noticePage.value - 1) * CONTENT_PAGE_SIZE;
  return dashboard.value.announcements.slice(start, start + CONTENT_PAGE_SIZE);
});
const pagedExamAssignments = computed(() => {
  const start = (examPage.value - 1) * CONTENT_PAGE_SIZE;
  return dashboard.value.exam_assignments.slice(
    start,
    start + CONTENT_PAGE_SIZE,
  );
});
const pagedLeaveRequests = computed(() => {
  const start = (leaveRequestPage.value - 1) * CONTENT_PAGE_SIZE;
  return dashboard.value.leave_requests.slice(start, start + CONTENT_PAGE_SIZE);
});
const totalStudents = computed(() =>
  dashboard.value.classrooms.reduce(
    (sum, item) => sum + Number(item.student_count),
    0,
  ),
);
const activePlans = computed(
  () =>
    (classDetail.value?.students || []).filter((item) =>
      ["active", "waiting_for_confirmation"].includes(
        item.latest_plan?.status || "",
      ),
    ).length,
);

function showToast(message: string) {
  toast.value = message;
  window.setTimeout(() => {
    toast.value = "";
  }, 2800);
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

async function refreshLeaveRequests() {
  try {
    const latest = await fetchTeacherDashboard();
    dashboard.value.leave_requests = latest.leave_requests;
  } catch {
    // Keep the current screen stable; the normal refresh action exposes connection errors.
  }
}

async function loadCollaboration(classroomId = selectedClassId.value) {
  if (!classroomId) return;
  collaborationLoading.value = true;
  try {
    collaborationMembers.value = (
      await fetchClassroomTeachers(classroomId)
    ).members;
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "协作成员加载失败";
  } finally {
    collaborationLoading.value = false;
  }
}

async function removeTeacher(member: ClassroomTeacherMember) {
  if (
    !selectedClassId.value ||
    !window.confirm(`确认移除 ${member.teacher_name} 的协作权限？`)
  )
    return;
  try {
    await removeClassroomTeacher(selectedClassId.value, member.teacher_id);
    await loadCollaboration();
    showToast("已移除协作教师");
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "移除失败";
  }
}

async function decideTeacherJoin(
  member: ClassroomTeacherMember,
  decision: "approved" | "rejected",
) {
  if (!selectedClassId.value) return;
  try {
    await reviewTeacherJoin(selectedClassId.value, member.teacher_id, decision);
    await loadCollaboration();
    showToast(decision === "approved" ? "已批准加入" : "已拒绝加入申请");
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "审批失败";
  }
}

async function transferOwner(member: ClassroomTeacherMember) {
  if (
    !selectedClassId.value ||
    !window.confirm(
      `确认将“${currentClass.value?.class_name || "当前班级"}”的班主任职权转移给 ${member.teacher_name}？转移后你将成为该班的协作教师。`,
    )
  )
    return;
  try {
    await transferClassroomOwner(selectedClassId.value, member.teacher_id);
    await loadDashboard();
    await loadCollaboration(selectedClassId.value);
    showToast(`班主任职权已转移给 ${member.teacher_name}`);
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "班主任转移失败";
  }
}

async function leaveCurrentClassroom() {
  if (
    !selectedClassId.value ||
    !window.confirm("提交退班申请后，需要等待班主任审批。确认提交？")
  )
    return;
  try {
    await leaveTeacherClassroom(selectedClassId.value);
    await loadDashboard();
    showToast("退班申请已提交，请等待班主任审批");
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "退班申请提交失败";
  }
}

async function toggleJoinPolicy(policy: "open" | "approval") {
  if (!selectedClassId.value) return;
  try {
    await updateClassroomJoinPolicy(selectedClassId.value, policy);
    await loadDashboard();
    showToast(policy === "open" ? "已开启班级码直接加入" : "已开启加入审批");
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "加入策略更新失败";
  }
}

async function selectClassroomForBatch(id: number) {
  selectedBatchClassIds.value = selectedBatchClassIds.value.includes(id)
    ? selectedBatchClassIds.value.filter((item) => item !== id)
    : [...selectedBatchClassIds.value, id];
}

async function selectClass(classroomId: number) {
  selectedClassId.value = classroomId;
  studentPage.value = 1;
  classDetail.value = await fetchClassroomDetail(classroomId);
  if (activeView.value === "collaboration")
    await loadCollaboration(classroomId);
}

watch(search, () => {
  studentPage.value = 1;
});
watch(activeView, (view) => {
  if (view === "collaboration") void loadCollaboration();
});
watch(hasOwnedClass, (ownsClass) => {
  if (!ownsClass && activeView.value === "leave-requests") {
    activeView.value = "overview";
  }
});

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

async function submitTeacherJoin() {
  if (!/^[A-Za-z0-9]{8}$/.test(joinCode.value.trim())) {
    error.value = "请输入其他教师提供的 8 位班级码";
    return;
  }
  actionLoading.value = true;
  error.value = "";
  try {
    const joined = await joinTeacherClassroom(joinCode.value);
    joinCode.value = "";
    joinOpen.value = false;
    selectedClassId.value = joined.id;
    await loadDashboard();
    showToast(
      joined.membership_status === "pending"
        ? `已提交加入“${joined.class_name}”的申请，请等待班主任审批`
        : `已作为协作教师加入“${joined.class_name}”，现在可以查看学情并发布教学内容`,
    );
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "加入班级失败";
  } finally {
    actionLoading.value = false;
  }
}

async function submitNotice() {
  if (
    !noticeForm.classroomId ||
    !noticeForm.title.trim() ||
    !noticeForm.content.trim()
  )
    return;
  actionLoading.value = true;
  try {
    const targets = selectedBatchClassIds.value.length
      ? selectedBatchClassIds.value
      : [noticeForm.classroomId];
    if (targets.length > 1) {
      const result = await publishAnnouncementsBatch({
        classroomIds: targets,
        ...noticeForm,
      });
      batchResult.value = {
        succeeded: result.succeeded.length,
        failed: result.failed.length,
      };
    } else {
      await publishAnnouncement(noticeForm.classroomId, noticeForm);
      batchResult.value = null;
    }
    noticeForm.title = "";
    noticeForm.content = "";
    noticeForm.dueAt = "";
    await loadDashboard();
    showToast(
      batchResult.value
        ? `已向 ${batchResult.value.succeeded} 个班级发布通知${batchResult.value.failed ? `，${batchResult.value.failed} 个失败` : ""}`
        : "通知已发布到学生端",
    );
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "通知发布失败";
  } finally {
    actionLoading.value = false;
  }
}

function leaveApplicantName(item: ClassroomLeaveRequest) {
  return (
    item.applicant_name || item.student_name || item.teacher_name || "申请人"
  );
}

function leaveApplicantId(item: ClassroomLeaveRequest) {
  return item.applicant_id || item.student_id || item.teacher_id || "--";
}

async function reviewLeave(
  item: ClassroomLeaveRequest,
  decision: "approved" | "rejected",
) {
  const action = decision === "approved" ? "同意" : "拒绝";
  const source = item.request_source === "collaborator" ? "协作教师" : "学生";
  if (
    !window.confirm(
      `${action}${source}${leaveApplicantName(item)}退出“${item.class_name}”的申请？`,
    )
  )
    return;
  reviewingRequestId.value = item.request_id;
  error.value = "";
  try {
    if (item.request_source === "collaborator") {
      await reviewTeacherClassroomLeave(item.request_id, decision);
    } else {
      await reviewClassroomLeave(item.request_id, decision);
    }
    await loadDashboard();
    showToast(
      decision === "approved"
        ? `已同意退班，${source}已退出该班级`
        : `已拒绝退班，${source}仍保留在该班级`,
    );
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "退班申请处理失败";
  } finally {
    reviewingRequestId.value = "";
  }
}

function paperChanged() {
  const paper = catalogPapers.value.find(
    (item) => item.paper_id === examForm.paperId,
  );
  if (paper && !examForm.title) examForm.title = paper.title;
}

async function submitExam() {
  if (!examForm.classroomId || !examForm.paperId || !examForm.title.trim())
    return;
  actionLoading.value = true;
  try {
    const targets = selectedBatchClassIds.value.length
      ? selectedBatchClassIds.value
      : [examForm.classroomId];
    if (targets.length > 1 && !examForm.assignmentId) {
      const result = await publishExamAssignmentsBatch({
        classroomIds: targets,
        ...examForm,
      });
      batchResult.value = {
        succeeded: result.succeeded.length,
        failed: result.failed.length,
      };
    } else {
      await saveExamAssignment(examForm.classroomId, examForm);
      batchResult.value = null;
    }
    examForm.assignmentId = "";
    examForm.paperId = "";
    examForm.title = "";
    examForm.dueAt = "";
    examForm.status = "published";
    await loadDashboard();
    showToast(
      batchResult.value
        ? `已向 ${batchResult.value.succeeded} 个班级发布诊断卷${batchResult.value.failed ? `，${batchResult.value.failed} 个失败` : ""}`
        : "学情诊断卷已更新并同步到学生端",
    );
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

function classroomOptionLabel(
  classroom: TeacherDashboard["classrooms"][number],
) {
  const access =
    classroom.teacher_access_role === "collaborator"
      ? `协作 · ${classroom.owner_teacher_name || "其他教师"}`
      : "我创建的";
  return `${classroom.class_name}（${access}）`;
}

function planGoal(student: ClassroomStudentState) {
  const basis = student.latest_plan?.generation_basis;
  if (!student.latest_plan) return "尚未生成规划";
  const subject = basis?.goal_subject as SubjectKey | undefined;
  const score = basis?.goal_target_value;
  return subject && score
    ? `${subjectLabels[subject]}目标 ${score} 分`
    : "已生成个性化规划";
}

function diagnosisLabel(student: ClassroomStudentState) {
  const diagnosis = student.latest_diagnosis;
  if (!diagnosis) return "暂无学情诊断";
  const status = String(diagnosis.diagnosis_status || "");
  const states = (diagnosis.knowledge_states || []) as Array<
    Record<string, any>
  >;
  const weak = states
    .filter((item) =>
      ["needs_support", "developing"].includes(String(item.mastery_level)),
    )
    .slice(0, 2)
    .map((item) => item.dimension_label || item.dimension_id);
  return weak.length
    ? `需关注：${weak.join("、")}`
    : status === "stable"
      ? "学情状态稳定"
      : "证据仍在积累";
}

let dashboardTimer = 0;
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
  dashboardTimer = window.setInterval(() => {
    void refreshLeaveRequests();
  }, 30_000);
});
onBeforeUnmount(() => window.clearInterval(dashboardTimer));
</script>

<template>
  <div class="teacher-shell">
    <div v-if="sidebarOpen" class="teacher-mask" @click="sidebarOpen = false" />
    <aside :class="{ open: sidebarOpen }">
      <div class="teacher-workspace-brand">
        <span><GraduationCap :size="24" /></span>
        <div><strong>知途教师平台</strong><small>TEACHER HUB</small></div>
        <button @click="sidebarOpen = false"><X :size="18" /></button>
      </div>
      <nav>
        <small>教学工作台</small
        ><button
          :class="{ active: activeView === 'overview' }"
          @click="
            activeView = 'overview';
            sidebarOpen = false;
          "
        >
          <LayoutDashboard :size="18" /><span>教学总览</span
          ><ChevronRight :size="14" />
        </button>
        <div class="teacher-nav-group">
          <button
            class="teacher-nav-parent"
            :class="{ active: activeView.startsWith('preparation-') }"
            @click="preparationOpen = !preparationOpen"
          >
            <Sparkles :size="18" /><span>智能备课</span
            ><ChevronRight :size="14" :class="{ expanded: preparationOpen }" />
          </button>
          <div v-if="preparationOpen" class="teacher-nav-children">
            <button
              :class="{ active: activeView === 'preparation-create' }"
              @click="
                activeView = 'preparation-create';
                sidebarOpen = false;
              "
            >
              <i /><span>生成备课方案</span></button
            ><button
              :class="{ active: activeView === 'preparation-library' }"
              @click="
                activeView = 'preparation-library';
                sidebarOpen = false;
              "
            >
              <i /><span>我的备课方案</span>
            </button>
          </div>
        </div>
        <button
          v-for="item in navItems"
          :key="item.id"
          :class="{ active: activeView === item.id }"
          @click="
            activeView = item.id;
            sidebarOpen = false;
          "
        >
          <component :is="item.icon" :size="18" /><span>{{ item.label }}</span
          ><b
            v-if="
              item.id === 'leave-requests' && dashboard.leave_requests.length
            "
            class="leave-nav-badge"
            >{{ dashboard.leave_requests.length }}</b
          ><ChevronRight :size="14" />
        </button>
      </nav>
      <div class="teacher-class-shortcuts">
        <small>我的班级</small
        ><button
          v-for="item in dashboard.classrooms.slice(0, 4)"
          :key="item.id"
          :class="{ active: selectedClassId === item.id }"
          @click="
            selectClass(item.id);
            activeView = 'students';
          "
        >
          <span>{{ item.class_name.slice(0, 1) }}</span>
          <div>
            <strong>{{ item.class_name }}</strong
            ><small>{{ item.student_count }} 名学生</small>
          </div>
        </button>
      </div>
      <div class="teacher-profile">
        <span>{{ profile.teacherName.slice(0, 1) }}</span>
        <div>
          <strong>{{ profile.teacherName }}老师</strong
          ><small>{{ profile.schoolName }}</small>
        </div>
        <button title="退出登录" @click="emit('logout')">
          <LogOut :size="17" />
        </button>
      </div>
    </aside>

    <main>
      <header class="teacher-topbar">
        <button @click="sidebarOpen = true"><Menu :size="20" /></button>
        <div>
          <small>TEACHER INTELLIGENCE</small
          ><strong>{{ currentViewLabel }}</strong>
        </div>
        <span><i /> MySQL 教学数据已连接</span
        ><button class="refresh-teacher" @click="loadDashboard">
          <RefreshCw :size="16" />刷新
        </button>
      </header>
      <div class="teacher-content">
        <p v-if="error" class="teacher-error">{{ error }}</p>
        <div v-if="loading" class="teacher-loading">
          <LoaderCircle class="spin" :size="25" />正在读取班级教学数据…
        </div>

        <template v-else-if="activeView === 'overview'">
          <section class="teacher-hero">
            <div>
              <small>GOOD DAY, TEACHER</small>
              <h1>{{ profile.teacherName }}老师，掌握班级真实进展。</h1>
              <p>
                从规划目标、学习证据到诊断结果，把每一位学生放回具体的学习过程里观察。
              </p>
              <button class="hero-create-class" @click="createOpen = true">
                <Plus :size="19" />创建新班级
              </button>
            </div>
            <div class="hero-school">
              <School :size="28" /><span
                ><strong>{{ profile.schoolName }}</strong
                ><small>{{
                  profile.subject
                    ? `${subjectLabels[profile.subject]}教师`
                    : "教师账号"
                }}</small></span
              >
            </div>
          </section>
          <section class="teacher-metrics">
            <article>
              <span><School :size="21" /></span>
              <div>
                <small>管理班级</small
                ><strong>{{ dashboard.classrooms.length }}</strong>
              </div>
            </article>
            <article>
              <span><UsersRound :size="21" /></span>
              <div>
                <small>班级学生</small><strong>{{ totalStudents }}</strong>
              </div>
            </article>
            <article>
              <span><Bell :size="21" /></span>
              <div>
                <small>已发布通知</small
                ><strong>{{ dashboard.announcements.length }}</strong>
              </div>
            </article>
            <article>
              <span><ClipboardCheck :size="21" /></span>
              <div>
                <small>诊断卷任务</small
                ><strong>{{ dashboard.exam_assignments.length }}</strong>
              </div>
            </article>
          </section>
          <button
            v-if="dashboard.leave_requests.length"
            class="leave-overview-alert"
            @click="activeView = 'leave-requests'"
          >
            <span><UserMinus :size="21" /></span>
            <div>
              <strong
                >有
                {{ dashboard.leave_requests.length }} 条退班申请待处理</strong
              ><small>申请获批前，申请人仍保留原班级关系与权限</small>
            </div>
            <ChevronRight :size="19" />
          </button>
          <section class="teacher-section">
            <header>
              <div>
                <small>MY CLASSROOMS</small>
                <h2>班级与班级码</h2>
              </div>
              <div class="classroom-header-actions">
                <button
                  class="classroom-action-button"
                  @click="joinOpen = true"
                >
                  <UsersRound :size="18" />班级码加入
                </button>
                <button
                  class="classroom-action-button"
                  @click="createOpen = true"
                >
                  <Plus :size="18" />创建新班级
                </button>
              </div>
            </header>
            <div v-if="dashboard.classrooms.length" class="teacher-class-grid">
              <article v-for="item in dashboard.classrooms" :key="item.id">
                <div>
                  <span>{{ item.class_name.slice(0, 1) }}</span
                  ><button
                    title="复制班级码"
                    @click="copyCode(item.class_code)"
                  >
                    <Copy :size="15" />
                  </button>
                </div>
                <h3>{{ item.class_name }}</h3>
                <p>
                  {{ gradeLabel(item.grade) }} ·
                  {{ item.subject ? subjectLabels[item.subject] : "综合班级" }}
                </p>
                <span
                  class="class-access-badge"
                  :class="item.teacher_access_role"
                >
                  {{
                    item.teacher_access_role !== "owner"
                      ? "协作班级"
                      : "我创建的"
                  }}
                </span>
                <small v-if="item.owner_teacher_name" class="class-owner">
                  班主任：{{ item.owner_teacher_name }}
                </small>
                <strong>{{ item.class_code }}</strong>
                <footer>
                  <span
                    ><UsersRound :size="14" />{{
                      item.student_count
                    }}
                    名学生</span
                  ><button
                    @click="
                      selectClass(item.id);
                      activeView = 'students';
                    "
                  >
                    查看学情 <ChevronRight :size="14" />
                  </button>
                </footer>
              </article>
            </div>
            <div v-else class="teacher-empty">
              <School :size="35" /><strong>还没有班级</strong>
              <p>
                你可以创建班级，也可以使用其他老师提供的 8 位班级码加入协作。
              </p>
            </div>
          </section>
          <div class="teacher-overview-grid">
            <section class="teacher-section compact">
              <header>
                <div>
                  <small>RECENT NOTICES</small>
                  <h2>最近通知</h2>
                </div>
                <button @click="activeView = 'notices'">发布通知</button>
              </header>
              <div class="notice-mini">
                <article
                  v-for="item in dashboard.announcements.slice(0, 4)"
                  :key="item.announcement_id"
                >
                  <span :class="item.announcement_type"
                    ><Bell :size="15"
                  /></span>
                  <div>
                    <strong>{{ item.title }}</strong
                    ><small
                      >{{ item.class_name }} ·
                      {{ item.publisher_teacher_name || "教师" }}老师 ·
                      {{
                        new Date(item.created_at).toLocaleDateString("zh-CN")
                      }}</small
                    >
                  </div>
                </article>
                <p v-if="!dashboard.announcements.length">暂无通知</p>
              </div>
            </section>
            <section class="teacher-section compact">
              <header>
                <div>
                  <small>DIAGNOSTIC TASKS</small>
                  <h2>诊断卷发布</h2>
                </div>
                <button @click="activeView = 'exams'">发布试卷</button>
              </header>
              <div class="notice-mini">
                <article
                  v-for="item in dashboard.exam_assignments.slice(0, 4)"
                  :key="item.assignment_id"
                >
                  <span class="exam"><ClipboardCheck :size="15" /></span>
                  <div>
                    <strong>{{ item.title }}</strong
                    ><small
                      >{{ item.class_name }} ·
                      {{ item.publisher_teacher_name || "教师" }}老师 ·
                      {{
                        item.status === "published" ? "进行中" : "已关闭"
                      }}</small
                    >
                  </div>
                  <button
                    v-if="
                      !item.publisher_teacher_id ||
                      item.publisher_teacher_id === props.profile.teacherId
                    "
                    @click="editAssignment(item)"
                  >
                    更新
                  </button>
                </article>
                <p v-if="!dashboard.exam_assignments.length">暂无诊断卷任务</p>
              </div>
            </section>
          </div>
        </template>

        <template
          v-else-if="
            activeView === 'preparation-create' ||
            activeView === 'preparation-library'
          "
          ><TeacherPreparationWorkspace
            :classrooms="dashboard.classrooms"
            :mode="activeView === 'preparation-library' ? 'library' : 'create'"
        /></template>

        <template v-else-if="activeView === 'students'">
          <section class="teacher-subhero">
            <div>
              <small>STUDENT LEARNING STATES</small>
              <h1>学生学情与规划目标</h1>
              <p>
                查看班级成员最近一次可核验的规划、学情诊断和高考真题诊断记录。
              </p>
            </div>
            <label
              ><span>当前班级</span
              ><select
                :value="selectedClassId || ''"
                @change="
                  selectClass(
                    Number(($event.target as HTMLSelectElement).value),
                  )
                "
              >
                <option
                  v-for="item in dashboard.classrooms"
                  :key="item.id"
                  :value="item.id"
                >
                  {{ classroomOptionLabel(item) }}
                </option>
              </select></label
            >
          </section>
          <section v-if="currentClass" class="student-state-metrics">
            <article>
              <small>班级码</small><strong>{{ currentClass.class_code }}</strong
              ><button @click="copyCode(currentClass.class_code)">
                <Copy :size="14" />
              </button>
            </article>
            <article>
              <small>学生人数</small
              ><strong>{{ classDetail?.students.length || 0 }}</strong>
            </article>
            <article>
              <small>已有规划</small><strong>{{ activePlans }}</strong>
            </article>
            <article>
              <small>已发布诊断卷</small
              ><strong>{{ classDetail?.exam_assignments.length || 0 }}</strong>
            </article>
          </section>
          <section class="teacher-section student-table-section">
            <header>
              <div>
                <small>CLASS MEMBERS</small>
                <h2>{{ currentClass?.class_name || "请选择班级" }}</h2>
              </div>
              <label class="student-search"
                ><Search :size="18" /><input
                  v-model="search"
                  placeholder="搜索姓名或账号"
              /></label>
            </header>
            <div class="student-table">
              <div class="student-table-head">
                <span>学生</span><span>规划目标</span><span>最近学情诊断</span
                ><span>真题诊断</span>
              </div>
              <article
                v-for="student in pagedStudents"
                :key="student.student_id"
              >
                <div>
                  <span>{{ student.student_name.slice(0, 1) }}</span
                  ><strong
                    >{{ student.student_name
                    }}<small
                      >{{ student.student_id }} ·
                      {{ gradeLabel(student.grade) }}</small
                    ></strong
                  >
                </div>
                <p>
                  <Target :size="18" />{{ planGoal(student)
                  }}<small>{{
                    student.latest_plan
                      ? `计划状态：${student.latest_plan.status}`
                      : "等待学生完成首次规划"
                  }}</small>
                </p>
                <p>
                  <BookOpenCheck :size="18" />{{ diagnosisLabel(student)
                  }}<small>{{
                    student.latest_diagnosis
                      ? `状态版本 v${student.latest_diagnosis.state_version || 1}`
                      : "暂无可展示证据"
                  }}</small>
                </p>
                <p>
                  <ClipboardCheck :size="18" />{{
                    student.latest_exam
                      ? `${student.latest_exam.score ?? "待评分"} / ${student.latest_exam.paper_max ?? "--"} 分`
                      : "尚未测试"
                  }}<small>{{
                    student.latest_exam?.subject
                      ? subjectLabels[student.latest_exam.subject as SubjectKey]
                      : "暂无真题诊断记录"
                  }}</small>
                </p>
              </article>
              <div v-if="!filteredStudents.length" class="teacher-empty">
                <UsersRound :size="32" /><strong>班级暂无学生</strong>
                <p>请把班级码发给学生，学生加入后会显示在这里。</p>
              </div>
              <PaginationControls
                :page="studentPage"
                :total="filteredStudents.length"
                :page-size="STUDENT_PAGE_SIZE"
                label="名学生"
                @change="studentPage = $event"
              />
            </div>
          </section>
        </template>

        <template v-else-if="activeView === 'collaboration'">
          <section class="teacher-subhero collaboration-hero">
            <div>
              <small>COLLABORATION CONTROL CENTER</small>
              <h1>协作教师与班级权限</h1>
              <p>
                管理成员、处理加入申请，并明确每位教师能做什么。班级 owner
                始终保留最高权限。
              </p>
            </div>
            <UsersRound :size="45" />
          </section>
          <section class="teacher-section collaboration-panel">
            <header>
              <div>
                <small>SELECTED CLASSROOM</small>
                <h2>{{ currentClass?.class_name || "请选择班级" }}</h2>
              </div>
              <label class="collaboration-class-select">
                <span>当前管理班级</span>
                <div>
                  <School :size="17" />
                  <select
                    :value="selectedClassId || ''"
                    aria-label="选择需要管理的班级"
                    @change="
                      selectClass(
                        Number(($event.target as HTMLSelectElement).value),
                      )
                    "
                  >
                    <option
                      v-for="item in dashboard.classrooms"
                      :key="item.id"
                      :value="item.id"
                    >
                      {{ classroomOptionLabel(item) }}
                    </option>
                  </select>
                  <ChevronDown :size="17" />
                </div>
              </label>
            </header>
            <div
              v-if="
                currentClass && currentClass.teacher_access_role === 'owner'
              "
              class="policy-strip"
            >
              <div>
                <strong>班级码加入方式</strong
                ><small>{{
                  currentClass.join_policy === "approval"
                    ? "教师加入后需班主任审批"
                    : "持码教师可直接成为协作教师"
                }}</small>
              </div>
              <div class="policy-buttons">
                <button
                  :class="{ active: currentClass.join_policy !== 'approval' }"
                  @click="toggleJoinPolicy('open')"
                >
                  直接加入</button
                ><button
                  :class="{ active: currentClass.join_policy === 'approval' }"
                  @click="toggleJoinPolicy('approval')"
                >
                  加入需审批
                </button>
              </div>
            </div>
            <div v-else-if="currentClass" class="policy-strip">
              <div>
                <strong>协作教师权限</strong>
                <small
                  >可查看本班学情，发布通知、作业和诊断卷；退班审批仅班主任可见。</small
                >
              </div>
              <button
                class="danger-outline"
                :disabled="
                  currentClass.teacher_leave_request_status === 'pending'
                "
                @click="leaveCurrentClassroom"
              >
                {{
                  currentClass.teacher_leave_request_status === "pending"
                    ? "退班申请待审批"
                    : "申请退出协作"
                }}
              </button>
            </div>
            <div v-if="collaborationLoading" class="teacher-loading">
              <LoaderCircle class="spin" :size="20" />正在读取成员…
            </div>
            <div v-else class="member-list">
              <article
                v-for="member in collaborationMembers"
                :key="member.teacher_id"
                :class="member.status"
              >
                <span class="member-avatar">{{
                  member.teacher_name.slice(0, 1)
                }}</span>
                <div class="member-identity">
                  <strong
                    >{{ member.teacher_name
                    }}<em v-if="member.role === 'owner'">班主任</em
                    ><em v-else>协作教师</em></strong
                  ><small
                    >{{ member.teacher_id }} · {{ member.school_name }}</small
                  >
                </div>
                <span class="member-status">{{
                  member.status === "pending"
                    ? "待审批"
                    : member.status === "active"
                      ? "已生效"
                      : member.status === "rejected"
                        ? "已拒绝"
                        : "已退出"
                }}</span>
                <div
                  v-if="
                    member.status === 'pending' &&
                    currentClass?.teacher_access_role === 'owner'
                  "
                  class="member-actions"
                >
                  <button @click="decideTeacherJoin(member, 'approved')">
                    批准</button
                  ><button
                    class="danger-outline"
                    @click="decideTeacherJoin(member, 'rejected')"
                  >
                    拒绝
                  </button>
                </div>
                <div
                  v-else-if="
                    member.role !== 'owner' &&
                    currentClass?.teacher_access_role === 'owner' &&
                    member.status === 'active'
                  "
                  class="member-actions"
                >
                  <button class="transfer-owner" @click="transferOwner(member)">
                    转为班主任
                  </button>
                  <button class="danger-outline" @click="removeTeacher(member)">
                    移除
                  </button>
                </div>
              </article>
              <div v-if="!collaborationMembers.length" class="teacher-empty">
                <UsersRound :size="30" /><strong>暂无协作教师</strong>
                <p>将班级码分享给备课或协同教师即可加入。</p>
              </div>
            </div>
          </section>
        </template>

        <template v-else-if="activeView === 'leave-requests'">
          <section class="teacher-subhero leave-hero">
            <div>
              <small>CLASS LEAVE APPROVAL</small>
              <h1>班级退班申请审批</h1>
              <p>
                统一处理学生和协作教师的退班申请。申请获批前，申请人仍保留原班级关系与权限。
              </p>
            </div>
            <UserMinus :size="45" />
          </section>
          <section class="teacher-section leave-request-section">
            <header>
              <div>
                <small>PENDING REQUESTS</small>
                <h2>待处理申请</h2>
              </div>
              <span>{{ dashboard.leave_requests.length }} 条待办</span>
            </header>
            <div class="leave-request-list">
              <article
                v-for="item in pagedLeaveRequests"
                :key="item.request_id"
              >
                <span>{{ leaveApplicantName(item).slice(0, 1) }}</span>
                <div>
                  <strong>{{ leaveApplicantName(item) }}</strong>
                  <small
                    >{{
                      item.request_source === "collaborator"
                        ? "教师账号"
                        : "学生账号"
                    }}：{{ leaveApplicantId(item) }}</small
                  >
                </div>
                <div>
                  <strong>{{ item.class_name }}</strong>
                  <small
                    class="leave-request-source"
                    :class="item.request_source || 'student'"
                  >
                    {{
                      item.request_source === "collaborator"
                        ? "来源：协作教师退班申请"
                        : "来源：学生退班申请"
                    }}
                  </small>
                  <small
                    >申请时间：{{
                      new Date(item.requested_at).toLocaleString("zh-CN")
                    }}</small
                  >
                </div>
                <div class="leave-review-actions">
                  <button
                    :disabled="reviewingRequestId === item.request_id"
                    @click="reviewLeave(item, 'rejected')"
                  >
                    <XCircle :size="17" />拒绝</button
                  ><button
                    :disabled="reviewingRequestId === item.request_id"
                    @click="reviewLeave(item, 'approved')"
                  >
                    <LoaderCircle
                      v-if="reviewingRequestId === item.request_id"
                      class="spin"
                      :size="17"
                    /><CheckCircle2 v-else :size="17" />同意退出
                  </button>
                </div>
              </article>
              <div
                v-if="!dashboard.leave_requests.length"
                class="teacher-empty"
              >
                <CheckCircle2 :size="36" /><strong
                  >暂时没有待处理的退班申请</strong
                >
                <p>新申请会在这里提示，并每 30 秒自动刷新。</p>
              </div>
            </div>
            <PaginationControls
              :page="leaveRequestPage"
              :total="dashboard.leave_requests.length"
              :page-size="CONTENT_PAGE_SIZE"
              label="条申请"
              @change="leaveRequestPage = $event"
            />
          </section>
        </template>

        <template v-else-if="activeView === 'notices'">
          <section class="teacher-subhero notice-hero">
            <div>
              <small>CLASS COMMUNICATION</small>
              <h1>发布通知与作业</h1>
              <p>
                学生加入班级后，会在自己的“班级与通知”页面实时看到发布内容。
              </p>
            </div>
            <Bell :size="42" />
          </section>
          <div class="teacher-editor-grid">
            <form
              class="teacher-section teacher-publish-form"
              @submit.prevent="submitNotice"
            >
              <header>
                <div>
                  <small>NEW ANNOUNCEMENT</small>
                  <h2>新建班级通知</h2>
                </div>
                <Send :size="20" />
              </header>
              <label
                ><span>发布班级</span
                ><select v-model.number="noticeForm.classroomId">
                  <option
                    v-for="item in dashboard.classrooms"
                    :key="item.id"
                    :value="item.id"
                  >
                    {{ classroomOptionLabel(item) }}
                  </option>
                </select></label
              >
              <div class="batch-class-picker">
                <strong>批量发布（可选）</strong
                ><small
                  >勾选多个班级后，本次内容会一次发布并返回逐班结果。</small
                ><label
                  v-for="item in dashboard.classrooms"
                  :key="`notice-${item.id}`"
                  ><input
                    type="checkbox"
                    :checked="selectedBatchClassIds.includes(item.id)"
                    @change="selectClassroomForBatch(item.id)"
                  />{{ classroomOptionLabel(item) }}</label
                >
              </div>
              <label
                ><span>通知类型</span>
                <div class="type-buttons">
                  <button
                    type="button"
                    :class="{
                      active: noticeForm.announcementType === 'homework',
                    }"
                    @click="noticeForm.announcementType = 'homework'"
                  >
                    作业</button
                  ><button
                    type="button"
                    :class="{
                      active: noticeForm.announcementType === 'holiday',
                    }"
                    @click="noticeForm.announcementType = 'holiday'"
                  >
                    放假</button
                  ><button
                    type="button"
                    :class="{
                      active: noticeForm.announcementType === 'notice',
                    }"
                    @click="noticeForm.announcementType = 'notice'"
                  >
                    普通通知
                  </button>
                </div></label
              ><label
                ><span>标题</span
                ><input
                  v-model="noticeForm.title"
                  placeholder="例如：周末数学作业" /></label
              ><label
                ><span>详细内容</span
                ><textarea
                  v-model="noticeForm.content"
                  rows="6"
                  placeholder="填写作业要求、放假安排或其他通知…"
                /></label
              ><label
                ><span>截止/提醒时间（选填）</span
                ><input
                  v-model="noticeForm.dueAt"
                  type="datetime-local" /></label
              ><button class="green-submit" :disabled="actionLoading">
                <LoaderCircle
                  v-if="actionLoading"
                  class="spin"
                  :size="17"
                /><Send v-else :size="17" />发布到学生端
              </button>
            </form>
            <section class="teacher-section publish-history">
              <header>
                <div>
                  <small>PUBLISHED</small>
                  <h2>已发布内容</h2>
                </div>
                <span>{{ dashboard.announcements.length }} 条</span>
              </header>
              <article
                v-for="item in pagedAnnouncements"
                :key="item.announcement_id"
              >
                <span :class="item.announcement_type"><Bell :size="16" /></span>
                <div>
                  <small
                    >{{ item.class_name }} ·
                    {{ item.publisher_teacher_name || "教师" }}老师 ·
                    {{
                      item.announcement_type === "homework"
                        ? "作业"
                        : item.announcement_type === "holiday"
                          ? "放假通知"
                          : "班级通知"
                    }}</small
                  ><strong>{{ item.title }}</strong>
                  <p>{{ item.content }}</p>
                  <time>{{
                    new Date(item.created_at).toLocaleString("zh-CN")
                  }}</time>
                </div>
              </article>
              <div v-if="!dashboard.announcements.length" class="teacher-empty">
                <Bell :size="31" /><strong>暂无通知</strong>
              </div>
              <PaginationControls
                :page="noticePage"
                :total="dashboard.announcements.length"
                :page-size="CONTENT_PAGE_SIZE"
                label="条通知"
                @change="noticePage = $event"
              />
            </section>
          </div>
        </template>

        <template v-else-if="activeView === 'exams'">
          <section class="teacher-subhero exam-hero">
            <div>
              <small>DIAGNOSTIC PAPER ASSIGNMENT</small>
              <h1>发布与更新学情诊断卷</h1>
              <p>
                从现有高考真题诊断卷中选卷。更新任务时可更换试卷、截止时间与发布状态。
              </p>
            </div>
            <ClipboardCheck :size="45" />
          </section>
          <div class="teacher-editor-grid">
            <form
              class="teacher-section teacher-publish-form"
              @submit.prevent="submitExam"
            >
              <header>
                <div>
                  <small>{{
                    examForm.assignmentId ? "UPDATE TASK" : "NEW TASK"
                  }}</small>
                  <h2>
                    {{
                      examForm.assignmentId ? "更新诊断任务" : "发布诊断试卷"
                    }}
                  </h2>
                </div>
                <ClipboardCheck :size="21" />
              </header>
              <label
                ><span>发布班级</span
                ><select v-model.number="examForm.classroomId">
                  <option
                    v-for="item in dashboard.classrooms"
                    :key="item.id"
                    :value="item.id"
                  >
                    {{ classroomOptionLabel(item) }}
                  </option>
                </select></label
              >
              <div class="batch-class-picker">
                <strong>批量发布（可选）</strong
                ><small>勾选多个班级后，按相同试卷和截止时间发布。</small
                ><label
                  v-for="item in dashboard.classrooms"
                  :key="`exam-${item.id}`"
                  ><input
                    type="checkbox"
                    :checked="selectedBatchClassIds.includes(item.id)"
                    @change="selectClassroomForBatch(item.id)"
                  />{{ classroomOptionLabel(item) }}</label
                >
              </div>
              <label
                ><span>选择真题诊断卷</span
                ><select v-model="examForm.paperId" @change="paperChanged">
                  <option value="">请选择试卷</option>
                  <optgroup
                    v-for="[key, label] in Object.entries(subjectLabels)"
                    :key="key"
                    :label="label"
                  >
                    <option
                      v-for="paper in catalogPapers.filter(
                        (item) => item.subject === key,
                      )"
                      :key="paper.paper_id"
                      :value="paper.paper_id"
                    >
                      {{ paper.title }}
                    </option>
                  </optgroup>
                </select></label
              ><label
                ><span>任务标题</span
                ><input
                  v-model="examForm.title"
                  placeholder="学生端显示的任务名称" /></label
              ><label
                ><span>截止时间（选填）</span
                ><input v-model="examForm.dueAt" type="datetime-local" /></label
              ><label
                ><span>任务状态</span
                ><select v-model="examForm.status">
                  <option value="published">发布中</option>
                  <option value="closed">已关闭</option>
                  <option value="archived">归档</option>
                </select></label
              ><button class="green-submit" :disabled="actionLoading">
                <LoaderCircle
                  v-if="actionLoading"
                  class="spin"
                  :size="17"
                /><CheckCircle2 v-else :size="17" />{{
                  examForm.assignmentId ? "保存更新" : "发布诊断卷"
                }}
              </button>
            </form>
            <section class="teacher-section publish-history exam-history">
              <header>
                <div>
                  <small>ASSIGNMENTS</small>
                  <h2>已发布诊断卷</h2>
                </div>
                <span>{{ dashboard.exam_assignments.length }} 份</span>
              </header>
              <article
                v-for="item in pagedExamAssignments"
                :key="item.assignment_id"
              >
                <span class="exam"><ClipboardCheck :size="17" /></span>
                <div>
                  <small
                    >{{ item.class_name }} ·
                    {{ item.publisher_teacher_name || "教师" }}老师 ·
                    {{
                      item.status === "published" ? "发布中" : "已关闭"
                    }}</small
                  ><strong>{{ item.title }}</strong>
                  <p>试卷 ID：{{ item.paper_id }}</p>
                  <time>{{
                    item.due_at
                      ? `截止 ${new Date(item.due_at).toLocaleString("zh-CN")}`
                      : "未设置截止时间"
                  }}</time>
                </div>
                <button
                  v-if="
                    !item.publisher_teacher_id ||
                    item.publisher_teacher_id === props.profile.teacherId
                  "
                  @click="editAssignment(item)"
                >
                  更新
                </button>
              </article>
              <div
                v-if="!dashboard.exam_assignments.length"
                class="teacher-empty"
              >
                <ClipboardCheck :size="31" /><strong>暂无诊断卷任务</strong>
              </div>
              <PaginationControls
                :page="examPage"
                :total="dashboard.exam_assignments.length"
                :page-size="CONTENT_PAGE_SIZE"
                label="份任务"
                @change="examPage = $event"
              />
            </section>
          </div>
        </template>
      </div>
    </main>

    <div
      v-if="createOpen"
      class="teacher-modal-mask"
      @click.self="createOpen = false"
    >
      <form class="teacher-modal" @submit.prevent="submitClassroom">
        <header>
          <div>
            <small>CREATE CLASSROOM</small>
            <h2>创建新班级</h2>
          </div>
          <button type="button" @click="createOpen = false">
            <X :size="18" />
          </button>
        </header>
        <label
          ><span>班级名称</span
          ><input
            v-model="classForm.className"
            placeholder="例如：高二 3 班数学" /></label
        ><label
          ><span>年级</span
          ><select v-model="classForm.grade">
            <option value="grade_10">高一</option>
            <option value="grade_11">高二</option>
            <option value="grade_12">高三</option>
          </select></label
        ><label
          ><span>主要学科</span
          ><select v-model="classForm.subject">
            <option
              v-for="[key, label] in Object.entries(subjectLabels)"
              :key="key"
              :value="key"
            >
              {{ label }}
            </option>
          </select></label
        >
        <p>创建后会生成唯一的 8 位班级码，学生使用班级码加入。</p>
        <button class="green-submit" :disabled="actionLoading">
          <LoaderCircle v-if="actionLoading" class="spin" :size="17" /><Plus
            v-else
            :size="17"
          />创建并生成班级码
        </button>
      </form>
    </div>
    <div
      v-if="joinOpen"
      class="teacher-modal-mask"
      @click.self="joinOpen = false"
    >
      <form
        class="teacher-modal join-teacher-modal"
        @submit.prevent="submitTeacherJoin"
      >
        <header>
          <div>
            <small>JOIN CLASSROOM</small>
            <h2>通过班级码加入</h2>
          </div>
          <button type="button" @click="joinOpen = false">
            <X :size="18" />
          </button>
        </header>
        <label>
          <span>其他教师提供的 8 位班级码</span>
          <input
            v-model="joinCode"
            maxlength="8"
            autocomplete="off"
            placeholder="例如：ABCD2345"
            @input="joinCode = joinCode.toUpperCase()"
          />
        </label>
        <p>
          加入后可查看该班学生，并可在“通知与作业”和“诊断卷发布”中选择该班级。
        </p>
        <button class="green-submit" :disabled="actionLoading">
          <LoaderCircle v-if="actionLoading" class="spin" :size="17" />
          <UsersRound v-else :size="17" />加入班级
        </button>
      </form>
    </div>
    <Transition name="toast"
      ><div v-if="toast" class="teacher-toast">
        <CheckCircle2 :size="17" />{{ toast }}
      </div></Transition
    >
  </div>
</template>

<style scoped>
.teacher-shell {
  --green: #168363;
  --green-dark: #124d3e;
  --green-soft: #e7f6f0;
  min-height: 100vh;
  color: #24483d;
  background: #f4f8f6;
}
.teacher-shell > aside {
  position: fixed;
  z-index: 30;
  inset: 0 auto 0 0;
  display: flex;
  width: 248px;
  flex-direction: column;
  padding: 24px 17px 18px;
  color: #dff3ec;
  background: linear-gradient(180deg, #103e34, #17694f);
}
.teacher-workspace-brand {
  display: flex;
  align-items: center;
  gap: 10px;
}
.teacher-workspace-brand > span {
  display: grid;
  width: 40px;
  height: 40px;
  place-items: center;
  color: #0f5d45;
  background: #dff5ec;
  border-radius: 11px;
}
.teacher-workspace-brand > div {
  display: grid;
  gap: 3px;
}
.teacher-workspace-brand strong {
  font-size: 14px;
}
.teacher-workspace-brand small {
  color: #9bcdbb;
  font-size: 7px;
  letter-spacing: 0.15em;
}
.teacher-workspace-brand > button {
  display: none;
  margin-left: auto;
  color: #dff3ec;
  border: 0;
  background: transparent;
}
.teacher-shell aside nav {
  display: grid;
  gap: 7px;
  margin-top: 38px;
}
.teacher-shell aside nav > small,
.teacher-class-shortcuts > small {
  margin: 0 9px 5px;
  color: #81bca7;
  font-size: 7px;
  font-weight: 800;
  letter-spacing: 0.15em;
}
.teacher-shell aside nav button {
  display: flex;
  height: 43px;
  align-items: center;
  gap: 10px;
  padding: 0 12px;
  color: #b9ddcf;
  border: 0;
  background: transparent;
  border-radius: 9px;
  font-size: 10px;
  text-align: left;
}
.teacher-shell aside nav button span {
  flex: 1;
}
.teacher-shell aside nav button.active {
  color: #155c47;
  background: #e3f4ed;
  box-shadow: 0 7px 17px rgba(5, 43, 31, 0.2);
}
.teacher-class-shortcuts {
  display: grid;
  gap: 6px;
  margin-top: 28px;
  padding-top: 20px;
  border-top: 1px solid rgba(255, 255, 255, 0.09);
}
.teacher-class-shortcuts > button {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 8px;
  color: #c0dfd3;
  border: 0;
  background: transparent;
  border-radius: 8px;
  text-align: left;
}
.teacher-class-shortcuts > button:hover,
.teacher-class-shortcuts > button.active {
  background: rgba(255, 255, 255, 0.08);
}
.teacher-class-shortcuts > button > span {
  display: grid;
  width: 29px;
  height: 29px;
  place-items: center;
  color: #174e3e;
  background: #bfe8d9;
  border-radius: 8px;
  font-size: 9px;
  font-weight: 850;
}
.teacher-class-shortcuts > button > div {
  display: grid;
  gap: 2px;
}
.teacher-class-shortcuts strong {
  font-size: 8px;
}
.teacher-class-shortcuts small {
  color: #8fc1af;
  font-size: 7px;
}
.teacher-profile {
  display: flex;
  align-items: center;
  gap: 9px;
  margin-top: auto;
  padding: 12px 9px;
  border: 1px solid rgba(255, 255, 255, 0.09);
  background: rgba(255, 255, 255, 0.05);
  border-radius: 11px;
}
.teacher-profile > span {
  display: grid;
  width: 34px;
  height: 34px;
  place-items: center;
  color: #165741;
  background: #d9f2e9;
  border-radius: 9px;
  font-size: 11px;
  font-weight: 850;
}
.teacher-profile > div {
  display: grid;
  min-width: 0;
  flex: 1;
  gap: 3px;
}
.teacher-profile strong {
  font-size: 9px;
}
.teacher-profile small {
  overflow: hidden;
  color: #8fc1af;
  font-size: 7px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.teacher-profile button {
  color: #aad3c4;
  border: 0;
  background: transparent;
}
.teacher-shell > main {
  min-height: 100vh;
  margin-left: 248px;
}
.teacher-topbar {
  position: sticky;
  z-index: 20;
  top: 0;
  display: flex;
  height: 68px;
  align-items: center;
  padding: 0 30px;
  border-bottom: 1px solid #dfe9e5;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(12px);
}
.teacher-topbar > button:first-child {
  display: none;
  color: #2b6554;
  border: 0;
  background: transparent;
}
.teacher-topbar > div {
  display: grid;
  gap: 2px;
}
.teacher-topbar > div small {
  color: #78a093;
  font-size: 7px;
  letter-spacing: 0.15em;
}
.teacher-topbar > div strong {
  font-size: 13px;
}
.teacher-topbar > span {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-left: auto;
  color: #728d84;
  font-size: 8px;
}
.teacher-topbar > span i {
  width: 7px;
  height: 7px;
  background: #27af7f;
  border-radius: 50%;
  box-shadow: 0 0 0 4px #e2f5ee;
}
.refresh-teacher {
  display: flex;
  align-items: center;
  gap: 5px;
  margin-left: 17px;
  padding: 8px 10px;
  color: #426b5e;
  border: 1px solid #d7e5df;
  background: #fff;
  border-radius: 8px;
  font-size: 8px;
}
.teacher-content {
  width: min(100%, 1440px);
  margin: auto;
  padding: 28px 32px 60px;
}
.teacher-error {
  padding: 11px 13px;
  color: #a43b3b;
  background: #fff0ef;
  border-radius: 9px;
  font-size: 9px;
}
.teacher-loading {
  display: grid;
  min-height: 65vh;
  place-content: center;
  justify-items: center;
  gap: 12px;
  color: #67847a;
  font-size: 10px;
}
.teacher-hero,
.teacher-subhero {
  display: flex;
  min-height: 215px;
  align-items: center;
  justify-content: space-between;
  overflow: hidden;
  padding: 35px 39px;
  color: #fff;
  background:
    radial-gradient(
      circle at 85% 30%,
      rgba(255, 255, 255, 0.16),
      transparent 27%
    ),
    linear-gradient(135deg, #11523f, #188465 70%, #3eae86);
  border-radius: 18px;
  box-shadow: 0 19px 40px rgba(22, 117, 88, 0.15);
}
.teacher-hero > div:first-child,
.teacher-subhero > div:first-child {
  max-width: 790px;
}
.teacher-hero small,
.teacher-subhero small {
  color: #bde9da;
  font-size: 8px;
  font-weight: 850;
  letter-spacing: 0.17em;
}
.teacher-hero h1,
.teacher-subhero h1 {
  margin: 13px 0 9px;
  font-size: clamp(27px, 3.2vw, 42px);
  letter-spacing: -0.045em;
}
.teacher-hero p,
.teacher-subhero p {
  margin: 0;
  color: #cceade;
  font-size: 10px;
  line-height: 1.8;
}
.teacher-hero > div:first-child > button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-top: 20px;
  padding: 10px 14px;
  color: #145c47;
  border: 0;
  background: #fff;
  border-radius: 8px;
  font-size: 9px;
  font-weight: 750;
}
.teacher-hero .hero-create-class {
  min-height: 44px;
  padding: 0 18px;
  font-size: 15px;
  font-weight: 800;
}
.hero-school {
  display: flex;
  max-width: 300px;
  align-items: center;
  gap: 13px;
  padding: 18px;
  border: 1px solid rgba(255, 255, 255, 0.18);
  background: rgba(255, 255, 255, 0.09);
  border-radius: 13px;
}
.hero-school span {
  display: grid;
  gap: 5px;
}
.hero-school strong {
  font-size: 11px;
}
.hero-school small {
  color: #bce5d6;
  font-size: 8px;
}
.teacher-metrics,
.student-state-metrics {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 13px;
  margin: 16px 0;
}
.teacher-metrics article {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 16px;
  border: 1px solid #dfe9e5;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 5px 16px rgba(25, 76, 60, 0.04);
}
.teacher-metrics article > span {
  display: grid;
  width: 38px;
  height: 38px;
  place-items: center;
  color: #168363;
  background: #e7f6f0;
  border-radius: 10px;
}
.teacher-metrics article > div {
  display: grid;
  gap: 3px;
}
.teacher-metrics small,
.student-state-metrics small {
  color: #81968f;
  font-size: 8px;
}
.teacher-metrics strong {
  font-size: 20px;
}
.teacher-section {
  margin-top: 16px;
  padding: 23px;
  border: 1px solid #dfe9e5;
  background: #fff;
  border-radius: 15px;
  box-shadow: 0 6px 20px rgba(29, 75, 61, 0.045);
}
.teacher-section > header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 15px;
  padding-bottom: 16px;
  border-bottom: 1px solid #edf2f0;
}
.teacher-section > header small {
  color: #4b947e;
  font-size: 7px;
  font-weight: 850;
  letter-spacing: 0.14em;
}
.teacher-section > header h2 {
  margin: 5px 0 0;
  font-size: 16px;
}
.teacher-section > header > button,
.teacher-section > header > span {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 8px 10px;
  color: #157254;
  border: 1px solid #bcded2;
  background: #f5fbf8;
  border-radius: 8px;
  font-size: 8px;
}
.teacher-class-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 13px;
  margin-top: 17px;
}
.teacher-class-grid > article {
  padding: 18px;
  border: 1px solid #dfebe6;
  background: linear-gradient(145deg, #fff, #f8fcfa);
  border-radius: 13px;
}
.teacher-class-grid > article > div {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.teacher-class-grid > article > div > span {
  display: grid;
  width: 39px;
  height: 39px;
  place-items: center;
  color: #fff;
  background: #188363;
  border-radius: 10px;
  font-size: 12px;
  font-weight: 850;
}
.teacher-class-grid > article > div > button {
  color: #72958a;
  border: 0;
  background: transparent;
}
.teacher-class-grid h3 {
  margin: 15px 0 5px;
  font-size: 13px;
}
.teacher-class-grid p {
  margin: 0;
  color: #7c918a;
  font-size: 8px;
}
.teacher-class-grid > article > strong {
  display: block;
  margin-top: 15px;
  color: #176f54;
  font-size: 19px;
  letter-spacing: 0.15em;
}
.teacher-class-grid footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 16px;
  padding-top: 13px;
  border-top: 1px solid #e8f0ed;
}
.teacher-class-grid footer span,
.teacher-class-grid footer button {
  display: flex;
  align-items: center;
  gap: 5px;
  color: #758d85;
  border: 0;
  background: transparent;
  font-size: 8px;
}
.teacher-class-grid footer button {
  color: #167758;
}
.teacher-empty {
  display: grid;
  min-height: 190px;
  place-content: center;
  justify-items: center;
  gap: 8px;
  color: #7f9990;
  text-align: center;
}
.teacher-empty strong {
  color: #3e6659;
  font-size: 11px;
}
.teacher-empty p {
  margin: 0;
  font-size: 8px;
}
.teacher-overview-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
.teacher-section.compact {
  min-height: 320px;
}
.notice-mini {
  display: grid;
  margin-top: 10px;
}
.notice-mini article {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 12px 2px;
  border-bottom: 1px solid #edf2f0;
}
.notice-mini article > span,
.publish-history article > span {
  display: grid;
  width: 34px;
  height: 34px;
  place-items: center;
  color: #7c651a;
  background: #fff3cf;
  border-radius: 9px;
}
.notice-mini article > span.homework,
.publish-history article > span.homework {
  color: #176f54;
  background: #e4f5ed;
}
.notice-mini article > span.exam,
.publish-history article > span.exam {
  color: #426ca8;
  background: #eaf1fb;
}
.notice-mini article > div {
  display: grid;
  flex: 1;
  gap: 4px;
}
.notice-mini strong {
  font-size: 9px;
}
.notice-mini small {
  color: #83988f;
  font-size: 7px;
}
.notice-mini article > button {
  color: #167758;
  border: 0;
  background: transparent;
  font-size: 8px;
}
.notice-mini > p {
  color: #899c95;
  font-size: 9px;
}
.teacher-subhero {
  min-height: 180px;
}
.teacher-subhero > label {
  display: grid;
  min-width: 220px;
  gap: 7px;
}
.teacher-subhero > label span {
  font-size: 8px;
}
.teacher-subhero select {
  height: 42px;
  padding: 0 12px;
  color: #245346;
  border: 1px solid rgba(255, 255, 255, 0.3);
  background: #fff;
  border-radius: 8px;
  font-size: 9px;
}
.student-state-metrics article {
  position: relative;
  display: grid;
  gap: 5px;
  padding: 15px;
  border: 1px solid #dfe9e5;
  background: #fff;
  border-radius: 11px;
}
.student-state-metrics strong {
  color: #185c49;
  font-size: 15px;
}
.student-state-metrics button {
  position: absolute;
  right: 12px;
  top: 18px;
  color: #67877c;
  border: 0;
  background: transparent;
}
.student-table-section {
  padding-bottom: 8px;
}
.student-search {
  display: flex;
  height: 38px;
  align-items: center;
  gap: 7px;
  padding: 0 10px;
  border: 1px solid #dbe7e2;
  background: #f9fcfb;
  border-radius: 8px;
}
.student-search input {
  width: 180px;
  border: 0;
  outline: 0;
  background: transparent;
  font-size: 8px;
}
.student-table {
  margin-top: 7px;
}
.student-table-head,
.student-table > article {
  display: grid;
  grid-template-columns: 1.1fr 1fr 1.4fr 1fr;
  gap: 13px;
  align-items: center;
}
.student-table-head {
  padding: 10px 12px;
  color: #82978f;
  font-size: 7px;
  font-weight: 800;
}
.student-table > article {
  padding: 14px 12px;
  border-top: 1px solid #edf2f0;
}
.student-table > article > div {
  display: flex;
  align-items: center;
  gap: 9px;
}
.student-table > article > div > span {
  display: grid;
  width: 35px;
  height: 35px;
  place-items: center;
  color: #17684f;
  background: #e1f3ec;
  border-radius: 9px;
  font-size: 10px;
  font-weight: 850;
}
.student-table > article > div strong {
  display: grid;
  gap: 4px;
  font-size: 9px;
}
.student-table small {
  display: block;
  color: #899b95;
  font-size: 7px;
  font-weight: 400;
}
.student-table p {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 4px 6px;
  align-items: center;
  margin: 0;
  color: #47685d;
  font-size: 8px;
}
.student-table p svg {
  color: #17805f;
}
.student-table p small {
  grid-column: 2;
}
.notice-hero {
  background: linear-gradient(135deg, #125441, #198563);
}
.exam-hero {
  background: linear-gradient(135deg, #174e43, #2b8e73);
}
.teacher-editor-grid {
  display: grid;
  grid-template-columns: 0.86fr 1.14fr;
  gap: 16px;
}
.teacher-publish-form {
  display: grid;
  align-content: start;
  gap: 15px;
}
.teacher-publish-form > header {
  margin-bottom: 2px;
}
.teacher-publish-form > label,
.teacher-modal > label {
  display: grid;
  gap: 7px;
}
.teacher-publish-form > label > span,
.teacher-modal > label > span {
  color: #42685d;
  font-size: 8px;
  font-weight: 750;
}
.teacher-publish-form input,
.teacher-publish-form select,
.teacher-publish-form textarea,
.teacher-modal input,
.teacher-modal select {
  width: 100%;
  padding: 0 11px;
  color: #264c41;
  border: 1px solid #d8e6e1;
  outline: 0;
  background: #fbfdfc;
  border-radius: 8px;
  font: inherit;
  font-size: 9px;
}
.teacher-publish-form input,
.teacher-publish-form select,
.teacher-modal input,
.teacher-modal select {
  height: 42px;
}
.teacher-publish-form textarea {
  padding-block: 10px;
  line-height: 1.6;
  resize: vertical;
}
.type-buttons {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 7px;
}
.type-buttons button {
  height: 37px;
  color: #68847a;
  border: 1px solid #dbe7e2;
  background: #fff;
  border-radius: 8px;
  font-size: 8px;
}
.type-buttons button.active {
  color: #fff;
  border-color: #168363;
  background: #168363;
}
.green-submit {
  display: flex;
  min-height: 44px;
  align-items: center;
  justify-content: center;
  gap: 6px;
  color: #fff;
  border: 0;
  background: linear-gradient(135deg, #157457, #1b9972);
  border-radius: 9px;
  font-size: 9px;
  font-weight: 800;
  box-shadow: 0 9px 20px rgba(22, 131, 99, 0.16);
}
.publish-history {
  max-height: 760px;
  overflow: auto;
}
.publish-history > article {
  display: flex;
  align-items: flex-start;
  gap: 11px;
  padding: 15px 2px;
  border-bottom: 1px solid #edf2f0;
}
.publish-history > article > div {
  display: grid;
  flex: 1;
  gap: 5px;
}
.publish-history article small {
  color: #41816d;
  font-size: 7px;
}
.publish-history article strong {
  font-size: 10px;
}
.publish-history article p {
  margin: 0;
  color: #70887f;
  font-size: 8px;
  line-height: 1.65;
}
.publish-history article time {
  color: #96a69f;
  font-size: 7px;
}
.publish-history article > button {
  padding: 7px 9px;
  color: #167758;
  border: 1px solid #c9e1d8;
  background: #f5fbf8;
  border-radius: 7px;
  font-size: 8px;
}
.teacher-modal-mask {
  position: fixed;
  z-index: 60;
  inset: 0;
  display: grid;
  place-items: center;
  padding: 20px;
  background: rgba(14, 47, 38, 0.48);
  backdrop-filter: blur(4px);
}
.teacher-modal {
  display: grid;
  width: min(100%, 470px);
  gap: 15px;
  padding: 27px;
  border: 1px solid #dce8e3;
  background: #fff;
  border-radius: 17px;
  box-shadow: 0 24px 65px rgba(9, 46, 35, 0.22);
}
.teacher-modal header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.teacher-modal header small {
  color: #4c907b;
  font-size: 7px;
  letter-spacing: 0.14em;
}
.teacher-modal h2 {
  margin: 5px 0 0;
  font-size: 18px;
}
.teacher-modal header button {
  color: #6d877e;
  border: 0;
  background: transparent;
}
.teacher-modal > p {
  margin: 0;
  color: #7b9189;
  font-size: 8px;
}
.teacher-toast {
  position: fixed;
  z-index: 80;
  right: 24px;
  bottom: 24px;
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 12px 15px;
  color: #fff;
  background: #155f49;
  border-radius: 9px;
  box-shadow: 0 13px 30px rgba(16, 75, 57, 0.25);
  font-size: 9px;
}
.teacher-mask {
  display: none;
}
@media (max-width: 1050px) {
  .teacher-class-grid {
    grid-template-columns: 1fr 1fr;
  }
  .teacher-overview-grid,
  .teacher-editor-grid {
    grid-template-columns: 1fr;
  }
  .student-table-head {
    display: none;
  }
  .student-table > article {
    grid-template-columns: 1fr 1fr;
  }
}
@media (max-width: 780px) {
  .teacher-shell > aside {
    transform: translateX(-100%);
    transition: 0.25s ease;
  }
  .teacher-shell > aside.open {
    transform: translateX(0);
  }
  .teacher-workspace-brand > button {
    display: block;
  }
  .teacher-mask {
    position: fixed;
    z-index: 25;
    inset: 0;
    display: block;
    background: rgba(9, 43, 33, 0.4);
  }
  .teacher-shell > main {
    margin-left: 0;
  }
  .teacher-topbar {
    padding: 0 16px;
  }
  .teacher-topbar > button:first-child {
    display: block;
    margin-right: 10px;
  }
  .teacher-topbar > span {
    display: none;
  }
  .teacher-content {
    padding: 18px 16px 45px;
  }
  .teacher-hero,
  .teacher-subhero {
    align-items: flex-start;
    flex-direction: column;
    gap: 20px;
    padding: 27px 23px;
  }
  .hero-school {
    display: none;
  }
  .teacher-metrics,
  .student-state-metrics {
    grid-template-columns: 1fr 1fr;
  }
  .teacher-class-grid {
    grid-template-columns: 1fr;
  }
  .student-table > article {
    grid-template-columns: 1fr;
  }
  .teacher-subhero > label {
    width: 100%;
  }
}
@media (max-width: 480px) {
  .teacher-metrics,
  .student-state-metrics {
    grid-template-columns: 1fr;
  }
  .teacher-overview-grid {
    display: block;
  }
}
/* Classroom-readable typography: optimized for prolonged teacher use. */
.teacher-shell {
  font-size: 15px;
  line-height: 1.55;
}
.teacher-shell aside nav button {
  min-height: 48px;
  font-size: 14px;
}
.teacher-shell aside nav > small,
.teacher-class-shortcuts > small {
  font-size: 11px;
}
.teacher-class-shortcuts strong {
  font-size: 13px;
}
.teacher-class-shortcuts small,
.teacher-profile small {
  font-size: 11px;
}
.teacher-profile strong {
  font-size: 14px;
}
.teacher-topbar > div small {
  font-size: 11px;
}
.teacher-topbar > div strong {
  font-size: 18px;
}
.teacher-topbar > span,
.refresh-teacher {
  font-size: 13px;
}
.teacher-hero small,
.teacher-subhero small {
  font-size: 12px;
}
.teacher-hero p,
.teacher-subhero p {
  font-size: 15px;
  line-height: 1.75;
}
.teacher-metrics small,
.student-state-metrics small {
  font-size: 13px;
}
.teacher-metrics strong {
  font-size: 24px;
}
.teacher-section > header small {
  font-size: 11px;
}
.teacher-section > header h2 {
  font-size: 20px;
}
.teacher-section > header > button,
.teacher-section > header > span {
  min-height: 40px;
  font-size: 13px;
}
.teacher-class-grid h3 {
  font-size: 17px;
}
.teacher-class-grid p,
.teacher-class-grid footer span,
.teacher-class-grid footer button {
  font-size: 13px;
}
.notice-mini strong {
  font-size: 14px;
}
.notice-mini small,
.notice-mini article > button {
  font-size: 12px;
}
.student-state-metrics strong {
  font-size: 20px;
}
.student-search {
  height: 46px;
}
.student-search input {
  width: 230px;
  font-size: 15px;
}
.student-table-head {
  padding: 14px 16px;
  font-size: 13px;
}
.student-table > article {
  min-height: 96px;
  padding: 18px 16px;
}
.student-table > article > div > span {
  width: 44px;
  height: 44px;
  font-size: 15px;
}
.student-table > article > div strong {
  font-size: 15px;
}
.student-table p {
  font-size: 14px;
  line-height: 1.45;
}
.student-table small {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.4;
}
.teacher-publish-form > label > span,
.teacher-modal > label > span {
  font-size: 14px;
}
.teacher-publish-form input,
.teacher-publish-form select,
.teacher-publish-form textarea,
.teacher-modal input,
.teacher-modal select {
  font-size: 15px;
}
.teacher-publish-form input,
.teacher-publish-form select,
.teacher-modal input,
.teacher-modal select {
  height: 48px;
}
.type-buttons button,
.green-submit {
  font-size: 14px;
}
.green-submit {
  min-height: 48px;
}
.publish-history {
  max-height: none;
  overflow: visible;
}
.publish-history article small {
  font-size: 12px;
}
.publish-history article strong {
  font-size: 15px;
}
.publish-history article p {
  font-size: 14px;
}
.publish-history article time,
.publish-history article > button {
  font-size: 12px;
}
.teacher-empty strong {
  font-size: 15px;
}
.teacher-empty p,
.teacher-modal > p,
.teacher-error,
.teacher-loading,
.teacher-toast {
  font-size: 13px;
}
.leave-nav-badge {
  display: grid;
  min-width: 22px;
  height: 22px;
  place-items: center;
  padding: 0 6px;
  color: #fff;
  background: #e06a55;
  border-radius: 11px;
  font-size: 12px;
}
.teacher-shell aside nav button.active .leave-nav-badge {
  color: #fff;
  background: #d45843;
}
.leave-overview-alert {
  display: flex;
  width: 100%;
  align-items: center;
  gap: 13px;
  margin: 0 0 16px;
  padding: 15px 18px;
  color: #6f3a2f;
  border: 1px solid #f0c9bf;
  background: #fff4f0;
  border-radius: 13px;
  text-align: left;
}
.leave-overview-alert > span {
  display: grid;
  width: 42px;
  height: 42px;
  place-items: center;
  color: #bd4f3e;
  background: #ffe2da;
  border-radius: 10px;
}
.leave-overview-alert > div {
  display: grid;
  flex: 1;
  gap: 4px;
}
.leave-overview-alert strong {
  font-size: 15px;
}
.leave-overview-alert small {
  color: #956357;
  font-size: 13px;
}
.leave-hero {
  background: linear-gradient(135deg, #174e43, #287c69);
}
.leave-request-list > article {
  display: grid;
  grid-template-columns: auto 1fr 1.4fr auto;
  gap: 16px;
  align-items: center;
  padding: 18px 4px;
  border-bottom: 1px solid #e7efec;
}
.leave-request-list > article > span {
  display: grid;
  width: 46px;
  height: 46px;
  place-items: center;
  color: #17684f;
  background: #e1f3ec;
  border-radius: 11px;
  font-size: 16px;
  font-weight: 850;
}
.leave-request-list > article > div:not(.leave-review-actions) {
  display: grid;
  gap: 5px;
}
.leave-request-list strong {
  font-size: 15px;
}
.leave-request-list small {
  color: #7d938b;
  font-size: 13px;
}
.leave-review-actions {
  display: flex;
  gap: 9px;
}
.leave-review-actions button {
  display: flex;
  min-height: 42px;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 0 14px;
  color: #9c4739;
  border: 1px solid #edc9c1;
  background: #fff8f6;
  border-radius: 9px;
  font-size: 14px;
}
.leave-review-actions button:last-child {
  color: #fff;
  border-color: #168363;
  background: #168363;
}
.leave-review-actions button:disabled {
  cursor: wait;
  opacity: 0.58;
}
@media (max-width: 1050px) {
  .student-table > article {
    grid-template-columns: 1fr 1fr;
  }
  .student-table > article > div {
    grid-column: 1/-1;
  }
}
@media (max-width: 780px) {
  .student-table > article {
    grid-template-columns: 1fr;
  }
  .student-search input {
    width: 100%;
  }
}
@media (max-width: 900px) {
  .leave-request-list > article {
    grid-template-columns: auto 1fr;
  }
  .leave-request-list > article > div:nth-child(3),
  .leave-review-actions {
    grid-column: 2;
  }
  .leave-review-actions {
    justify-content: flex-start;
  }
}
@media (max-width: 560px) {
  .leave-request-list > article {
    grid-template-columns: 1fr;
  }
  .leave-request-list > article > div:nth-child(3),
  .leave-review-actions {
    grid-column: 1;
  }
  .leave-review-actions {
    display: grid;
    grid-template-columns: 1fr 1fr;
  }
}
.teacher-nav-group {
  display: grid;
  gap: 4px;
}
.teacher-nav-parent svg:last-child {
  transition: transform 0.2s;
}
.teacher-nav-parent svg:last-child.expanded {
  transform: rotate(90deg);
}
.teacher-nav-children {
  display: grid;
  gap: 3px;
  padding: 1px 0 4px 26px;
}
.teacher-shell aside nav .teacher-nav-children button {
  min-height: 38px;
  height: 38px;
  padding: 0 10px;
  color: #acd3c4;
  font-size: 13px;
}
.teacher-shell aside nav .teacher-nav-children button i {
  width: 7px;
  height: 7px;
  border: 2px solid #8fc9b4;
  border-radius: 50%;
}
.teacher-shell aside nav .teacher-nav-children button.active {
  color: #fff;
  background: rgba(255, 255, 255, 0.12);
  box-shadow: none;
}
.teacher-shell aside nav .teacher-nav-children button.active i {
  border-color: #fff;
  background: #fff;
}
.classroom-header-actions {
  display: flex;
  align-items: center;
  gap: 9px;
}
.teacher-section header .classroom-action-button {
  display: inline-flex;
  min-height: 44px;
  align-items: center;
  justify-content: center;
  gap: 7px;
  padding: 0 16px;
  color: #16654f;
  border: 1px solid #b9dfd1;
  background: #effaf6;
  border-radius: 9px;
  font-size: 14px;
  font-weight: 800;
}
.teacher-section header .classroom-action-button:hover {
  border-color: #78bea5;
  background: #e4f6ef;
}
.class-access-badge {
  display: inline-flex;
  width: fit-content;
  align-items: center;
  min-height: 24px;
  padding: 0 8px;
  color: #17684f;
  background: #e5f5ef;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 750;
}
.class-access-badge.collaborator {
  color: #315f9b;
  background: #eaf2ff;
}
.class-owner {
  display: block;
  margin-top: 5px;
  color: #728980;
  font-size: 12px;
}
.join-teacher-modal input {
  text-transform: uppercase;
  letter-spacing: 0.2em;
  font-weight: 800;
}
@media (max-width: 620px) {
  .classroom-header-actions {
    width: 100%;
    align-items: stretch;
    flex-direction: column;
  }
}

.collaboration-hero {
  background: linear-gradient(135deg, #125441, #198563);
}
.collaboration-panel {
  margin-top: 18px;
}
.collaboration-class-select {
  display: grid;
  width: min(100%, 330px);
  gap: 7px;
}
.collaboration-class-select > span {
  color: #5d796f;
  font-size: 12px;
  font-weight: 750;
}
.collaboration-class-select > div {
  position: relative;
  display: flex;
  min-height: 46px;
  align-items: center;
  gap: 9px;
  padding: 0 12px;
  color: #168363;
  border: 1px solid #cfe0da;
  background: linear-gradient(180deg, #fff, #f7fbf9);
  border-radius: 9px;
  box-shadow: 0 5px 15px rgba(31, 92, 73, 0.07);
}
.collaboration-class-select select {
  width: 100%;
  height: 44px;
  padding: 0 25px 0 0;
  color: #244d41;
  border: 0;
  outline: 0;
  appearance: none;
  background: transparent;
  font: inherit;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
}
.collaboration-class-select svg:last-child {
  position: absolute;
  right: 12px;
  pointer-events: none;
}
.policy-strip {
  display: flex;
  align-items: center;
  gap: 18px;
  padding: 17px 18px;
  margin-bottom: 16px;
  border: 1px solid #d8e7e1;
  background: #f7fbf9;
  border-radius: 10px;
}
.policy-strip > div:first-child {
  display: grid;
  gap: 6px;
  margin-right: auto;
}
.policy-strip > div:first-child strong {
  color: #294f43;
  font-size: 14px;
}
.policy-strip small {
  color: #688279;
  font-size: 13px;
  line-height: 1.5;
}
.policy-buttons {
  display: flex;
  gap: 8px;
  padding: 4px;
  background: #eaf3ef;
  border-radius: 9px;
}
.policy-buttons button {
  min-height: 38px;
  padding: 0 14px;
  color: #527067;
  border: 0;
  background: transparent;
  border-radius: 7px;
  font-size: 13px;
  font-weight: 700;
}
.policy-buttons button.active {
  color: #12694f;
  background: #fff;
  box-shadow: 0 3px 10px rgba(25, 91, 70, 0.11);
}
.danger-outline {
  color: #b34a4a !important;
  border: 1px solid #f0caca !important;
  background: #fff7f7 !important;
}
.member-list {
  display: grid;
  gap: 9px;
}
.member-list article {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 15px;
  border: 1px solid #e0ebe7;
  background: #fff;
  border-radius: 10px;
}
.member-list article.pending {
  border-color: #ead9ac;
  background: #fffcf2;
}
.member-avatar {
  display: grid;
  width: 38px;
  height: 38px;
  flex: 0 0 auto;
  place-items: center;
  color: #fff;
  background: #188363;
  border-radius: 9px;
  font-weight: 800;
}
.member-identity {
  display: grid;
  min-width: 190px;
  gap: 5px;
}
.member-identity strong {
  color: #27483f;
  font-size: 14px;
}
.member-identity em {
  margin-left: 7px;
  padding: 3px 6px;
  color: #16724f;
  background: #e2f6ed;
  border-radius: 5px;
  font-size: 11px;
  font-style: normal;
}
.member-identity small {
  color: #71877f;
  font-size: 12px;
}
.member-status {
  margin-left: auto;
  color: #607a71;
  font-size: 12px;
  font-weight: 700;
}
.member-list article select {
  min-height: 38px;
  padding: 0 30px 0 10px;
  color: #385c50;
  border: 1px solid #d3e3dd;
  background: #f9fcfb;
  border-radius: 7px;
  font-size: 12px;
}
.member-actions {
  display: flex;
  gap: 6px;
}
.member-actions button {
  min-height: 36px;
  padding: 0 12px;
  color: #17684f;
  border: 1px solid #b8e0d0;
  background: #effaf5;
  border-radius: 7px;
  font-size: 12px;
  font-weight: 700;
}
.member-actions .transfer-owner {
  color: #315f9b;
  border-color: #bfd2ed;
  background: #edf4ff;
}
.leave-request-source {
  width: fit-content;
  padding: 3px 7px;
  color: #315f9b !important;
  background: #eaf2ff;
  border-radius: 999px;
  font-weight: 750;
}
.leave-request-source.student {
  color: #167159 !important;
  background: #e3f5ee;
}
.batch-class-picker {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  padding: 14px;
  border: 1px solid #d8e6e1;
  background: #f8fbfa;
  border-radius: 9px;
}
.batch-class-picker > strong,
.batch-class-picker > small {
  grid-column: 1 / -1;
}
.batch-class-picker > strong {
  color: #315b4f;
  font-size: 13px;
}
.batch-class-picker > small {
  margin-bottom: 2px;
  color: #657e75;
  font-size: 12px;
  line-height: 1.6;
}
.batch-class-picker label {
  display: flex;
  min-width: 0;
  min-height: 38px;
  align-items: center;
  gap: 9px;
  padding: 7px 9px;
  color: #3f6257;
  border: 1px solid #e0eae6;
  background: #fff;
  border-radius: 7px;
  font-size: 12px;
  line-height: 1.4;
  cursor: pointer;
}
.teacher-publish-form .batch-class-picker input[type="checkbox"] {
  width: 15px;
  min-width: 15px;
  height: 15px;
  margin: 0;
  padding: 0;
  flex: 0 0 15px;
  accent-color: #168363;
  cursor: pointer;
}
@media (max-width: 700px) {
  .collaboration-panel > header {
    align-items: stretch;
    flex-direction: column;
  }
  .collaboration-class-select {
    width: 100%;
  }
  .policy-strip {
    align-items: stretch;
    flex-direction: column;
  }
  .policy-strip > div:first-child {
    margin-right: 0;
  }
  .policy-buttons {
    display: grid;
    grid-template-columns: 1fr 1fr;
  }
  .member-list article {
    align-items: flex-start;
    flex-wrap: wrap;
  }
  .member-status {
    margin-left: 0;
  }
  .batch-class-picker {
    grid-template-columns: 1fr;
  }
}
</style>
