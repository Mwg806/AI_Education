<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from "vue";

import LoginSuccessToast from "@/components/LoginSuccessToast.vue";
import LoginView from "@/components/LoginView.vue";
import PlannerWorkspace from "@/components/PlannerWorkspace.vue";
import RoleSelectView from "@/components/RoleSelectView.vue";
import TeacherLoginView from "@/components/TeacherLoginView.vue";
import TeacherWorkspace from "@/components/TeacherWorkspace.vue";
import { currentUser, logoutStudent } from "@/lib/auth-client";
import type { AuthSession, UserLoginProfile } from "@/lib/types";

const STORAGE_KEY = "ai_education_auth_session";
const LEGACY_STORAGE_KEY = "ai_education_student_profile";
const portalRole: "student" | "teacher" =
  import.meta.env.VITE_APP_MODE === "teacher" ? "teacher" : "student";
const normalizedPath = window.location.pathname.replace(/\/+$/, "") || "/";
const showRoleGateway =
  portalRole === "student" && normalizedPath === "/choose-role";

function restoredSession(): AuthSession | null {
  try {
    const stored =
      window.localStorage.getItem(STORAGE_KEY) ||
      window.sessionStorage.getItem(STORAGE_KEY);
    return stored ? (JSON.parse(stored) as AuthSession) : null;
  } catch {
    return null;
  }
}

const session = ref<AuthSession | null>(restoredSession());
const profile = ref<UserLoginProfile | null>(null);
const restoring = ref(Boolean(session.value));
const loginToastVisible = ref(false);
const loginToastRole = ref<"student" | "teacher">("student");
let loginToastTimer: number | undefined;

function clearStoredSession() {
  window.localStorage.removeItem(STORAGE_KEY);
  window.sessionStorage.removeItem(STORAGE_KEY);
  window.localStorage.removeItem(LEGACY_STORAGE_KEY);
  window.sessionStorage.removeItem(LEGACY_STORAGE_KEY);
}

onMounted(async () => {
  document.title = showRoleGateway
    ? "问鹿 · 选择登录身份"
    : portalRole === "teacher"
      ? "问鹿教师端"
      : "问鹿学生端";
  window.localStorage.removeItem(LEGACY_STORAGE_KEY);
  window.sessionStorage.removeItem(LEGACY_STORAGE_KEY);
  if (!session.value) {
    restoring.value = false;
    return;
  }
  try {
    profile.value = await currentUser(session.value.access_token);
    if (profile.value.role !== portalRole) {
      clearStoredSession();
      session.value = null;
      profile.value = null;
      return;
    }
    session.value.profile = profile.value;
  } catch {
    clearStoredSession();
    session.value = null;
  } finally {
    restoring.value = false;
  }
});

onBeforeUnmount(() => {
  if (loginToastTimer) window.clearTimeout(loginToastTimer);
});

function showLoginSuccess(role: "student" | "teacher") {
  if (loginToastTimer) window.clearTimeout(loginToastTimer);
  loginToastRole.value = role;
  loginToastVisible.value = true;
  loginToastTimer = window.setTimeout(() => {
    loginToastVisible.value = false;
  }, 3200);
}

function login(payload: { session: AuthSession; remember: boolean }) {
  if (payload.session.profile.role !== portalRole) return;
  session.value = payload.session;
  profile.value = payload.session.profile;
  const storage = payload.remember
    ? window.localStorage
    : window.sessionStorage;
  const otherStorage = payload.remember
    ? window.sessionStorage
    : window.localStorage;
  otherStorage.removeItem(STORAGE_KEY);
  storage.setItem(STORAGE_KEY, JSON.stringify(payload.session));
  showLoginSuccess(payload.session.profile.role);
}

function selectPortal(role: "student" | "teacher") {
  const target = new URL(window.location.href);
  target.port = role === "teacher" ? "3005" : "3000";
  target.pathname = "/";
  target.search = "";
  target.hash = "";
  window.location.assign(target.toString());
}

function logout() {
  if (session.value) void logoutStudent(session.value.access_token);
  clearStoredSession();
  session.value = null;
  profile.value = null;
}
</script>

<template>
  <RoleSelectView v-if="showRoleGateway" @select="selectPortal" />
  <main v-else-if="restoring" class="auth-restoring">
    <span /><strong>正在验证登录状态</strong
    ><small>从 MySQL 恢复你的学习空间…</small>
  </main>
  <LoginView
    v-else-if="!profile && portalRole === 'student'"
    :show-role-switch="false"
    @login="login"
  />
  <TeacherLoginView
    v-else-if="!profile && portalRole === 'teacher'"
    :show-role-switch="false"
    @login="login"
  />
  <PlannerWorkspace
    v-else-if="profile?.role === 'student'"
    :profile="profile"
    @logout="logout"
  />
  <TeacherWorkspace
    v-else-if="profile?.role === 'teacher'"
    :profile="profile"
    @logout="logout"
  />
  <LoginSuccessToast :visible="loginToastVisible" :role="loginToastRole" />
</template>
