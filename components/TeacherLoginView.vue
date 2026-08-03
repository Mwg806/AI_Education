<script setup lang="ts">
import {
  ArrowLeft, ArrowRight, Check, GraduationCap, KeyRound, LoaderCircle,
  LockKeyhole, School, ShieldCheck, UserPlus, UserRound,
} from "@lucide/vue";
import { computed, reactive, ref } from "vue";

import { loginTeacher, registerTeacher } from "@/lib/auth-client";
import { subjectLabels } from "@/lib/curriculum-catalog";
import type { AuthSession, SubjectKey } from "@/lib/types";

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
  teacherName: "",
  teacherId: "",
  schoolName: "",
  subject: "mathematics" as SubjectKey,
  password: "",
  passwordConfirmation: "",
});
const subjects = Object.entries(subjectLabels) as Array<[SubjectKey, string]>;

const valid = computed(() => {
  const accountValid = /^[A-Za-z0-9_.-]{4,64}$/.test(form.teacherId.trim());
  if (mode.value === "login") return accountValid && Boolean(form.password);
  return accountValid
    && form.teacherName.trim().length >= 2
    && form.schoolName.trim().length >= 2
    && form.password.length >= 8
    && form.password === form.passwordConfirmation;
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
      ? await registerTeacher({
        teacherId: form.teacherId.trim(),
        password: form.password,
        passwordConfirmation: form.passwordConfirmation,
        teacherName: form.teacherName.trim(),
        schoolName: form.schoolName.trim(),
        subject: form.subject,
      })
      : await loginTeacher(form.teacherId.trim(), form.password, remember.value);
    emit("login", { session, remember: mode.value === "register" || remember.value });
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "教师账号服务暂时不可用";
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <main class="teacher-auth-page">
    <section class="teacher-auth-story">
      <button class="back-role" @click="emit('back')"><ArrowLeft :size="17" />重新选择身份</button>
      <div class="teacher-brand"><span><GraduationCap :size="26" /></span><div><strong>知途教师平台</strong><small>TEACHER INTELLIGENCE HUB</small></div></div>
      <div class="teacher-story-copy"><small>CLASSROOM · EVIDENCE · GROWTH</small><h1>看见每位学生，<br />真实发生的成长。</h1><p>班级、规划、诊断和通知汇聚在一处，让教学决策有证据，也保留温度。</p><div><article><strong>班级码连接</strong><span>学生自主加入教师创建的班级</span></article><article><strong>学情一览</strong><span>规划目标、诊断结论与考试表现</span></article><article><strong>教学发布</strong><span>诊断卷、作业与放假通知实时送达</span></article></div></div>
      <footer><ShieldCheck :size="16" />仅展示已加入本人班级的学生数据</footer>
    </section>

    <section class="teacher-auth-form">
      <form @submit.prevent="submit">
        <div class="teacher-login-heading"><span><School :size="23" /></span><div><h2>{{ mode === 'login' ? '教师账号登录' : '创建教师账号' }}</h2><p>{{ mode === 'login' ? '进入你的班级与教学工作台。' : '注册后即可创建班级并生成班级码。' }}</p></div></div>
        <div class="teacher-auth-tabs"><button type="button" :class="{active:mode==='login'}" @click="switchMode('login')"><KeyRound :size="15" />教师登录</button><button type="button" :class="{active:mode==='register'}" @click="switchMode('register')"><UserPlus :size="15" />教师注册</button></div>
        <div class="teacher-fields">
          <label v-if="mode==='register'"><span>教师姓名</span><div><UserRound :size="17" /><input v-model="form.teacherName" placeholder="请输入教师姓名" /></div></label>
          <label v-if="mode==='register'"><span>学校名称</span><div><School :size="17" /><input v-model="form.schoolName" placeholder="请输入学校全称" /></div></label>
          <label v-if="mode==='register'"><span>主要任教学科</span><div><select v-model="form.subject"><option v-for="[key,label] in subjects" :key="key" :value="key">{{ label }}</option></select></div></label>
          <label><span>教师账号</span><div><UserRound :size="17" /><input v-model="form.teacherId" autocomplete="username" placeholder="4—64 位字母、数字或常用符号" /></div><small v-if="submitted&&!/^[A-Za-z0-9_.-]{4,64}$/.test(form.teacherId.trim())">教师账号格式不正确</small></label>
          <label><span>登录密码</span><div><LockKeyhole :size="17" /><input v-model="form.password" type="password" :autocomplete="mode==='login'?'current-password':'new-password'" placeholder="请输入密码" /></div></label>
          <label v-if="mode==='register'"><span>确认密码</span><div><LockKeyhole :size="17" /><input v-model="form.passwordConfirmation" type="password" autocomplete="new-password" placeholder="请再次输入密码" /></div><small v-if="submitted&&form.password!==form.passwordConfirmation">两次输入的密码不一致</small></label>
        </div>
        <p v-if="error" class="teacher-auth-error">{{ error }}</p>
        <label v-if="mode==='login'" class="teacher-remember"><input v-model="remember" type="checkbox" /><i><Check :size="12" /></i><span>在这台设备保持登录</span></label>
        <button class="teacher-login-submit" :disabled="submitting"><LoaderCircle v-if="submitting" class="spin" :size="18" /><template v-else>{{ mode==='login'?'进入教师工作台':'注册并创建班级' }}<ArrowRight :size="18" /></template></button>
      </form>
    </section>
  </main>
</template>

<style scoped>
.teacher-auth-page{display:grid;min-height:100vh;grid-template-columns:48% 52%;background:#fff}.teacher-auth-story{display:flex;min-height:100vh;flex-direction:column;padding:34px 5vw;color:#fff;background:radial-gradient(circle at 15% 20%,rgba(130,232,192,.22),transparent 32%),linear-gradient(145deg,#0d513f,#137c5d 62%,#22a273)}.back-role{display:inline-flex;width:max-content;align-items:center;gap:6px;padding:8px 11px;color:#d9f5e9;border:1px solid rgba(255,255,255,.2);background:rgba(255,255,255,.06);border-radius:8px;font-size:9px}.teacher-brand{display:flex;align-items:center;gap:11px;margin-top:30px}.teacher-brand>span{display:grid;width:43px;height:43px;place-items:center;background:rgba(255,255,255,.13);border-radius:12px}.teacher-brand>div{display:grid;gap:4px}.teacher-brand strong{font-size:16px}.teacher-brand small{color:#bfe8d8;font-size:7px;letter-spacing:.14em}.teacher-story-copy{margin:auto 0;max-width:650px}.teacher-story-copy>small{color:#9edac4;font-size:8px;font-weight:850;letter-spacing:.18em}.teacher-story-copy h1{margin:17px 0 13px;font-size:clamp(35px,4vw,58px);line-height:1.22;letter-spacing:-.055em}.teacher-story-copy>p{max-width:580px;color:#c7e9dc;font-size:11px;line-height:1.9}.teacher-story-copy>div{display:grid;grid-template-columns:repeat(3,1fr);gap:9px;margin-top:32px}.teacher-story-copy article{display:grid;gap:7px;padding:15px;border:1px solid rgba(255,255,255,.12);background:rgba(255,255,255,.07);border-radius:11px}.teacher-story-copy article strong{font-size:10px}.teacher-story-copy article span{color:#bde0d3;font-size:8px;line-height:1.6}.teacher-auth-story footer{display:flex;align-items:center;gap:7px;color:#b7ddcf;font-size:8px}.teacher-auth-form{display:grid;place-items:center;padding:35px}.teacher-auth-form form{width:min(100%,480px);padding:38px;border:1px solid #e1ebe7;background:#fff;border-radius:20px;box-shadow:0 20px 55px rgba(21,84,65,.09)}.teacher-login-heading{display:flex;align-items:center;gap:12px}.teacher-login-heading>span{display:grid;width:44px;height:44px;place-items:center;color:#168363;background:#e6f5ef;border-radius:12px}.teacher-login-heading h2{margin:0;color:#163b31;font-size:23px}.teacher-login-heading p{margin:6px 0 0;color:#7c918b;font-size:9px}.teacher-auth-tabs{display:grid;grid-template-columns:1fr 1fr;gap:7px;margin:25px 0 20px;padding:5px;background:#f1f7f4;border-radius:10px}.teacher-auth-tabs button{display:flex;height:39px;align-items:center;justify-content:center;gap:6px;color:#708780;border:0;background:transparent;border-radius:7px;font-size:9px}.teacher-auth-tabs button.active{color:#147457;background:#fff;box-shadow:0 4px 12px rgba(25,95,73,.09)}.teacher-fields{display:grid;gap:13px}.teacher-fields label{display:grid;gap:7px}.teacher-fields label>span{color:#355b50;font-size:9px;font-weight:750}.teacher-fields label>div{display:flex;height:44px;align-items:center;gap:8px;padding:0 12px;color:#6f8d84;border:1px solid #d8e6e1;background:#fbfdfc;border-radius:9px}.teacher-fields input,.teacher-fields select{width:100%;height:100%;color:#24483e;border:0;outline:0;background:transparent;font:inherit;font-size:10px}.teacher-fields label>small{color:#ba4b4b;font-size:8px}.teacher-auth-error{padding:10px;color:#a63d3d;background:#fff0ef;border-radius:8px;font-size:9px}.teacher-remember{display:flex;align-items:center;gap:7px;margin:15px 0;color:#70857f;font-size:9px}.teacher-remember input{display:none}.teacher-remember i{display:grid;width:17px;height:17px;place-items:center;color:#fff;border:1px solid #b8cfc7;border-radius:5px}.teacher-remember input:checked+i{border-color:#168363;background:#168363}.teacher-login-submit{display:flex;width:100%;height:46px;align-items:center;justify-content:center;gap:7px;color:#fff;border:0;background:linear-gradient(135deg,#147457,#1a9a72);border-radius:10px;font-size:10px;font-weight:800;box-shadow:0 10px 24px rgba(22,131,99,.2)}@media(max-width:850px){.teacher-auth-page{display:block;background:#f4faf7}.teacher-auth-story{min-height:250px;padding:25px}.teacher-story-copy{margin:45px 0 25px}.teacher-story-copy h1{font-size:35px}.teacher-story-copy>div,.teacher-auth-story footer{display:none}.teacher-auth-form{margin-top:-25px;padding:18px}.teacher-auth-form form{padding:27px}}
</style>
