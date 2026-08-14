<script setup lang="ts">
import {
  BookOpenCheck,
  CalendarDays,
  Check,
  ChevronRight,
  CircleAlert,
  Clock3,
  Download,
  FileCheck2,
  FlaskConical,
  Layers3,
  LoaderCircle,
  Lock,
  MessageSquareText,
  RefreshCw,
  School,
  Search,
  Send,
  ShieldCheck,
  Sparkles,
  Unlock,
  Target,
} from "@lucide/vue";
import { computed, onMounted, reactive, ref, watch } from "vue";

import PaginationControls from "@/components/PaginationControls.vue";
import {
  getSubjectEdition,
  progressGroups,
  subjectEditions,
  subjectLabels,
} from "@/lib/curriculum-catalog";
import {
  approveLessonPlan,
  createLessonPlan,
  fetchLessonPlan,
  fetchLessonPlans,
  fetchTeacherPreparationCatalog,
  publishLessonPlan,
  recordLessonFeedback,
  reviseLessonPlan,
  searchTeachingResources,
} from "@/lib/teacher-client";
import type {
  ClassroomSummary,
  LessonPlan,
  TeachingResourceReference,
} from "@/lib/teacher-client";
import type { SubjectKey } from "@/lib/types";

const props = defineProps<{
  classrooms: ClassroomSummary[];
  mode: "create" | "library";
}>();

const plans = ref<LessonPlan[]>([]);
const selected = ref<LessonPlan | null>(null);
const catalog = ref<Awaited<
  ReturnType<typeof fetchTeacherPreparationCatalog>
> | null>(null);
const searchedResources = ref<TeachingResourceReference[]>([]);
const loading = ref(false);
const operation = ref("");
const error = ref("");
const notice = ref("");
const revisionOpen = ref(false);
const feedbackOpen = ref(false);
const planPage = ref(1);
const detailPage = ref(1);
const generationIdempotencyKey = ref("");
const PLAN_PAGE_SIZE = 5;
const revision = reactive({
  component: "full",
  request: "",
  lockedIds: [] as string[],
});
const feedback = reactive({
  actualDuration: 45,
  accuracy: 0.8,
  rating: 4,
  notes: "",
});
const topicMode = ref<"chapter" | "custom">("chapter");
const selectedVolumeId = ref("");
const selectedChapterId = ref("");
const form = reactive({
  classroomId: 0,
  subject: "mathematics" as SubjectKey,
  lessonType: "new_lesson",
  topic: "",
  lessonRequest: "",
  durationMinutes: 45,
  teachingStage: "日常教学",
  textbookVersion: subjectEditions("mathematics")[0]?.id || "教师指定教材",
  examYear: 2027,
});

const currentClass = computed(() =>
  props.classrooms.find((item) => item.id === form.classroomId),
);
const editions = computed(() => subjectEditions(form.subject));
const chapterGroups = computed(() =>
  progressGroups(form.subject, form.textbookVersion).filter(
    (group) => group.id !== "whole_book_scope" && Boolean(group.options.length),
  ),
);
const selectedVolume = computed(() =>
  chapterGroups.value.find((group) => group.id === selectedVolumeId.value),
);
const selectedChapter = computed(() =>
  selectedVolume.value?.options.find(
    (chapter) => chapter.id === selectedChapterId.value,
  ),
);
const resolvedTopic = computed(() => {
  if (topicMode.value === "custom") return form.topic.trim();
  const chapter = selectedChapter.value;
  return chapter
    ? [chapter.number, chapter.title].filter(Boolean).join(" ")
    : "";
});
const libraryStatuses = new Set<LessonPlan["status"]>([
  "approved",
  "published",
  "executed",
  "feedback_recorded",
  "archived",
]);
const visiblePlans = computed(() =>
  plans.value.filter((plan) =>
    props.mode === "library"
      ? libraryStatuses.has(plan.status)
      : !libraryStatuses.has(plan.status),
  ),
);
const activityMinutes = computed(
  () =>
    selected.value?.activities.reduce(
      (sum, item) => sum + item.duration_minutes,
      0,
    ) || 0,
);
const canApprove = computed(
  () =>
    selected.value?.status === "teacher_review" &&
    selected.value.quality_report.alignment_status === "pass" &&
    selected.value.quality_report.feasibility_status === "pass" &&
    selected.value.quality_report.resource_compliance_status !== "fail",
);
const pagedPlans = computed(() => {
  const start = (planPage.value - 1) * PLAN_PAGE_SIZE;
  return visiblePlans.value.slice(start, start + PLAN_PAGE_SIZE);
});

watch(
  () => props.classrooms,
  (classrooms) => {
    if (!form.classroomId && classrooms[0]) form.classroomId = classrooms[0].id;
    syncSubject();
  },
  { immediate: true, deep: true },
);
watch(() => form.classroomId, syncSubject);
watch(() => form.subject, syncTextbook);
watch(() => form.textbookVersion, syncChapterSelection);
watch(selectedVolumeId, syncChapterSelection);
watch(
  [() => JSON.stringify(form), topicMode, selectedVolumeId, selectedChapterId],
  () => {
    generationIdempotencyKey.value = "";
  },
);
watch(
  () => props.mode,
  () => {
    planPage.value = 1;
    selected.value = null;
    revisionOpen.value = false;
    feedbackOpen.value = false;
  },
);

function syncSubject() {
  const classroom = props.classrooms.find(
    (item) => item.id === form.classroomId,
  );
  if (classroom?.subject) form.subject = classroom.subject;
  syncTextbook();
}

function syncTextbook() {
  const available = subjectEditions(form.subject);
  if (!available.some((item) => item.id === form.textbookVersion)) {
    form.textbookVersion = available[0]?.id || "教师指定教材";
  }
  syncChapterSelection();
}

function syncChapterSelection() {
  const groups = chapterGroups.value;
  if (!groups.length) {
    selectedVolumeId.value = "";
    selectedChapterId.value = "";
    topicMode.value = "custom";
    return;
  }
  if (!groups.some((group) => group.id === selectedVolumeId.value)) {
    selectedVolumeId.value = groups[0].id;
  }
  const chapters =
    groups.find((group) => group.id === selectedVolumeId.value)?.options || [];
  if (!chapters.some((chapter) => chapter.id === selectedChapterId.value)) {
    selectedChapterId.value = chapters[0]?.id || "";
  }
}

function selectedTextbookLabel() {
  const edition = editions.value.find(
    (item) => item.id === form.textbookVersion,
  );
  const editionLabel = edition
    ? edition.label + " · " + edition.publisher
    : form.textbookVersion;
  return topicMode.value === "chapter" && selectedVolume.value
    ? editionLabel + " · " + selectedVolume.value.label.replace(" · 待复核", "")
    : editionLabel;
}
function flash(message: string) {
  notice.value = message;
  window.setTimeout(() => {
    notice.value = "";
  }, 3000);
}

