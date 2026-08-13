<script setup lang="ts">
import { CircleCheck } from "@lucide/vue";
import { computed } from "vue";

type LoginRole = "student" | "teacher" | "admin";

const props = defineProps<{
  visible: boolean;
  role: LoginRole;
}>();

const detail = computed(() => ({
  student: "已进入学生学习空间",
  teacher: "已进入教师教学空间",
  admin: "已进入超级管理员中心",
})[props.role]);
</script>

<template>
  <Transition name="login-toast">
    <aside
      v-if="visible"
      class="login-success-toast"
      role="status"
      aria-live="polite"
      aria-atomic="true"
    >
      <span class="login-success-icon" aria-hidden="true">
        <CircleCheck :size="24" :stroke-width="2.2" />
      </span>
      <span class="login-success-copy">
        <strong>登录成功</strong>
        <small>{{ detail }}</small>
      </span>
      <span class="login-success-progress" aria-hidden="true" />
    </aside>
  </Transition>
</template>

<style scoped>
.login-success-toast {
  position: fixed;
  right: 24px;
  bottom: 24px;
  z-index: 5000;
  display: grid;
  grid-template-columns: 44px minmax(0, 1fr);
  align-items: center;
  width: min(328px, calc(100vw - 32px));
  min-height: 76px;
  padding: 14px 18px 16px 14px;
  overflow: hidden;
  color: #17231d;
  background: rgba(255, 255, 253, 0.98);
  border: 1px solid rgba(47, 139, 87, 0.22);
  border-radius: 16px;
  box-shadow: 0 18px 46px rgba(34, 54, 43, 0.18), 0 3px 10px rgba(34, 54, 43, 0.08);
  backdrop-filter: blur(14px);
}

.login-success-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  color: #247b4b;
  background: #e9f7ef;
  border-radius: 50%;
}

.login-success-copy {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.login-success-copy strong {
  font-size: 16px;
  font-weight: 750;
  line-height: 1.2;
  letter-spacing: 0.02em;
}

.login-success-copy small {
  overflow: hidden;
  color: #66736b;
  font-size: 13px;
  line-height: 1.35;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.login-success-progress {
  position: absolute;
  right: 0;
  bottom: 0;
  left: 0;
  height: 3px;
  background: linear-gradient(90deg, #2d8a57, #66b781);
  transform-origin: left;
  animation: login-success-progress 3.2s linear forwards;
}

.login-toast-enter-active,
.login-toast-leave-active {
  transition: opacity 180ms ease, transform 220ms cubic-bezier(0.2, 0.75, 0.25, 1);
}

.login-toast-enter-from,
.login-toast-leave-to {
  opacity: 0;
  transform: translateY(14px);
}

@keyframes login-success-progress {
  to { transform: scaleX(0); }
}

@media (max-width: 640px) {
  .login-success-toast {
    right: 16px;
    bottom: 16px;
    left: 16px;
    width: auto;
  }
}

@media (prefers-reduced-motion: reduce) {
  .login-toast-enter-active,
  .login-toast-leave-active {
    transition: opacity 120ms linear;
  }

  .login-toast-enter-from,
  .login-toast-leave-to {
    transform: none;
  }

  .login-success-progress {
    animation: none;
  }
}
</style>
