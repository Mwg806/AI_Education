<script setup lang="ts">
import {
  ArrowLeft,
  ArrowRight,
  BookOpenCheck,
  BrainCircuit,
  Check,
  GraduationCap,
  KeyRound,
  LoaderCircle,
  LockKeyhole,
  MapPin,
  ShieldCheck,
  Sparkles,
  UserPlus,
  UserRound,
} from "@lucide/vue";
import { computed, reactive, ref } from "vue";

import { loginStudent, registerStudent } from "@/lib/auth-client";
import { provinceRoutes } from "@/lib/curriculum-catalog";
import type { AuthSession, StudentLoginProfile } from "@/lib/types";

const emit = defineEmits<{
  login: [payload: { session: AuthSession; remember: boolean }];
  back: [];
}>();

const mode = ref<"login" | "register">("login");
const remember = ref(true);
const submitted = ref(false);
const submitting = ref(false);
const error = ref("");
const form = reactive({
  studentName: "",
  studentId: "",
  password: "",
  passwordConfirmation: "",
  grade: "grade_11" as StudentLoginProfile["grade"],
  provinceCode: "43",
  targetExamYear: 2027,
});

const valid = computed(() => {
  const accountValid = /^[A-Za-z0-9_.-]{4,64}$/.test(form.studentId.trim());
  if (mode.value === "login") return accountValid && form.password.length > 0;
  return accountValid
    && form.studentName.trim().length >= 2
    && form.password.length >= 8
    && form.password === form.passwordConfirmation
    && Boolean(form.grade)
    && Boolean(form.provinceCode);
});

function switchMode(next: "login" | "register") {
  mode.value = next;
  submitted.value = false;
  error.value = "";
  form.password = "";
  form.passwordConfirmation = "";
}

async function submit() {
  submitted.value = true;
  error.value = "";
  if (!valid.value || submitting.value) return;
  submitting.value = true;
  try {
    const session = mode.value === "register"
      ? await registerStudent({
        studentId: form.studentId.trim(),
        password: form.password,
        passwordConfirmation: form.passwordConfirmation,
        studentName: form.studentName.trim(),
        grade: form.grade,
        provinceCode: form.provinceCode,
        targetExamYear: form.targetExamYear,
      })
      : await loginStudent(form.studentId.trim(), form.password, remember.value);
    emit("login", { session, remember: mode.value === "register" ? true : remember.value });
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "账号服务暂时不可用";
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <main class="login-page">
    <section class="login-story">
      <button class="student-role-back" type="button" @click="emit('back')"><ArrowLeft :size="16" />重新选择身份</button>
      <div class="login-brand">
        <span class="brand-mark"><GraduationCap :size="27" /></span>
        <span><strong>知途 AI</strong><small>三智能体学习中心</small></span>
      </div>

      <div class="story-content">
        <span class="eyebrow light"><Sparkles :size="15" /> 全国新课标Ⅰ卷学习助手</span>
        <h1>让每一次努力，<br />都有清晰的方向。</h1>
        <p>学习规划、作业辅导与学情诊断 Agent 协同工作，所有学习记录都与个人账号绑定并安全保存。</p>
        <div class="story-features">
          <article><BrainCircuit :size="22" /><span><strong>三 Agent 协同</strong><small>规划、辅导、诊断形成学习闭环</small></span></article>
          <article><BookOpenCheck :size="22" /><span><strong>学习记录持久化</strong><small>答题、用时、得分和知识点写入 MySQL</small></span></article>
          <article><ShieldCheck :size="22" /><span><strong>真实账号保护</strong><small>密码不可逆加密，服务端会话验证</small></span></article>
        </div>
      </div>

      <p class="story-foot">AI Education · MySQL 持久化学习档案</p>
    </section>

    <section class="login-form-wrap">
      <form class="login-card" @submit.prevent="submit">
        <div class="login-heading">
          <span class="mobile-logo"><GraduationCap :size="23" /></span>
          <h2>{{ mode === 'login' ? '登录学习空间' : '创建学生账号' }}</h2>
          <p>{{ mode === 'login' ? '使用已注册的学习账号和密码继续学习。' : '注册后，学习资料和诊断记录将保存到 MySQL。' }}</p>
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
            <span>学习账号</span>
            <div class="input-shell"><UserRound :size="18" /><input v-model="form.studentId" autocomplete="username" placeholder="4—64 位字母、数字、点、横线或下划线" /></div>
            <small v-if="submitted && !/^[A-Za-z0-9_.-]{4,64}$/.test(form.studentId.trim())" class="field-error">账号格式不正确</small>
          </label>

          <label>
            <span>登录密码</span>
            <div class="input-shell"><LockKeyhole :size="18" /><input v-model="form.password" type="password" :autocomplete="mode === 'login' ? 'current-password' : 'new-password'" :placeholder="mode === 'login' ? '请输入登录密码' : '至少 8 个字符'" /></div>
            <small v-if="submitted && mode === 'register' && form.password.length < 8" class="field-error">密码至少需要 8 个字符</small>
          </label>

          <label v-if="mode === 'register'">
            <span>确认密码</span>
            <div class="input-shell"><LockKeyhole :size="18" /><input v-model="form.passwordConfirmation" type="password" autocomplete="new-password" placeholder="请再次输入密码" /></div>
            <small v-if="submitted && form.password !== form.passwordConfirmation" class="field-error">两次输入的密码不一致</small>
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

        <label v-if="mode === 'login'" class="remember-row">
          <input v-model="remember" type="checkbox" />
          <span class="check-box"><Check :size="13" /></span>
          <span>在这台设备保持登录</span>
        </label>
        <div v-else class="register-space" />

        <button class="login-submit" type="submit" :disabled="submitting">
          <LoaderCircle v-if="submitting" class="spin" :size="19" />
          <template v-else>{{ mode === 'login' ? '登录学习空间' : '注册并进入学习空间' }} <ArrowRight :size="19" /></template>
        </button>
        <p class="login-note"><ShieldCheck :size="15" /> 密码只以不可逆哈希保存；账号资料、诊断记录和逐题学习数据存储在已配置的 MySQL 数据库中。</p>
      </form>
    </section>
  </main>
</template>
