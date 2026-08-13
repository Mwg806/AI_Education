<script setup lang="ts">
import {
  ArrowLeft,
  ArrowRight,
  BookOpenCheck,
  BrainCircuit,
  ClipboardCheck,
  GraduationCap,
  KeyRound,
  LoaderCircle,
  Megaphone,
  MessageSquareText,
  School,
  ShieldCheck,
  Smartphone,
  UserPlus,
  UserRound,
  UsersRound,
} from "@lucide/vue";
import { onBeforeUnmount, reactive, ref } from "vue";

import WenluBrandMark from "@/components/WenluBrandMark.vue";
import {
  loginTeacher,
  registerTeacher,
  sendVerificationCode,
} from "@/lib/auth-client";
import { subjectLabels } from "@/lib/curriculum-catalog";
import type { AuthSession, SubjectKey } from "@/lib/types";

const props = withDefaults(defineProps<{ showRoleSwitch?: boolean }>(), {
  showRoleSwitch: true,
});

const emit = defineEmits<{
  login: [payload: { session: AuthSession; remember: boolean }];
  back: [];
}>();

const teacherBubbleDefinitions = [
  {
    icon: UsersRound,
    title: "班级码连接",
    detail: "教师协作 · 学生加入",
    size: 174,
  },
  {
    icon: BrainCircuit,
    title: "学情一览",
    detail: "用真实证据理解成长",
    size: 190,
  },
  {
    icon: Megaphone,
    title: "教学发布",
    detail: "通知 · 作业 · 诊断卷",
    size: 174,
  },
  {
    icon: BookOpenCheck,
    title: "智能备课",
    detail: "生成 · 修订 · 发布",
    size: 190,
  },
  {
    icon: ClipboardCheck,
    title: "班级诊断",
    detail: "定位共性与个体问题",
    size: 180,
  },
  { icon: ShieldCheck, title: "数据边界", detail: "仅限所属班级", size: 168 },
];

const teacherBubbleZones = [
  { x: [2, 10], y: [10, 19] },
  { x: [10, 19], y: [39, 49] },
  { x: [2, 11], y: [70, 78] },
  { x: [75, 83], y: [9, 19] },
  { x: [79, 87], y: [40, 51] },
  { x: [74, 83], y: [70, 79] },
];

function randomBetween([minimum, maximum]: number[]) {
  return minimum + Math.random() * (maximum - minimum);
}

const teacherBubbles = reactive(
  teacherBubbleDefinitions.map((bubble, index) => ({
    ...bubble,
    x: randomBetween(teacherBubbleZones[index].x),
    y: randomBetween(teacherBubbleZones[index].y),
    driftDelay: -(Math.random() * 4),
    driftDuration: 4.8 + Math.random() * 2.4,
    launched: false,
  })),
);
const bubbleTimers = new Set<number>();

const mode = ref<"login" | "register">("login");
const submitted = ref(false);
const submitting = ref(false);
const sendingCode = ref(false);
const countdown = ref(0);
const error = ref("");
let countdownTimer: number | undefined;
const form = reactive({
  teacherName: "",
  teacherId: "",
  schoolName: "",
  subject: "mathematics" as SubjectKey,
  phone: "",
  verificationCode: "",
});
const subjects = Object.entries(subjectLabels) as Array<[SubjectKey, string]>;
type SubmitAction = "login" | "register";

function validationMessage(action: SubmitAction): string {
  const accountValid = /^[A-Za-z0-9_.-]{4,64}$/.test(form.teacherId.trim());
  if (!accountValid)
    return "教师账号需为 4—64 位字母、数字、点、下划线或短横线";
  if (!/^1[3-9]\d{9}$/.test(form.phone.trim()))
    return "请输入正确的中国大陆手机号";
  if (!/^\d{4,8}$/.test(form.verificationCode.trim()))
    return "请输入短信验证码";
  if (action === "login") return "";
  if (form.teacherName.trim().length < 2) return "教师姓名至少填写 2 个字符";
  if (form.schoolName.trim().length < 2) return "学校名称至少填写 2 个字符";
  return "";
}

function switchMode(next: "login" | "register") {
  if (submitting.value) return;
  mode.value = next;
  submitted.value = false;
  error.value = "";
  form.verificationCode = "";
}

