<script setup lang="ts">
import { ref } from "vue";

import LoginView from "@/components/LoginView.vue";
import PlannerWorkspace from "@/components/PlannerWorkspace.vue";
import type { StudentLoginProfile } from "@/lib/types";

const STORAGE_KEY = "ai_education_student_profile";

function restoredProfile(): StudentLoginProfile | null {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY)
      || window.sessionStorage.getItem(STORAGE_KEY);
    return stored ? JSON.parse(stored) as StudentLoginProfile : null;
  } catch {
    return null;
  }
}

const profile = ref<StudentLoginProfile | null>(restoredProfile());

function login(payload: { profile: StudentLoginProfile; remember: boolean }) {
  profile.value = payload.profile;
  const storage = payload.remember ? window.localStorage : window.sessionStorage;
  const otherStorage = payload.remember ? window.sessionStorage : window.localStorage;
  otherStorage.removeItem(STORAGE_KEY);
  storage.setItem(STORAGE_KEY, JSON.stringify(payload.profile));
}

function logout() {
  window.localStorage.removeItem(STORAGE_KEY);
  window.sessionStorage.removeItem(STORAGE_KEY);
  profile.value = null;
}
</script>

<template>
  <LoginView v-if="!profile" @login="login" />
  <PlannerWorkspace v-else :profile="profile" @logout="logout" />
</template>