async function run<T>(name: string, task: () => Promise<T>): Promise<T | null> {
  operation.value = name;
  error.value = "";
  try {
    return await task();
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "智能备课操作失败";
    return null;
  } finally {
    operation.value = "";
  }
}

async function loadPlans() {
  loading.value = true;
  const result = await run("list", () => fetchLessonPlans());
  if (result) plans.value = result;
  loading.value = false;
}

async function choosePlan(plan: LessonPlan) {
  const result = await run("detail", () =>
    fetchLessonPlan(plan.lesson_plan_id),
  );
  if (result) {
    selected.value = result;
    detailPage.value = 1;
    revision.lockedIds = [...result.locked_component_ids];
    feedback.actualDuration = result.context.duration_minutes;
  }
}

async function generate() {
  if (
    !form.classroomId ||
    !resolvedTopic.value ||
    form.lessonRequest.trim().length < 5
  ) {
    error.value =
      topicMode.value === "chapter"
        ? "请选择班级、教材分册和具体章节，并填写至少 5 个字的备课要求"
        : "请选择班级，并填写自定义课题和至少 5 个字的备课要求";
    return;
  }
  if (!generationIdempotencyKey.value) {
    const nonce = globalThis.crypto?.randomUUID?.() || Date.now().toString(36);
    generationIdempotencyKey.value = `lesson-create-${form.classroomId}-${nonce}`;
  }
  const idempotencyKey = generationIdempotencyKey.value;
  const result = await run("generate", () =>
    createLessonPlan({
      classroomId: form.classroomId,
      subject: form.subject,
      lessonType: form.lessonType,
      idempotencyKey,
      topic: resolvedTopic.value,
      lessonRequest: form.lessonRequest,
      durationMinutes: form.durationMinutes,
      teachingStage: form.teachingStage,
      textbookVersion: selectedTextbookLabel(),
      examYear: form.examYear,
    }),
  );
  if (result) {
    generationIdempotencyKey.value = "";
    selected.value = result;
    detailPage.value = 1;
    revision.lockedIds = [];
    await loadPlans();
    flash("备课初稿已生成，等待教师审核");
  }
}

async function searchReferences() {
  if (!resolvedTopic.value) return;
  const result = await run("search", () =>
    searchTeachingResources(form.subject, resolvedTopic.value),
  );
  if (result) searchedResources.value = result;
}

function toggleLock(componentId: string) {
  const index = revision.lockedIds.indexOf(componentId);
  if (index >= 0) revision.lockedIds.splice(index, 1);
  else revision.lockedIds.push(componentId);
}

function isLocked(componentId: string) {
  return revision.lockedIds.includes(componentId);
}

async function submitRevision() {
  if (!selected.value || revision.request.trim().length < 3) return;
  const result = await run("revise", () =>
    reviseLessonPlan(selected.value!.lesson_plan_id, {
      expectedVersion: selected.value!.version,
      component: revision.component,
      revisionRequest: revision.request,
      lockedComponentIds: revision.lockedIds,
    }),
  );
  if (result) {
    selected.value = result;
    revision.request = "";
    revisionOpen.value = false;
    await loadPlans();
    flash("已生成新版本，锁定内容保持不变");
  }
}

async function approve() {
  if (!selected.value) return;
  const result = await run("approve", () =>
    approveLessonPlan(selected.value!.lesson_plan_id, selected.value!.version),
  );
  if (result) {
    selected.value = result;
    await loadPlans();
    flash("方案已批准，尚未发布");
  }
}

async function publish() {
  if (!selected.value) return;
  const result = await run("publish", () =>
    publishLessonPlan(selected.value!.lesson_plan_id, selected.value!.version),
  );
  if (result) {
    selected.value = result;
    await loadPlans();
    flash("方案已发布，课堂检测与作业蓝图已同步");
  }
}

async function submitFeedback() {
  if (!selected.value) return;
  const result = await run("feedback", () =>
    recordLessonFeedback(selected.value!.lesson_plan_id, {
      lessonVersion: selected.value!.version,
      actualDurationMinutes: feedback.actualDuration,
      completedActivityIds: selected.value!.activities.map(
        (item) => item.activity_id,
      ),
      skippedActivityIds: [],
      classCheckAccuracy: feedback.accuracy,
      teacherRating: feedback.rating,
      effectiveComponents: [],
      issues: [],
      teacherNotes: feedback.notes,
    }),
  );
  if (result) {
    selected.value = result;
    feedbackOpen.value = false;
    await loadPlans();
    flash("课后反馈已记录为新版本");
  }
}

function classroomLabel(classroomId: number) {
  return (
    props.classrooms.find((item) => item.id === classroomId)?.class_name ||
    "班级 #" + classroomId
  );
}

function formatDate(value?: string | null) {
  if (!value) return "暂无";
  return new Date(value).toLocaleString("zh-CN", { hour12: false });
}

function textbookLabel(plan: LessonPlan) {
  const edition = getSubjectEdition(
    plan.context.subject,
    plan.context.textbook_version,
  );
  return edition?.id === plan.context.textbook_version
    ? edition.label + " · " + edition.publisher
    : plan.context.textbook_version;
}

