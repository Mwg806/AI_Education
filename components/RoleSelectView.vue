<script setup lang="ts">
import {
  ArrowRight,
  BookOpenCheck,
  BrainCircuit,
  ClipboardCheck,
  GraduationCap,
  School,
  ShieldCheck,
  Sparkles,
  UsersRound,
} from "@lucide/vue";

import WenluBrandMark from "@/components/WenluBrandMark.vue";

const emit = defineEmits<{
  select: [role: "student" | "teacher"];
}>();
</script>

<template>
  <main class="role-gateway student-theme">
    <div class="gateway-glow gateway-glow-violet" aria-hidden="true" />
    <div class="gateway-glow gateway-glow-green" aria-hidden="true" />
    <div class="gateway-stars" aria-hidden="true">
      <i /><i /><i /><i /><i /><i />
    </div>

    <section class="role-shell">
      <header class="role-topbar">
        <div class="role-brand">
          <WenluBrandMark class="role-brand-mark" :size="42" />
          <span>
            <strong>问鹿</strong>
            <small>智能学习成长平台</small>
          </span>
        </div>
        <div class="gateway-state">
          <i />
          学生 · 教师统一入口
        </div>
      </header>

      <section class="role-heading">
        <span class="heading-eyebrow">
          <Sparkles :size="15" />WELCOME TO WENLU
        </span>
        <h1>登录身份选择</h1>
        <p>选择你的身份，进入专属学习空间或教师协同工作台。</p>
      </section>

      <section class="role-cards" aria-label="请选择登录身份">
        <button
          class="role-card student-role"
          type="button"
          @click="emit('select', 'student')"
        >
          <span class="role-card-orbit" aria-hidden="true" />
          <span class="role-card-watermark" aria-hidden="true">
            <GraduationCap :size="154" :stroke-width="1.2" />
          </span>

          <span class="role-card-head">
            <span class="role-icon"><BookOpenCheck :size="29" /></span>
            <span class="role-number">01</span>
          </span>

          <span class="role-card-copy">
            <small>STUDENT PORTAL</small>
            <h2>我是学生</h2>
            <p>进入专属学习空间，让目标、规划和每一次进步都有迹可循。</p>
          </span>

          <span class="role-capabilities">
            <span><BrainCircuit :size="15" />多模型协同</span>
            <span><BookOpenCheck :size="15" />学习规划</span>
          </span>

          <strong class="role-action">
            进入学生登录
            <i><ArrowRight :size="18" /></i>
          </strong>
        </button>

        <button
          class="role-card teacher-role"
          type="button"
          @click="emit('select', 'teacher')"
        >
          <span class="role-card-orbit" aria-hidden="true" />
          <span class="role-card-watermark" aria-hidden="true">
            <School :size="154" :stroke-width="1.2" />
          </span>

          <span class="role-card-head">
            <span class="role-icon"><UsersRound :size="29" /></span>
            <span class="role-number">02</span>
          </span>

          <span class="role-card-copy">
            <small>TEACHER PORTAL</small>
            <h2>我是教师</h2>
            <p>进入教师协同工作台，用清晰学情连接备课、班级与学生成长。</p>
          </span>

          <span class="role-capabilities">
            <span><ClipboardCheck :size="15" />学情诊断</span>
            <span><UsersRound :size="15" />班级协同</span>
          </span>

          <strong class="role-action">
            进入教师登录
            <i><ArrowRight :size="18" /></i>
          </strong>
        </button>
      </section>

      <footer>
        <span>
          <ShieldCheck :size="16" />
          身份与权限由服务端安全校验
        </span>
        <small>问鹿 · 让学习与教学更有方向</small>
      </footer>
    </section>
  </main>
</template>

<style scoped>
.role-gateway {
  position: relative;
  display: grid;
  height: 100svh;
  place-items: center;
  overflow: hidden;
  padding: 24px;
  color: #2e2440;
  background:
    linear-gradient(
      125deg,
      rgba(42, 22, 87, 0.98),
      rgba(65, 42, 128, 0.92) 48%,
      rgba(8, 94, 71, 0.92)
    ),
    #39216f;
  isolation: isolate;
}

