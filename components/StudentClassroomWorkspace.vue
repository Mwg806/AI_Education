<script setup lang="ts">
import {
  Bell,
  BookOpenCheck,
  CalendarClock,
  CheckCircle2,
  ClipboardCheck,
  Copy,
  GraduationCap,
  LoaderCircle,
  LogOut,
  School,
  UsersRound,
  XCircle,
} from "@lucide/vue";
import { computed, onMounted, ref } from "vue";

import PaginationControls from "@/components/PaginationControls.vue";
import {
  fetchStudentClassroomPortal,
  joinClassroom,
  requestClassroomLeave,
} from "@/lib/teacher-client";
import type {
  ClassroomSummary,
  StudentClassroomPortal,
} from "@/lib/teacher-client";

const emit = defineEmits<{ openDiagnosis: [assignmentId: string] }>();
const portal = ref<StudentClassroomPortal>({
  classrooms: [],
  announcements: [],
  exam_assignments: [],
  join_requests: [],
  leave_requests: [],
});
const classCode = ref("");
const loading = ref(true);
const joining = ref(false);
const requestingClassId = ref<number | null>(null);
const error = ref("");
const success = ref("");
const classroomPage = ref(1);
const noticePage = ref(1);
const examPage = ref(1);
const joinRequestPage = ref(1);
const leavePage = ref(1);
const PAGE_SIZE = 4;
const pagedClassrooms = computed(() =>
  portal.value.classrooms.slice(
    (classroomPage.value - 1) * PAGE_SIZE,
    classroomPage.value * PAGE_SIZE,
  ),
);
const pagedAnnouncements = computed(() =>
  portal.value.announcements.slice(
    (noticePage.value - 1) * PAGE_SIZE,
    noticePage.value * PAGE_SIZE,
  ),
);
const pagedAssignments = computed(() =>
  portal.value.exam_assignments.slice(
    (examPage.value - 1) * PAGE_SIZE,
    examPage.value * PAGE_SIZE,
  ),
);
const pagedJoinRequests = computed(() =>
  portal.value.join_requests.slice(
    (joinRequestPage.value - 1) * PAGE_SIZE,
    joinRequestPage.value * PAGE_SIZE,
  ),
);
const pagedLeaveRequests = computed(() =>
  portal.value.leave_requests.slice(
    (leavePage.value - 1) * PAGE_SIZE,
    leavePage.value * PAGE_SIZE,
  ),
);

async function load() {
  loading.value = true;
  error.value = "";
  try {
    portal.value = await fetchStudentClassroomPortal();
    classroomPage.value = 1;
    noticePage.value = 1;
    examPage.value = 1;
    joinRequestPage.value = 1;
    leavePage.value = 1;
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "班级信息读取失败";
  } finally {
    loading.value = false;
  }
}

async function requestLeave(classroom: ClassroomSummary) {
  if (classroom.leave_request_status === "pending") return;
  if (
    !window.confirm(
      `确定申请退出“${classroom.class_name}”吗？教师同意前你仍是班级成员。`,
    )
  )
    return;
  requestingClassId.value = classroom.id;
  error.value = "";
  try {
    await requestClassroomLeave(classroom.id);
    success.value = "退出申请已提交，等待教师审批";
    await load();
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "退出申请提交失败";
  } finally {
    requestingClassId.value = null;
  }
}

async function join() {
  if (!/^[A-Za-z0-9]{8}$/.test(classCode.value.trim())) {
    error.value = "请输入教师提供的 8 位班级码";
    return;
  }
  joining.value = true;
  error.value = "";
  try {
    const classroom = await joinClassroom(classCode.value);
    success.value =
      classroom.membership_status === "pending"
        ? `已提交加入 ${classroom.class_name} 的申请，请等待班主任审批`
        : `已加入 ${classroom.class_name}`;
    classCode.value = "";
    await load();
    window.setTimeout(() => {
      success.value = "";
    }, 3000);
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "加入班级失败";
  } finally {
    joining.value = false;
  }
}