function downloadPlan(plan: LessonPlan) {
  const lines = [
    "# " + plan.title,
    "",
    "- 课题：" + plan.context.topic,
    "- 班级：" + classroomLabel(plan.context.classroom_id),
    "- 教材：" + textbookLabel(plan),
    "- 版本：v" + plan.version + " · " + statusLabel(plan.status),
    "- 创建时间：" + formatDate(plan.created_at),
    "- 批准时间：" + formatDate(plan.approved_at),
    "",
    plan.summary,
    "",
    "## 教学重点",
    ...plan.key_points.map((item) => "- " + item),
    "",
    "## 教学难点",
    ...plan.difficult_points.map((item) => "- " + item),
    "",
    "## 教学目标",
    ...plan.objectives.map(
      (item, index) =>
        index +
        1 +
        ". " +
        item.description +
        "（" +
        item.observable_behavior +
        "）",
    ),
    "",
    "## 课堂活动",
    ...plan.activities.map(
      (item) =>
        "### " +
        item.stage +
        " · " +
        item.duration_minutes +
        " 分钟\n- 教师活动：" +
        item.teacher_action +
        "\n- 学生活动：" +
        item.student_action +
        "\n- 课堂证据：" +
        item.expected_output,
    ),
    "",
    "## 板书设计",
    ...Object.entries(plan.board_plan.layout).map(
      ([area, text]) => "- " + area + "：" + text,
    ),
    "",
    "## 课堂检测与作业",
    ...plan.assessments.map(
      (item, index) =>
        index +
        1 +
        ". " +
        (item.purpose === "homework" ? "【作业】" : "【检测】") +
        item.prompt +
        "\n   - 评分要点：" +
        item.scoring_rubric.join("；"),
    ),
    "",
    "## 分层支持",
    ...plan.differentiation_plan.map(
      (item) => "- " + item.target_profile + "：" + item.task_adjustment,
    ),
    "",
    "## 参考来源",
    ...(plan.resources || []).map(
      (item) => "- " + item.title + "（" + item.source_organization + "）",
    ),
  ];
  const url = URL.createObjectURL(
    new Blob([lines.join("\n")], { type: "text/markdown;charset=utf-8" }),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download =
    plan.context.topic.replace(/[\\/:*?"<>|]/g, "-") +
    "_备课方案_v" +
    plan.version +
    ".md";
  link.click();
  URL.revokeObjectURL(url);
}

function statusLabel(status: LessonPlan["status"]) {
  return {
    draft: "草稿",
    teacher_review: "待教师审核",
    approved: "已批准",
    published: "已发布",
    executed: "已授课",
    feedback_recorded: "已记录反馈",
    superseded: "已被替代",
    archived: "已归档",
  }[status];
}

onMounted(async () => {
  const [catalogResult] = await Promise.all([
    run("catalog", () => fetchTeacherPreparationCatalog()),
    loadPlans(),
  ]);
  if (catalogResult) catalog.value = catalogResult;
});
</script>

<template>
  <div class="prep-workspace">
    <section class="prep-hero">
      <div>
        <small>TEACHER PREPARATION AGENT · AGENT 04</small>
        <h1>
          {{
            mode === "library" ? "我的备课方案" : "智能备课，由教师做最终决定。"
          }}
        </h1>
        <p>
          {{
            mode === "library"
              ? "集中回看已经由教师批准的备课记录，按课题、班级和完成时间查看并下载完整方案。"
              : "结合班级匿名聚合学情、知识库教材目录与九学科优秀教案，生成可修订、可批准的课堂方案。"
          }}
        </p>
      </div>
      <div class="resource-health">
        <ShieldCheck :size="26" />
        <span
          ><strong>{{
            catalog?.integrity.valid ? "资源校验通过" : "资源库检查中"
          }}</strong>
          <small
            >{{ catalog?.integrity.verified_count || 0 }}/{{
              catalog?.resource_count || 27
            }}
            份教案 · {{ catalog?.subject_count || 9 }} 学科</small
          ></span
        >
      </div>
    </section>

    <p v-if="error" class="prep-error"><CircleAlert :size="16" />{{ error }}</p>
    <p v-if="notice" class="prep-notice"><Check :size="16" />{{ notice }}</p>

    <section v-if="!classrooms.length" class="prep-empty">
      <BookOpenCheck :size="38" /><strong>请先创建教学班级</strong>
      <p>智能备课需要班级年级、学科和匿名聚合学情作为教学上下文。</p>
    </section>

    <div v-else class="prep-layout">
      <aside>
        <form
          v-if="mode === 'create'"
          class="prep-card generation-form"
          @submit.prevent="generate"
        >
          <header>
            <div>
              <small>NEW LESSON</small>
              <h2>生成备课方案</h2>
            </div>
            <Sparkles :size="21" />
          </header>
          <label
            ><span>教学班级</span
            ><select v-model.number="form.classroomId">
              <option
                v-for="item in classrooms"
                :key="item.id"
                :value="item.id"
              >
                {{ item.class_name }} · {{ item.student_count }} 人
              </option>
            </select></label
          >
          <div class="form-pair">
            <label
              ><span>学科</span
              ><select
                v-model="form.subject"
                :disabled="Boolean(currentClass?.subject)"
              >
                <option
                  v-for="[key, label] in Object.entries(subjectLabels)"
                  :key="key"
                  :value="key"
                >
                  {{ label }}
                </option>
              </select></label
            >
            <label
              ><span>课型</span
              ><select v-model="form.lessonType">
                <option value="new_lesson">新授课</option>
                <option value="review">复习课</option>
                <option value="thematic_review">专题复习</option>
                <option value="lab">实验课</option>
                <option value="paper_review">试卷讲评</option>
              </select></label
            >
          </div>
          <label class="textbook-field"
            ><span>教材版本</span
            ><select v-model="form.textbookVersion">
              <option v-for="item in editions" :key="item.id" :value="item.id">
                {{ item.label }} · {{ item.publisher }}（{{
                  item.pdf_count || item.volumes.length
                }}
                册）
              </option></select
            ><small class="catalog-hint"
              >章节选项来自知识库教材 PDF
              目录；切换教材版本后，分册与章节会自动同步。</small
            ></label
          >
          <div class="topic-source">
            <span>课题来源</span>
            <div
              class="topic-source-options"
              role="group"
              aria-label="课题来源"
            >
              <button
                type="button"
                :class="{ active: topicMode === 'chapter' }"
                :disabled="!chapterGroups.length"
                @click="topicMode = 'chapter'"
              >
                <BookOpenCheck :size="15" />教材章节
              </button>
              <button
                type="button"
                :class="{ active: topicMode === 'custom' }"
                @click="topicMode = 'custom'"
              >
                <Sparkles :size="15" />自定义课题
              </button>
            </div>
          </div>
          <div v-if="topicMode === 'chapter'" class="chapter-topic-panel">
            <div class="form-pair">
              <label
                ><span>教材分册</span
                ><select v-model="selectedVolumeId">
                  <option
                    v-for="group in chapterGroups"
                    :key="group.id"
                    :value="group.id"
                  >
                    {{ group.label }}
                  </option>
                </select></label
              >
              <label
                ><span>具体章节</span
                ><select v-model="selectedChapterId">
                  <option
                    v-for="chapter in selectedVolume?.options || []"
                    :key="chapter.id"
                    :value="chapter.id"
                  >
                    {{ chapter.number ? chapter.number + " " : ""
                    }}{{ chapter.title }}
                  </option>
                </select></label
              >
            </div>
            <div class="selected-chapter">
              <div>
                <small>当前备课课题</small>
                <strong>{{ resolvedTopic || "请选择具体章节" }}</strong>
              </div>
              <button
                type="button"
                :disabled="!resolvedTopic || operation === 'search'"
                @click="searchReferences"
              >
                <Search :size="15" />检索参考教案
              </button>
            </div>
            <small v-if="selectedChapter?.evidence" class="chapter-evidence">
              目录依据：{{
                selectedChapter.evidence.source_pdf.split("/").at(-1)
              }}
              · PDF 第 {{ selectedChapter.evidence.pdf_page }} 页
            </small>
          </div>

          <label v-if="topicMode === 'custom'"
            ><span>自定义课题</span>
            <div class="search-field">
              <input
                v-model="form.topic"
                placeholder="例如：氧化还原反应"
              /><button
                type="button"
                title="检索优秀教案"
                @click="searchReferences"
              >
                <Search :size="15" />
              </button></div
          ></label>
          <label
            ><span>本课要求</span
            ><textarea
              v-model="form.lessonRequest"
              rows="4"
              placeholder="说明教学范围、重点、难点或希望采用的课堂组织方式…"
            />
          </label>
          <div class="form-pair">
            <label
              ><span>课时（分钟）</span
              ><input
                v-model.number="form.durationMinutes"
                type="number"
                min="20"
                max="240"
            /></label>
            <label
              ><span>教学阶段</span><input v-model="form.teachingStage"
            /></label>
          </div>
          <button class="prep-primary" :disabled="Boolean(operation)">
            <LoaderCircle
              v-if="operation === 'generate'"
              class="spin"
              :size="17"
            /><Sparkles v-else :size="17" />生成可审核教案
          </button>
          <p>
            <ShieldCheck :size="14" />不会自动发布；所有内容必须由教师批准。
          </p>
        </form>

        <section
          v-if="mode === 'create' && searchedResources.length"
          class="prep-card searched"
        >
          <header>
            <div>
              <small>CURATED SOURCES</small>
              <h2>匹配参考教案</h2>
            </div>
          </header>
          <article v-for="item in searchedResources" :key="item.resource_id">
            <BookOpenCheck :size="16" />
            <div>
              <strong>{{ item.title }}</strong
              ><small
                >{{ item.source_organization }} ·
                {{ item.page_count }} 页</small
              >
            </div>
          </article>
        </section>

        <section class="prep-card history">
          <header>
            <div>
              <small>VERSIONED PLANS</small>
              <h2>{{ mode === "library" ? "我的备课方案" : "待审核方案" }}</h2>
            </div>
            <button @click="loadPlans"><RefreshCw :size="15" /></button>
          </header>
          <div v-if="loading" class="mini-loading">
            <LoaderCircle class="spin" :size="18" />读取方案…
          </div>
          <button
            v-for="plan in pagedPlans"
            :key="plan.lesson_plan_id"
            :class="{
              active: selected?.lesson_plan_id === plan.lesson_plan_id,
            }"
            @click="choosePlan(plan)"
          >
            <span>{{ subjectLabels[plan.context.subject] }}</span>
            <div>
              <strong>{{ plan.title }}</strong
              ><small
                >{{ classroomLabel(plan.context.classroom_id) }} · v{{
                  plan.version
                }}
                · {{ statusLabel(plan.status) }}<br />{{
                  formatDate(plan.approved_at || plan.created_at)
                }}</small
              >
            </div>
            <ChevronRight :size="15" />
          </button>
          <p v-if="!loading && !visiblePlans.length">还没有备课方案。</p>
          <PaginationControls
            :page="planPage"
            :total="visiblePlans.length"
            :page-size="PLAN_PAGE_SIZE"
            label="份教案"
            @change="planPage = $event"
          />
        </section>
      </aside>

      <main>
        <section v-if="!selected" class="prep-card prep-welcome">
          <FileCheck2 :size="45" />
          <h2>
            {{
              mode === "library"
                ? "选择一份已批准方案进行回看"
                : "生成或选择一份待审核教案"
            }}
          </h2>
          <p>
            Agent
            会先完成目标—活动—评价一致性、课堂时间和来源合规检查，再交给教师修订与批准。
          </p>
        </section>

        <template v-else>
          <section class="prep-card plan-heading">
            <div class="plan-meta">
              <span>{{ subjectLabels[selected.context.subject] }}</span
              ><span>v{{ selected.version }}</span
              ><span :class="selected.status">{{
                statusLabel(selected.status)
              }}</span
              ><span>{{
                selected.generation_mode === "llm" ? "LLM 生成" : "参考模板降级"
              }}</span>
            </div>
            <h1>{{ selected.title }}</h1>
            <p>{{ selected.summary }}</p>
            <div class="plan-record-summary">
              <span
                ><School :size="15" />{{
                  classroomLabel(selected.context.classroom_id)
                }}</span
              ><span
                ><BookOpenCheck :size="15" />{{ textbookLabel(selected) }}</span
              ><span
                ><CalendarDays :size="15" />创建
                {{ formatDate(selected.created_at) }}</span
              ><span v-if="selected.approved_at"
                ><FileCheck2 :size="15" />批准
                {{ formatDate(selected.approved_at) }}</span
              >
            </div>
            <div class="quality-row">
              <span :class="selected.quality_report.alignment_status"
                ><Check />目标对齐</span
              >
              <span :class="selected.quality_report.feasibility_status"
                ><Clock3 />{{ activityMinutes }}+{{
                  selected.context.buffer_minutes
                }}
                分钟</span
              >
              <span :class="selected.quality_report.resource_compliance_status"
                ><ShieldCheck />来源合规</span
              >
              <span
                ><Layers3 />{{
                  selected.context.diagnosis_adapted
                    ? "已适配班级学情"
                    : "暂无可用学情"
                }}</span
              >
            </div>
            <div class="plan-actions">
              <button
                v-if="mode === 'library'"
                class="download-plan"
                @click="downloadPlan(selected)"
              >
                <Download :size="16" />下载完整教案
              </button>
              <button
                v-if="mode === 'create'"
                @click="revisionOpen = !revisionOpen"
              >
                <MessageSquareText :size="16" />提出修订
              </button>
              <button
                v-if="mode === 'create' && canApprove"
                class="approve"
                :disabled="Boolean(operation)"
                @click="approve"
              >
                <Check :size="16" />教师批准
              </button>
              <button
                v-if="selected.status === 'approved'"
                class="publish"
                :disabled="Boolean(operation)"
                @click="publish"
              >
                <Send :size="16" />确认发布
              </button>
              <button
                v-if="['published', 'executed'].includes(selected.status)"
                @click="feedbackOpen = !feedbackOpen"
              >
                <FileCheck2 :size="16" />课后反馈
              </button>
            </div>
          </section>

          <form
            v-if="mode === 'create' && revisionOpen"
            class="prep-card revision-panel"
            @submit.prevent="submitRevision"
          >
            <header>
              <div>
                <small>TEACHER REVISION</small>
                <h2>局部修订与内容锁定</h2>
              </div>
              <Lock :size="19" />
            </header>
            <div class="form-pair">
              <label
                ><span>修订范围</span
                ><select v-model="revision.component">
                  <option value="full">完整方案</option>
                  <option value="objectives">教学目标</option>
                  <option value="activities">课堂活动</option>
                  <option value="board">板书设计</option>
                  <option value="assessments">检测与作业</option>
                  <option value="differentiation">分层支持</option>
                </select></label
              ><label
                ><span>已锁定</span
                ><strong>{{ revision.lockedIds.length }} 个组件</strong></label
              >
            </div>
            <label
              ><span>教师修订要求</span
              ><textarea
                v-model="revision.request"
                rows="3"
                placeholder="例如：保留目标和课堂检测，将探究活动改成小组实验…"
              />
            </label>
            <button
              class="prep-primary"
              :disabled="
                revision.request.trim().length < 3 || Boolean(operation)
              "
            >
              <LoaderCircle
                v-if="operation === 'revise'"
                class="spin"
                :size="16"
              /><Sparkles v-else :size="16" />生成新版本
            </button>
          </form>

          <form
            v-if="mode === 'create' && feedbackOpen"
            class="prep-card feedback-panel"
            @submit.prevent="submitFeedback"
          >
            <header>
              <div>
                <small>POST-LESSON FEEDBACK</small>
                <h2>记录课堂实施效果</h2>
              </div>
            </header>
            <div class="form-pair">
              <label
                ><span>实际用时</span
                ><input
                  v-model.number="feedback.actualDuration"
                  type="number"
                  min="1"
                  max="360" /></label
              ><label
                ><span>课堂检测正确率</span
                ><input
                  v-model.number="feedback.accuracy"
                  type="number"
                  min="0"
                  max="1"
                  step="0.05"
              /></label>
            </div>
            <label
              ><span>教师评分（1—5）</span
              ><input
                v-model.number="feedback.rating"
                type="range"
                min="1"
                max="5"
              /><strong>{{ feedback.rating }} 分</strong></label
            >
            <label
              ><span>复盘记录</span
              ><textarea
                v-model="feedback.notes"
                rows="3"
                placeholder="记录有效环节、课堂问题和下次调整建议…"
              />
            </label>
            <button class="prep-primary" :disabled="Boolean(operation)">
              <FileCheck2 :size="16" />保存课后反馈
            </button>
          </form>

          <nav class="lesson-page-tabs">
            <button
              v-for="(label, index) in [
                '目标与课堂',
                '板书与分层',
                '检测与作业',
                '对齐与来源',
              ]"
              :key="label"
              :class="{ active: detailPage === index + 1 }"
              @click="detailPage = index + 1"
            >
              <span>{{ index + 1 }}</span
              >{{ label }}
            </button>
          </nav>

          <section v-if="detailPage === 1" class="prep-card content-section">
            <header>
              <div>
                <small>OBJECTIVES</small>
                <h2>教学目标</h2>
              </div>
              <Target />
            </header>
            <article
              v-for="objective in selected.objectives"
              :key="objective.objective_id"
              class="objective-row"
            >
              <button
                :title="
                  isLocked(objective.objective_id)
                    ? '解除锁定'
                    : '锁定后修订不改动'
                "
                @click="toggleLock(objective.objective_id)"
              >
                <Lock
                  v-if="isLocked(objective.objective_id)"
                  :size="14"
                /><Unlock v-else :size="14" />
              </button>
              <span>{{ objective.objective_id.replace("obj_", "0") }}</span>
              <div>
                <strong>{{ objective.description }}</strong>
                <p>可观察行为：{{ objective.observable_behavior }}</p>
                <small v-for="tag in objective.exam_ability_tags" :key="tag">{{
                  tag
                }}</small>
              </div>
            </article>
          </section>

          <section v-if="detailPage === 1" class="prep-card content-section">
            <header>
              <div>
                <small>CLASSROOM FLOW</small>
                <h2>课堂活动时间线</h2>
              </div>
              <Clock3 :size="20" />
            </header>
            <article
              v-for="activity in selected.activities"
              :key="activity.activity_id"
              class="activity-row"
            >
              <button @click="toggleLock(activity.activity_id)">
                <Lock v-if="isLocked(activity.activity_id)" :size="14" /><Unlock
                  v-else
                  :size="14"
                />
              </button>
              <time>{{ activity.duration_minutes }}′</time>
              <div>
                <strong>{{ activity.stage }}</strong>
                <p><b>教师：</b>{{ activity.teacher_action }}</p>
                <p><b>学生：</b>{{ activity.student_action }}</p>
                <small
                  >课堂证据：{{ activity.expected_output }} ·
                  {{ activity.assessment_method }}</small
                >
              </div>
            </article>
          </section>

          <div v-if="detailPage === 2" class="two-column">
            <section class="prep-card content-section">
              <header>
                <div>
                  <small>BOARD DESIGN</small>
                  <h2>板书设计</h2>
                </div>
                <button @click="toggleLock('board_1')">
                  <Lock v-if="isLocked('board_1')" :size="14" /><Unlock
                    v-else
                    :size="14"
                  />
                </button>
              </header>
              <div class="board">
                <div
                  v-for="[area, text] in Object.entries(
                    selected.board_plan.layout,
                  )"
                  :key="area"
                >
                  <small>{{ area }}</small>
                  <p>{{ text }}</p>
                </div>
              </div>
            </section>
            <section class="prep-card content-section">
              <header>
                <div>
                  <small>DIFFERENTIATION</small>
                  <h2>动态分层支持</h2>
                </div>
                <Layers3 :size="20" />
              </header>
              <article
                v-for="layer in selected.differentiation_plan"
                :key="layer.layer_id"
                class="layer-row"
              >
                <span :class="layer.layer_id">{{
                  layer.layer_id === "support"
                    ? "支架"
                    : layer.layer_id === "core"
                      ? "核心"
                      : "进阶"
                }}</span>
                <div>
                  <strong>{{ layer.target_profile }}</strong>
                  <p>{{ layer.task_adjustment }}</p>
                </div>
              </article>
            </section>
          </div>

          <section v-if="detailPage === 3" class="prep-card content-section">
            <header>
              <div>
                <small>ASSESSMENT & HOMEWORK</small>
                <h2>课堂检测与作业</h2>
              </div>
              <FlaskConical :size="20" />
            </header>
            <article
              v-for="item in selected.assessments"
              :key="item.question_id"
              class="assessment-row"
            >
              <button @click="toggleLock(item.question_id)">
                <Lock v-if="isLocked(item.question_id)" :size="14" /><Unlock
                  v-else
                  :size="14"
                />
              </button>
              <span>{{ item.purpose === "homework" ? "作业" : "检测" }}</span>
              <div>
                <strong>{{ item.prompt }}</strong>
                <details>
                  <summary>答案提纲与评分点</summary>
                  <p>{{ item.answer_outline }}</p>
                  <ol>
                    <li v-for="point in item.scoring_rubric" :key="point">
                      {{ point }}
                    </li>
                  </ol>
                </details>
                <small
                  >{{ item.knowledge_tags.join(" · ") }} · 难度
                  {{ item.difficulty }}</small
                >
              </div>
            </article>
          </section>

          <section v-if="detailPage === 4" class="prep-card content-section">
            <header>
              <div>
                <small>ALIGNMENT MATRIX</small>
                <h2>目标—活动—评价一致性</h2>
              </div>
              <ShieldCheck :size="20" />
            </header>
            <div class="alignment-table">
              <div class="alignment-head">
                <span>目标</span><span>活动</span><span>评价</span
                ><span>状态</span>
              </div>
              <article
                v-for="row in selected.alignment_matrix"
                :key="row.objective_id"
              >
                <strong>{{ row.objective_description }}</strong
                ><span>{{ row.activity_ids.join("、") }}</span
                ><span>{{ row.assessment_ids.join("、") }}</span
                ><i :class="row.status">{{
                  row.status === "pass" ? "通过" : "未通过"
                }}</i>
              </article>
            </div>
          </section>

          <section v-if="detailPage === 4" class="prep-card content-section">
            <header>
              <div>
                <small>SOURCE PROVENANCE</small>
                <h2>参考来源与版权边界</h2>
              </div>
              <BookOpenCheck :size="20" />
            </header>
            <article
              v-for="resource in selected.resources"
              :key="resource.resource_id"
              class="resource-row"
            >
              <ShieldCheck :size="17" />
              <div>
                <strong>{{ resource.title }}</strong>
                <p>
                  {{ resource.source_organization }} ·
                  {{ resource.source_location }}
                </p>
                <small
                  >{{ resource.material_type }} · SHA256
                  {{ resource.checksum_verified ? "已核验" : "待核验" }}</small
                >
              </div>
            </article>
          </section>
          <PaginationControls
            :page="detailPage"
            :total="4"
            :page-size="1"
            label="个教案页面"
            @change="detailPage = $event"
          />
        </template>
      </main>
    </div>
  </div>