.gateway-glow {
  position: absolute;
  z-index: -1;
  pointer-events: none;
  border-radius: 50%;
  filter: blur(70px);
}
.gateway-glow-violet {
  top: -14rem;
  left: -10rem;
  width: 42rem;
  height: 42rem;
  background: rgba(181, 145, 255, 0.28);
}
.gateway-glow-green {
  right: -12rem;
  bottom: -16rem;
  width: 46rem;
  height: 46rem;
  background: rgba(93, 222, 169, 0.22);
}
.gateway-stars {
  position: absolute;
  z-index: -1;
  inset: 0;
  pointer-events: none;
}
.gateway-stars i {
  position: absolute;
  width: 5px;
  height: 5px;
  background: rgba(255, 255, 255, 0.68);
  border-radius: 50%;
  box-shadow: 0 0 14px rgba(255, 255, 255, 0.72);
  animation: star-pulse 3.8s ease-in-out infinite alternate;
}
.gateway-stars i:nth-child(1) {
  top: 14%;
  left: 8%;
}
.gateway-stars i:nth-child(2) {
  top: 25%;
  right: 11%;
  width: 3px;
  height: 3px;
  animation-delay: -1s;
}
.gateway-stars i:nth-child(3) {
  bottom: 18%;
  left: 13%;
  width: 4px;
  height: 4px;
  animation-delay: -2.1s;
}
.gateway-stars i:nth-child(4) {
  right: 7%;
  bottom: 32%;
  animation-delay: -0.6s;
}
.gateway-stars i:nth-child(5) {
  top: 8%;
  left: 54%;
  width: 3px;
  height: 3px;
  animation-delay: -2.7s;
}
.gateway-stars i:nth-child(6) {
  right: 30%;
  bottom: 8%;
  width: 4px;
  height: 4px;
  animation-delay: -1.5s;
}

.role-shell {
  display: grid;
  width: min(1180px, calc(100vw - 48px));
  height: calc(100svh - 48px);
  min-height: 0;
  grid-template-rows: auto auto 1fr auto;
  gap: 18px;
  padding: 26px 32px 20px;
  border: 1px solid rgba(255, 255, 255, 0.72);
  background: rgba(255, 255, 255, 0.96);
  border-radius: 32px;
  box-shadow: 0 38px 100px rgba(14, 5, 39, 0.4);
  backdrop-filter: blur(24px);
}

.role-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.role-brand {
  display: flex;
  align-items: center;
  gap: 12px;
}
.role-brand > span {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.role-brand strong {
  color: #4e2d61;
  font-size: 20px;
  letter-spacing: 0.08em;
}
.role-brand small {
  color: #8d7b9b;
  font-size: 10px;
  letter-spacing: 0.05em;
}
.gateway-state {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: #7e7089;
  font-size: 10px;
  font-weight: 700;
}
.gateway-state i {
  width: 7px;
  height: 7px;
  background: #26a978;
  border-radius: 50%;
  box-shadow: 0 0 0 5px rgba(38, 169, 120, 0.11);
}

.role-heading {
  max-width: 760px;
  margin: 0 auto;
  text-align: center;
}
.heading-eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  color: #7650ba;
  font-size: 10px;
  font-weight: 850;
  letter-spacing: 0.16em;
}
.role-heading h1 {
  margin: 10px 0 7px;
  color: #30203f;
  font-size: clamp(30px, 3.2vw, 43px);
  line-height: 1.16;
  letter-spacing: -0.05em;
}
.role-heading p {
  margin: 0;
  color: #8a7b94;
  font-size: 12px;
  line-height: 1.7;
}

.role-cards {
  display: grid;
  min-height: 0;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}