async function sendCode() {
  error.value = "";
  if (!/^1[3-9]\d{9}$/.test(form.phone.trim())) {
    error.value = "请先填写正确的手机号";
    return;
  }
  sendingCode.value = true;
  try {
    const result = await sendVerificationCode(
      form.phone.trim(),
      mode.value,
      "teacher",
    );
    countdown.value = result.retry_after || 60;
    window.clearInterval(countdownTimer);
    countdownTimer = window.setInterval(() => {
      countdown.value -= 1;
      if (countdown.value <= 0) window.clearInterval(countdownTimer);
    }, 1000);
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "验证码发送失败";
  } finally {
    sendingCode.value = false;
  }
}
function launchBubble(index: number) {
  const bubble = teacherBubbles[index];
  if (bubble.launched) return;
  bubble.launched = true;
  const timer = window.setTimeout(() => {
    bubble.launched = false;
    bubbleTimers.delete(timer);
  }, 1650);
  bubbleTimers.add(timer);
}

function bubbleAriaLabel(title: string) {
  return "点击让“" + title + "”气泡上浮";
}

function bubbleStyle(bubble: (typeof teacherBubbles)[number]) {
  return {
    left: bubble.x + "%",
    top: bubble.y + "%",
    "--bubble-size": bubble.size + "px",
    "--drift-delay": bubble.driftDelay + "s",
    "--drift-duration": bubble.driftDuration + "s",
  };
}

onBeforeUnmount(() => {
  window.clearInterval(countdownTimer);
  bubbleTimers.forEach((timer) => window.clearTimeout(timer));
});

