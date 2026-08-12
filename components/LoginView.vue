<script setup lang="ts">
import {
  ArrowLeft,
  ArrowRight,
  BookOpenCheck,
  BrainCircuit,
  GraduationCap,
  KeyRound,
  LoaderCircle,
  MessageSquareText,
  Smartphone,
  MapPin,
  ShieldCheck,
  Sparkles,
  UserPlus,
  UserRound,
} from "@lucide/vue";
import { computed, onBeforeUnmount, reactive, ref } from "vue";

import {
  loginStudent,
  registerStudent,
  sendVerificationCode,
} from "@/lib/auth-client";
import { provinceRoutes } from "@/lib/curriculum-catalog";
import type { AuthSession, StudentLoginProfile } from "@/lib/types";
import WenluBrandMark from "@/components/WenluBrandMark.vue";

const bubbleDefinitions = [
  { icon: Sparkles, title: "全国新课标Ⅰ卷", detail: "学习助手", size: 164 },
  {
    icon: BrainCircuit,
    title: "三 Agent 协同",
    detail: "规划 · 辅导 · 诊断",
    size: 188,
  },
  {
    icon: BookOpenCheck,
    title: "学习记录",
    detail: "让进步清晰可见",
    size: 170,
  },
  {
    icon: GraduationCap,
    title: "每一次努力",
    detail: "都有清晰的方向",
    size: 196,
  },
  { icon: ShieldCheck, title: "安心学习", detail: "短信安全验证", size: 164 },
  {
    icon: MessageSquareText,
    title: "随时提问",
    detail: "智能陪伴学习",
    size: 174,
  },
];

const bubbleZones = [
  { x: [2, 11], y: [10, 20] },
  { x: [11, 21], y: [38, 49] },
  { x: [2, 12], y: [68, 78] },
  { x: [75, 83], y: [10, 21] },
  { x: [79, 87], y: [40, 52] },
  { x: [73, 82], y: [69, 79] },
];

function randomBetween([minimum, maximum]: number[]) {
  return minimum + Math.random() * (maximum - minimum);
}

const learningBubbles = reactive(
  bubbleDefinitions.map((bubble, index) => ({
    ...bubble,
    x: randomBetween(bubbleZones[index].x),
    y: randomBetween(bubbleZones[index].y),
    driftDelay: -(Math.random() * 4),
    driftDuration: 4.8 + Math.random() * 2.4,
    launched: false,
  })),
);
const bubbleTimers = new Set<number>();

const emit = defineEmits<{
  login: [payload: { session: AuthSession; remember: boolean }];
  back: [];
}>();

const mode = ref<"login" | "register">("login");
const submitted = ref(false);
const submitting = ref(false);
const sendingCode = ref(false);
const countdown = ref(0);
const error = ref("");
let countdownTimer: number | undefined;
const form = reactive({
  studentName: "",
  studentId: "",
  phone: "",
  verificationCode: "",
  grade: "grade_11" as StudentLoginProfile["grade"],
  provinceCode: "43",
  targetExamYear: 2027,
});

const valid = computed(() => {
  const accountValid = /^[A-Za-z0-9_.-]{4,64}$/.test(form.studentId.trim());
  const phoneValid = /^1[3-9]\d{9}$/.test(form.phone.trim());
  const codeValid = /^\d{4,8}$/.test(form.verificationCode.trim());
  if (mode.value === "login") return accountValid && phoneValid && codeValid;
  return (
    accountValid &&
    form.studentName.trim().length >= 2 &&
    phoneValid &&
    codeValid &&
    Boolean(form.grade) &&
    Boolean(form.provinceCode)
  );
});

function switchMode(next: "login" | "register") {
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
      "student",
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
  const bubble = learningBubbles[index];
  if (bubble.launched) return;
  bubble.launched = true;
  const timer = window.setTimeout(() => {
    bubble.launched = false;
    bubbleTimers.delete(timer);
  }, 1650);
  bubbleTimers.add(timer);
}

function bubbleStyle(bubble: (typeof learningBubbles)[number]) {
  return {
    left: `${bubble.x}%`,
    top: `${bubble.y}%`,
    "--bubble-size": `${bubble.size}px`,
    "--drift-delay": `${bubble.driftDelay}s`,
    "--drift-duration": `${bubble.driftDuration}s`,
  };
}

onBeforeUnmount(() => {
  window.clearInterval(countdownTimer);
  bubbleTimers.forEach((timer) => window.clearTimeout(timer));
});