.role-card {
  position: relative;
  display: flex;
  min-width: 0;
  min-height: 0;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  overflow: hidden;
  padding: 26px 28px 24px;
  text-align: center;
  border: 1px solid transparent;
  border-radius: 24px;
  isolation: isolate;
  transition:
    transform 0.24s ease,
    box-shadow 0.24s ease,
    border-color 0.24s ease;
}
.student-role {
  color: #38215a;
  border-color: #e6dbf8;
  background:
    radial-gradient(
      circle at 92% 8%,
      rgba(198, 168, 255, 0.42),
      transparent 14rem
    ),
    linear-gradient(145deg, #fbf8ff, #eee5ff);
  box-shadow: 0 16px 38px rgba(91, 52, 151, 0.1);
}
.teacher-role {
  color: #16493b;
  border-color: #d4ece2;
  background:
    radial-gradient(
      circle at 92% 8%,
      rgba(111, 214, 172, 0.38),
      transparent 14rem
    ),
    linear-gradient(145deg, #f7fdfa, #def3e9);
  box-shadow: 0 16px 38px rgba(18, 105, 79, 0.1);
}
.role-card:hover {
  transform: translateY(-6px);
}
.student-role:hover {
  border-color: #cbb5ee;
  box-shadow: 0 24px 48px rgba(91, 52, 151, 0.18);
}
.teacher-role:hover {
  border-color: #9fd9c1;
  box-shadow: 0 24px 48px rgba(18, 105, 79, 0.18);
}
.role-card:focus-visible {
  outline: 3px solid rgba(255, 255, 255, 0.9);
  outline-offset: 4px;
}
.role-card-orbit {
  position: absolute;
  z-index: -1;
  right: -90px;
  bottom: -110px;
  width: 280px;
  height: 280px;
  border: 1px solid currentColor;
  border-radius: 50%;
  opacity: 0.1;
  box-shadow:
    0 0 0 36px currentColor,
    0 0 0 72px currentColor;
}
.role-card-watermark {
  position: absolute;
  z-index: -1;
  right: 18px;
  bottom: 60px;
  color: currentColor;
  opacity: 0.07;
  transform: rotate(-8deg);
  transition:
    opacity 0.24s ease,
    transform 0.24s ease;
}
.role-card:hover .role-card-watermark {
  opacity: 0.12;
  transform: translateY(-5px) rotate(-4deg);
}

.role-card-head {
  display: flex;
  width: auto;
  align-items: center;
  justify-content: center;
}
.role-icon {
  display: grid;
  width: 58px;
  height: 58px;
  place-items: center;
  color: #fff;
  border-radius: 17px;
  box-shadow: 0 12px 24px rgba(46, 28, 75, 0.16);
}
.student-role .role-icon {
  background: linear-gradient(145deg, #6843c8, #956fe5);
}
.teacher-role .role-icon {
  background: linear-gradient(145deg, #147457, #35aa7e);
}
.role-number {
  position: absolute;
  top: 24px;
  right: 26px;
  color: currentColor;
  font-size: 32px;
  font-weight: 850;
  letter-spacing: -0.05em;
  opacity: 0.14;
}

.role-card-copy {
  display: block;
  margin-top: 20px;
}
.role-card-copy small {
  display: block;
  color: currentColor;
  font-size: 9px;
  font-weight: 850;
  letter-spacing: 0.16em;
  opacity: 0.62;
}
.role-card-copy h2 {
  margin: 6px 0 9px;
  color: currentColor;
  font-size: 27px;
  letter-spacing: -0.035em;
}
.role-card-copy p {
  max-width: 390px;
  margin: 0 auto;
  color: currentColor;
  font-size: 13px;
  line-height: 1.8;
  opacity: 0.7;
}

.role-capabilities {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 14px;
  margin-top: 18px;
  color: currentColor;
}
.role-capabilities > span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 750;
  opacity: 0.82;
}

.role-action {
  display: flex;
  width: auto;
  align-items: center;
  justify-content: center;
  gap: 9px;
  margin-top: 22px;
  padding-top: 0;
  color: currentColor;
  font-size: 14px;
  font-weight: 800;
}
.role-action i {
  display: grid;
  width: 34px;
  height: 34px;
  place-items: center;
  color: #fff;
  background: currentColor;
  border-radius: 50%;
  transition: transform 0.22s ease;
}
.role-card:hover .role-action i {
  transform: translateX(4px);
}

.role-shell footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: #897b93;
}
.role-shell footer > span {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  font-size: 12px;
}
.role-shell footer svg {
  color: #6f54a4;
}
.role-shell footer small {
  font-size: 12px;
}

@keyframes star-pulse {
  from {
    opacity: 0.35;
    transform: scale(0.8);
  }
  to {
    opacity: 1;
    transform: scale(1.25);
  }
}

@media (max-width: 900px) {
  .role-gateway {
    overflow: auto;
    padding: 24px;
  }
  .role-shell {
    width: calc(100vw - 48px);
    height: calc(100svh - 48px);
    min-height: 0;
    padding: 26px;
  }
  .role-cards {
    gap: 14px;
  }
  .role-card {
    min-height: 350px;
    padding: 24px;
  }
}

@media (max-width: 700px) {
  .role-gateway {
    display: block;
    padding: 0;
    background: #f7f3fb;
  }
  .role-shell {
    width: 100%;
    height: auto;
    min-height: 100svh;
    gap: 22px;
    padding: 24px 18px 30px;
    border: 0;
    border-radius: 0;
    box-shadow: none;
  }
  .gateway-state {
    display: none;
  }
  .role-heading {
    padding-top: 12px;
  }
  .role-heading h1 {
    font-size: 31px;
  }
  .role-cards {
    grid-template-columns: 1fr;
  }
  .role-card {
    min-height: 315px;
  }
  .role-shell footer {
    justify-content: center;
  }
  .role-shell footer small {
    display: none;
  }
}

@media (max-width: 420px) {
  .role-card {
    min-height: 300px;
    padding: 22px;
  }
  .role-card-watermark {
    right: 8px;
  }
  .role-capabilities {
    gap: 10px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .gateway-stars i,
  .role-card,
  .role-card-watermark,
  .role-action i {
    animation: none;
    transition: none;
  }
}
</style>