</template>

<style scoped>
.prep-workspace {
  --p: #168363;
  --pd: #125b47;
  display: grid;
  gap: 16px;
}
.prep-hero {
  display: flex;
  min-height: 190px;
  align-items: center;
  justify-content: space-between;
  gap: 28px;
  padding: 32px 36px;
  color: #fff;
  background:
    radial-gradient(
      circle at 80% 10%,
      rgba(255, 255, 255, 0.17),
      transparent 32%
    ),
    linear-gradient(135deg, #103f35, #168365 72%, #4bad89);
  border-radius: 18px;
}
.prep-hero > div:first-child {
  max-width: 760px;
}
.prep-hero small {
  color: #afe2d1;
  font-size: 8px;
  font-weight: 850;
  letter-spacing: 0.14em;
}
.prep-hero h1 {
  margin: 12px 0 8px;
  font-size: clamp(26px, 3vw, 40px);
  letter-spacing: -0.04em;
}
.prep-hero p {
  margin: 0;
  color: #d1eee5;
  font-size: 10px;
  line-height: 1.8;
}
.resource-health {
  display: flex;
  min-width: 245px;
  align-items: center;
  gap: 12px;
  padding: 16px;
  border: 1px solid rgba(255, 255, 255, 0.18);
  background: rgba(255, 255, 255, 0.09);
  border-radius: 12px;
}
.resource-health span {
  display: grid;
  gap: 5px;
}
.resource-health strong {
  font-size: 10px;
}
.resource-health small {
  font-size: 7px;
}
.prep-error,
.prep-notice {
  display: flex;
  align-items: center;
  gap: 7px;
  margin: 0;
  padding: 11px 13px;
  border-radius: 9px;
  font-size: 9px;
}
.prep-error {
  color: #a13d3d;
  background: #fff0ef;
}
.prep-notice {
  color: #17674f;
  background: #e5f6ef;
}
.prep-empty,
.prep-welcome {
  display: grid;
  min-height: 330px;
  place-content: center;
  justify-items: center;
  color: #759187;
  text-align: center;
}
.prep-empty {
  background: #fff;
  border: 1px solid #dce8e3;
  border-radius: 15px;
}
.prep-empty strong,
.prep-welcome h2 {
  margin: 12px 0 4px;
  color: #315c4f;
  font-size: 14px;
}
.prep-empty p,
.prep-welcome p {
  max-width: 490px;
  color: #7f968e;
  font-size: 9px;
  line-height: 1.7;
}
.prep-layout {
  display: grid;
  grid-template-columns: 370px minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}
.prep-layout > aside,
.prep-layout > main {
  display: grid;
  gap: 16px;
}
.prep-card {
  padding: 21px;
  border: 1px solid #dce8e3;
  background: #fff;
  border-radius: 14px;
  box-shadow: 0 6px 20px rgba(29, 75, 61, 0.04);
}
.prep-card > header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding-bottom: 14px;
  border-bottom: 1px solid #edf2f0;
}
.prep-card > header small {
  color: #4c927d;
  font-size: 7px;
  font-weight: 850;
  letter-spacing: 0.13em;
}
.prep-card > header h2 {
  margin: 4px 0 0;
  font-size: 14px;
}
.generation-form,
.revision-panel,
.feedback-panel {
  display: grid;
  gap: 13px;
}
.generation-form label,
.revision-panel label,
.feedback-panel label {
  display: grid;
  gap: 6px;
}
.generation-form label > span,
.revision-panel label > span,
.feedback-panel label > span {
  color: #456b60;
  font-size: 8px;
  font-weight: 750;
}
.topic-source > span {
  color: #456b60;
  font-size: 8px;
  font-weight: 750;
}
.topic-source-options {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}
.topic-source-options button {
  display: flex;
  min-height: 42px;
  align-items: center;
  justify-content: center;
  gap: 6px;
  color: #53756b;
  border: 1px solid #d7e5e0;
  background: #fbfdfc;
  border-radius: 9px;
  font-size: 10px;
  font-weight: 750;
  transition:
    border-color 160ms ease,
    background 160ms ease,
    color 160ms ease;
}
.topic-source-options button:hover,
.topic-source-options button:focus-visible {
  border-color: #7bb6a3;
}
.topic-source-options button.active {
  color: #126149;
  border-color: #55a58c;
  background: #eaf6f1;
  box-shadow: inset 0 0 0 1px rgba(22, 131, 99, 0.08);
}
.chapter-topic-panel {
  display: grid;
  gap: 10px;
  padding: 12px;
  border: 1px solid #dcebe5;
  background: linear-gradient(145deg, #f8fcfa, #edf7f3);
  border-radius: 11px;
}
.selected-chapter {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 10px;
  background: #fff;
  border-radius: 9px;
}
.selected-chapter > div {
  display: grid;
  min-width: 0;
  gap: 3px;
}
.selected-chapter small,
.chapter-evidence {
  color: #6f8b82;
  font-size: 9px;
  line-height: 1.5;
}
.selected-chapter strong {
  overflow: hidden;
  color: #214f42;
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.selected-chapter button {
  display: flex;
  min-height: 34px;
  flex: 0 0 auto;
  align-items: center;
  gap: 5px;
  padding: 0 10px;
  color: #fff;
  border: 0;
  background: var(--p);
  border-radius: 8px;
  font-size: 9px;
  font-weight: 750;
}
.selected-chapter button:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}
.chapter-evidence {
  overflow-wrap: anywhere;
}
.topic-source {
  display: grid;
  gap: 7px;
}
.generation-form input,
.generation-form select,
.generation-form textarea,
.revision-panel input,
.revision-panel select,
.revision-panel textarea,
.feedback-panel input,
.feedback-panel textarea {
  width: 100%;
  padding: 0 10px;
  color: #264c41;
  border: 1px solid #d7e5e0;
  outline: 0;
  background: #fbfdfc;
  border-radius: 8px;
  font: inherit;
  font-size: 9px;
}
.generation-form input,
.generation-form select,
.revision-panel input,
.revision-panel select,
.feedback-panel input {
  height: 40px;
}
.generation-form textarea,
.revision-panel textarea,
.feedback-panel textarea {
  padding-block: 9px;
  line-height: 1.6;
  resize: vertical;
}
.form-pair {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 9px;
}
.search-field {
  display: flex;
}
.search-field input {
  border-radius: 8px 0 0 8px;
}
.search-field button {
  width: 42px;
  color: #fff;
  border: 0;
  background: var(--p);
  border-radius: 0 8px 8px 0;
}
.prep-primary {
  display: flex;
  min-height: 42px;
  align-items: center;
  justify-content: center;
  gap: 6px;
  color: #fff;
  border: 0;
  background: linear-gradient(135deg, #157457, #1b9972);
  border-radius: 9px;
  font-size: 9px;
  font-weight: 800;
}
.prep-primary:disabled {
  opacity: 0.55;
}
.generation-form > p {
  display: flex;
  align-items: center;
  gap: 5px;
  margin: 0;
  color: #7d938b;
  font-size: 7px;
}
.searched article,
.resource-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 11px 1px;
  border-bottom: 1px solid #edf2f0;
}
.searched article div,
.resource-row div {
  display: grid;
  gap: 3px;
}
.searched strong,
.resource-row strong {
  font-size: 8px;
}
.searched small,
.resource-row small {
  color: #789188;
  font-size: 7px;
}
.history > header button {
  color: #598176;
  border: 0;
  background: transparent;
}
.history > button {
  display: flex;
  width: 100%;
  align-items: center;
  gap: 8px;
  padding: 11px 5px;
  color: #496b61;
  border: 0;
  border-bottom: 1px solid #edf2f0;
  background: transparent;
  text-align: left;
}
.history > button.active {
  color: #126;
}
.history > button > span {
  padding: 5px 6px;
  color: #176f54;
  background: #e5f5ef;
  border-radius: 5px;
  font-size: 7px;
}
.history > button > div {
  display: grid;
  min-width: 0;
  flex: 1;
  gap: 3px;
}
.history > button strong {
  overflow: hidden;
  font-size: 8px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.history > button small,
.history > p {
  color: #83978f;
  font-size: 7px;
}
.mini-loading {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 16px;
  color: #729087;
  font-size: 8px;
}
.plan-heading h1 {
  margin: 14px 0 7px;
  font-size: 23px;
}
.plan-heading > p {
  margin: 0;
  color: #657f76;
  font-size: 9px;
  line-height: 1.7;
}
.plan-meta,
.quality-row,
.plan-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
}
.plan-meta span {
  padding: 5px 7px;
  color: #52766b;
  background: #eef6f3;
  border-radius: 5px;
  font-size: 7px;
}
.plan-meta span.teacher_review {
  color: #8a671d;
  background: #fff4d7;
}
.plan-meta span.approved,
.plan-meta span.published {
  color: #137052;
  background: #def4ea;
}
.quality-row {
  margin-top: 15px;
  padding: 11px;
  background: #f7fbf9;
  border-radius: 8px;
}
.quality-row span {
  display: flex;
  align-items: center;
  gap: 4px;
  color: #68867c;
  font-size: 7px;
}
.quality-row svg {
  width: 13px;
  height: 13px;
}
.quality-row span.pass {
  color: #17805f;
}
.quality-row span.fail {
  color: #b54444;
}
.plan-actions {
  margin-top: 14px;
}
.plan-actions button {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 8px 10px;
  color: #246b56;
  border: 1px solid #c8ded6;
  background: #fff;
  border-radius: 7px;
  font-size: 8px;
}
.plan-actions button.approve,
.plan-actions button.publish {
  color: #fff;
  border-color: var(--p);
  background: var(--p);
}
.revision-panel,
.feedback-panel {
  border-color: #bcded2;
  background: #fbfefc;
}
.content-section > header > button,
.objective-row > button,
.activity-row > button,
.assessment-row > button {
  color: #64887c;
  border: 0;
  background: transparent;
}
.objective-row,
.activity-row,
.assessment-row {
  display: grid;
  grid-template-columns: 24px 35px 1fr;
  gap: 9px;
  padding: 14px 1px;
  border-bottom: 1px solid #edf2f0;
}
.objective-row > span {
  display: grid;
  width: 28px;
  height: 28px;
  place-items: center;
  color: #fff;
  background: var(--p);
  border-radius: 7px;
  font-size: 8px;
}
.objective-row strong,
.activity-row strong,
.assessment-row strong {
  font-size: 9px;
}
.objective-row p,
.activity-row p,
.assessment-row p {
  margin: 5px 0;
  color: #6c857c;
  font-size: 8px;
  line-height: 1.65;
}
.objective-row small,
.activity-row small,
.assessment-row small {
  display: inline-block;
  margin: 3px 5px 0 0;
  padding: 3px 5px;
  color: #29715c;
  background: #eaf6f1;
  border-radius: 4px;
  font-size: 7px;
}
.activity-row time {
  color: #167657;
  font-size: 12px;
  font-weight: 850;
}
.activity-row p b {
  color: #38685a;
}
.two-column {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
.board {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-top: 13px;
  padding: 13px;
  color: #e5f3ee;
  background: #173e34;
  border-radius: 8px;
}
.board div {
  min-height: 70px;
  padding: 9px;
  border: 1px dashed #4d796c;
}
.board small {
  color: #82b5a5;
  font-size: 7px;
}
.board p {
  font-size: 8px;
  line-height: 1.6;
}
.layer-row {
  display: flex;
  gap: 8px;
  padding: 11px 0;
  border-bottom: 1px solid #edf2f0;
}
.layer-row > span {
  height: max-content;
  padding: 5px 6px;
  border-radius: 5px;
  font-size: 7px;
}
.layer-row > span.support {
  color: #8b6821;
  background: #fff2d5;
}
.layer-row > span.core {
  color: #176e53;
  background: #e3f4ed;
}
.layer-row > span.advanced {
  color: #4c62a0;
  background: #eaf0ff;
}
.layer-row strong {
  font-size: 8px;
}
.layer-row p,
.resource-row p {
  margin: 5px 0;
  color: #70877f;
  font-size: 7px;
  line-height: 1.6;
}
.assessment-row > span {
  height: max-content;
  padding: 5px;
  color: #216d56;
  background: #e4f4ed;
  border-radius: 5px;
  font-size: 7px;
}
.assessment-row details {
  margin: 7px 0;
  color: #57766c;
  font-size: 8px;
}
.assessment-row summary {
  cursor: pointer;
  color: #237259;
}
.assessment-row ol {
  padding-left: 17px;
}
.alignment-table {
  overflow: auto;
  margin-top: 10px;
}
.alignment-head,
.alignment-table article {
  display: grid;
  min-width: 620px;
  grid-template-columns: 2fr 1fr 1fr 65px;
  gap: 10px;
  align-items: center;
  padding: 10px;
  border-bottom: 1px solid #edf2f0;
}
.alignment-head {
  color: #81958e;
  font-size: 7px;
}
.alignment-table article {
  font-size: 7px;
}
.alignment-table article strong {
  font-size: 8px;
}
.alignment-table i {
  width: max-content;
  padding: 4px 6px;
  color: #176f54;
  background: #e2f4ec;
  border-radius: 4px;
  font-style: normal;
}
.alignment-table i.fail {
  color: #a44242;
  background: #ffeded;
}
.spin {
  animation: prep-spin 0.8s linear infinite;
}
@keyframes prep-spin {
  to {
    transform: rotate(360deg);
  }
}
@media (max-width: 1100px) {
  .prep-layout {
    grid-template-columns: 1fr;
  }
  .prep-layout > aside {
    grid-template-columns: 1fr 1fr;
  }
  .generation-form {
    grid-row: span 2;
  }
}
@media (max-width: 780px) {
  .prep-hero {
    align-items: flex-start;
    flex-direction: column;
    padding: 26px 22px;
  }
  .resource-health {
    width: 100%;
  }
  .prep-layout > aside {
    grid-template-columns: 1fr;
  }
  .two-column {
    grid-template-columns: 1fr;
  }
  .form-pair {
    grid-template-columns: 1fr;
  }
  .objective-row,
  .activity-row,
  .assessment-row {
    grid-template-columns: 22px 30px 1fr;
  }
  .prep-card {
    padding: 17px;
  }
}
/* Readable teaching content and page-based lesson navigation. */
.prep-workspace {
  font-size: 15px;
  line-height: 1.55;
}
.prep-hero small {
  font-size: 12px;
}
.prep-hero p {
  font-size: 15px;
}
.resource-health strong {
  font-size: 15px;
}
.resource-health small {
  font-size: 12px;
}
.prep-layout {
  grid-template-columns: 410px minmax(0, 1fr);
}
.prep-card > header small {
  font-size: 11px;
}
.prep-card > header h2 {
  font-size: 19px;
}
.generation-form label > span,
.revision-panel label > span,
.feedback-panel label > span {
  font-size: 14px;
}
.generation-form input,
.generation-form select,
.generation-form textarea,
.revision-panel input,
.revision-panel select,
.revision-panel textarea,
.feedback-panel input,
.feedback-panel textarea {
  font-size: 15px;
}
.generation-form input,
.generation-form select,
.revision-panel input,
.revision-panel select,
.feedback-panel input {
  height: 48px;
}
.prep-primary {
  min-height: 48px;
  font-size: 14px;
}
.generation-form > p {
  font-size: 12px;
}
.searched strong,
.resource-row strong,
.history > button strong {
  font-size: 14px;
}
.searched small,
.resource-row small,
.history > button small,
.history > p {
  font-size: 12px;
}
.history > button {
  min-height: 62px;
}
.history > button > span {
  font-size: 12px;
}
.plan-meta span {
  font-size: 12px;
}
.plan-heading > p {
  font-size: 14px;
}
.quality-row span {
  font-size: 13px;
}
.plan-actions button {
  min-height: 42px;
  font-size: 14px;
}
.lesson-page-tabs {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  padding: 8px;
  border: 1px solid #dce8e3;
  background: #fff;
  border-radius: 13px;
}
.lesson-page-tabs button {
  display: flex;
  min-height: 48px;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: #58766c;
  border: 0;
  background: #f4f8f6;
  border-radius: 9px;
  font-size: 14px;
  font-weight: 700;
}
.lesson-page-tabs button span {
  display: grid;
  width: 25px;
  height: 25px;
  place-items: center;
  color: #176f54;
  background: #dff2ea;
  border-radius: 50%;
  font-size: 12px;
}
.lesson-page-tabs button.active {
  color: #fff;
  background: #168363;
}
.lesson-page-tabs button.active span {
  color: #168363;
  background: #fff;
}
.objective-row strong,
.activity-row strong,
.assessment-row strong {
  font-size: 15px;
}
.objective-row p,
.activity-row p,
.assessment-row p {
  font-size: 14px;
}
.objective-row small,
.activity-row small,
.assessment-row small {
  font-size: 12px;
}
.activity-row time {
  font-size: 17px;
}
.board small {
  font-size: 12px;
}
.board p {
  font-size: 14px;
}
.layer-row strong {
  font-size: 14px;
}
.layer-row p,
.resource-row p {
  font-size: 13px;
}
.layer-row > span,
.assessment-row > span {
  font-size: 12px;
}
.assessment-row details {
  font-size: 13px;
}
.alignment-table {
  overflow: visible;
}
.alignment-head,
.alignment-table article {
  min-width: 0;
  grid-template-columns:
    minmax(180px, 2fr) minmax(90px, 1fr) minmax(90px, 1fr)
    70px;
  font-size: 12px;
}
.alignment-table article strong {
  font-size: 14px;
}
.prep-error,
.prep-notice,
.prep-empty p,
.prep-welcome p {
  font-size: 13px;
}
@media (max-width: 1200px) {
  .prep-layout {
    grid-template-columns: 1fr;
  }
  .prep-layout > aside {
    grid-template-columns: 1fr 1fr;
  }
}
@media (max-width: 780px) {
  .prep-layout > aside,
  .lesson-page-tabs {
    grid-template-columns: 1fr;
  }
  .alignment-head {
    display: none;
  }
  .alignment-table article {
    grid-template-columns: 1fr;
  }
  .alignment-table article span:before {
    content: "关联项：";
    font-weight: 700;
  }
}
.catalog-hint {
  color: #789188;
  font-size: 12px;
  line-height: 1.55;
}
.plan-record-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 14px;
}
.plan-record-summary span {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 7px 9px;
  color: #426c5f;
  background: #f0f7f4;
  border-radius: 7px;
  font-size: 12px;
}
.plan-actions button.download-plan {
  color: #fff;
  border-color: #17795b;
  background: #17795b;
}
</style>