async function submit(action: SubmitAction) {
  submitted.value = true;
  error.value = "";
  if (submitting.value) return;
  const validationError = validationMessage(action);
  if (validationError) {
    error.value = validationError;
    return;
  }
  submitting.value = true;
  try {
    const session =
      action === "register"
        ? await registerTeacher({
            teacherId: form.teacherId.trim(),
            phone: form.phone.trim(),
            verificationCode: form.verificationCode.trim(),
            teacherName: form.teacherName.trim(),
            schoolName: form.schoolName.trim(),
            subject: form.subject,
          })
        : await loginTeacher(
            form.teacherId.trim(),
            form.phone.trim(),
            form.verificationCode.trim(),
          );
    emit("login", { session, remember: true });
  } catch (cause) {
    error.value =
      cause instanceof Error ? cause.message : "教师账号服务暂时不可用";
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <main class="teacher-auth-page teacher-auth-immersive">
    <div class="teacher-ambient teacher-ambient-one" aria-hidden="true" />
    <div class="teacher-ambient teacher-ambient-two" aria-hidden="true" />

    <button v-if="props.showRoleSwitch" class="back-role" type="button" @click="emit('back')">
      <ArrowLeft :size="16" />重新选择身份
    </button>

    <div class="teacher-learning-bubbles" aria-label="教师工作主题互动气泡">
      <button
        v-for="(bubble, index) in teacherBubbles"
        :key="bubble.title"
        class="teacher-learning-bubble"
        :class="{ launched: bubble.launched }"
        :style="bubbleStyle(bubble)"
        type="button"
        :aria-label="bubbleAriaLabel(bubble.title)"
        @click="launchBubble(index)"
      >
        <span class="teacher-bubble-surface">
          <component :is="bubble.icon" :size="23" />
          <strong>{{ bubble.title }}</strong>
          <small>{{ bubble.detail }}</small>
        </span>
      </button>
    </div>

    <section class="teacher-auth-form">
      <form @submit.prevent="submit(mode)">
        <div class="teacher-login-heading">
          <div class="teacher-login-title-row">
            <WenluBrandMark class="teacher-title-logo" :size="36" />
            <h2>{{ mode === "login" ? "教师账号登录" : "创建教师账号" }}</h2>
          </div>
          <p>
            {{
              mode === "login"
                ? "使用工号、手机号和验证码进入教师工作台"
                : "验证手机号后创建问鹿教师账号"
            }}
          </p>
        </div>

        <div class="teacher-auth-tabs" role="tablist">
          <button
            type="button"
            :class="{ active: mode === 'login' }"
            @click="switchMode('login')"
          >
            <KeyRound :size="16" />教师登录
          </button>
          <button
            type="button"
            :class="{ active: mode === 'register' }"
            @click="switchMode('register')"
          >
            <UserPlus :size="16" />教师注册
          </button>
        </div>

        <div class="teacher-fields">
          <label v-if="mode === 'register'">
            <span>教师姓名</span>
            <div>
              <UserRound :size="18" /><input
                v-model="form.teacherName"
                autocomplete="name"
                placeholder="请输入教师姓名"
              />
            </div>
          </label>
          <label v-if="mode === 'register'">
            <span>学校名称</span>
            <div>
              <School :size="18" /><input
                v-model="form.schoolName"
                placeholder="请输入学校全称"
              />
            </div>
          </label>
          <label v-if="mode === 'register'">
            <span>主要任教学科</span>
            <div>
              <GraduationCap :size="18" /><select v-model="form.subject">
                <option
                  v-for="[key, label] in subjects"
                  :key="key"
                  :value="key"
                >
                  {{ label }}
                </option>
              </select>
            </div>
          </label>
          <label>
            <span>教师账号 / 工号</span>
            <div>
              <UserRound :size="18" /><input
                v-model="form.teacherId"
                autocomplete="username"
                placeholder="请输入唯一教师账号或工号"
              />
            </div>
            <small
              v-if="
                submitted &&
                !/^[A-Za-z0-9_.-]{4,64}$/.test(form.teacherId.trim())
              "
              >教师账号格式不正确</small
            >
          </label>
          <label>
            <span>手机号</span>
            <div>
              <Smartphone :size="18" /><input
                v-model="form.phone"
                type="tel"
                inputmode="numeric"
                autocomplete="tel"
                maxlength="11"
                placeholder="请输入中国大陆手机号"
              />
            </div>
          </label>
          <label>
            <span>短信验证码</span>
            <div class="teacher-code-field">
              <MessageSquareText :size="18" /><input
                v-model="form.verificationCode"
                inputmode="numeric"
                autocomplete="one-time-code"
                maxlength="8"
                placeholder="请输入验证码"
              /><button
                type="button"
                :disabled="sendingCode || countdown > 0"
                @click="sendCode"
              >
                {{
                  countdown > 0
                    ? countdown + " 秒"
                    : sendingCode
                      ? "发送中"
                      : "获取验证码"
                }}
              </button>
            </div>
          </label>
        </div>

        <p v-if="error" class="teacher-auth-error">{{ error }}</p>

        <button
          class="teacher-login-submit"
          type="submit"
          :disabled="submitting"
        >
          <LoaderCircle v-if="submitting" class="spin" :size="19" />
          <template v-else
            >{{ mode === "login" ? "进入教师工作台" : "注册并进入教师工作台"
            }}<ArrowRight :size="19"
          /></template>
        </button>
      </form>
    </section>
  </main>
</template>

<style scoped>
.teacher-auth-immersive {
  position: relative;
  display: grid;
  min-height: 100svh;
  place-items: center;
  overflow: hidden;
  background:
    radial-gradient(
      circle at 50% 42%,
      rgba(114, 225, 180, 0.24),
      transparent 31rem
    ),
    linear-gradient(145deg, #073d32 0%, #0f7559 52%, #31a979 100%);
  isolation: isolate;
}

.teacher-ambient {
  position: absolute;
  z-index: 0;
  width: 34rem;
  height: 34rem;
  pointer-events: none;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 50%;
}
.teacher-ambient-one {
  top: -20rem;
  right: -10rem;
  box-shadow:
    0 0 0 4.8rem rgba(255, 255, 255, 0.025),
    0 0 0 10rem rgba(255, 255, 255, 0.018);
}
.teacher-ambient-two {
  bottom: -26rem;
  left: -8rem;
  background: rgba(255, 255, 255, 0.025);
}

.back-role {
  position: absolute;
  z-index: 5;
  top: 24px;
  left: 28px;
  display: inline-flex;
  min-height: 38px;
  align-items: center;
  gap: 6px;
  padding: 0 14px;
  color: #effbf6;
  border: 1px solid rgba(255, 255, 255, 0.3);
  background: rgba(255, 255, 255, 0.11);
  border-radius: 999px;
  font-size: 13px;
  backdrop-filter: blur(14px);
  transition:
    background 0.2s ease,
    transform 0.2s ease;
}
.back-role:hover {
  background: rgba(255, 255, 255, 0.18);
  transform: translateY(-1px);
}

.teacher-learning-bubbles {
  position: absolute;
  z-index: 1;
  inset: 0;
  overflow: hidden;
  pointer-events: none;
}
.teacher-learning-bubble {
  position: absolute;
  width: var(--bubble-size);
  height: var(--bubble-size);
  padding: 0;
  color: #fff;
  border: 0;
  background: transparent;
  border-radius: 50%;
  pointer-events: auto;
  will-change: transform, opacity;
}
.teacher-learning-bubble:focus-visible {
  outline: 3px solid rgba(255, 255, 255, 0.76);
  outline-offset: 4px;
}
.teacher-bubble-surface {
  display: flex;
  width: 100%;
  height: 100%;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  gap: 7px;
  padding: 22px;
  border: 1px solid rgba(255, 255, 255, 0.31);
  background:
    radial-gradient(
      circle at 30% 20%,
      rgba(255, 255, 255, 0.35) 0 5px,
      transparent 6px
    ),
    linear-gradient(
      145deg,
      rgba(255, 255, 255, 0.21),
      rgba(255, 255, 255, 0.07)
    );
  border-radius: 50%;
  box-shadow:
    inset 10px 12px 24px rgba(255, 255, 255, 0.11),
    inset -12px -14px 25px rgba(2, 72, 52, 0.14),
    0 18px 45px rgba(1, 53, 39, 0.22);
  text-align: center;
  backdrop-filter: blur(12px);
  animation: teacher-bubble-drift var(--drift-duration) ease-in-out
    var(--drift-delay) infinite alternate;
  transition:
    border-color 0.2s ease,
    background 0.2s ease,
    box-shadow 0.2s ease;
}
.teacher-learning-bubble:hover .teacher-bubble-surface {
  border-color: rgba(255, 255, 255, 0.55);
  background: linear-gradient(
    145deg,
    rgba(255, 255, 255, 0.28),
    rgba(255, 255, 255, 0.1)
  );
  box-shadow:
    inset 10px 12px 24px rgba(255, 255, 255, 0.14),
    0 22px 52px rgba(1, 53, 39, 0.28);
}
.teacher-bubble-surface > svg {
  color: #dff8ed;
}
.teacher-bubble-surface strong {
  max-width: 145px;
  font-size: 15px;
  line-height: 1.25;
}
.teacher-bubble-surface small {
  color: rgba(255, 255, 255, 0.78);
  font-size: 11px;
  line-height: 1.35;
}
.teacher-learning-bubble.launched {
  animation: teacher-bubble-launch 1.65s cubic-bezier(0.42, 0, 0.2, 1) both;
}

.teacher-auth-form {
  position: relative;
  z-index: 3;
  display: grid;
  width: 100%;
  min-height: 100svh;
  place-items: center;
  padding: 42px 24px;
  pointer-events: none;
}
.teacher-auth-form form {
  width: min(100%, 520px);
  max-height: calc(100svh - 48px);
  overflow-y: auto;
  padding: 36px 40px 38px;
  border: 1px solid rgba(255, 255, 255, 0.74);
  background: rgba(255, 255, 255, 0.97);
  border-radius: 24px;
  box-shadow: 0 28px 80px rgba(1, 53, 39, 0.3);
  scrollbar-width: thin;
  backdrop-filter: blur(22px);
  pointer-events: auto;
}
.teacher-login-heading {
  display: grid;
  justify-items: center;
  gap: 9px;
  margin-bottom: 25px;
  text-align: center;
}
.teacher-login-title-row {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 13px;
}
.teacher-title-logo {
  width: 46px;
  height: 46px;
}
.teacher-login-heading h2 {
  margin: 0;
  color: #123d31;
  font-size: 29px;
  letter-spacing: -0.035em;
}
.teacher-login-heading p {
  margin: 0;
  color: #71887f;
  font-size: 13px;
}
.teacher-auth-tabs {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 7px;
  margin: 0 0 23px;
  padding: 5px;
  background: #edf6f2;
  border-radius: 11px;
}
.teacher-auth-tabs button {
  display: flex;
  min-height: 42px;
  align-items: center;
  justify-content: center;
  gap: 7px;
  color: #6d857c;
  border: 0;
  background: transparent;
  border-radius: 8px;
  font-size: 13px;
}
.teacher-auth-tabs button.active {
  color: #12694f;
  background: #fff;
  box-shadow: 0 4px 13px rgba(16, 102, 76, 0.1);
}
.teacher-fields {
  display: grid;
  gap: 15px;
}
.teacher-fields label {
  display: grid;
  gap: 7px;
}
.teacher-fields label > span {
  color: #315c4f;
  font-size: 13px;
  font-weight: 750;
}
.teacher-fields label > div {
  display: flex;
  min-height: 47px;
  align-items: center;
  gap: 9px;
  padding: 0 13px;
  color: #6d8b81;
  border: 1px solid #d5e6df;
  background: #fbfdfc;
  border-radius: 10px;
  transition:
    border-color 0.2s ease,
    box-shadow 0.2s ease;
}
.teacher-fields label > div:focus-within {
  border-color: #62aa8f;
  box-shadow: 0 0 0 3px rgba(32, 139, 102, 0.1);
}
.teacher-fields input,
.teacher-fields select {
  width: 100%;
  min-width: 0;
  height: 45px;
  color: #23483d;
  border: 0;
  outline: 0;
  background: transparent;
  font: inherit;
  font-size: 14px;
}
.teacher-fields label > small {
  color: #b54545;
  font-size: 12px;
}
.teacher-code-field button {
  flex: 0 0 auto;
  padding: 8px 10px;
  color: #147457;
  border: 0;
  border-left: 1px solid #d8e6e1;
  background: transparent;
  font-size: 12px;
  font-weight: 800;
  white-space: nowrap;
}
.teacher-code-field button:disabled {
  color: #9cafaa;
  cursor: not-allowed;
}
.teacher-auth-error {
  margin: 14px 0 0;
  padding: 10px 12px;
  color: #a63d3d;
  background: #fff0ef;
  border-radius: 9px;
  font-size: 13px;
}
.teacher-login-submit {
  display: flex;
  width: 100%;
  min-height: 48px;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-top: 20px;
  color: #fff;
  border: 0;
  background: linear-gradient(135deg, #12694f, #25a476);
  border-radius: 11px;
  font-size: 14px;
  font-weight: 800;
  box-shadow: 0 11px 26px rgba(18, 105, 79, 0.23);
}
.teacher-login-submit:disabled {
  opacity: 0.58;
  cursor: wait;
}

@keyframes teacher-bubble-drift {
  from {
    transform: translate3d(-4px, -7px, 0) rotate(-1.2deg);
  }
  to {
    transform: translate3d(5px, 9px, 0) rotate(1.2deg);
  }
}
@keyframes teacher-bubble-launch {
  0% {
    transform: translate3d(0, 0, 0) scale(1);
    opacity: 1;
  }
  42% {
    transform: translate3d(8px, -115vh, 0) scale(0.9);
    opacity: 0;
  }
  43% {
    transform: translate3d(-8px, 100vh, 0) scale(0.86);
    opacity: 0;
  }
  64% {
    opacity: 0.82;
  }
  100% {
    transform: translate3d(0, 0, 0) scale(1);
    opacity: 1;
  }
}

@media (max-width: 980px) {
  .teacher-learning-bubble {
    --bubble-size: 142px !important;
    opacity: 0.64;
  }
  .teacher-bubble-surface strong {
    font-size: 13px;
  }
  .teacher-bubble-surface small {
    font-size: 10px;
  }
}
@media (max-width: 760px) {
  .back-role {
    top: 16px;
    left: 16px;
    min-height: 36px;
  }
  .teacher-auth-form {
    padding: 70px 16px 24px;
  }
  .teacher-auth-form form {
    max-height: calc(100svh - 94px);
    padding: 28px 22px 30px;
    border-radius: 20px;
  }
  .teacher-login-heading h2 {
    font-size: 24px;
  }
  .teacher-title-logo {
    width: 42px;
    height: 42px;
  }
  .teacher-learning-bubble {
    --bubble-size: 112px !important;
    opacity: 0.42;
  }
  .teacher-learning-bubble:nth-child(2),
  .teacher-learning-bubble:nth-child(3),
  .teacher-learning-bubble:nth-child(5) {
    display: none;
  }
  .teacher-bubble-surface {
    gap: 4px;
    padding: 14px;
  }
  .teacher-bubble-surface > svg {
    width: 18px;
  }
  .teacher-bubble-surface strong {
    font-size: 11px;
  }
  .teacher-bubble-surface small {
    font-size: 9px;
  }
}
@media (max-height: 720px) and (min-width: 761px) {
  .teacher-auth-form {
    padding-block: 22px;
  }
  .teacher-auth-form form {
    max-height: calc(100svh - 32px);
    padding-block: 28px;
  }
}
@media (prefers-reduced-motion: reduce) {
  .teacher-bubble-surface {
    animation: none;
  }
  .teacher-learning-bubble.launched {
    animation-duration: 0.45s;
  }
}
</style>