function copyCode(code: string) {
  void navigator.clipboard.writeText(code);
  success.value = "班级码已复制";
}

function noticeLabel(type: string) {
  return type === "homework"
    ? "作业"
    : type === "holiday"
      ? "放假通知"
      : "班级通知";
}

function joinStatusLabel(status: string) {
  return status === "pending"
    ? "等待班主任审批"
    : status === "approved"
      ? "班主任已同意，已加入班级"
      : "班主任未同意加入";
}

function leaveStatusLabel(status: string) {
  return status === "pending"
    ? "等待教师审批"
    : status === "approved"
      ? "教师已同意，已退出班级"
      : "教师未同意退出";
}

onMounted(load);
</script>

<template>
  <div class="student-classroom-page">
    <section class="classroom-hero student-module-hero">
      <div>
        <span><UsersRound :size="15" /> 班级协同</span>
        <h1>连接你的班级与老师</h1>
        <p>
          使用教师提供的班级码加入班级，及时接收作业、放假通知和学情诊断卷任务。
        </p>
      </div>
      <form @submit.prevent="join">
        <label>输入 8 位班级码</label>
        <div>
          <input
            v-model="classCode"
            maxlength="8"
            placeholder="例如 A3K9P2Q8"
            @input="classCode = classCode.toUpperCase()"
          /><button :disabled="joining">
            <LoaderCircle v-if="joining" class="spin" :size="17" /><template
              v-else
              >加入班级</template
            >
          </button>
        </div>
        <small>班级码不区分大小写；是否直接加入由班主任设置。</small>
      </form>
    </section>
    <p v-if="error" class="classroom-message error">{{ error }}</p>
    <p v-if="success" class="classroom-message success">
      <CheckCircle2 :size="16" />{{ success }}
    </p>
    <div v-if="loading" class="classroom-loading">
      <LoaderCircle class="spin" :size="24" />正在读取班级信息…
    </div>
    <template v-else>
      <section class="student-class-section">
        <header>
          <div>
            <small>MY CLASSROOMS</small>
            <h2>已加入班级</h2>
          </div>
          <span>{{ portal.classrooms.length }} 个</span>
        </header>
        <div v-if="portal.classrooms.length" class="joined-class-grid">
          <article
            v-for="item in pagedClassrooms"
            :key="item.id"
            :class="{ leaving: item.leave_request_status === 'pending' }"
          >
            <span><School :size="22" /></span>
            <div>
              <small>{{ item.school_name }}</small>
              <h3>{{ item.class_name }}</h3>
              <p>
                {{ item.teacher_name }}老师 · {{ item.subject || "综合班级" }}
              </p>
              <i v-if="item.leave_request_status === 'pending'"
                >退出申请正在等待教师审批</i
              >
            </div>
            <div class="class-actions">
              <button class="copy-class" @click="copyCode(item.class_code)">
                <Copy :size="14" />{{ item.class_code }}</button
              ><button
                class="leave-class"
                :disabled="
                  item.leave_request_status === 'pending' ||
                  requestingClassId === item.id
                "
                @click="requestLeave(item)"
              >
                <LoaderCircle
                  v-if="requestingClassId === item.id"
                  class="spin"
                  :size="14"
                /><LogOut v-else :size="14" />{{
                  item.leave_request_status === "pending"
                    ? "等待审批"
                    : item.leave_request_status === "rejected"
                      ? "重新申请退出"
                      : "申请退出"
                }}
              </button>
            </div>
          </article>
        </div>
        <div v-else class="classroom-empty">
          <GraduationCap :size="34" /><strong>尚未加入班级</strong>
          <p>向教师获取 8 位班级码后，在上方输入即可加入。</p>
        </div>
        <PaginationControls
          :page="classroomPage"
          :total="portal.classrooms.length"
          :page-size="PAGE_SIZE"
          label="个班级"
          @change="classroomPage = $event"
        />
      </section>
      <section
        v-if="portal.join_requests.length"
        class="student-class-section leave-progress join-progress"
      >
        <header>
          <div>
            <small>JOIN REQUESTS</small>
            <h2>入班申请进度</h2>
          </div>
          <span>{{ portal.join_requests.length }} 条</span>
        </header>
        <article
          v-for="item in pagedJoinRequests"
          :key="item.request_id"
          :class="item.status"
        >
          <span
            ><LoaderCircle
              v-if="item.status === 'pending'"
              :size="19" /><CheckCircle2
              v-else-if="item.status === 'approved'"
              :size="19" /><XCircle v-else :size="19"
          /></span>
          <div>
            <strong>{{ item.class_name }}</strong>
            <p>{{ joinStatusLabel(item.status) }}</p>
            <small
              >申请于 {{ new Date(item.requested_at).toLocaleString()
              }}<template v-if="item.reviewer_note">
                · 班主任说明：{{ item.reviewer_note }}</template
              ></small
            >
          </div>
        </article>
        <PaginationControls
          :page="joinRequestPage"
          :total="portal.join_requests.length"
          :page-size="PAGE_SIZE"
          label="条申请"
          @change="joinRequestPage = $event"
        />
      </section>
      <section
        v-if="portal.leave_requests.length"
        class="student-class-section leave-progress"
      >
        <header>
          <div>
            <small>LEAVE REQUESTS</small>
            <h2>退出申请进度</h2>
          </div>
          <span>{{ portal.leave_requests.length }} 条</span>
        </header>
        <article
          v-for="item in pagedLeaveRequests"
          :key="item.request_id"
          :class="item.status"
        >
          <span
            ><LoaderCircle
              v-if="item.status === 'pending'"
              :size="19" /><CheckCircle2
              v-else-if="item.status === 'approved'"
              :size="19" /><XCircle v-else :size="19"
          /></span>
          <div>
            <strong>{{ item.class_name }}</strong>
            <p>{{ leaveStatusLabel(item.status) }}</p>
            <small
              >申请于 {{ new Date(item.requested_at).toLocaleString("zh-CN")
              }}<template v-if="item.reviewer_note">
                · 教师说明：{{ item.reviewer_note }}</template
              ></small
            >
          </div>
        </article>
        <PaginationControls
          :page="leavePage"
          :total="portal.leave_requests.length"
          :page-size="PAGE_SIZE"
          label="条申请"
          @change="leavePage = $event"
        />
      </section>
      <div class="student-class-columns">
        <section class="student-class-section notice-list">
          <header>
            <div>
              <small>ANNOUNCEMENTS</small>
              <h2>班级通知与作业</h2>
            </div>
            <Bell :size="20" />
          </header>
          <article
            v-for="item in pagedAnnouncements"
            :key="item.announcement_id"
          >
            <span :class="item.announcement_type"><Bell :size="17" /></span>
            <div>
              <small
                >{{ item.class_name }} ·
                {{ noticeLabel(item.announcement_type) }}</small
              >
              <h3>{{ item.title }}</h3>
              <p>{{ item.content }}</p>
              <time
                ><CalendarClock :size="13" />{{
                  item.due_at
                    ? `截止 ${new Date(item.due_at).toLocaleString("zh-CN")}`
                    : `发布于 ${new Date(item.created_at).toLocaleString("zh-CN")}`
                }}</time
              >
            </div>
          </article>
          <div
            v-if="!portal.announcements.length"
            class="classroom-empty compact"
          >
            <Bell :size="29" /><strong>暂无班级通知</strong>
          </div>
          <PaginationControls
            :page="noticePage"
            :total="portal.announcements.length"
            :page-size="PAGE_SIZE"
            label="条通知"
            @change="noticePage = $event"
          />
        </section>
        <section class="student-class-section exam-task-list">
          <header>
            <div>
              <small>DIAGNOSTIC TASKS</small>
              <h2>教师发布的诊断卷</h2>
            </div>
            <ClipboardCheck :size="20" />
          </header>
          <article v-for="item in pagedAssignments" :key="item.assignment_id">
            <span><BookOpenCheck :size="19" /></span>
            <div>
              <small
                >{{ item.class_name }} ·
                {{ item.status === "published" ? "进行中" : "已关闭" }}</small
              >
              <h3>{{ item.title }}</h3>
              <p>试卷编号：{{ item.paper_id }}</p>
              <time
                ><CalendarClock :size="13" />{{
                  item.due_at
                    ? `截止 ${new Date(item.due_at).toLocaleString("zh-CN")}`
                    : "未设置截止时间"
                }}</time
              >
            </div>
            <button
              v-if="item.status === 'published'"
              @click="emit('openDiagnosis', item.assignment_id)"
            >
              {{
                item.task_status === "completed"
                  ? "查看或重做"
                  : item.task_status === "in_progress"
                    ? "继续诊断"
                    : "前往诊断"
              }}
            </button>
          </article>
          <div
            v-if="!portal.exam_assignments.length"
            class="classroom-empty compact"
          >
            <ClipboardCheck :size="29" /><strong>暂无诊断任务</strong>
          </div>
          <PaginationControls
            :page="examPage"
            :total="portal.exam_assignments.length"
            :page-size="PAGE_SIZE"
            label="份任务"
            @change="examPage = $event"
          />
        </section>
      </div>
    </template>
  </div>
