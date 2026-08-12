<script setup lang="ts">
import {
  ArrowLeft, ArrowRight, GraduationCap, KeyRound, LoaderCircle,
  MessageSquareText, School, ShieldCheck, Smartphone, UserPlus, UserRound,
} from "@lucide/vue";
import { onBeforeUnmount, reactive, ref } from "vue";

import { loginTeacher, registerTeacher, sendVerificationCode } from "@/lib/auth-client";
import { subjectLabels } from "@/lib/curriculum-catalog";
import type { AuthSession, SubjectKey } from "@/lib/types";

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
  if (!accountValid) return "教师账号需为 4—64 位字母、数字、点、下划线或短横线";
  if (!/^1[3-9]\d{9}$/.test(form.phone.trim())) return "请输入正确的中国大陆手机号";
  if (!/^\d{4,8}$/.test(form.verificationCode.trim())) return "请输入短信验证码";
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
    const result = await sendVerificationCode(form.phone.trim(), mode.value, "teacher");
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
    const session = action === "register"
      ? await registerTeacher({
        teacherId: form.teacherId.trim(),
        phone: form.phone.trim(),
        verificationCode: form.verificationCode.trim(),
        teacherName: form.teacherName.trim(),
        schoolName: form.schoolName.trim(),
        subject: form.subject,
      })
      : await loginTeacher(form.teacherId.trim(), form.phone.trim(), form.verificationCode.trim());
    emit("login", { session, remember: true });
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
      <form @submit.prevent="submit(mode)">
        <div class="teacher-login-heading"><span><School :size="23" /></span><div><h2>{{ mode === 'login' ? '教师账号登录' : '创建教师账号' }}</h2><p>{{ mode === 'login' ? '使用工号、手机号和验证码进入工作台。' : '验证手机号后创建教师账号。' }}</p></div></div>
        <div class="teacher-auth-tabs"><button type="button" :class="{active:mode==='login'}" @click="switchMode('login')"><KeyRound :size="15" />教师登录</button><button type="button" :class="{active:mode==='register'}" @click="switchMode('register')"><UserPlus :size="15" />教师注册</button></div>
        <div class="teacher-fields">
          <label v-if="mode==='register'"><span>教师姓名</span><div><UserRound :size="17" /><input v-model="form.teacherName" placeholder="请输入教师姓名" /></div></label>
          <label v-if="mode==='register'"><span>学校名称</span><div><School :size="17" /><input v-model="form.schoolName" placeholder="请输入学校全称" /></div></label>
          <label v-if="mode==='register'"><span>主要任教学科</span><div><select v-model="form.subject"><option v-for="[key,label] in subjects" :key="key" :value="key">{{ label }}</option></select></div></label>
          <label><span>教师账号 / 工号</span><div><UserRound :size="17" /><input v-model="form.teacherId" autocomplete="username" placeholder="请输入唯一教师账号或工号" /></div><small v-if="submitted&&!/^[A-Za-z0-9_.-]{4,64}$/.test(form.teacherId.trim())">教师账号格式不正确</small></label>
          <label><span>手机号</span><div><Smartphone :size="17" /><input v-model="form.phone" type="tel" inputmode="numeric" autocomplete="tel" maxlength="11" placeholder="请输入中国大陆手机号" /></div></label>
          <label><span>短信验证码</span><div class="teacher-code-field"><MessageSquareText :size="17" /><input v-model="form.verificationCode" inputmode="numeric" autocomplete="one-time-code" maxlength="8" placeholder="请输入验证码" /><button type="button" :disabled="sendingCode||countdown>0" @click="sendCode">{{ countdown>0 ? countdown+' 秒' : sendingCode ? '发送中' : '获取验证码' }}</button></div></label>
        </div>
        <p v-if="error" class="teacher-auth-error">{{ error }}</p>
        <button v-if="mode==='login'" type="button" class="teacher-login-submit" :disabled="submitting" @click="submit('login')"><LoaderCircle v-if="submitting" class="spin" :size="18" /><template v-else>进入教师工作台<ArrowRight :size="18" /></template></button>
        <button v-else type="button" class="teacher-login-submit" :disabled="submitting" @click="submit('register')"><LoaderCircle v-if="submitting" class="spin" :size="18" /><template v-else>注册并创建班级<ArrowRight :size="18" /></template></button>
      </form>
    </section>
  </main>
</template>

