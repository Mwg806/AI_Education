<script setup lang="ts">
import { ChevronLeft, ChevronRight } from "@lucide/vue";
import { computed } from "vue";

const props = withDefaults(defineProps<{
  page: number;
  total: number;
  pageSize?: number;
  label?: string;
}>(), {
  pageSize: 6,
  label: "条记录",
});
const emit = defineEmits<{ change: [page: number] }>();

const pageCount = computed(() => Math.max(1, Math.ceil(props.total / props.pageSize)));
const safePage = computed(() => Math.min(Math.max(props.page, 1), pageCount.value));
const start = computed(() => props.total ? (safePage.value - 1) * props.pageSize + 1 : 0);
const end = computed(() => Math.min(safePage.value * props.pageSize, props.total));
</script>

<template>
  <nav v-if="total > pageSize" class="pagination-controls" aria-label="分页导航">
    <span>显示 {{ start }}—{{ end }}，共 {{ total }} {{ label }}</span>
    <div>
      <button :disabled="safePage <= 1" @click="emit('change', safePage - 1)">
        <ChevronLeft :size="17" />上一页
      </button>
      <strong>第 {{ safePage }} / {{ pageCount }} 页</strong>
      <button :disabled="safePage >= pageCount" @click="emit('change', safePage + 1)">
        下一页<ChevronRight :size="17" />
      </button>
    </div>
  </nav>
</template>

<style scoped>
.pagination-controls{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-top:18px;padding-top:16px;border-top:1px solid #e4ebe8;color:#637b73;font-size:14px}
.pagination-controls>div{display:flex;align-items:center;gap:12px}.pagination-controls button{display:flex;min-height:42px;align-items:center;gap:5px;padding:0 14px;color:#176f54;border:1px solid #c7ddd5;background:#fff;border-radius:9px;font-size:14px;font-weight:700}
.pagination-controls button:disabled{color:#91a39d;background:#f3f6f5}.pagination-controls strong{min-width:92px;color:#365e51;font-size:14px;text-align:center}
@media(max-width:640px){.pagination-controls{align-items:stretch;flex-direction:column}.pagination-controls>div{justify-content:space-between}.pagination-controls button{padding-inline:10px}}
</style>
