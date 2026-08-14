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
onBeforeUnmount(() => {
  window.clearInterval(countdownTimer);
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
  <main class="login-page student-theme student-login-showcase">
    <div class="page-glow page-glow-top" aria-hidden="true" />
    <div class="page-glow page-glow-bottom" aria-hidden="true" />

    <button
      v-if="props.showRoleSwitch"
      class="student-role-back"
      type="button"
      @click="emit('back')"
    >
      <ArrowLeft :size="16" />重新选择身份
    </button>

    <section class="student-login-shell">
      <aside class="login-visual">
        <header class="visual-brand">
          <WenluBrandMark :size="44" />
          <span>
            <strong>问鹿</strong>
            <small>智能学习成长平台</small>
          </span>
        </header>

        <div class="visual-copy">
          <span class="visual-eyebrow"><Sparkles :size="15" />AI 学习伙伴</span>
          <h1>让每一次学习<br />都有清晰的方向</h1>
          <p>多模型协同分析学习过程，为你规划当下，也陪你走向更远的目标。</p>
        </div>

        <div class="visual-art" aria-hidden="true">
          <span class="art-orbit art-orbit-one" />
          <span class="art-orbit art-orbit-two" />
          <div class="study-dashboard">
            <div class="dashboard-bar">
              <span /><span /><span />
              <small>今日学习空间</small>
            </div>
            <div class="dashboard-content">
              <WenluBrandMark :size="68" />
              <div class="dashboard-summary">
                <small>本周学习进度</small>
                <strong>目标正在稳步达成</strong>
                <span class="progress-track"><i /></span>
              </div>
              <div class="dashboard-rows">
                <span><i /><b /></span>
                <span><i /><b /></span>
                <span><i /><b /></span>
              </div>
            </div>
          </div>
          <div class="visual-chip chip-model">
            <BrainCircuit :size="18" /><span
              ><strong>多模型协同</strong><small>智能分析</small></span
            >
          </div>
          <div class="visual-chip chip-plan">
            <BookOpenCheck :size="18" /><span
              ><strong>学习规划</strong><small>清晰可见</small></span
            >
          </div>
        </div>

        <div class="visual-features">
          <span><GraduationCap :size="17" />新课标学习路径</span>
          <span><ShieldCheck :size="17" />安全可信的学习空间</span>
        </div>
      </aside>

      <section class="login-panel">
        <form class="login-card" @submit.prevent="submit">
          <div class="login-heading">
            <span class="login-kicker">
              {{ mode === "login" ? "STUDENT SIGN IN" : "CREATE ACCOUNT" }}
            </span>
            <h2>{{ mode === "login" ? "欢迎回来" : "开启学习旅程" }}</h2>
            <p>
              {{
                mode === "login"
                  ? "登录问鹿，继续你的专属学习计划"
                  : "填写信息，创建你的问鹿学生账号"
              }}
            </p>
          </div>

          <div class="auth-tabs" role="tablist" aria-label="登录方式">
            <button
              type="button"
              role="tab"
              :aria-selected="mode === 'login'"
              :class="{ active: mode === 'login' }"
              @click="switchMode('login')"
            >
              <KeyRound :size="16" />账号登录
            </button>
            <button
              type="button"
              role="tab"
              :aria-selected="mode === 'register'"
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
                <UserRound :size="18" />
                <input
                  v-model="form.studentName"
                  autocomplete="name"
                  placeholder="请输入学生真实姓名"
                />
              </div>
              <small
                v-if="submitted && form.studentName.trim().length < 2"
                class="field-error"
              >
                请填写至少 2 个字的姓名
              </small>
            </label>

            <label>
              <span>学号</span>
              <div class="input-shell">
                <UserRound :size="18" />
                <input
                  v-model="form.studentId"
                  autocomplete="username"
                  placeholder="请输入你的学号"
                />
              </div>
              <small
                v-if="
                  submitted &&
                  !/^[A-Za-z0-9_.-]{4,64}$/.test(form.studentId.trim())
                "
                class="field-error"
              >
                请输入 4—64 位字母、数字、点、横线或下划线
              </small>
            </label>

            <label>
              <span>手机号</span>
              <div class="input-shell">
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
              <small
                v-if="submitted && !/^1[3-9]\d{9}$/.test(form.phone.trim())"
                class="field-error"
              >
                手机号格式不正确
              </small>
            </label>

            <label>
              <span>短信验证码</span>
              <div class="input-shell verification-shell">
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

            <template v-if="mode === 'register'">
              <div class="two-fields">
                <label>
                  <span>当前年级</span>
                  <div class="input-shell">
                    <GraduationCap :size="18" />
                    <select v-model="form.grade">
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
                  <MapPin :size="18" />
                  <select v-model="form.provinceCode">
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

          <div v-if="error" class="auth-error" role="alert">{{ error }}</div>

          <button class="login-submit" type="submit" :disabled="submitting">
            <LoaderCircle v-if="submitting" class="spin" :size="19" />
            <template v-else>
              {{ mode === "login" ? "登录学习空间" : "注册并进入学习空间" }}
              <ArrowRight :size="19" />
            </template>
          </button>

          <p class="login-assurance">
            <ShieldCheck :size="15" />
            手机号仅用于身份验证，问鹿会妥善保护你的个人信息
          </p>
        </form>
      </section>
    </section>
  </main>
</template>

<style scoped>
.student-login-showcase.login-page {
  position: relative;
  display: grid;
  min-height: 100svh;
  grid-template-columns: minmax(0, 1fr);
  place-items: center;
  overflow: hidden;
  padding: 36px;
  background:
    linear-gradient(122deg, rgba(46, 22, 99, 0.96), rgba(92, 58, 190, 0.9)),
    #4d2c9f;
  isolation: isolate;
}

.page-glow {
  position: absolute;
  z-index: -1;
  pointer-events: none;
  border-radius: 999px;
  filter: blur(2px);
}
.page-glow-top {
  top: -28rem;
  left: -8rem;
  width: 52rem;
  height: 52rem;
  border: 1px solid rgba(255, 255, 255, 0.14);
  box-shadow:
    0 0 0 7rem rgba(255, 255, 255, 0.025),
    0 0 0 14rem rgba(255, 255, 255, 0.02);
}
.page-glow-bottom {
  right: -12rem;
  bottom: -20rem;
  width: 44rem;
  height: 44rem;
  background: rgba(179, 156, 255, 0.16);
  filter: blur(70px);
}

.student-login-showcase .student-role-back {
  position: fixed;
  z-index: 5;
  top: 18px;
  left: 22px;
  right: auto;
  display: inline-flex;
  min-height: 38px;
  align-items: center;
  gap: 6px;
  padding: 0 14px;
  color: rgba(255, 255, 255, 0.88);
  border: 1px solid rgba(255, 255, 255, 0.25);
  background: rgba(32, 17, 69, 0.24);
  border-radius: 999px;
  font-size: 12px;
  backdrop-filter: blur(14px);
  transition:
    background 0.2s ease,
    transform 0.2s ease;
}
.student-login-showcase .student-role-back:hover {
  background: rgba(255, 255, 255, 0.15);
  transform: translateY(-1px);
}

.student-login-shell {
  display: grid;
  width: clamp(900px, 60vw, 1320px);
  height: min(860px, calc(100svh - 72px));
  min-height: 700px;
  grid-template-columns: minmax(390px, 43%) minmax(500px, 57%);
  overflow: hidden;
  background: #fff;
  border: 1px solid rgba(255, 255, 255, 0.68);
  border-radius: 30px;
  box-shadow: 0 36px 90px rgba(23, 8, 59, 0.34);
}

.login-visual {
  position: relative;
  display: flex;
  min-width: 0;
  flex-direction: column;
  overflow: hidden;
  padding: 42px 48px 34px;
  color: #3a215f;
  background:
    radial-gradient(
      circle at 16% 10%,
      rgba(255, 255, 255, 0.92),
      transparent 17rem
    ),
    linear-gradient(160deg, #f7f1ff 0%, #e5d8ff 48%, #cfb9ff 100%);
}
.login-visual::before {
  position: absolute;
  right: -12rem;
  bottom: -14rem;
  width: 36rem;
  height: 36rem;
  content: "";
  border: 1px solid rgba(92, 52, 150, 0.13);
  border-radius: 50%;
  box-shadow:
    0 0 0 4.5rem rgba(255, 255, 255, 0.13),
    0 0 0 9rem rgba(255, 255, 255, 0.09);
}
.login-visual::after {
  position: absolute;
  top: 17%;
  right: -22%;
  width: 42%;
  height: 45%;
  content: "";
  background: rgba(255, 255, 255, 0.2);
  transform: rotate(-12deg);
}

.visual-brand {
  position: relative;
  z-index: 2;
  display: flex;
  align-items: center;
  gap: 13px;
}
.visual-brand > span {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.visual-brand strong {
  color: #4f2c64;
  font-size: 23px;
  letter-spacing: 0.08em;
}
.visual-brand small {
  color: #826b99;
  font-size: 11px;
  letter-spacing: 0.06em;
}

.visual-copy {
  position: relative;
  z-index: 2;
  margin-top: 48px;
}
.visual-eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  color: #7650ba;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.12em;
}
.visual-copy h1 {
  margin: 17px 0 15px;
  color: #3c2055;
  font-size: clamp(34px, 3.15vw, 49px);
  line-height: 1.22;
  letter-spacing: -0.045em;
}
.visual-copy p {
  max-width: 470px;
  margin: 0;
  color: #786587;
  font-size: 14px;
  line-height: 1.8;
}

.visual-art {
  position: relative;
  z-index: 2;
  flex: 1;
  min-height: 260px;
  margin: 24px -8px 8px;
}
.art-orbit {
  position: absolute;
  border: 1px solid rgba(89, 53, 145, 0.15);
  border-radius: 50%;
}
.art-orbit-one {
  left: 8%;
  bottom: 4%;
  width: 260px;
  height: 260px;
}
.art-orbit-two {
  right: 2%;
  bottom: 15%;
  width: 170px;
  height: 170px;
  box-shadow: 0 0 0 30px rgba(255, 255, 255, 0.12);
}

.study-dashboard {
  position: absolute;
  left: 50%;
  bottom: 15px;
  width: min(390px, 78%);
  min-height: 220px;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.94);
  border: 1px solid rgba(255, 255, 255, 0.96);
  border-radius: 22px;
  box-shadow: 0 28px 55px rgba(74, 42, 115, 0.22);
  transform: translateX(-50%) rotate(-1.5deg);
}
.dashboard-bar {
  display: flex;
  height: 42px;
  align-items: center;
  gap: 6px;
  padding: 0 16px;
  background: #faf8fd;
  border-bottom: 1px solid #eee7f5;
}
.dashboard-bar > span {
  width: 7px;
  height: 7px;
  background: #d8cae8;
  border-radius: 50%;
}
.dashboard-bar small {
  margin-left: auto;
  color: #9a88ac;
  font-size: 9px;
}
.dashboard-content {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 16px;
  padding: 21px 23px;
}
.dashboard-summary {
  display: flex;
  min-width: 0;
  justify-content: center;
  flex-direction: column;
  gap: 6px;
}
.dashboard-summary small {
  color: #a18caf;
  font-size: 9px;
}
.dashboard-summary strong {
  overflow: hidden;
  color: #4a2b61;
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.progress-track {
  display: block;
  width: 100%;
  height: 7px;
  margin-top: 5px;
  overflow: hidden;
  background: #efe9f5;
  border-radius: 999px;
}
.progress-track i {
  display: block;
  width: 72%;
  height: 100%;
  background: linear-gradient(90deg, #7250dc, #e496c3);
  border-radius: inherit;
}
.dashboard-rows {
  display: grid;
  grid-column: 1 / -1;
  gap: 9px;
}
.dashboard-rows > span {
  display: flex;
  height: 20px;
  align-items: center;
  gap: 10px;
  padding: 0 8px;
  background: #faf8fc;
  border-radius: 7px;
}
.dashboard-rows i {
  width: 8px;
  height: 8px;
  background: #c4a8ed;
  border-radius: 3px;
}
.dashboard-rows b {
  width: 58%;
  height: 5px;
  background: #e8dfef;
  border-radius: 999px;
}
.dashboard-rows > span:nth-child(2) b {
  width: 75%;
}
.dashboard-rows > span:nth-child(3) b {
  width: 47%;
}

.visual-chip {
  position: absolute;
  z-index: 3;
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 10px 13px;
  color: #5d3b79;
  border: 1px solid rgba(255, 255, 255, 0.86);
  background: rgba(255, 255, 255, 0.88);
  border-radius: 13px;
  box-shadow: 0 14px 32px rgba(74, 42, 115, 0.16);
  backdrop-filter: blur(12px);
}
.visual-chip > svg {
  color: #7756c8;
}
.visual-chip span {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.visual-chip strong {
  font-size: 10px;
}
.visual-chip small {
  color: #9a85aa;
  font-size: 8px;
}
.chip-model {
  top: 20%;
  right: -2%;
  animation: chip-float 4.8s ease-in-out infinite alternate;
}
.chip-plan {
  left: 0;
  bottom: 11%;
  animation: chip-float 5.4s ease-in-out -2s infinite alternate;
}

.visual-features {
  position: relative;
  z-index: 2;
  display: flex;
  flex-wrap: wrap;
  gap: 18px;
  color: #6c5580;
  font-size: 10px;
  font-weight: 700;
}
.visual-features span {
  display: inline-flex;
  align-items: center;
  gap: 7px;
}
.visual-features svg {
  color: #7650ba;
}

.login-panel {
  display: grid;
  min-width: 0;
  overflow-y: auto;
  place-items: center;
  padding: 42px clamp(48px, 6vw, 104px);
  background:
    radial-gradient(circle at 100% 0%, #f8f4ff 0, transparent 23rem), #fff;
  scrollbar-width: thin;
}
.student-login-showcase .login-card {
  width: min(100%, 520px);
  padding: 8px 0;
}
.student-login-showcase .login-heading {
  margin-bottom: 28px;
}
.login-kicker {
  display: block;
  margin-bottom: 12px;
  color: #8b69d1;
  font-size: 10px;
  font-weight: 850;
  letter-spacing: 0.17em;
}
.student-login-showcase .login-heading h2 {
  margin: 0 0 10px;
  color: #2e1d41;
  font-size: clamp(32px, 3vw, 43px);
  letter-spacing: -0.045em;
}
.student-login-showcase .login-heading p {
  margin: 0;
  color: #8a7d94;
  font-size: 13px;
  line-height: 1.7;
}

.student-login-showcase .auth-tabs {
  margin: 0 0 24px;
  padding: 5px;
  background: #f4f0f8;
  border: 1px solid #eee7f3;
  border-radius: 13px;
}
.student-login-showcase .auth-tabs button {
  min-height: 43px;
  color: #8a7d94;
  border-radius: 9px;
  font-size: 11px;
}
.student-login-showcase .auth-tabs button.active {
  color: #6843b0;
  background: #fff;
  box-shadow: 0 5px 15px rgba(73, 45, 103, 0.1);
}

.student-login-showcase .login-fields {
  gap: 15px;
}
.student-login-showcase .login-fields label > span {
  color: #4d3e58;
  font-size: 11px;
}
.student-login-showcase .input-shell {
  min-height: 53px;
  border: 1px solid #e5deea;
  background: #fbf9fc;
  border-radius: 11px;
}
.student-login-showcase .input-shell:focus-within {
  border-color: #8a62d0;
  background: #fff;
  box-shadow: 0 0 0 3px rgba(116, 76, 185, 0.1);
}
.student-login-showcase .input-shell > svg {
  color: #9c8ba9;
}
.student-login-showcase .input-shell input,
.student-login-showcase .input-shell select {
  color: #382744;
  font-size: 12px;
}
.student-login-showcase .input-shell input::placeholder {
  color: #b2a5bb;
}

.student-login-showcase .verification-shell button {
  flex: 0 0 auto;
  padding: 8px 4px 8px 13px;
  color: #7650ba;
  border: 0;
  border-left: 1px solid #e6dfea;
  background: transparent;
  font-size: 11px;
  font-weight: 800;
  white-space: nowrap;
}
.student-login-showcase .verification-shell button:disabled {
  color: #aaa0b1;
}
.student-login-showcase .field-error {
  color: #b64355;
  font-size: 10px;
}
.student-login-showcase .auth-error {
  margin-top: 15px;
}

.student-login-showcase .login-submit {
  width: 100%;
  min-height: 54px;
  margin-top: 24px;
  color: #fff;
  border: 0;
  background: linear-gradient(100deg, #5f36c8, #8b62df);
  border-radius: 11px;
  font-size: 12px;
  box-shadow: 0 13px 27px rgba(105, 64, 184, 0.24);
}
.student-login-showcase .login-submit:hover {
  transform: translateY(-1px);
  box-shadow: 0 17px 31px rgba(105, 64, 184, 0.3);
}
.login-assurance {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  margin: 16px 0 0;
  color: #a093a9;
  font-size: 9px;
  line-height: 1.6;
}
.login-assurance svg {
  flex: 0 0 auto;
  color: #8a68c4;
}

@keyframes chip-float {
  from {
    transform: translate3d(0, -3px, 0);
  }
  to {
    transform: translate3d(0, 7px, 0);
  }
}

@media (max-width: 1120px) {
  .student-login-showcase.login-page {
    padding: 24px;
  }
  .student-login-shell {
    width: calc(100vw - 48px);
    height: calc(100svh - 48px);
    grid-template-columns: minmax(350px, 42%) minmax(440px, 58%);
  }
  .login-visual {
    padding: 36px 34px 30px;
  }
  .visual-copy {
    margin-top: 36px;
  }
  .visual-copy h1 {
    font-size: 36px;
  }
  .login-panel {
    padding-inline: 54px;
  }
}

@media (max-width: 820px) {
  .student-login-showcase.login-page {
    display: block;
    overflow: auto;
    padding: 0;
    background: #fff;
  }
  .student-login-showcase .student-role-back {
    position: absolute;
    top: 14px;
    left: 14px;
    color: #62458a;
    border-color: rgba(92, 52, 150, 0.2);
    background: rgba(255, 255, 255, 0.72);
  }
  .student-login-shell {
    width: 100%;
    height: auto;
    min-height: 100svh;
    grid-template-columns: 1fr;
    overflow: visible;
    border: 0;
    border-radius: 0;
    box-shadow: none;
  }
  .login-visual {
    min-height: 330px;
    padding: 70px 24px 24px;
  }
  .visual-brand {
    justify-content: center;
  }
  .visual-copy {
    margin-top: 24px;
    text-align: center;
  }
  .visual-copy h1 {
    margin-block: 12px 10px;
    font-size: 31px;
  }
  .visual-copy p {
    max-width: 500px;
    margin-inline: auto;
    font-size: 12px;
  }
  .visual-art {
    display: none;
  }
  .visual-features {
    justify-content: center;
    margin-top: auto;
    padding-top: 26px;
  }
  .login-panel {
    overflow: visible;
    padding: 42px 24px 50px;
  }
  .student-login-showcase .login-card {
    width: min(100%, 520px);
  }
}

@media (max-width: 480px) {
  .login-visual {
    min-height: 300px;
  }
  .visual-brand strong {
    font-size: 20px;
  }
  .visual-copy h1 {
    font-size: 27px;
  }
  .visual-copy p {
    padding-inline: 4px;
  }
  .visual-features {
    gap: 11px;
    font-size: 9px;
  }
  .login-panel {
    padding-inline: 18px;
  }
  .student-login-showcase .login-heading h2 {
    font-size: 32px;
  }
  .student-login-showcase .two-fields {
    grid-template-columns: 1fr;
  }
}

@media (max-height: 760px) and (min-width: 821px) {
  .student-login-shell {
    min-height: 640px;
  }
  .login-visual {
    padding-block: 30px 24px;
  }
  .visual-copy {
    margin-top: 25px;
  }
  .visual-copy h1 {
    font-size: 35px;
  }
  .visual-art {
    min-height: 210px;
  }
  .study-dashboard {
    min-height: 190px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .visual-chip {
    animation: none;
  }
}
</style>
