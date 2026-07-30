<script setup lang="ts">
import {
  ArrowRight,
  BookOpenCheck,
  BrainCircuit,
  Check,
  GraduationCap,
  LockKeyhole,
  MapPin,
  ShieldCheck,
  Sparkles,
  UserRound,
} from "@lucide/vue";
import { computed, reactive, ref } from "vue";

import { provinceRoutes } from "@/lib/curriculum-catalog";
import type { StudentLoginProfile } from "@/lib/types";

const emit = defineEmits<{
  login: [payload: { profile: StudentLoginProfile; remember: boolean }];
}>();

const form = reactive<StudentLoginProfile>({
  studentName: "",
  studentId: "student_10001",
  grade: "grade_11",
  provinceCode: "43",
  targetExamYear: 2027,
});
const remember = ref(true);
const submitted = ref(false);

const valid = computed(() => (
  form.studentName.trim().length >= 2
  && form.studentId.trim().length >= 4
  && Boolean(form.grade)
  && Boolean(form.provinceCode)
));

function submit() {
  submitted.value = true;
  if (!valid.value) return;
  emit("login", {
    profile: { ...form, studentName: form.studentName.trim(), studentId: form.studentId.trim() },
    remember: remember.value,
  });
}
</script>

<template>
  <main class="login-page">
    <section class="login-story">
      <div class="login-brand">
        <span class="brand-mark"><GraduationCap :size="27" /></span>
        <span><strong>知途 AI</strong><small>个性化学习规划中心</small></span>
      </div>

      <div class="story-content">
        <span class="eyebrow light"><Sparkles :size="15" /> 全国新课标Ⅰ卷学习助手</span>
        <h1>让每一次努力，<br />都有清晰的方向。</h1>
        <p>依据地区考试政策、学校实际教材和真实学习证据，生成可执行、可调整、可追溯的个人学习计划。</p>
        <div class="story-features">
          <article><BrainCircuit :size="22" /><span><strong>智能诊断</strong><small>从目标和掌握度识别优先缺口</small></span></article>
          <article><BookOpenCheck :size="22" /><span><strong>教材可追溯</strong><small>329 册教材、1,336 个章节选项</small></span></article>
          <article><ShieldCheck :size="22" /><span><strong>证据有边界</strong><small>待复核内容明确标注，不虚构章节</small></span></article>
        </div>
      </div>

      <p class="story-foot">AI Education · LangGraph 多智能体扩展架构</p>
    </section>

    <section class="login-form-wrap">
      <form class="login-card" @submit.prevent="submit">
        <div class="login-heading">
          <span class="mobile-logo"><GraduationCap :size="23" /></span>
          <h2>登录学习空间</h2>
          <p>先完善基础资料，系统会自动带入规划工作台。</p>
        </div>

        <div class="login-fields">
          <label>
            <span>学生姓名</span>
            <div class="input-shell"><UserRound :size="18" /><input v-model="form.studentName" autocomplete="name" placeholder="请输入真实姓名" /></div>
            <small v-if="submitted && form.studentName.trim().length < 2" class="field-error">请填写至少 2 个字的姓名</small>
          </label>
          <label>
            <span>学号 / 学习账号</span>
            <div class="input-shell"><LockKeyhole :size="18" /><input v-model="form.studentId" autocomplete="username" placeholder="例如 student_10001" /></div>
            <small v-if="submitted && form.studentId.trim().length < 4" class="field-error">学习账号至少需要 4 个字符</small>
          </label>

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
        </div>

        <label class="remember-row">
          <input v-model="remember" type="checkbox" />
          <span class="check-box"><Check :size="13" /></span>
          <span>在这台设备记住我的学习资料</span>
        </label>

        <button class="login-submit" type="submit">进入学习空间 <ArrowRight :size="19" /></button>
        <p class="login-note"><ShieldCheck :size="15" /> 当前为学习档案入口，资料仅保存在本浏览器；正式账号鉴权需接入学校用户系统。</p>
      </form>
    </section>
  </main>
</template>