<style scoped>
.teacher-auth-page{display:grid;min-height:100vh;grid-template-columns:48% 52%;background:#fff}.teacher-auth-story{display:flex;min-height:100vh;flex-direction:column;padding:34px 5vw;color:#fff;background:radial-gradient(circle at 15% 20%,rgba(130,232,192,.22),transparent 32%),linear-gradient(145deg,#0d513f,#137c5d 62%,#22a273)}.back-role{display:inline-flex;width:max-content;align-items:center;gap:6px;padding:8px 11px;color:#d9f5e9;border:1px solid rgba(255,255,255,.2);background:rgba(255,255,255,.06);border-radius:8px;font-size:9px}.teacher-brand{display:flex;align-items:center;gap:11px;margin-top:30px}.teacher-brand>span{display:grid;width:43px;height:43px;place-items:center;background:rgba(255,255,255,.13);border-radius:12px}.teacher-brand>div{display:grid;gap:4px}.teacher-brand strong{font-size:16px}.teacher-brand small{color:#bfe8d8;font-size:7px;letter-spacing:.14em}.teacher-story-copy{margin:auto 0;max-width:650px}.teacher-story-copy>small{color:#9edac4;font-size:8px;font-weight:850;letter-spacing:.18em}.teacher-story-copy h1{margin:17px 0 13px;font-size:clamp(35px,4vw,58px);line-height:1.22;letter-spacing:-.055em}.teacher-story-copy>p{max-width:580px;color:#c7e9dc;font-size:11px;line-height:1.9}.teacher-story-copy>div{display:grid;grid-template-columns:repeat(3,1fr);gap:9px;margin-top:32px}.teacher-story-copy article{display:grid;gap:7px;padding:15px;border:1px solid rgba(255,255,255,.12);background:rgba(255,255,255,.07);border-radius:11px}.teacher-story-copy article strong{font-size:10px}.teacher-story-copy article span{color:#bde0d3;font-size:8px;line-height:1.6}.teacher-auth-story footer{display:flex;align-items:center;gap:7px;color:#b7ddcf;font-size:8px}.teacher-auth-form{display:grid;place-items:center;padding:35px}.teacher-auth-form form{width:min(100%,480px);padding:38px;border:1px solid #e1ebe7;background:#fff;border-radius:20px;box-shadow:0 20px 55px rgba(21,84,65,.09)}.teacher-login-heading{display:flex;align-items:center;gap:12px}.teacher-login-heading>span{display:grid;width:44px;height:44px;place-items:center;color:#168363;background:#e6f5ef;border-radius:12px}.teacher-login-heading h2{margin:0;color:#163b31;font-size:23px}.teacher-login-heading p{margin:6px 0 0;color:#7c918b;font-size:9px}.teacher-auth-tabs{display:grid;grid-template-columns:1fr 1fr;gap:7px;margin:25px 0 20px;padding:5px;background:#f1f7f4;border-radius:10px}.teacher-auth-tabs button{display:flex;height:39px;align-items:center;justify-content:center;gap:6px;color:#708780;border:0;background:transparent;border-radius:7px;font-size:9px}.teacher-auth-tabs button.active{color:#147457;background:#fff;box-shadow:0 4px 12px rgba(25,95,73,.09)}.teacher-fields{display:grid;gap:13px}.teacher-fields label{display:grid;gap:7px}.teacher-fields label>span{color:#355b50;font-size:9px;font-weight:750}.teacher-fields label>div{display:flex;height:44px;align-items:center;gap:8px;padding:0 12px;color:#6f8d84;border:1px solid #d8e6e1;background:#fbfdfc;border-radius:9px}.teacher-fields input,.teacher-fields select{width:100%;height:100%;color:#24483e;border:0;outline:0;background:transparent;font:inherit;font-size:10px}.teacher-fields label>small{color:#ba4b4b;font-size:8px}.teacher-auth-error{padding:10px;color:#a63d3d;background:#fff0ef;border-radius:8px;font-size:9px}.teacher-remember{display:flex;align-items:center;gap:7px;margin:15px 0;color:#70857f;font-size:9px}.teacher-remember input{display:none}.teacher-remember i{display:grid;width:17px;height:17px;place-items:center;color:#fff;border:1px solid #b8cfc7;border-radius:5px}.teacher-remember input:checked+i{border-color:#168363;background:#168363}.teacher-login-submit{display:flex;width:100%;height:46px;align-items:center;justify-content:center;gap:7px;color:#fff;border:0;background:linear-gradient(135deg,#147457,#1a9a72);border-radius:10px;font-size:10px;font-weight:800;box-shadow:0 10px 24px rgba(22,131,99,.2)}@media(max-width:850px){.teacher-auth-page{display:block;background:#f4faf7}.teacher-auth-story{min-height:250px;padding:25px}.teacher-story-copy{margin:45px 0 25px}.teacher-story-copy h1{font-size:35px}.teacher-story-copy>div,.teacher-auth-story footer{display:none}.teacher-auth-form{margin-top:-25px;padding:18px}.teacher-auth-form form{padding:27px}}
.teacher-code-field button{flex:0 0 auto;padding:6px 9px;color:#147457;border:0;border-left:1px solid #d8e6e1;background:transparent;font-size:9px;font-weight:800;white-space:nowrap}.teacher-code-field button:disabled{color:#9cafaa;cursor:not-allowed}
</style>
