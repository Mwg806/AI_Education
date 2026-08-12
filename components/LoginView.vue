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

import { loginStudent, registerStudent, sendVerificationCode } from "@/lib/auth-client";
import { provinceRoutes } from "@/lib/curriculum-catalog";
import type { AuthSession, StudentLoginProfile } from "@/lib/types";
import WenluBrandMark from "@/components/WenluBrandMark.vue";

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
  return accountValid
    && form.studentName.trim().length >= 2
    && phoneValid
    && codeValid
    && Boolean(form.grade)
    && Boolean(form.provinceCode);
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
    const result = await sendVerificationCode(form.phone.trim(), mode.value, "student");
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
onBeforeUnmount(() => window.clearInterval(countdownTimer));

async function submit() {
  submitted.value = true;
  error.value = "";
  if (!valid.value || submitting.value) return;
  submitting.value = true;
  try {
    const session = mode.value === "register"
      ? await registerStudent({
        studentId: form.studentId.trim(),
        phone: form.phone.trim(),
        verificationCode: form.verificationCode.trim(),
        studentName: form.studentName.trim(),
        grade: form.grade,
        provinceCode: form.provinceCode,
        targetExamYear: form.targetExamYear,
      })
      : await loginStudent(form.studentId.trim(), form.phone.trim(), form.verificationCode.trim());
    emit("login", { session, remember: true });
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "账号服务暂时不可用";
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <main class="login-page student-theme">
    <section class="login-story">
      <button class="student-role-back" type="button" @click="emit('back')"><ArrowLeft :size="16" />重新选择身份</button>
      <div class="login-brand">
        <WenluBrandMark class="login-brand-mark" :size="30" />
        <span><strong>问鹿</strong><small>AI 多智能体学习中心</small></span>
      </div>

      <div class="story-content">
        <span class="eyebrow light"><Sparkles :size="15" /> 全国新课标Ⅰ卷学习助手</span>
        <h1>让每一次努力，<br />都有清晰的方向。</h1>
        <p>学习规划、作业辅导与学情诊断 Agent 协同工作，所有学习记录都与个人账号绑定并安全保存。</p>
        <div class="story-features">
          <article><BrainCircuit :size="22" /><span><strong>三 Agent 协同</strong><small>规划、辅导、诊断形成学习闭环</small></span></article>
          <article><BookOpenCheck :size="22" /><span><strong>学习记录持久化</strong><small>答题、用时、得分和知识点写入 MySQL</small></span></article>
          <article><ShieldCheck :size="22" /><span><strong>短信安全验证</strong><small>学号与已绑定手机号共同验证身份</small></span></article>
        </div>
      </div>

      <p class="story-foot">AI Education · MySQL 持久化学习档案</p>
    </section>

    <section class="login-form-wrap">
      <form class="login-card" @submit.prevent="submit">
        <div class="login-heading">
          <WenluBrandMark class="mobile-logo" :size="30" />
          <h2>{{ mode === 'login' ? '登录学习空间' : '创建学生账号' }}</h2>
          <p>{{ mode === 'login' ? '使用学号、手机号和短信验证码继续学习。' : '验证手机号后创建独立学生档案。' }}</p>
        </div>

        <div class="auth-tabs" role="tablist">
          <button type="button" :class="{ active: mode === 'login' }" @click="switchMode('login')"><KeyRound :size="16" />账号登录</button>
          <button type="button" :class="{ active: mode === 'register' }" @click="switchMode('register')"><UserPlus :size="16" />新生注册</button>
        </div>

        <div class="login-fields">
          <label v-if="mode === 'register'">
            <span>学生姓名</span>
            <div class="input-shell"><UserRound :size="18" /><input v-model="form.studentName" autocomplete="name" placeholder="请输入学生真实姓名" /></div>
            <small v-if="submitted && form.studentName.trim().length < 2" class="field-error">请填写至少 2 个字的姓名</small>
          </label>

          <label>
            <span>学号</span>
            <div class="input-shell"><UserRound :size="18" /><input v-model="form.studentId" autocomplete="username" placeholder="4—64 位字母、数字、点、横线或下划线" /></div>
            <small v-if="submitted && !/^[A-Za-z0-9_.-]{4,64}$/.test(form.studentId.trim())" class="field-error">账号格式不正确</small>
          </label>

          <label>
            <span>手机号</span>
            <div class="input-shell"><Smartphone :size="18" /><input v-model="form.phone" type="tel" inputmode="numeric" autocomplete="tel" maxlength="11" placeholder="请输入中国大陆手机号" /></div>
            <small v-if="submitted && !/^1[3-9]\d{9}$/.test(form.phone.trim())" class="field-error">手机号格式不正确</small>
          </label>

          <label>
            <span>短信验证码</span>
            <div class="input-shell verification-shell"><MessageSquareText :size="18" /><input v-model="form.verificationCode" inputmode="numeric" autocomplete="one-time-code" maxlength="8" placeholder="请输入验证码" /><button type="button" :disabled="sendingCode || countdown > 0" @click="sendCode">{{ countdown > 0 ? countdown + ' 秒' : sendingCode ? '发送中' : '获取验证码' }}</button></div>
          </label>

          <template v-if="mode === 'register'">
            <div class="two-fields">
              <label>
                <span>当前年级</span>
                <div class="input-shell"><GraduationCap :size="18" /><select v-model="form.grade"><option value="grade_10">高一</option><option value="grade_11">高二</option><option value="grade_12">高三</option></select></div>
              </label>
              <label>
                <span>目标高考年份</span>
                <div class="input-shell"><select v-model.number="form.targetExamYear"><option v-for="year in [2027, 2028, 2029, 2030]" :key="year" :value="year">{{ year }} 年</option></select></div>
              </label>
            </div>

            <label>
              <span>所在地区（全国新课标Ⅰ卷范围）</span>
              <div class="input-shell"><MapPin :size="18" /><select v-model="form.provinceCode"><option v-for="province in provinceRoutes" :key="province.code" :value="province.code">{{ province.name }}省 · {{ province.exam_mode }}</option></select></div>
            </label>
          </template>
        </div>

        <div v-if="error" class="auth-error">{{ error }}</div>

        <div class="register-space" />

        <button class="login-submit" type="submit" :disabled="submitting">
          <LoaderCircle v-if="submitting" class="spin" :size="19" />
          <template v-else>{{ mode === 'login' ? '登录学习空间' : '注册并进入学习空间' }} <ArrowRight :size="19" /></template>
        </button>
        <p class="login-note"><ShieldCheck :size="15" /> 不保存登录密码；同一手机号可绑定多个独立学号，学习数据按学号分别保存。</p>
      </form>
    </section>
  </main>
</template>

<style scoped>
.verification-shell button{flex:0 0 auto;padding:7px 10px;color:#176e56;border:0;border-left:1px solid #dbe8e3;background:transparent;font-size:9px;font-weight:800;white-space:nowrap}.verification-shell button:disabled{color:#9aa9a4;cursor:not-allowed}
</style>
