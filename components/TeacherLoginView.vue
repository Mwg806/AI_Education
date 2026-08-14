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
onBeforeUnmount(() => {
  window.clearInterval(countdownTimer);
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
  <main class="teacher-auth-page teacher-login-showcase">
    <div class="teacher-page-glow teacher-page-glow-top" aria-hidden="true" />
    <div
      class="teacher-page-glow teacher-page-glow-bottom"
      aria-hidden="true"
    />

    <button
      v-if="props.showRoleSwitch"
      class="back-role"
      type="button"
      @click="emit('back')"
    >
      <ArrowLeft :size="16" />重新选择身份
    </button>

    <section class="teacher-login-shell">
      <aside class="teacher-login-visual">
        <header class="teacher-visual-brand">
          <WenluBrandMark :size="44" />
          <span>
            <strong>问鹿</strong>
            <small>教师协同工作台</small>
          </span>
        </header>

        <div class="teacher-visual-copy">
          <span class="teacher-visual-eyebrow">
            <School :size="15" />TEACHER WORKSPACE
          </span>
          <h1>让教学协作<br />更清晰、更高效</h1>
          <p>多模型协同支持教学全过程</p>
        </div>

        <div class="teacher-visual-art" aria-hidden="true">
          <span class="teacher-art-orbit teacher-art-orbit-one" />
          <span class="teacher-art-orbit teacher-art-orbit-two" />
          <div class="teacher-dashboard">
            <div class="teacher-dashboard-bar">
              <span /><span /><span />
              <small>班级教学概览</small>
            </div>
            <div class="teacher-dashboard-content">
              <WenluBrandMark :size="68" />
              <div class="teacher-dashboard-summary">
                <small>本周教学进度</small>
                <strong>学情数据持续更新</strong>
                <span class="teacher-progress-track"><i /></span>
              </div>
              <div class="teacher-dashboard-rows">
                <span><i /><b /></span>
                <span><i /><b /></span>
                <span><i /><b /></span>
              </div>
            </div>
          </div>
          <div class="teacher-visual-chip teacher-chip-insight">
            <BrainCircuit :size="18" />
            <span><strong>学情分析</strong><small>证据清晰</small></span>
          </div>
          <div class="teacher-visual-chip teacher-chip-prepare">
            <BookOpenCheck :size="18" />
            <span><strong>智能备课</strong><small>高效协作</small></span>
          </div>
        </div>

        <div class="teacher-visual-features">
          <span><UsersRound :size="17" />班级协同连接</span>
          <span><ShieldCheck :size="17" />教学数据安全边界</span>
        </div>
      </aside>

      <section class="teacher-login-panel">
        <form @submit.prevent="submit(mode)">
          <div class="teacher-login-heading">
            <span class="teacher-login-kicker">
              {{ mode === "login" ? "TEACHER SIGN IN" : "CREATE ACCOUNT" }}
            </span>
            <h2>{{ mode === "login" ? "欢迎回来" : "创建教师账号" }}</h2>
            <p>
              {{
                mode === "login"
                  ? "登录问鹿，进入你的教师协同工作台"
                  : "验证手机号后创建问鹿教师账号"
              }}
            </p>
          </div>

          <div class="teacher-auth-tabs" role="tablist" aria-label="登录方式">
            <button
              type="button"
              role="tab"
              :aria-selected="mode === 'login'"
              :class="{ active: mode === 'login' }"
              @click="switchMode('login')"
            >
              <KeyRound :size="16" />教师登录
            </button>
            <button
              type="button"
              role="tab"
              :aria-selected="mode === 'register'"
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
                <UserRound :size="18" />
                <input
                  v-model="form.teacherName"
                  autocomplete="name"
                  placeholder="请输入教师姓名"
                />
              </div>
            </label>

            <label v-if="mode === 'register'">
              <span>学校名称</span>
              <div>
                <School :size="18" />
                <input v-model="form.schoolName" placeholder="请输入学校全称" />
              </div>
            </label>

            <label v-if="mode === 'register'">
              <span>主要任教学科</span>
              <div>
                <GraduationCap :size="18" />
                <select v-model="form.subject">
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
                <UserRound :size="18" />
                <input
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
              >
                教师账号格式不正确
              </small>
            </label>

            <label>
              <span>手机号</span>
              <div>
                <Smartphone :size="18" />
                <input
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
                <MessageSquareText :size="18" />
                <input
                  v-model="form.verificationCode"
                  inputmode="numeric"
                  autocomplete="one-time-code"
                  maxlength="8"
                  placeholder="请输入验证码"
                />
                <button
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

          <p v-if="error" class="teacher-auth-error" role="alert">
            {{ error }}
          </p>

          <button
            class="teacher-login-submit"
            type="submit"
            :disabled="submitting"
          >
            <LoaderCircle v-if="submitting" class="spin" :size="19" />
            <template v-else>
              {{ mode === "login" ? "进入教师工作台" : "注册并进入教师工作台" }}
              <ArrowRight :size="19" />
            </template>
          </button>

          <p class="teacher-login-assurance">
            <ShieldCheck :size="15" />
            手机号仅用于身份验证，教学数据按照班级权限安全隔离
          </p>
        </form>
      </section>
    </section>
  </main>
</template>

<style scoped>
.teacher-login-showcase {
  position: relative;
  display: grid;
  min-height: 100svh;
  grid-template-columns: minmax(0, 1fr);
  place-items: center;
  overflow: hidden;
  padding: 36px;
  background:
    linear-gradient(122deg, rgba(4, 54, 42, 0.97), rgba(18, 116, 84, 0.92)),
    #0d6c4f;
  isolation: isolate;
}

.teacher-page-glow {
  position: absolute;
  z-index: -1;
  pointer-events: none;
  border-radius: 999px;
}
.teacher-page-glow-top {
  top: -28rem;
  left: -8rem;
  width: 52rem;
  height: 52rem;
  border: 1px solid rgba(255, 255, 255, 0.14);
  box-shadow:
    0 0 0 7rem rgba(255, 255, 255, 0.025),
    0 0 0 14rem rgba(255, 255, 255, 0.02);
}
.teacher-page-glow-bottom {
  right: -12rem;
  bottom: -20rem;
  width: 44rem;
  height: 44rem;
  background: rgba(114, 225, 180, 0.16);
  filter: blur(70px);
}

.back-role {
  position: fixed;
  z-index: 5;
  top: 18px;
  left: 22px;
  display: inline-flex;
  min-height: 38px;
  align-items: center;
  gap: 6px;
  padding: 0 14px;
  color: rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(255, 255, 255, 0.26);
  background: rgba(3, 45, 34, 0.3);
  border-radius: 999px;
  font-size: 12px;
  backdrop-filter: blur(14px);
  transition:
    background 0.2s ease,
    transform 0.2s ease;
}
.back-role:hover {
  background: rgba(255, 255, 255, 0.15);
  transform: translateY(-1px);
}

.teacher-login-shell {
  display: grid;
  width: clamp(900px, 60vw, 1320px);
  height: 70svh;
  min-height: 0;
  grid-template-columns: minmax(390px, 43%) minmax(500px, 57%);
  overflow: hidden;
  background: #fff;
  border: 1px solid rgba(255, 255, 255, 0.68);
  border-radius: 30px;
  box-shadow: 0 36px 90px rgba(1, 41, 30, 0.38);
}

.teacher-login-visual {
  position: relative;
  display: flex;
  min-width: 0;
  flex-direction: column;
  overflow: hidden;
  padding: 28px 36px 24px;
  color: #173f35;
  background:
    radial-gradient(
      circle at 16% 10%,
      rgba(255, 255, 255, 0.94),
      transparent 17rem
    ),
    linear-gradient(160deg, #f0fbf6 0%, #d8f3e7 48%, #b8e6d2 100%);
}
.teacher-login-visual::before {
  position: absolute;
  right: -12rem;
  bottom: -14rem;
  width: 36rem;
  height: 36rem;
  content: "";
  border: 1px solid rgba(17, 112, 80, 0.13);
  border-radius: 50%;
  box-shadow:
    0 0 0 4.5rem rgba(255, 255, 255, 0.14),
    0 0 0 9rem rgba(255, 255, 255, 0.09);
}
.teacher-login-visual::after {
  position: absolute;
  top: 17%;
  right: -22%;
  width: 42%;
  height: 45%;
  content: "";
  background: rgba(255, 255, 255, 0.2);
  transform: rotate(-12deg);
}

.teacher-visual-brand {
  position: relative;
  z-index: 2;
  display: flex;
  align-items: center;
  gap: 13px;
}
.teacher-visual-brand > span {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.teacher-visual-brand strong {
  color: #214f43;
  font-size: 23px;
  letter-spacing: 0.08em;
}
.teacher-visual-brand small {
  color: #648a7d;
  font-size: 11px;
  letter-spacing: 0.06em;
}

.teacher-visual-copy {
  position: relative;
  z-index: 2;
  margin-top: 24px;
}
.teacher-visual-eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  color: #228363;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.12em;
}
.teacher-visual-copy h1 {
  margin: 12px 0 10px;
  color: #173f35;
  font-size: clamp(30px, 2.6vw, 42px);
  line-height: 1.22;
  letter-spacing: -0.045em;
}
.teacher-visual-copy p {
  max-width: 470px;
  margin: 0;
  color: #597a70;
  font-size: 13px;
  line-height: 1.6;
}

.teacher-visual-art {
  position: relative;
  z-index: 2;
  flex: 1;
  min-height: 160px;
  margin: 14px -8px 4px;
}
.teacher-art-orbit {
  position: absolute;
  border: 1px solid rgba(17, 112, 80, 0.15);
  border-radius: 50%;
}
.teacher-art-orbit-one {
  left: 8%;
  bottom: 4%;
  width: 260px;
  height: 260px;
}
.teacher-art-orbit-two {
  right: 2%;
  bottom: 15%;
  width: 170px;
  height: 170px;
  box-shadow: 0 0 0 30px rgba(255, 255, 255, 0.12);
}

.teacher-dashboard {
  position: absolute;
  left: 50%;
  bottom: 15px;
  width: min(390px, 78%);
  min-height: 190px;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.95);
  border: 1px solid rgba(255, 255, 255, 0.98);
  border-radius: 22px;
  box-shadow: 0 28px 55px rgba(13, 94, 67, 0.2);
  transform: translateX(-50%) rotate(-1.5deg);
}
.teacher-dashboard-bar {
  display: flex;
  height: 42px;
  align-items: center;
  gap: 6px;
  padding: 0 16px;
  background: #f7fbf9;
  border-bottom: 1px solid #e1eee8;
}
.teacher-dashboard-bar > span {
  width: 7px;
  height: 7px;
  background: #bfdacf;
  border-radius: 50%;
}
.teacher-dashboard-bar small {
  margin-left: auto;
  color: #7f9e93;
  font-size: 9px;
}
.teacher-dashboard-content {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 16px;
  padding: 21px 23px;
}
.teacher-dashboard-summary {
  display: flex;
  min-width: 0;
  justify-content: center;
  flex-direction: column;
  gap: 6px;
}
.teacher-dashboard-summary small {
  color: #80a095;
  font-size: 9px;
}
.teacher-dashboard-summary strong {
  overflow: hidden;
  color: #235044;
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.teacher-progress-track {
  display: block;
  width: 100%;
  height: 7px;
  margin-top: 5px;
  overflow: hidden;
  background: #e3f0ea;
  border-radius: 999px;
}
.teacher-progress-track i {
  display: block;
  width: 72%;
  height: 100%;
  background: linear-gradient(90deg, #1f8f69, #72d0a8);
  border-radius: inherit;
}
.teacher-dashboard-rows {
  display: grid;
  grid-column: 1 / -1;
  gap: 9px;
}
.teacher-dashboard-rows > span {
  display: flex;
  height: 20px;
  align-items: center;
  gap: 10px;
  padding: 0 8px;
  background: #f5faf8;
  border-radius: 7px;
}
.teacher-dashboard-rows i {
  width: 8px;
  height: 8px;
  background: #8dcdb2;
  border-radius: 3px;
}
.teacher-dashboard-rows b {
  width: 58%;
  height: 5px;
  background: #d8ebe3;
  border-radius: 999px;
}
.teacher-dashboard-rows > span:nth-child(2) b {
  width: 75%;
}
.teacher-dashboard-rows > span:nth-child(3) b {
  width: 47%;
}

.teacher-visual-chip {
  position: absolute;
  z-index: 3;
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 10px 13px;
  color: #285d4e;
  border: 1px solid rgba(255, 255, 255, 0.88);
  background: rgba(255, 255, 255, 0.9);
  border-radius: 13px;
  box-shadow: 0 14px 32px rgba(13, 94, 67, 0.15);
  backdrop-filter: blur(12px);
}
.teacher-visual-chip > svg {
  color: #218661;
}
.teacher-visual-chip span {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.teacher-visual-chip strong {
  font-size: 10px;
}
.teacher-visual-chip small {
  color: #729589;
  font-size: 8px;
}
.teacher-chip-insight {
  top: 20%;
  right: -2%;
  animation: teacher-chip-float 4.8s ease-in-out infinite alternate;
}
.teacher-chip-prepare {
  left: 0;
  bottom: 11%;
  animation: teacher-chip-float 5.4s ease-in-out -2s infinite alternate;
}

.teacher-visual-features {
  position: relative;
  z-index: 2;
  display: flex;
  flex-wrap: wrap;
  gap: 18px;
  color: #55796e;
  font-size: 10px;
  font-weight: 700;
}
.teacher-visual-features span {
  display: inline-flex;
  align-items: center;
  gap: 7px;
}
.teacher-visual-features svg {
  color: #218661;
}

.teacher-login-panel {
  display: grid;
  min-width: 0;
  overflow-y: auto;
  place-items: center;
  padding: 28px clamp(38px, 4.5vw, 76px);
  background:
    radial-gradient(circle at 100% 0%, #effaf5 0, transparent 23rem), #fff;
  scrollbar-width: thin;
}
.teacher-login-panel form {
  width: min(100%, 520px);
  padding: 0;
}
.teacher-login-heading {
  margin-bottom: 18px;
}
.teacher-login-kicker {
  display: block;
  margin-bottom: 8px;
  color: #278563;
  font-size: 10px;
  font-weight: 850;
  letter-spacing: 0.17em;
}
.teacher-login-heading h2 {
  margin: 0 0 7px;
  color: #173f35;
  font-size: clamp(30px, 2.6vw, 38px);
  letter-spacing: -0.045em;
}
.teacher-login-heading p {
  margin: 0;
  color: #728b82;
  font-size: 13px;
  line-height: 1.7;
}

.teacher-auth-tabs {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
  margin: 0 0 16px;
  padding: 5px;
  background: #edf6f2;
  border: 1px solid #e1eee8;
  border-radius: 13px;
}
.teacher-auth-tabs button {
  display: inline-flex;
  min-height: 40px;
  align-items: center;
  justify-content: center;
  gap: 7px;
  color: #728b82;
  border: 0;
  background: transparent;
  border-radius: 9px;
  font-size: 11px;
  font-weight: 750;
}
.teacher-auth-tabs button.active {
  color: #12694f;
  background: #fff;
  box-shadow: 0 5px 15px rgba(16, 102, 76, 0.1);
}

.teacher-fields {
  display: grid;
  gap: 10px;
}
.teacher-fields label {
  display: grid;
  gap: 6px;
}
.teacher-fields label > span {
  color: #315c4f;
  font-size: 11px;
  font-weight: 750;
}
.teacher-fields label > div {
  display: flex;
  min-height: 48px;
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
  background: #fff;
  box-shadow: 0 0 0 3px rgba(32, 139, 102, 0.1);
}
.teacher-fields input,
.teacher-fields select {
  width: 100%;
  min-width: 0;
  height: 46px;
  color: #23483d;
  border: 0;
  outline: 0;
  background: transparent;
  font: inherit;
  font-size: 12px;
}
.teacher-fields label > small {
  color: #b54545;
  font-size: 10px;
}

.teacher-code-field button {
  flex: 0 0 auto;
  padding: 8px 4px 8px 13px;
  color: #147457;
  border: 0;
  border-left: 1px solid #d8e6e1;
  background: transparent;
  font-size: 11px;
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
  font-size: 11px;
}
.teacher-login-submit {
  display: flex;
  width: 100%;
  min-height: 50px;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-top: 18px;
  color: #fff;
  border: 0;
  background: linear-gradient(100deg, #12694f, #25a476);
  border-radius: 11px;
  font-size: 12px;
  font-weight: 800;
  box-shadow: 0 13px 27px rgba(18, 105, 79, 0.23);
  transition:
    transform 0.2s ease,
    box-shadow 0.2s ease;
}
.teacher-login-submit:hover {
  transform: translateY(-1px);
  box-shadow: 0 17px 31px rgba(18, 105, 79, 0.3);
}
.teacher-login-submit:disabled {
  opacity: 0.58;
  cursor: wait;
}
.teacher-login-assurance {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  margin: 12px 0 0;
  color: #82978f;
  font-size: 9px;
  line-height: 1.6;
}
.teacher-login-assurance svg {
  flex: 0 0 auto;
  color: #278563;
}

@keyframes teacher-chip-float {
  from {
    transform: translate3d(0, -3px, 0);
  }
  to {
    transform: translate3d(0, 7px, 0);
  }
}

@media (max-width: 1120px) {
  .teacher-login-showcase {
    padding: 24px;
  }
  .teacher-login-shell {
    width: calc(100vw - 48px);
    height: 70svh;
    grid-template-columns: minmax(350px, 42%) minmax(440px, 58%);
  }
  .teacher-login-visual {
    padding: 30px 34px 24px;
  }
  .teacher-login-panel {
    padding-inline: 48px;
  }
}

@media (max-width: 820px) {
  .teacher-login-showcase {
    display: block;
    overflow: auto;
    padding: 0;
    background: #fff;
  }
  .back-role {
    position: absolute;
    top: 14px;
    left: 14px;
    color: #176149;
    border-color: rgba(18, 105, 79, 0.2);
    background: rgba(255, 255, 255, 0.74);
  }
  .teacher-login-shell {
    width: 100%;
    height: auto;
    min-height: 100svh;
    grid-template-columns: 1fr;
    overflow: visible;
    border: 0;
    border-radius: 0;
    box-shadow: none;
  }
  .teacher-login-visual {
    min-height: 320px;
    padding: 70px 24px 24px;
  }
  .teacher-visual-brand {
    justify-content: center;
  }
  .teacher-visual-copy {
    margin-top: 24px;
    text-align: center;
  }
  .teacher-visual-copy h1 {
    margin-block: 12px 10px;
    font-size: 30px;
  }
  .teacher-visual-copy p {
    max-width: 500px;
    margin-inline: auto;
    font-size: 12px;
  }
  .teacher-visual-art {
    display: none;
  }
  .teacher-visual-features {
    justify-content: center;
    margin-top: auto;
    padding-top: 24px;
  }
  .teacher-login-panel {
    overflow: visible;
    padding: 42px 24px 50px;
  }
  .teacher-login-panel form {
    width: min(100%, 520px);
  }
}

@media (max-width: 480px) {
  .teacher-login-visual {
    min-height: 300px;
  }
  .teacher-visual-brand strong {
    font-size: 20px;
  }
  .teacher-visual-copy h1 {
    font-size: 27px;
  }
  .teacher-visual-features {
    gap: 11px;
    font-size: 9px;
  }
  .teacher-login-panel {
    padding-inline: 18px;
  }
  .teacher-login-heading h2 {
    font-size: 32px;
  }
}

@media (max-height: 760px) and (min-width: 821px) {
  .teacher-login-shell {
    min-height: 520px;
  }
  .teacher-login-visual {
    padding-block: 24px 20px;
  }
  .teacher-visual-copy {
    margin-top: 18px;
  }
  .teacher-visual-copy h1 {
    font-size: 34px;
  }
  .teacher-visual-art {
    min-height: 145px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .teacher-visual-chip {
    animation: none;
  }
}
</style>