</template>

<style scoped>
.student-classroom-page {
  display: grid;
  gap: 16px;
}
.classroom-hero {
  display: flex;
  min-height: 220px;
  align-items: center;
  justify-content: space-between;
  gap: 30px;
  padding: 34px 38px;
  color: #fff;
  background:
    radial-gradient(
      circle at 80% 10%,
      rgba(255, 255, 255, 0.14),
      transparent 28%
    ),
    linear-gradient(135deg, #103d8f, #1764cb 65%, #3194ae);
  border-radius: 18px;
  box-shadow: 0 18px 40px rgba(21, 94, 239, 0.14);
}
.classroom-hero > div {
  max-width: 680px;
}
.classroom-hero > div > span {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #d9ecff;
  font-size: 9px;
  font-weight: 800;
}
.classroom-hero h1 {
  margin: 15px 0 10px;
  font-size: clamp(27px, 3vw, 40px);
  letter-spacing: -0.045em;
}
.classroom-hero p {
  margin: 0;
  color: #c8dcf6;
  font-size: 10px;
  line-height: 1.8;
}
.classroom-hero form {
  width: min(100%, 390px);
  padding: 18px;
  border: 1px solid rgba(255, 255, 255, 0.18);
  background: rgba(255, 255, 255, 0.09);
  border-radius: 13px;
}
.classroom-hero form > label {
  font-size: 9px;
  font-weight: 750;
}
.classroom-hero form > div {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 7px;
  margin: 9px 0;
}
.classroom-hero input {
  min-width: 0;
  height: 43px;
  padding: 0 11px;
  color: #21456f;
  border: 0;
  outline: 0;
  background: #fff;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 800;
  letter-spacing: 0.13em;
  text-transform: uppercase;
}
.classroom-hero form button {
  display: flex;
  min-width: 84px;
  align-items: center;
  justify-content: center;
  color: #155eef;
  border: 0;
  background: #dceaff;
  border-radius: 8px;
  font-size: 9px;
  font-weight: 800;
}
.classroom-hero form small {
  color: #bed7f3;
  font-size: 7px;
}
.classroom-message {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 0;
  padding: 11px 13px;
  border-radius: 9px;
  font-size: 9px;
}
.classroom-message.error {
  color: #a83f3f;
  background: #fff0ef;
}
.classroom-message.success {
  color: #187158;
  background: #e5f6ef;
}
.classroom-loading {
  display: grid;
  min-height: 350px;
  place-content: center;
  justify-items: center;
  gap: 10px;
  color: #72859e;
  font-size: 9px;
}
.student-class-section {
  padding: 23px;
  border: 1px solid #dfe7f2;
  background: #fff;
  border-radius: 15px;
  box-shadow: 0 5px 18px rgba(27, 55, 96, 0.05);
}
.student-class-section > header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 16px;
  border-bottom: 1px solid #edf1f7;
}
.student-class-section > header small {
  color: #5c82bc;
  font-size: 7px;
  font-weight: 850;
  letter-spacing: 0.14em;
}
.student-class-section > header h2 {
  margin: 5px 0 0;
  color: #1e385e;
  font-size: 16px;
}
.student-class-section > header > span {
  padding: 7px 10px;
  color: #155eef;
  background: #edf4ff;
  border-radius: 7px;
  font-size: 8px;
}
.student-class-section > header > svg {
  color: #6689bc;
}
.joined-class-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-top: 16px;
}
.joined-class-grid article {
  position: relative;
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 16px;
  border: 1px solid #dfe8f4;
  background: #f9fbff;
  border-radius: 11px;
}
.joined-class-grid article > span {
  display: grid;
  width: 41px;
  height: 41px;
  place-items: center;
  color: #155eef;
  background: #e4efff;
  border-radius: 10px;
}
.joined-class-grid article > div {
  display: grid;
  gap: 3px;
}
.joined-class-grid small {
  color: #8394aa;
  font-size: 7px;
}
.joined-class-grid h3 {
  margin: 0;
  color: #294360;
  font-size: 11px;
}
.joined-class-grid p {
  margin: 0;
  color: #75879f;
  font-size: 8px;
}
.joined-class-grid button {
  position: absolute;
  right: 11px;
  top: 11px;
  display: flex;
  align-items: center;
  gap: 4px;
  color: #5e7899;
  border: 0;
  background: transparent;
  font-size: 7px;
}
.classroom-empty {
  display: grid;
  min-height: 170px;
  place-content: center;
  justify-items: center;
  gap: 8px;
  color: #8294aa;
  text-align: center;
}
.classroom-empty strong {
  color: #38516f;
  font-size: 10px;
}
.classroom-empty p {
  margin: 0;
  font-size: 8px;
}
.classroom-empty.compact {
  min-height: 210px;
}
.student-class-columns {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
.notice-list > article,
.exam-task-list > article {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 15px 2px;
  border-bottom: 1px solid #edf1f7;
}
.notice-list > article > span,
.exam-task-list > article > span {
  display: grid;
  width: 37px;
  height: 37px;
  flex: 0 0 auto;
  place-items: center;
  color: #8f6918;
  background: #fff3ce;
  border-radius: 9px;
}
.notice-list > article > span.homework {
  color: #1b765c;
  background: #e4f5ee;
}
.notice-list > article > span.holiday {
  color: #8b5420;
  background: #ffead7;
}
.exam-task-list > article > span {
  color: #155eef;
  background: #e7f0ff;
}
.notice-list article > div,
.exam-task-list article > div {
  display: grid;
  flex: 1;
  gap: 5px;
}
.notice-list small,
.exam-task-list small {
  color: #5c82b8;
  font-size: 7px;
}
.notice-list h3,
.exam-task-list h3 {
  margin: 0;
  color: #2b4464;
  font-size: 10px;
}
.notice-list p,
.exam-task-list p {
  margin: 0;
  color: #72849c;
  font-size: 8px;
  line-height: 1.65;
  white-space: pre-wrap;
}
.notice-list time,
.exam-task-list time {
  display: flex;
  align-items: center;
  gap: 4px;
  color: #91a0b2;
  font-size: 7px;
}
.exam-task-list article > button {
  align-self: center;
  padding: 8px 10px;
  color: #fff;
  border: 0;
  background: #155eef;
  border-radius: 7px;
  font-size: 8px;
}
@media (max-width: 980px) {
  .joined-class-grid {
    grid-template-columns: 1fr 1fr;
  }
  .student-class-columns {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 700px) {
  .classroom-hero {
    align-items: stretch;
    flex-direction: column;
    padding: 27px 22px;
  }
  .classroom-hero form {
    width: 100%;
  }
  .joined-class-grid {
    grid-template-columns: 1fr;
  }
}
/* Student-readable typography and page-sized lists. */
.student-classroom-page {
  font-size: 15px;
  line-height: 1.55;
}
.classroom-hero > div > span {
  font-size: 13px;
}
.classroom-hero p {
  font-size: 15px;
}
.classroom-hero form > label {
  font-size: 14px;
}
.classroom-hero input {
  height: 48px;
  font-size: 16px;
}
.classroom-hero form button {
  min-width: 104px;
  font-size: 14px;
}
.classroom-hero form small {
  font-size: 12px;
}
.student-class-section > header small {
  font-size: 11px;
}
.student-class-section > header h2 {
  font-size: 20px;
}
.student-class-section > header > span {
  font-size: 13px;
}
.joined-class-grid small {
  font-size: 12px;
}
.joined-class-grid h3 {
  font-size: 16px;
}
.joined-class-grid p,
.joined-class-grid button {
  font-size: 13px;
}
.joined-class-grid article {
  align-items: flex-start;
  padding-top: 48px;
}
.joined-class-grid article.leaving {
  border-color: #e8c878;
  background: #fffaf0;
}
.joined-class-grid article > div > i {
  color: #9a6815;
  font-size: 12px;
  font-style: normal;
  font-weight: 700;
}
.joined-class-grid article > .class-actions {
  position: absolute;
  inset: 10px 10px auto 10px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.class-actions button {
  position: static;
  display: inline-flex;
  min-height: 34px;
  align-items: center;
  gap: 5px;
  padding: 0 9px;
  border-radius: 7px;
}
.class-actions .copy-class {
  color: #5e7899;
  border: 0;
  background: transparent;
}
.class-actions .leave-class {
  color: #9a4545;
  border: 1px solid #efc9c9;
  background: #fff7f7;
}
.class-actions .leave-class:disabled {
  color: #9a761f;
  border-color: #ead79d;
  background: #fff9e8;
}
.leave-progress > article {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 15px 2px;
  border-bottom: 1px solid #edf1f7;
}
.leave-progress > article > span {
  display: grid;
  width: 39px;
  height: 39px;
  flex: 0 0 auto;
  place-items: center;
  border-radius: 10px;
}
.leave-progress > article.pending > span {
  color: #9a6b16;
  background: #fff1c9;
}
.leave-progress > article.approved > span {
  color: #167159;
  background: #def4eb;
}
.leave-progress > article.rejected > span {
  color: #a14b4b;
  background: #fce9e9;
}
.leave-progress article > div {
  display: grid;
  gap: 4px;
}
.leave-progress strong {
  color: #294360;
  font-size: 15px;
}
.leave-progress p {
  margin: 0;
  color: #637791;
  font-size: 14px;
}
.leave-progress small {
  color: #8a99aa;
  font-size: 12px;
}
.notice-list small,
.exam-task-list small {
  font-size: 12px;
}
.notice-list h3,
.exam-task-list h3 {
  font-size: 16px;
}
.notice-list p,
.exam-task-list p {
  font-size: 14px;
}
.notice-list time,
.exam-task-list time {
  font-size: 12px;
}
.exam-task-list article > button {
  min-height: 42px;
  font-size: 14px;
}
.classroom-empty strong {
  font-size: 15px;
}
.classroom-empty p,
.classroom-message,
.classroom-loading {
  font-size: 13px;
}
@media (max-width: 1120px) {
  .student-class-columns {
    grid-template-columns: 1fr;
  }
  .joined-class-grid {
    grid-template-columns: 1fr 1fr;
  }
}
@media (max-width: 700px) {
  .joined-class-grid {
    grid-template-columns: 1fr;
  }
}
</style>
