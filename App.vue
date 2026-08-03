<script setup lang="ts">
import { onMounted, ref } from "vue";

import LoginView from "@/components/LoginView.vue";
import PlannerWorkspace from "@/components/PlannerWorkspace.vue";
import RoleSelectView from "@/components/RoleSelectView.vue";
import TeacherLoginView from "@/components/TeacherLoginView.vue";
import TeacherWorkspace from "@/components/TeacherWorkspace.vue";
import { currentUser, logoutStudent } from "@/lib/auth-client";
import type { AuthSession, UserLoginProfile } from "@/lib/types";

const STORAGE_KEY = "ai_education_auth_session";
const LEGACY_STORAGE_KEY = "ai_education_student_profile";

function restoredSession(): AuthSession | null {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY)
      || window.sessionStorage.getItem(STORAGE_KEY);
    return stored ? JSON.parse(stored) as AuthSession : null;
  } catch {
    return null;
  }
}

const session = ref<AuthSession | null>(restoredSession());
const profile = ref<UserLoginProfile | null>(null);
const selectedRole = ref<"student" | "teacher" | null>(
  session.value?.profile?.role || null,
);
const restoring = ref(Boolean(session.value));

function clearStoredSession() {
  window.localStorage.removeItem(STORAGE_KEY);
  window.sessionStorage.removeItem(STORAGE_KEY);
  window.localStorage.removeItem(LEGACY_STORAGE_KEY);
  window.sessionStorage.removeItem(LEGACY_STORAGE_KEY);
}

onMounted(async () => {
  window.localStorage.removeItem(LEGACY_STORAGE_KEY);
  window.sessionStorage.removeItem(LEGACY_STORAGE_KEY);
  if (!session.value) { restoring.value = false; return; }
  try {
    profile.value = await currentUser(session.value.access_token);
    selectedRole.value = profile.value.role;
    session.value.profile = profile.value;
  } catch {
    clearStoredSession();
    session.value = null;
  } finally {
    restoring.value = false;
  }
});

function login(payload: { session: AuthSession; remember: boolean }) {
  session.value = payload.session;
  profile.value = payload.session.profile;
  selectedRole.value = payload.session.profile.role;
  const storage = payload.remember ? window.localStorage : window.sessionStorage;
  const otherStorage = payload.remember ? window.sessionStorage : window.localStorage;
  otherStorage.removeItem(STORAGE_KEY);
  storage.setItem(STORAGE_KEY, JSON.stringify(payload.session));
}

function logout() {
  if (session.value) void logoutStudent(session.value.access_token);
  clearStoredSession();
  session.value = null;
  profile.value = null;
  selectedRole.value = null;
}
</script>

<template>
  <main v-if="restoring" class="auth-restoring"><span /><strong>正在验证登录状态</strong><small>从 MySQL 恢复你的学习空间…</small></main>
  <RoleSelectView v-else-if="!profile && !selectedRole" @select="selectedRole = $event" />
  <LoginView v-else-if="!profile && selectedRole === 'student'" @login="login" @back="selectedRole = null" />
  <TeacherLoginView v-else-if="!profile && selectedRole === 'teacher'" @login="login" @back="selectedRole = null" />
  <PlannerWorkspace v-else-if="profile?.role === 'student'" :profile="profile" @logout="logout" />
  <TeacherWorkspace v-else-if="profile?.role === 'teacher'" :profile="profile" @logout="logout" />
</template>
