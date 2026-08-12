<script setup lang="ts">
withDefaults(
  defineProps<{
    size?: number;
    label?: string;
  }>(),
  {
    size: 44,
    label: "问鹿",
  },
);
</script>

<template>
  <span
    class="wenlu-mark"
    :style="{ '--wenlu-mark-size': `${size}px` }"
    role="img"
    :aria-label="label"
  >
    <img src="/wenlu-logo.svg" alt="" aria-hidden="true" />
  </span>
</template>

<style scoped>
.wenlu-mark {
  display: grid;
  width: var(--wenlu-mark-size);
  height: var(--wenlu-mark-size);
  flex: 0 0 auto;
  place-items: center;
  color: #5b2d59;
  background: #fffdfb;
  border: 1px solid rgba(255, 255, 255, 0.72);
  border-radius: calc(var(--wenlu-mark-size) * 0.24);
  box-shadow:
    0 10px 24px rgba(48, 28, 92, 0.18),
    inset 0 1px 4px rgba(255, 255, 255, 0.8);
}
.wenlu-mark img {
  width: 78%;
  height: 78%;
  overflow: visible;
}
</style>