async function submit() {
  submitted.value = true;
  error.value = "";
  if (!valid.value || submitting.value) return;
  submitting.value = true;
  try {
    const session =
      mode.value === "register"
        ? await registerStudent({
            studentId: form.studentId.trim(),
            phone: form.phone.trim(),
            verificationCode: form.verificationCode.trim(),
            studentName: form.studentName.trim(),
            grade: form.grade,
            provinceCode: form.provinceCode,
            targetExamYear: form.targetExamYear,
          })
        : await loginStudent(
            form.studentId.trim(),
            form.phone.trim(),
            form.verificationCode.trim(),
          );
    emit("login", { session, remember: true });
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "账号服务暂时不可用";
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <main class="login-page student-theme student-login-immersive">
    <div class="ambient-light ambient-light-one" aria-hidden="true" />
    <div class="ambient-light ambient-light-two" aria-hidden="true" />

    <button class="student-role-back" type="button" @click="emit('back')">
      <ArrowLeft :size="16" />重新选择身份
    </button>

    <div class="learning-bubbles" aria-label="学习主题互动气泡">
      <button
        v-for="(bubble, index) in learningBubbles"
        :key="bubble.title"
        class="learning-bubble"
        :class="{ launched: bubble.launched }"
        :style="bubbleStyle(bubble)"
        type="button"
        :aria-label="`点击让“${bubble.title}”气泡上浮`"
        @click="launchBubble(index)"
      >
        <span class="bubble-surface">
          <component :is="bubble.icon" :size="23" />
          <strong>{{ bubble.title }}</strong>
          <small>{{ bubble.detail }}</small>
        </span>
      </button>
    </div>

    <section class="login-form-wrap">
      <form class="login-card" @submit.prevent="submit">
        <div class="login-heading">
          <div class="login-title-row">
            <WenluBrandMark class="login-title-logo" :size="34" />
            <h2>{{ mode === "login" ? "登录学习空间" : "创建学生账号" }}</h2>
          </div>
        </div>

        <div class="auth-tabs" role="tablist">
          <button
            type="button"
            :class="{ active: mode === 'login' }"
            @click="switchMode('login')"
          >
            <KeyRound :size="16" />账号登录
          </button>
          <button
            type="button"
            :class="{ active: mode === 'register' }"
            @click="switchMode('register')"
          >
            <UserPlus :size="16" />新生注册
          </button>
        </div>

        <div class="login-fields">
          <label v-if="mode === 'register'">
            <span>学生姓名</span>
            <div class="input-shell">
              <UserRound :size="18" /><input
                v-model="form.studentName"
                autocomplete="name"
                placeholder="请输入学生真实姓名"
              />
            </div>
            <small
              v-if="submitted && form.studentName.trim().length < 2"
              class="field-error"
              >请填写至少 2 个字的姓名</small
            >
          </label>

          <label>
            <span>学号</span>
            <div class="input-shell">
              <UserRound :size="18" /><input
                v-model="form.studentId"
                autocomplete="username"
                placeholder="4—64 位字母、数字、点、横线或下划线"
              />
            </div>
            <small
              v-if="
                submitted &&
                !/^[A-Za-z0-9_.-]{4,64}$/.test(form.studentId.trim())
              "
              class="field-error"
              >账号格式不正确</small
            >
          </label>

          <label>
            <span>手机号</span>
            <div class="input-shell">
              <Smartphone :size="18" /><input
                v-model="form.phone"
                type="tel"
                inputmode="numeric"
                autocomplete="tel"
                maxlength="11"
                placeholder="请输入中国大陆手机号"
              />
            </div>
            <small
              v-if="submitted && !/^1[3-9]\d{9}$/.test(form.phone.trim())"
              class="field-error"
              >手机号格式不正确</small
            >
          </label>

          <label>
            <span>短信验证码</span>
            <div class="input-shell verification-shell">
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

          <template v-if="mode === 'register'">
            <div class="two-fields">
              <label>
                <span>当前年级</span>
                <div class="input-shell">
                  <GraduationCap :size="18" /><select v-model="form.grade">
                    <option value="grade_10">高一</option>
                    <option value="grade_11">高二</option>
                    <option value="grade_12">高三</option>
                  </select>
                </div>
              </label>
              <label>
                <span>目标高考年份</span>
                <div class="input-shell">
                  <select v-model.number="form.targetExamYear">
                    <option
                      v-for="year in [2027, 2028, 2029, 2030]"
                      :key="year"
                      :value="year"
                    >
                      {{ year }} 年
                    </option>
                  </select>
                </div>
              </label>
            </div>

            <label>
              <span>所在地区（全国新课标Ⅰ卷范围）</span>
              <div class="input-shell">
                <MapPin :size="18" /><select v-model="form.provinceCode">
                  <option
                    v-for="province in provinceRoutes"
                    :key="province.code"
                    :value="province.code"
                  >
                    {{ province.name }}省 · {{ province.exam_mode }}
                  </option>
                </select>
              </div>
            </label>
          </template>
        </div>

        <div v-if="error" class="auth-error">{{ error }}</div>

        <div class="register-space" />

        <button class="login-submit" type="submit" :disabled="submitting">
          <LoaderCircle v-if="submitting" class="spin" :size="19" />
          <template v-else
            >{{ mode === "login" ? "登录学习空间" : "注册并进入学习空间" }}
            <ArrowRight :size="19"
          /></template>
        </button>
      </form>
    </section>
  </main>
</template>

<style scoped>
.student-login-immersive.login-page {
  position: relative;
  display: grid;
  min-height: 100svh;
  grid-template-columns: 1fr;
  place-items: center;
  overflow: hidden;
  background:
    radial-gradient(
      circle at 50% 42%,
      rgba(174, 145, 255, 0.26),
      transparent 31rem
    ),
    linear-gradient(145deg, #4520bc 0%, #6131e8 48%, #8a5cf6 100%);
  isolation: isolate;
}

.ambient-light {
  position: absolute;
  z-index: 0;
  width: 34rem;
  height: 34rem;
  pointer-events: none;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 50%;
}
.ambient-light-one {
  top: -20rem;
  right: -10rem;
  box-shadow:
    0 0 0 4.8rem rgba(255, 255, 255, 0.025),
    0 0 0 10rem rgba(255, 255, 255, 0.018);
}
.ambient-light-two {
  bottom: -26rem;
  left: -8rem;
  background: rgba(255, 255, 255, 0.025);
}

.student-login-immersive .student-role-back {
  position: absolute;
  z-index: 5;
  top: 24px;
  left: 28px;
  right: auto;
  min-height: 38px;
  padding: 0 14px;
  color: #f6f3ff;
  border: 1px solid rgba(255, 255, 255, 0.3);
  background: rgba(255, 255, 255, 0.11);
  border-radius: 999px;
  font-size: 13px;
  backdrop-filter: blur(14px);
  transition:
    background 0.2s ease,
    transform 0.2s ease;
}
.student-login-immersive .student-role-back:hover {
  background: rgba(255, 255, 255, 0.18);
  transform: translateY(-1px);
}

.learning-bubbles {
  position: absolute;
  z-index: 1;
  inset: 0;
  overflow: hidden;
  pointer-events: none;
}
.learning-bubble {
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
.learning-bubble:focus-visible {
  box-shadow: 0 0 0 4px rgba(255, 255, 255, 0.4);
}
.bubble-surface {
  display: flex;
  width: 100%;
  height: 100%;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  gap: 7px;
  padding: 22px;
  border: 1px solid rgba(255, 255, 255, 0.3);
  background:
    radial-gradient(
      circle at 30% 20%,
      rgba(255, 255, 255, 0.35) 0 5px,
      transparent 6px
    ),
    linear-gradient(145deg, rgba(255, 255, 255, 0.2), rgba(255, 255, 255, 0.07));
  border-radius: 50%;
  box-shadow:
    inset 10px 12px 24px rgba(255, 255, 255, 0.11),
    inset -12px -14px 25px rgba(52, 22, 143, 0.12),
    0 18px 45px rgba(39, 17, 113, 0.18);
  text-align: center;
  backdrop-filter: blur(12px);
  animation: bubble-drift var(--drift-duration) ease-in-out var(--drift-delay)
    infinite alternate;
  transition:
    border-color 0.2s ease,
    background 0.2s ease,
    box-shadow 0.2s ease;
}
.learning-bubble:hover .bubble-surface {
  border-color: rgba(255, 255, 255, 0.52);
  background: linear-gradient(
    145deg,
    rgba(255, 255, 255, 0.27),
    rgba(255, 255, 255, 0.1)
  );
  box-shadow:
    inset 10px 12px 24px rgba(255, 255, 255, 0.14),
    0 22px 52px rgba(38, 16, 111, 0.23);
}
.bubble-surface > svg {
  color: #f0eaff;
}
.bubble-surface strong {
  max-width: 145px;
  font-size: 15px;
  line-height: 1.25;
}
.bubble-surface small {
  color: rgba(255, 255, 255, 0.78);
  font-size: 11px;
  line-height: 1.35;
}
.learning-bubble.launched {
  animation: bubble-launch 1.65s cubic-bezier(0.42, 0, 0.2, 1) both;
}

.student-login-immersive .login-form-wrap {
  position: relative;
  z-index: 3;
  display: grid;
  width: 100%;
  min-height: 100svh;
  place-items: center;
  padding: 42px 24px;
  background: transparent;
  pointer-events: none;
}
.student-login-immersive .login-card {
  width: min(100%, 520px);
  max-height: calc(100svh - 48px);
  overflow-y: auto;
  padding: 36px 40px 38px;
  border: 1px solid rgba(255, 255, 255, 0.72);
  background: rgba(255, 255, 255, 0.96);
  border-radius: 24px;
  box-shadow: 0 28px 80px rgba(39, 17, 111, 0.28);
  scrollbar-width: thin;
  backdrop-filter: blur(22px);
  pointer-events: auto;
}
.student-login-immersive .login-heading {
  margin-bottom: 27px;
}
.login-title-row {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 13px;
}
.login-title-logo {
  display: grid;
  width: 46px;
  height: 46px;
  flex: 0 0 auto;
  place-items: center;
  color: #fff;
  background: linear-gradient(145deg, #5b34e8, #8e58f7);
  border-radius: 14px;
  box-shadow: 0 10px 22px rgba(104, 67, 237, 0.25);
}
.student-login-immersive .login-heading h2 {
  margin: 0;
  color: #261a59;
  font-size: 29px;
  letter-spacing: -0.035em;
}
.student-login-immersive .auth-tabs {
  margin: 0 0 23px;
}
.student-login-immersive .login-fields {
  gap: 16px;
}
.student-login-immersive .register-space {
  height: 18px;
}
.verification-shell button {
  flex: 0 0 auto;
  padding: 7px 10px;
  color: #6843ed;
  border: 0;
  border-left: 1px solid #dedceb;
  background: transparent;
  font-size: 12px;
  font-weight: 800;
  white-space: nowrap;
}
.verification-shell button:disabled {
  color: #9aa9a4;
  cursor: not-allowed;
}

@keyframes bubble-drift {
  from {
    transform: translate3d(-4px, -7px, 0) rotate(-1.2deg);
  }
  to {
    transform: translate3d(5px, 9px, 0) rotate(1.2deg);
  }
}

@keyframes bubble-launch {
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
  .learning-bubble {
    --bubble-size: 142px !important;
    opacity: 0.66;
  }
  .bubble-surface strong {
    font-size: 13px;
  }
  .bubble-surface small {
    font-size: 10px;
  }
}

@media (max-width: 760px) {
  .student-login-immersive.login-page {
    display: grid;
    background:
      radial-gradient(
        circle at 50% 35%,
        rgba(174, 145, 255, 0.25),
        transparent 22rem
      ),
      linear-gradient(145deg, #4520bc, #7443ec 65%, #936af7);
  }
  .student-login-immersive .student-role-back {
    top: 16px;
    left: 16px;
    min-height: 36px;
  }
  .student-login-immersive .login-form-wrap {
    min-height: 100svh;
    margin-top: 0;
    padding: 70px 16px 24px;
    border-radius: 0;
  }
  .student-login-immersive .login-card {
    max-height: calc(100svh - 94px);
    padding: 28px 22px 30px;
    border-radius: 20px;
  }
  .student-login-immersive .login-heading h2 {
    font-size: 24px;
  }
  .login-title-logo {
    width: 42px;
    height: 42px;
  }
  .learning-bubble {
    --bubble-size: 112px !important;
    opacity: 0.45;
  }
  .learning-bubble:nth-child(2),
  .learning-bubble:nth-child(3),
  .learning-bubble:nth-child(5) {
    display: none;
  }
  .bubble-surface {
    gap: 4px;
    padding: 14px;
  }
  .bubble-surface > svg {
    width: 18px;
  }
  .bubble-surface strong {
    font-size: 11px;
  }
  .bubble-surface small {
    font-size: 9px;
  }
}

@media (max-height: 720px) and (min-width: 761px) {
  .student-login-immersive .login-form-wrap {
    padding-block: 22px;
  }
  .student-login-immersive .login-card {
    max-height: calc(100svh - 32px);
    padding-block: 28px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .bubble-surface {
    animation: none;
  }
  .learning-bubble.launched {
    animation-duration: 0.45s;
  }
}
</style>
