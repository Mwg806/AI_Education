<script setup lang="ts">
import {
  ArrowRight, BookOpenCheck, School, ShieldCheck, UsersRound,
} from "@lucide/vue";
import WenluBrandMark from "@/components/WenluBrandMark.vue";

const emit = defineEmits<{
  select: [role: "student" | "teacher"];
}>();
</script>

<template>
  <main class="role-gateway student-theme">
    <div class="role-brand"><WenluBrandMark :size="44" /><strong>问鹿</strong><small>连接学生成长与教师教学</small></div>
    <section class="role-heading">
      <small>SELECT YOUR ROLE</small>
      <h1>请选择登录身份</h1>
      <p>学生和教师使用独立账号、独立工作台与权限范围。</p>
    </section>
    <section class="role-cards">
      <button class="student-role" @click="emit('select', 'student')">
        <span class="role-icon"><BookOpenCheck :size="32" /></span>
        <small>STUDENT PORTAL</small>
        <h2>我是学生</h2>
        <p>进入学习规划、作业辅导、学情诊断，并通过班级码接收教师通知。</p>
        <strong>进入学生登录 <ArrowRight :size="18" /></strong>
      </button>
      <button class="teacher-role" @click="emit('select', 'teacher')">
        <span class="role-icon"><UsersRound :size="32" /></span>
        <small>TEACHER PORTAL</small>
        <h2>我是教师</h2>
        <p>创建班级、查看学生学情和规划，发布诊断卷、作业与班级通知。</p>
        <strong>进入教师登录 <ArrowRight :size="18" /></strong>
      </button>
    </section>
    <footer><ShieldCheck :size="16" />角色权限由服务端会话校验，班级学习数据仅对所属教师开放。<span><School :size="15" /> 教学协同平台</span></footer>
  </main>
</template>

<style scoped>
.role-gateway{min-height:100vh;padding:34px clamp(22px,6vw,90px);color:#17324f;background:radial-gradient(circle at 15% 15%,#e8f1ff,transparent 30%),radial-gradient(circle at 88% 12%,#e2f7ee,transparent 31%),#f8fafc}.role-brand{display:flex;align-items:center;gap:10px}.role-brand>span{display:grid;width:42px;height:42px;place-items:center;color:#fff;background:linear-gradient(135deg,#155eef,#159477);border-radius:13px}.role-brand strong{font-size:18px}.role-brand small{padding-left:10px;color:#8090a2;border-left:1px solid #dbe3ec;font-size:10px}.role-heading{max-width:700px;margin:9vh auto 36px;text-align:center}.role-heading small{color:#4780ae;font-size:9px;font-weight:850;letter-spacing:.2em}.role-heading h1{margin:13px 0 10px;font-size:clamp(32px,5vw,54px);letter-spacing:-.055em}.role-heading p{margin:0;color:#708298;font-size:12px}.role-cards{display:grid;max-width:960px;margin:auto;grid-template-columns:1fr 1fr;gap:22px}.role-cards button{position:relative;min-height:330px;padding:36px;text-align:left;border:1px solid #dfe7f0;background:#fff;border-radius:22px;box-shadow:0 18px 45px rgba(32,58,87,.08);transition:.24s ease}.role-cards button:hover{transform:translateY(-6px);box-shadow:0 24px 55px rgba(32,58,87,.14)}.role-icon{display:grid;width:64px;height:64px;place-items:center;border-radius:18px}.student-role .role-icon{color:#155eef;background:#eaf2ff}.teacher-role .role-icon{color:#168363;background:#e4f6ee}.role-cards small{display:block;margin-top:25px;color:#7890a7;font-size:8px;font-weight:850;letter-spacing:.15em}.role-cards h2{margin:8px 0 11px;font-size:25px}.role-cards p{min-height:60px;margin:0;color:#718298;font-size:11px;line-height:1.8}.role-cards strong{display:inline-flex;align-items:center;gap:7px;margin-top:28px;font-size:11px}.student-role strong{color:#155eef}.teacher-role strong{color:#168363}.student-role:hover{border-color:#afcaff}.teacher-role:hover{border-color:#a9ddca}.role-gateway footer{display:flex;max-width:960px;align-items:center;gap:7px;margin:30px auto 0;color:#8291a3;font-size:9px}.role-gateway footer span{display:inline-flex;align-items:center;gap:5px;margin-left:auto}@media(max-width:700px){.role-gateway{padding:24px 18px}.role-brand small{display:none}.role-heading{margin:7vh auto 25px}.role-cards{grid-template-columns:1fr}.role-cards button{min-height:275px;padding:28px}.role-gateway footer span{display:none}}
</style>
