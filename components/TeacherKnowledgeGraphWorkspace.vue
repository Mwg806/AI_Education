<script setup lang="ts">
import {
  ArrowLeft,
  ArrowRight,
  BookOpenText,
  Check,
  Download,
  FileJson,
  Focus,
  Layers3,
  Link2,
  LoaderCircle,
  Maximize2,
  Network,
  RefreshCw,
  Search,
  Sparkles,
  WandSparkles,
  ZoomIn,
  ZoomOut,
} from "@lucide/vue";
import {
  CanvasEvent,
  Graph,
  NodeEvent,
  type EdgeData,
  type NodeData,
} from "@antv/g6";
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  shallowRef,
} from "vue";

import { subjectLabels } from "@/lib/curriculum-catalog";
import {
  generateTeacherKnowledgeGraph,
  type KnowledgeGraphNodeType,
  type KnowledgeGraphRelationType,
  type LessonPlan,
  type ProfessionalKnowledgeGraph,
  type ProfessionalKnowledgeGraphEdge,
  type ProfessionalKnowledgeGraphNode,
} from "@/lib/teacher-client";
import type { SubjectKey } from "@/lib/types";

const props = withDefaults(
  defineProps<{
    defaultSubject?: SubjectKey | null;
    sourcePlan?: LessonPlan | null;
  }>(),
  { defaultSubject: null, sourcePlan: null },
);
const emit = defineEmits<{ backToLibrary: [] }>();

type DetailLevel = "简洁" | "标准" | "详细";
type NodeTheme = { fill: string; stroke: string; text: string };

const subjectOptions = Object.entries(subjectLabels) as [SubjectKey, string][];
const selectedSubject = ref<SubjectKey>(
  props.defaultSubject || "mathematics",
);
const graphNameHint = ref("");
const detailLevel = ref<DetailLevel>("标准");
const lessonContent = ref("");
const graphResult = ref<ProfessionalKnowledgeGraph | null>(null);
const selectedNodeId = ref("");
const searchQuery = ref("");
const error = ref("");
const generating = ref(false);
const generationStage = ref(0);
const graphContainer = ref<HTMLElement | null>(null);
const graphInstance = shallowRef<Graph | null>(null);
let generationTimer: number | undefined;
let resizeObserver: ResizeObserver | null = null;

const detailLevels: Array<{
  value: DetailLevel;
  label: string;
  description: string;
}> = [
  { value: "简洁", label: "简洁", description: "8–16 个节点" },
  { value: "标准", label: "标准", description: "14–28 个节点" },
  { value: "详细", label: "详细", description: "24–45 个节点" },
];

const generationStages = [
  "理解教案结构",
  "提取核心知识",
  "分析知识关系",
  "生成专业图谱",
];

const nodeTypeLabels: Record<KnowledgeGraphNodeType, string> = {
  course: "课程主题",
  chapter: "章节",
  core_knowledge: "核心知识",
  knowledge: "知识点",
  sub_knowledge: "子知识点",
  definition: "定义",
  principle: "原理",
  formula: "公式",
  method: "方法",
  example: "例题",
  error: "易错点",
  prerequisite: "先修知识",
  application: "应用",
  ability: "能力",
  question: "问题",
};

const relationTypeLabels: Record<KnowledgeGraphRelationType, string> = {
  contains: "包含",
  prerequisite_of: "先修于",
  derives: "推导",
  depends_on: "依赖",
  applies_to: "应用于",
  example_of: "例证",
  confused_with: "易混淆",
  related_to: "相关",
  supports: "支撑",
  assesses: "评价",
};

const nodeThemes: Partial<Record<KnowledgeGraphNodeType, NodeTheme>> = {
  course: { fill: "#168363", stroke: "#0d5f48", text: "#ffffff" },
  chapter: { fill: "#dff5ed", stroke: "#269b78", text: "#125544" },
  core_knowledge: { fill: "#2c9a78", stroke: "#157156", text: "#ffffff" },
  knowledge: { fill: "#e6f2ff", stroke: "#4d89c8", text: "#285d91" },
  sub_knowledge: { fill: "#eff7ff", stroke: "#7da8d2", text: "#3d668c" },
  definition: { fill: "#e9efff", stroke: "#647dd6", text: "#3f5296" },
  principle: { fill: "#f0eaff", stroke: "#8b6ac9", text: "#5f4598" },
  formula: { fill: "#f1e9ff", stroke: "#9065d0", text: "#5c3f91" },
  method: { fill: "#fff0dc", stroke: "#d98b32", text: "#86551f" },
  example: { fill: "#fff6d9", stroke: "#d4a32e", text: "#785b13" },
  error: { fill: "#ffe9e3", stroke: "#d8705b", text: "#974637" },
  prerequisite: { fill: "#edf1f4", stroke: "#738597", text: "#435462" },
  application: { fill: "#fff1e6", stroke: "#d98550", text: "#89502d" },
  ability: { fill: "#e1f6f5", stroke: "#329996", text: "#216b69" },
  question: { fill: "#fceafa", stroke: "#bd6eae", text: "#7d4775" },
};

const defaultNodeTheme: NodeTheme = {
  fill: "#edf5f1",
  stroke: "#5c8e7f",
  text: "#365f53",
};

const contentLength = computed(() => lessonContent.value.trim().length);
const canGenerate = computed(
  () => contentLength.value >= 80 && !generating.value,
);
const selectedNode = computed(() =>
  graphResult.value?.nodes.find((node) => node.id === selectedNodeId.value),
);
const selectedConnections = computed(() => {
  if (!graphResult.value || !selectedNode.value) return [];
  return graphResult.value.edges
    .filter(
      (edge) =>
        edge.source === selectedNode.value?.id ||
        edge.target === selectedNode.value?.id,
    )
    .map((edge) => {
      const outbound = edge.source === selectedNode.value?.id;
      const relatedId = outbound ? edge.target : edge.source;
      return {
        edge,
        outbound,
        node: graphResult.value?.nodes.find((item) => item.id === relatedId),
      };
    });
});
const searchMatches = computed(() => {
  const keyword = searchQuery.value.trim().toLocaleLowerCase();
  if (!keyword || !graphResult.value) return [];
  return graphResult.value.nodes
    .filter((node) =>
      `${node.name} ${node.chapter} ${node.keywords.join(" ")}`
        .toLocaleLowerCase()
        .includes(keyword),
    )
    .slice(0, 6);
});
const typeDistribution = computed(() => {
  if (!graphResult.value) return [];
  const counts = new Map<KnowledgeGraphNodeType, number>();
  graphResult.value.nodes.forEach((node) =>
    counts.set(node.type, (counts.get(node.type) || 0) + 1),
  );
  return Array.from(counts.entries())
    .map(([type, count]) => ({ type, count, label: nodeTypeLabels[type] }))
    .sort((a, b) => b.count - a.count);
});

function themeFor(type: KnowledgeGraphNodeType): NodeTheme {
  return nodeThemes[type] || defaultNodeTheme;
}

function nodeMeta(datum: NodeData): ProfessionalKnowledgeGraphNode & {
  degree: number;
} {
  return datum.data as unknown as ProfessionalKnowledgeGraphNode & {
    degree: number;
  };
}

function edgeMeta(datum: EdgeData): ProfessionalKnowledgeGraphEdge {
  return datum.data as unknown as ProfessionalKnowledgeGraphEdge;
}

function shortLabel(value: string): string {
  return value.length > 10 ? `${value.slice(0, 9)}…` : value;
}

function graphLayout() {
  return {
    type: "d3-force" as const,
    animation: false,
    link: { distance: 135, strength: 0.75 },
    manyBody: { strength: -470, distanceMin: 40, distanceMax: 720 },
    collide: { radius: 54, strength: 0.9, iterations: 2 },
  };
}

function destroyGraph() {
  resizeObserver?.disconnect();
  resizeObserver = null;
  graphInstance.value?.destroy();
  graphInstance.value = null;
}

async function renderGraph() {
  if (!graphResult.value) return;
  await nextTick();
  if (!graphContainer.value) return;
  destroyGraph();

  const degree = new Map<string, number>();
  graphResult.value.edges.forEach((edge) => {
    degree.set(edge.source, (degree.get(edge.source) || 0) + 1);
    degree.set(edge.target, (degree.get(edge.target) || 0) + 1);
  });

  const instance = new Graph({
    container: graphContainer.value,
    autoFit: "view",
    padding: 72,
    zoomRange: [0.22, 3],
    animation: false,
    data: {
      nodes: graphResult.value.nodes.map((node) => ({
        id: node.id,
        data: { ...node, degree: degree.get(node.id) || 0 },
      })),
      edges: graphResult.value.edges.map((edge) => ({
        id: edge.id,
        source: edge.source,
        target: edge.target,
        data: { ...edge },
      })),
    },
    layout: graphLayout(),
    behaviors: ["drag-canvas", "zoom-canvas", "drag-element"],
    node: {
      type: "circle",
      style: (datum) => {
        const node = nodeMeta(datum);
        const theme = themeFor(node.type);
        return {
          size: 30 + node.importance * 4 + Math.min(node.degree, 4) * 2,
          fill: theme.fill,
          stroke: theme.stroke,
          lineWidth: node.importance >= 4 ? 2.4 : 1.7,
          shadowColor: "rgba(31, 74, 61, 0.14)",
          shadowBlur: 14,
          cursor: "pointer",
          label: true,
          labelText: shortLabel(node.name),
          labelPlacement: "bottom",
          labelOffsetY: 7,
          labelFontSize: 12,
          labelFontWeight: 600,
          labelFill: theme.text === "#ffffff" ? theme.stroke : theme.text,
          labelBackground: true,
          labelBackgroundFill: "rgba(255, 255, 255, 0.91)",
          labelBackgroundRadius: 5,
          labelPadding: [3, 5],
        };
      },
      state: {
        selected: {
          lineWidth: 4,
          stroke: "#f0a83d",
          halo: true,
          haloStroke: "rgba(240, 168, 61, 0.24)",
          haloLineWidth: 12,
        },
      },
    },
    edge: {
      type: (datum) => {
        const relation = edgeMeta(datum).relation;
        return relation === "related_to" || relation === "confused_with"
          ? "quadratic"
          : "line";
      },
      style: (datum) => {
        const edge = edgeMeta(datum);
        const highlighted = edge.strength >= 4;
        return {
          stroke:
            edge.relation === "confused_with"
              ? "#d8705b"
              : highlighted
                ? "#88a99e"
                : "#c0d0ca",
          lineWidth: 0.8 + edge.strength * 0.32,
          lineOpacity: highlighted ? 0.88 : 0.68,
          lineDash: edge.relation === "confused_with" ? [5, 4] : undefined,
          endArrow: true,
          endArrowSize: 6,
          label: highlighted,
          labelText: highlighted ? edge.label : "",
          labelFontSize: 10,
          labelFill: "#698078",
          labelBackground: true,
          labelBackgroundFill: "rgba(248, 251, 249, 0.9)",
          labelPadding: [2, 4],
          labelAutoRotate: false,
        };
      },
    },
  });

  instance.on(NodeEvent.CLICK, (event: any) => {
    const id = event.target?.id as string | undefined;
    if (id) void selectNode(id, false);
  });
  instance.on(CanvasEvent.CLICK, () => void clearSelection());
  graphInstance.value = instance;
  await instance.render();

  const initialNode =
    graphResult.value.nodes.find((node) => node.type === "core_knowledge") ||
    graphResult.value.nodes.find((node) => node.type === "course") ||
    graphResult.value.nodes[0];
  if (initialNode) await selectNode(initialNode.id, false);

  resizeObserver = new ResizeObserver(() => instance.resize());
  resizeObserver.observe(graphContainer.value);
}

async function selectNode(id: string, focus = true) {
  const instance = graphInstance.value;
  if (instance && selectedNodeId.value && selectedNodeId.value !== id) {
    await instance.setElementState(selectedNodeId.value, []);
  }
  selectedNodeId.value = id;
  if (instance) {
    await instance.setElementState(id, ["selected"]);
    if (focus) await instance.focusElement(id, { duration: 350 });
  }
  searchQuery.value = "";
}

async function clearSelection() {
  if (graphInstance.value && selectedNodeId.value) {
    await graphInstance.value.setElementState(selectedNodeId.value, []);
  }
  selectedNodeId.value = "";
}

function loadExample() {
  graphNameHint.value = "函数单调性与最值";
  selectedSubject.value = "mathematics";
  detailLevel.value = "标准";
  lessonContent.value = `课题：函数的单调性与最值
教学目标：理解增函数、减函数的定义，能够使用图像法和定义法判断函数在给定区间上的单调性，并利用单调性求函数最值。
先修知识：函数的定义域、函数图像、区间表示、一次函数和二次函数的基本性质。
核心内容：设函数 f(x) 的定义域为 I。若对于区间 I 内任意 x₁＜x₂，都有 f(x₁)＜f(x₂)，则 f(x) 在 I 上单调递增；若都有 f(x₁)＞f(x₂)，则函数单调递减。单调性必须针对定义域内的某个区间讨论。
教学活动一：观察三个函数图像，描述函数值随自变量增大的变化趋势，由直观语言过渡到符号定义。
教学活动二：使用定义法证明 f(x)=2x+1 在实数集上单调递增。步骤为任取 x₁＜x₂、作差 f(x₁)-f(x₂)、判断符号、得出结论。
教学活动三：根据二次函数图像写出单调区间，并结合开口方向和对称轴判断最值。
典型应用：已知函数在闭区间上单调递增，则最大值出现在右端点，最小值出现在左端点。
易错点：脱离定义域讨论单调性；用“某几个点的函数值变大”代替任意性；多个单调区间用并集符号连接；求最值时遗漏闭区间端点。
课堂评价：学生独立判断分段函数的单调区间，并说明判断依据；能够指出一个错误证明中缺失的任意性条件。`;
  error.value = "";
}

function lessonPlanContent(plan: LessonPlan): string {
  const lines = [
    `教案名称：${plan.title}`,
    `课题：${plan.context.topic}`,
    `教材：${plan.context.textbook_version}`,
    `课型：${plan.context.lesson_type}`,
    `课时：${plan.context.duration_minutes} 分钟`,
    `教学概述：${plan.summary}`,
    `教学重点：${plan.key_points.join("；")}`,
    `教学难点：${plan.difficult_points.join("；")}`,
    "教学目标：",
    ...plan.objectives.map(
      (item, index) =>
        `${index + 1}. ${item.description}；可观察行为：${item.observable_behavior}；能力：${item.exam_ability_tags.join("、")}`,
    ),
    "课堂活动：",
    ...plan.activities.map(
      (item, index) =>
        `${index + 1}. ${item.stage}（${item.duration_minutes}分钟）：教师${item.teacher_action}；学生${item.student_action}；预期产出${item.expected_output}；评价方式${item.assessment_method}`,
    ),
    "板书结构：",
    ...Object.entries(plan.board_plan.layout).map(
      ([area, content]) => `${area}：${content}`,
    ),
    "课堂检测与作业：",
    ...plan.assessments.map(
      (item, index) =>
        `${index + 1}. ${item.prompt}；考查知识：${item.knowledge_tags.join("、")}；能力：${item.ability_tags.join("、")}；常见错误：${item.common_error_tags.join("、") || "未标注"}`,
    ),
    "分层支持：",
    ...plan.differentiation_plan.map(
      (item) => `${item.layer_id}：${item.target_profile}；${item.task_adjustment}`,
    ),
    `课堂应变：${plan.contingency_paths.join("；")}`,
  ];
  return lines.join("\n").slice(0, 30_000);
}

function sourceCacheKey(plan: LessonPlan): string {
  return `wenlu_teacher_knowledge_graph:${plan.lesson_plan_id}:v${plan.version}`;
}

function restoreCachedGraph(plan: LessonPlan): ProfessionalKnowledgeGraph | null {
  try {
    const cached = window.sessionStorage.getItem(sourceCacheKey(plan));
    if (!cached) return null;
    const parsed = JSON.parse(cached) as ProfessionalKnowledgeGraph;
    return parsed.graph_name && parsed.nodes?.length && parsed.edges?.length
      ? parsed
      : null;
  } catch {
    return null;
  }
}

function cacheSourceGraph(graph: ProfessionalKnowledgeGraph) {
  if (!props.sourcePlan) return;
  try {
    window.sessionStorage.setItem(
      sourceCacheKey(props.sourcePlan),
      JSON.stringify(graph),
    );
  } catch {
    // 图谱缓存失败不影响当前查看与导出。
  }
}

async function openSourcePlan() {
  if (!props.sourcePlan) return;
  selectedSubject.value = props.sourcePlan.context.subject;
  graphNameHint.value = props.sourcePlan.title;
  lessonContent.value = lessonPlanContent(props.sourcePlan);
  const cached = restoreCachedGraph(props.sourcePlan);
  if (cached) {
    graphResult.value = cached;
    await renderGraph();
    return;
  }
  await generateGraph();
}

async function generateGraph() {
  error.value = "";
  if (contentLength.value < 80) {
    error.value = "请至少输入 80 个字的教案内容，让问鹿AI有足够依据分析。";
    return;
  }
  generating.value = true;
  generationStage.value = 0;
  window.clearInterval(generationTimer);
  generationTimer = window.setInterval(() => {
    generationStage.value = Math.min(
      generationStage.value + 1,
      generationStages.length - 1,
    );
  }, 4200);
  try {
    const response = await generateTeacherKnowledgeGraph({
      lessonContent: lessonContent.value.trim(),
      subject: selectedSubject.value,
      graphNameHint: graphNameHint.value.trim(),
      detailLevel: detailLevel.value,
    });
    graphResult.value = response.knowledge_graph;
    cacheSourceGraph(response.knowledge_graph);
    selectedNodeId.value = "";
    searchQuery.value = "";
    await renderGraph();
  } catch (cause) {
    error.value =
      cause instanceof Error ? cause.message : "知识图谱生成失败，请稍后重试";
  } finally {
    window.clearInterval(generationTimer);
    generating.value = false;
  }
}

async function fitGraph() {
  await graphInstance.value?.fitView({ when: "always", direction: "both" }, {
    duration: 350,
  });
}

async function zoomGraph(ratio: number) {
  await graphInstance.value?.zoomBy(ratio, { duration: 220 });
}

async function relayoutGraph() {
  if (!graphInstance.value) return;
  graphInstance.value.setLayout(graphLayout());
  await graphInstance.value.layout();
  await fitGraph();
}

function safeFileName(name: string): string {
  return name.replace(/[\\/:*?"<>|]/g, "-").trim() || "专业知识图谱";
}

async function exportPng() {
  if (!graphInstance.value || !graphResult.value) return;
  const url = await graphInstance.value.toDataURL({
    mode: "overall",
    type: "image/png",
  });
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${safeFileName(graphResult.value.graph_name)}.png`;
  anchor.click();
}

function exportJson() {
  if (!graphResult.value) return;
  const blob = new Blob([JSON.stringify(graphResult.value, null, 2)], {
    type: "application/json;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${safeFileName(graphResult.value.graph_name)}.json`;
  anchor.click();
  URL.revokeObjectURL(url);
}

onBeforeUnmount(() => {
  window.clearInterval(generationTimer);
  destroyGraph();
});
onMounted(() => void openSourcePlan());
</script>

<template>
  <div class="kg-page">
    <section class="kg-hero">
      <div class="kg-hero-copy">
        <button
          v-if="sourcePlan"
          type="button"
          class="kg-back-button"
          @click="emit('backToLibrary')"
        >
          <ArrowLeft :size="15" />返回我的备课方案
        </button>
        <span class="kg-eyebrow"><Network :size="15" /> KNOWLEDGE STUDIO</span>
        <h1>
          {{
            sourcePlan
              ? `《${sourcePlan.title}》知识图谱`
              : "把一份教案，变成一张可探索的知识网络。"
          }}
        </h1>
        <p>
          问鹿AI从教学内容中提取概念、方法、应用与易错关系，生成标准 JSON，
          再由 AntV G6 自动排布为专业知识图谱。
        </p>
      </div>
      <div class="kg-process" aria-label="知识图谱生成流程">
        <div><b>01</b><span><strong>教案正文</strong><small>输入教学依据</small></span></div>
        <ArrowRight :size="18" />
        <div><b>02</b><span><strong>问鹿AI</strong><small>结构化提取</small></span></div>
        <ArrowRight :size="18" />
        <div><b>03</b><span><strong>AntV G6</strong><small>自动生成图谱</small></span></div>
      </div>
    </section>

    <section class="kg-builder-grid">
      <form class="kg-input-card" @submit.prevent="generateGraph">
        <header>
          <span><BookOpenText :size="20" /></span>
          <div>
            <small>LESSON INPUT</small>
            <h2>输入教案内容</h2>
          </div>
          <button
            v-if="!sourcePlan"
            type="button"
            class="kg-example-button"
            @click="loadExample"
          >
            使用示例
          </button>
        </header>

        <div v-if="sourcePlan" class="kg-source-plan">
          <span><Network :size="18" /></span>
          <div>
            <small>当前备课方案 · v{{ sourcePlan.version }}</small>
            <strong>{{ sourcePlan.title }}</strong>
          </div>
          <b>{{ subjectLabels[sourcePlan.context.subject] }}</b>
        </div>

        <label class="kg-field">
          <span>学科</span>
          <select v-model="selectedSubject">
            <option v-for="[key, label] in subjectOptions" :key="key" :value="key">
              {{ label }}
            </option>
          </select>
        </label>

        <label class="kg-field">
          <span>图谱名称提示 <small>选填</small></span>
          <input
            v-model="graphNameHint"
            maxlength="120"
            placeholder="例如：函数单调性与最值"
          />
        </label>

        <div class="kg-field">
          <span>详细程度</span>
          <div class="kg-detail-levels">
            <button
              v-for="item in detailLevels"
              :key="item.value"
              type="button"
              :class="{ active: detailLevel === item.value }"
              @click="detailLevel = item.value"
            >
              <strong>{{ item.label }}</strong><small>{{ item.description }}</small>
            </button>
          </div>
        </div>

        <label class="kg-field kg-content-field">
          <span>教案正文 <small>至少 80 字</small></span>
          <textarea
            v-model="lessonContent"
            maxlength="30000"
            placeholder="粘贴课程目标、核心内容、教学活动、重难点、典型例题和易错点等教案正文……"
          />
          <small :class="{ warning: contentLength > 0 && contentLength < 80 }">
            {{ contentLength.toLocaleString("zh-CN") }} / 30,000 字
          </small>
        </label>

        <p v-if="error" class="kg-error">{{ error }}</p>

        <button class="kg-generate-button" :disabled="!canGenerate">
          <LoaderCircle v-if="generating" class="spin" :size="19" />
          <WandSparkles v-else :size="19" />
          <span>
            <strong>{{ generating ? "问鹿AI 正在生成" : "生成专业知识图谱" }}</strong>
            <small>{{ generating ? generationStages[generationStage] : "预计需要 20–60 秒" }}</small>
          </span>
          <ArrowRight v-if="!generating" :size="18" />
        </button>

        <div class="kg-quality-note">
          <Check :size="15" />
          <span>仅依据输入材料提取，不自动补造教材事实</span>
        </div>
      </form>

      <section class="kg-preview-card">
        <template v-if="graphResult">
          <header class="kg-result-head">
            <div>
              <span class="kg-result-mark"><Network :size="20" /></span>
              <div>
                <small>PROFESSIONAL KNOWLEDGE GRAPH</small>
                <h2>{{ graphResult.graph_name }}</h2>
              </div>
            </div>
            <div class="kg-result-stats">
              <span><strong>{{ graphResult.statistics.node_count }}</strong> 个节点</span>
              <i />
              <span><strong>{{ graphResult.statistics.edge_count }}</strong> 条关系</span>
            </div>
          </header>

          <div class="kg-summary-row">
            <p>{{ graphResult.summary }}</p>
            <div class="kg-type-legend">
              <span v-for="item in typeDistribution.slice(0, 5)" :key="item.type">
                <i :style="{ background: themeFor(item.type).stroke }" />
                {{ item.label }} {{ item.count }}
              </span>
              <span v-if="typeDistribution.length > 5">+{{ typeDistribution.length - 5 }} 类</span>
            </div>
          </div>

          <div class="kg-toolbar">
            <div class="kg-search-wrap">
              <Search :size="16" />
              <input v-model="searchQuery" placeholder="搜索知识点、章节或关键词" />
              <div v-if="searchMatches.length" class="kg-search-results">
                <button
                  v-for="node in searchMatches"
                  :key="node.id"
                  type="button"
                  @click="selectNode(node.id)"
                >
                  <i :style="{ background: themeFor(node.type).stroke }" />
                  <span><strong>{{ node.name }}</strong><small>{{ nodeTypeLabels[node.type] }}</small></span>
                </button>
              </div>
            </div>
            <div class="kg-view-tools">
              <button type="button" title="缩小" @click="zoomGraph(0.82)"><ZoomOut :size="16" /></button>
              <button type="button" title="放大" @click="zoomGraph(1.22)"><ZoomIn :size="16" /></button>
              <button type="button" title="适应画布" @click="fitGraph"><Maximize2 :size="16" /></button>
              <button type="button" title="重新布局" @click="relayoutGraph"><RefreshCw :size="16" /></button>
              <button type="button" class="with-label" @click="exportJson"><FileJson :size="16" /> JSON</button>
              <button type="button" class="with-label primary" @click="exportPng"><Download :size="16" /> PNG</button>
            </div>
          </div>

          <div class="kg-canvas-layout">
            <div class="kg-canvas-shell">
              <div ref="graphContainer" class="kg-canvas" />
              <span class="kg-canvas-hint"><Focus :size="14" /> 点击节点查看详情 · 滚轮缩放 · 拖拽调整</span>
              <div v-if="generating" class="kg-refresh-overlay">
                <LoaderCircle class="spin" :size="28" />
                <strong>问鹿AI 正在更新图谱</strong>
                <small>{{ generationStages[generationStage] }}</small>
              </div>
            </div>

            <aside class="kg-node-detail">
              <template v-if="selectedNode">
                <header>
                  <span :style="{ background: themeFor(selectedNode.type).fill, color: themeFor(selectedNode.type).text, borderColor: themeFor(selectedNode.type).stroke }">
                    <Layers3 :size="18" />
                  </span>
                  <div>
                    <small>{{ nodeTypeLabels[selectedNode.type] }}</small>
                    <h3>{{ selectedNode.name }}</h3>
                  </div>
                </header>
                <p>{{ selectedNode.description }}</p>
                <dl>
                  <div><dt>所在章节</dt><dd>{{ selectedNode.chapter || "未标注" }}</dd></div>
                  <div>
                    <dt>重要程度</dt>
                    <dd class="kg-rating"><i v-for="index in 5" :key="`importance-${index}`" :class="{ active: index <= selectedNode.importance }" /></dd>
                  </div>
                  <div>
                    <dt>理解难度</dt>
                    <dd class="kg-rating difficulty"><i v-for="index in 5" :key="`difficulty-${index}`" :class="{ active: index <= selectedNode.difficulty }" /></dd>
                  </div>
                </dl>
                <div v-if="selectedNode.keywords.length" class="kg-keywords">
                  <span v-for="keyword in selectedNode.keywords" :key="keyword">{{ keyword }}</span>
                </div>
                <section class="kg-relations">
                  <header><Link2 :size="15" /><strong>关联知识</strong><small>{{ selectedConnections.length }}</small></header>
                  <div>
                    <button
                      v-for="item in selectedConnections"
                      :key="item.edge.id"
                      type="button"
                      @click="item.node && selectNode(item.node.id)"
                    >
                      <span>{{ item.outbound ? "→" : "←" }} {{ relationTypeLabels[item.edge.relation] }}</span>
                      <strong>{{ item.node?.name || "未知节点" }}</strong>
                    </button>
                  </div>
                </section>
              </template>
              <div v-else class="kg-detail-empty">
                <Network :size="28" />
                <strong>选择一个知识节点</strong>
                <p>查看定义、层级、难度和上下游关系。</p>
              </div>
            </aside>
          </div>
        </template>

        <div v-else class="kg-empty-preview" :class="{ generating }">
          <div class="kg-empty-network" aria-hidden="true">
            <span class="node center"><Network :size="29" /></span>
            <span class="node n1" /><span class="node n2" /><span class="node n3" />
            <span class="node n4" /><span class="node n5" /><span class="node n6" />
            <i class="edge e1" /><i class="edge e2" /><i class="edge e3" />
            <i class="edge e4" /><i class="edge e5" /><i class="edge e6" />
          </div>
          <template v-if="generating">
            <span class="kg-ai-orbit"><Sparkles :size="18" /></span>
            <h2>问鹿AI 正在生成知识图谱</h2>
            <p>{{ generationStages[generationStage] }}，请保持当前页面打开。</p>
            <div class="kg-stage-list">
              <span
                v-for="(stage, index) in generationStages"
                :key="stage"
                :class="{ active: index === generationStage, done: index < generationStage }"
              ><i>{{ index < generationStage ? "✓" : index + 1 }}</i>{{ stage }}</span>
            </div>
          </template>
          <template v-else>
            <span class="kg-empty-kicker">等待教案输入</span>
            <h2>知识之间的关系，将在这里展开。</h2>
            <p>输入一份完整教案，问鹿AI会提取层级与跨知识点关系，自动生成可探索的专业图谱。</p>
            <div class="kg-empty-features">
              <span><Layers3 :size="15" /> 多层级节点</span>
              <span><Link2 :size="15" /> 跨知识关系</span>
              <span><FileJson :size="15" /> 标准 JSON</span>
            </div>
          </template>
        </div>
      </section>
    </section>
  </div>
</template>

<style scoped>
.kg-page {
  --kg-green: #168363;
  --kg-green-dark: #124d3e;
  --kg-ink: #18362f;
  --kg-muted: #6d807a;
  display: grid;
  gap: 20px;
  color: var(--kg-ink);
}

button,
input,
select,
textarea {
  font: inherit;
}

button {
  cursor: pointer;
}

.kg-hero {
  position: relative;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 30px;
  min-height: 182px;
  padding: 32px 36px;
  border: 1px solid #d7e8e1;
  border-radius: 22px;
  background:
    radial-gradient(circle at 85% 5%, rgba(106, 190, 155, 0.2), transparent 31%),
    linear-gradient(118deg, #f7fbf9 0%, #edf8f3 66%, #e7f4ee 100%);
  box-shadow: 0 18px 46px rgba(41, 88, 72, 0.08);
}

.kg-hero::after {
  content: "";
  position: absolute;
  right: -80px;
  top: -150px;
  width: 360px;
  height: 360px;
  border: 1px solid rgba(22, 131, 99, 0.1);
  border-radius: 50%;
  box-shadow: 0 0 0 42px rgba(22, 131, 99, 0.035), 0 0 0 88px rgba(22, 131, 99, 0.025);
  pointer-events: none;
}

.kg-hero-copy {
  position: relative;
  z-index: 1;
  max-width: 650px;
}

.kg-back-button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin: 0 0 14px;
  padding: 7px 10px;
  color: #396b5c;
  border: 1px solid rgba(22, 131, 99, 0.2);
  border-radius: 9px;
  background: rgba(255, 255, 255, 0.74);
  font-size: 11px;
  font-weight: 750;
}

.kg-back-button:hover,
.kg-back-button:focus-visible {
  color: #12684f;
  border-color: #70ad98;
  background: #fff;
}

.kg-eyebrow,
.kg-empty-kicker {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  color: var(--kg-green);
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.12em;
}

.kg-hero h1 {
  max-width: 620px;
  margin: 11px 0 9px;
  color: var(--kg-green-dark);
  font-family: "Noto Serif SC", "Source Han Serif SC", Georgia, serif;
  font-size: clamp(25px, 2.2vw, 36px);
  line-height: 1.25;
  letter-spacing: -0.03em;
}

.kg-hero p {
  max-width: 650px;
  margin: 0;
  color: #647a73;
  font-size: 14px;
  line-height: 1.75;
}

.kg-process {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  flex: 0 0 auto;
  gap: 10px;
  color: #8ca098;
}

.kg-process > div {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 13px 14px;
  border: 1px solid rgba(255, 255, 255, 0.82);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.72);
  box-shadow: 0 8px 22px rgba(38, 78, 65, 0.06);
}

.kg-process b {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  border-radius: 9px;
  background: #e2f3ec;
  color: var(--kg-green);
  font-size: 11px;
}

.kg-process span {
  display: grid;
  gap: 3px;
}

.kg-process strong {
  color: #274c41;
  font-size: 12px;
  white-space: nowrap;
}

.kg-process small {
  color: #83958f;
  font-size: 10px;
  white-space: nowrap;
}

.kg-builder-grid {
  display: grid;
  grid-template-columns: minmax(320px, 380px) minmax(0, 1fr);
  align-items: start;
  gap: 20px;
}

.kg-input-card,
.kg-preview-card {
  border: 1px solid #dce8e3;
  border-radius: 20px;
  background: #fff;
  box-shadow: 0 14px 38px rgba(39, 75, 64, 0.065);
}

.kg-input-card {
  position: sticky;
  top: 78px;
  display: grid;
  gap: 17px;
  padding: 22px;
}

.kg-input-card > header {
  display: flex;
  align-items: center;
  gap: 11px;
  padding-bottom: 4px;
}

.kg-input-card > header > span,
.kg-result-mark {
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  border-radius: 12px;
  background: #e7f5ef;
  color: var(--kg-green);
}

.kg-input-card header div {
  display: grid;
  gap: 2px;
}

.kg-input-card header small,
.kg-result-head small {
  color: #8a9a95;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.13em;
}

.kg-input-card h2,
.kg-result-head h2 {
  margin: 0;
  color: #24463c;
  font-size: 18px;
}

.kg-example-button {
  margin-left: auto;
  padding: 7px 10px;
  border: 1px solid #cfe1da;
  border-radius: 9px;
  background: #f8fbfa;
  color: #527368;
  font-size: 11px;
  font-weight: 700;
}

.kg-example-button:hover {
  border-color: #76ad99;
  color: var(--kg-green);
}

.kg-source-plan {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  padding: 11px;
  border: 1px solid #d7e8e1;
  border-radius: 11px;
  background: linear-gradient(145deg, #f6fbf9, #edf7f3);
}

.kg-source-plan > span {
  display: grid;
  place-items: center;
  width: 35px;
  height: 35px;
  border-radius: 10px;
  background: #dcefe7;
  color: var(--kg-green);
}

.kg-source-plan > div {
  display: grid;
  min-width: 0;
  gap: 2px;
}

.kg-source-plan small {
  color: #789087;
  font-size: 9px;
}

.kg-source-plan strong {
  overflow: hidden;
  color: #285447;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.kg-source-plan b {
  padding: 4px 7px;
  border-radius: 6px;
  background: #fff;
  color: #34725f;
  font-size: 9px;
}

.kg-field {
  display: grid;
  gap: 8px;
}

.kg-field > span {
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: #38584f;
  font-size: 12px;
  font-weight: 750;
}

.kg-field > span small {
  color: #97a49f;
  font-size: 10px;
  font-weight: 500;
}

.kg-field input,
.kg-field select,
.kg-field textarea {
  width: 100%;
  border: 1px solid #d9e5e0;
  border-radius: 11px;
  outline: none;
  background: #fbfdfc;
  color: #253f37;
  transition: border-color 0.18s, box-shadow 0.18s, background 0.18s;
}

.kg-field input,
.kg-field select {
  height: 43px;
  padding: 0 12px;
}

.kg-field textarea {
  min-height: 270px;
  resize: vertical;
  padding: 13px;
  font-size: 13px;
  line-height: 1.72;
}

.kg-field input:focus,
.kg-field select:focus,
.kg-field textarea:focus {
  border-color: #56a78d;
  background: #fff;
  box-shadow: 0 0 0 3px rgba(22, 131, 99, 0.09);
}

.kg-content-field > small {
  justify-self: end;
  color: #97a49f;
  font-size: 10px;
}

.kg-content-field > small.warning {
  color: #c37342;
}

.kg-detail-levels {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 7px;
}

.kg-detail-levels button {
  display: grid;
  gap: 3px;
  padding: 10px 6px;
  border: 1px solid #dce7e2;
  border-radius: 10px;
  background: #fbfdfc;
  color: #557067;
}

.kg-detail-levels button strong {
  font-size: 12px;
}

.kg-detail-levels button small {
  color: #96a39f;
  font-size: 9px;
}

.kg-detail-levels button.active {
  border-color: #4b9f82;
  background: #eaf7f1;
  color: #146c53;
  box-shadow: inset 0 0 0 1px rgba(22, 131, 99, 0.08);
}

.kg-detail-levels button.active small {
  color: #649783;
}

.kg-error {
  margin: -4px 0 0;
  padding: 10px 12px;
  border: 1px solid #f1d1c8;
  border-radius: 10px;
  background: #fff7f4;
  color: #a34f3d;
  font-size: 12px;
  line-height: 1.55;
}

.kg-generate-button {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 54px;
  padding: 9px 14px;
  border: 0;
  border-radius: 13px;
  background: linear-gradient(125deg, #168363, #116a52);
  color: #fff;
  box-shadow: 0 11px 25px rgba(22, 131, 99, 0.2);
}

.kg-generate-button > span {
  display: grid;
  flex: 1;
  gap: 2px;
  text-align: left;
}

.kg-generate-button strong {
  font-size: 13px;
}

.kg-generate-button small {
  color: rgba(255, 255, 255, 0.7);
  font-size: 10px;
}

.kg-generate-button:not(:disabled):hover {
  transform: translateY(-1px);
  box-shadow: 0 14px 28px rgba(22, 131, 99, 0.26);
}

.kg-generate-button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
  box-shadow: none;
}

.kg-quality-note {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  color: #86958f;
  font-size: 10px;
}

.kg-quality-note svg {
  color: #4c9c80;
}

.kg-preview-card {
  min-width: 0;
  overflow: visible;
}

.kg-result-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 20px 22px 15px;
}

.kg-result-head > div:first-child {
  display: flex;
  align-items: center;
  min-width: 0;
  gap: 11px;
}

.kg-result-head > div:first-child > div {
  min-width: 0;
}

.kg-result-head h2 {
  overflow: hidden;
  margin-top: 3px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.kg-result-stats {
  display: flex;
  align-items: center;
  flex: 0 0 auto;
  gap: 10px;
  color: #71847d;
  font-size: 11px;
}

.kg-result-stats strong {
  color: var(--kg-green);
  font-size: 17px;
}

.kg-result-stats i {
  width: 1px;
  height: 22px;
  background: #dde7e3;
}

.kg-summary-row {
  display: grid;
  gap: 11px;
  padding: 0 22px 16px;
}

.kg-summary-row p {
  margin: 0;
  color: #647770;
  font-size: 12px;
  line-height: 1.65;
}

.kg-type-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
}

.kg-type-legend span {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 7px;
  border-radius: 6px;
  background: #f5f8f7;
  color: #6b7c76;
  font-size: 9px;
}

.kg-type-legend i {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.kg-toolbar {
  position: relative;
  z-index: 4;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 14px;
  border-top: 1px solid #e6eeea;
  border-bottom: 1px solid #e6eeea;
  background: #fbfdfc;
}

.kg-search-wrap {
  position: relative;
  display: flex;
  align-items: center;
  flex: 1 1 240px;
  max-width: 330px;
  gap: 7px;
  padding: 0 10px;
  border: 1px solid #dce7e2;
  border-radius: 9px;
  background: #fff;
  color: #84958f;
}

.kg-search-wrap input {
  width: 100%;
  height: 34px;
  border: 0;
  outline: 0;
  background: transparent;
  color: #304b43;
  font-size: 11px;
}

.kg-search-results {
  position: absolute;
  z-index: 10;
  top: calc(100% + 7px);
  left: 0;
  right: 0;
  overflow: hidden;
  padding: 5px;
  border: 1px solid #dbe6e2;
  border-radius: 10px;
  background: #fff;
  box-shadow: 0 16px 34px rgba(31, 67, 55, 0.16);
}

.kg-search-results button {
  display: flex;
  align-items: center;
  width: 100%;
  gap: 8px;
  padding: 8px;
  border: 0;
  border-radius: 7px;
  background: transparent;
  text-align: left;
}

.kg-search-results button:hover {
  background: #f0f8f4;
}

.kg-search-results button > i {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.kg-search-results button span {
  display: flex;
  justify-content: space-between;
  flex: 1;
  gap: 8px;
}

.kg-search-results strong {
  color: #345249;
  font-size: 11px;
}

.kg-search-results small {
  color: #93a19c;
  font-size: 9px;
}

.kg-view-tools {
  display: flex;
  align-items: center;
  gap: 5px;
}

.kg-view-tools button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 34px;
  min-width: 34px;
  gap: 5px;
  padding: 0 8px;
  border: 1px solid #d9e5e0;
  border-radius: 8px;
  background: #fff;
  color: #5f756d;
  font-size: 10px;
  font-weight: 700;
}

.kg-view-tools button:hover {
  border-color: #76ad99;
  color: var(--kg-green);
}

.kg-view-tools button.primary {
  border-color: var(--kg-green);
  background: var(--kg-green);
  color: #fff;
}

.kg-canvas-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 270px;
  min-height: 630px;
}

.kg-canvas-shell {
  position: relative;
  min-width: 0;
  overflow: hidden;
  background:
    linear-gradient(rgba(29, 98, 77, 0.035) 1px, transparent 1px),
    linear-gradient(90deg, rgba(29, 98, 77, 0.035) 1px, transparent 1px),
    radial-gradient(circle at 50% 47%, #fff 0%, #f9fcfa 72%);
  background-size: 24px 24px, 24px 24px, auto;
}

.kg-canvas {
  width: 100%;
  height: 630px;
}

.kg-canvas-hint {
  position: absolute;
  left: 14px;
  bottom: 13px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 9px;
  border: 1px solid rgba(218, 230, 225, 0.9);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.88);
  color: #87968f;
  font-size: 9px;
  backdrop-filter: blur(8px);
}

.kg-refresh-overlay {
  position: absolute;
  inset: 0;
  display: grid;
  place-content: center;
  justify-items: center;
  gap: 7px;
  background: rgba(249, 252, 250, 0.84);
  color: var(--kg-green);
  backdrop-filter: blur(4px);
}

.kg-refresh-overlay strong {
  color: #294d42;
  font-size: 14px;
}

.kg-refresh-overlay small {
  color: #7a8d86;
  font-size: 11px;
}

.kg-node-detail {
  overflow: auto;
  max-height: 630px;
  padding: 20px;
  border-left: 1px solid #e3ece8;
  background: #fcfefd;
}

.kg-node-detail > header {
  display: flex;
  align-items: center;
  gap: 10px;
}

.kg-node-detail > header > span {
  display: grid;
  place-items: center;
  flex: 0 0 auto;
  width: 40px;
  height: 40px;
  border: 1px solid;
  border-radius: 50%;
}

.kg-node-detail header div {
  min-width: 0;
}

.kg-node-detail header small {
  color: #889991;
  font-size: 9px;
  font-weight: 700;
}

.kg-node-detail h3 {
  margin: 3px 0 0;
  color: #25483e;
  font-size: 16px;
  line-height: 1.3;
}

.kg-node-detail > p {
  margin: 17px 0;
  padding: 12px;
  border-radius: 10px;
  background: #f1f7f4;
  color: #566d65;
  font-size: 11px;
  line-height: 1.7;
}

.kg-node-detail dl {
  display: grid;
  gap: 10px;
  margin: 0;
}

.kg-node-detail dl > div {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.kg-node-detail dt {
  color: #899891;
  font-size: 10px;
}

.kg-node-detail dd {
  margin: 0;
  color: #3b594f;
  font-size: 10px;
  font-weight: 700;
  text-align: right;
}

.kg-rating {
  display: flex;
  gap: 3px;
}

.kg-rating i {
  width: 15px;
  height: 4px;
  border-radius: 4px;
  background: #dce6e2;
}

.kg-rating i.active {
  background: #2c9575;
}

.kg-rating.difficulty i.active {
  background: #d98b48;
}

.kg-keywords {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-top: 16px;
}

.kg-keywords span {
  padding: 4px 7px;
  border-radius: 6px;
  background: #e8f4ef;
  color: #4d796b;
  font-size: 9px;
}

.kg-relations {
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid #e2ebe7;
}

.kg-relations > header {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #5f766e;
}

.kg-relations > header strong {
  font-size: 11px;
}

.kg-relations > header small {
  margin-left: auto;
  color: #94a19c;
}

.kg-relations > div {
  display: grid;
  gap: 6px;
  margin-top: 10px;
}

.kg-relations button {
  display: grid;
  gap: 4px;
  padding: 9px;
  border: 1px solid #e0e9e5;
  border-radius: 8px;
  background: #fff;
  text-align: left;
}

.kg-relations button:hover {
  border-color: #7daf9d;
  background: #f3faf7;
}

.kg-relations button span {
  color: #8a9893;
  font-size: 8px;
}

.kg-relations button strong {
  overflow: hidden;
  color: #3a5a50;
  font-size: 10px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.kg-detail-empty {
  display: grid;
  place-items: center;
  min-height: 420px;
  align-content: center;
  color: #a2b0aa;
  text-align: center;
}

.kg-detail-empty strong {
  margin-top: 9px;
  color: #5c736b;
  font-size: 12px;
}

.kg-detail-empty p {
  margin: 5px 0 0;
  font-size: 10px;
}

.kg-empty-preview {
  display: grid;
  place-items: center;
  min-height: 704px;
  padding: 50px 28px;
  align-content: center;
  background:
    linear-gradient(rgba(30, 103, 80, 0.032) 1px, transparent 1px),
    linear-gradient(90deg, rgba(30, 103, 80, 0.032) 1px, transparent 1px),
    radial-gradient(circle at center, #fff 0%, #f8fcfa 72%);
  background-size: 28px 28px, 28px 28px, auto;
  text-align: center;
}

.kg-empty-network {
  position: relative;
  width: 260px;
  height: 210px;
  margin-bottom: 20px;
}

.kg-empty-network .node {
  position: absolute;
  z-index: 2;
  display: block;
  width: 18px;
  height: 18px;
  border: 4px solid #fff;
  border-radius: 50%;
  background: #69aa94;
  box-shadow: 0 7px 16px rgba(29, 92, 72, 0.15);
}

.kg-empty-network .center {
  left: 101px;
  top: 72px;
  display: grid;
  place-items: center;
  width: 58px;
  height: 58px;
  border: 7px solid #fff;
  background: linear-gradient(145deg, #1f9472, #12694f);
  color: #fff;
}

.kg-empty-network .n1 { left: 27px; top: 25px; background: #6b87cb; }
.kg-empty-network .n2 { right: 27px; top: 18px; background: #9a75c9; }
.kg-empty-network .n3 { left: 4px; top: 115px; background: #d59047; }
.kg-empty-network .n4 { right: 0; top: 105px; background: #d56f5c; }
.kg-empty-network .n5 { left: 55px; bottom: 2px; background: #3d9a96; }
.kg-empty-network .n6 { right: 50px; bottom: 0; background: #d1a536; }

.kg-empty-network .edge {
  position: absolute;
  z-index: 1;
  display: block;
  height: 1px;
  background: #b8cec5;
  transform-origin: left center;
}

.kg-empty-network .e1 { left: 42px; top: 40px; width: 89px; transform: rotate(34deg); }
.kg-empty-network .e2 { left: 133px; top: 91px; width: 103px; transform: rotate(-46deg); }
.kg-empty-network .e3 { left: 16px; top: 126px; width: 105px; transform: rotate(-16deg); }
.kg-empty-network .e4 { left: 139px; top: 104px; width: 104px; transform: rotate(6deg); }
.kg-empty-network .e5 { left: 80px; top: 179px; width: 78px; transform: rotate(-62deg); }
.kg-empty-network .e6 { left: 140px; top: 115px; width: 85px; transform: rotate(58deg); }

.kg-empty-preview h2 {
  max-width: 510px;
  margin: 9px 0 8px;
  color: #294d42;
  font-family: "Noto Serif SC", "Source Han Serif SC", Georgia, serif;
  font-size: 23px;
}

.kg-empty-preview > p {
  max-width: 530px;
  margin: 0;
  color: #7b8c86;
  font-size: 12px;
  line-height: 1.7;
}

.kg-empty-features,
.kg-stage-list {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 8px;
  margin-top: 20px;
}

.kg-empty-features span {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 7px 10px;
  border: 1px solid #dce9e4;
  border-radius: 9px;
  background: rgba(255, 255, 255, 0.82);
  color: #61766f;
  font-size: 10px;
}

.kg-ai-orbit {
  display: grid;
  place-items: center;
  width: 38px;
  height: 38px;
  border-radius: 50%;
  background: #e4f5ee;
  color: var(--kg-green);
  animation: kg-pulse 1.8s ease-in-out infinite;
}

.kg-stage-list span {
  display: flex;
  align-items: center;
  gap: 5px;
  color: #9aa7a2;
  font-size: 9px;
}

.kg-stage-list i {
  display: grid;
  place-items: center;
  width: 18px;
  height: 18px;
  border: 1px solid #d8e4df;
  border-radius: 50%;
  background: #fff;
  font-style: normal;
}

.kg-stage-list span.active {
  color: var(--kg-green);
  font-weight: 700;
}

.kg-stage-list span.active i {
  border-color: var(--kg-green);
  box-shadow: 0 0 0 4px rgba(22, 131, 99, 0.08);
}

.kg-stage-list span.done i {
  border-color: var(--kg-green);
  background: var(--kg-green);
  color: #fff;
}

.spin {
  animation: kg-spin 0.9s linear infinite;
}

@keyframes kg-spin {
  to { transform: rotate(360deg); }
}

@keyframes kg-pulse {
  50% { transform: scale(1.08); box-shadow: 0 0 0 10px rgba(22, 131, 99, 0.06); }
}

@media (max-width: 1380px) {
  .kg-hero {
    align-items: flex-start;
    flex-direction: column;
  }

  .kg-builder-grid {
    grid-template-columns: 1fr;
  }

  .kg-input-card {
    position: static;
    grid-template-columns: 1fr 1fr;
  }

  .kg-input-card > header,
  .kg-content-field,
  .kg-error,
  .kg-generate-button,
  .kg-quality-note {
    grid-column: 1 / -1;
  }

  .kg-content-field textarea {
    min-height: 220px;
  }
}

@media (max-width: 900px) {
  .kg-hero {
    padding: 26px;
  }

  .kg-process {
    overflow-x: auto;
    width: 100%;
    padding-bottom: 4px;
  }

  .kg-result-head,
  .kg-toolbar {
    align-items: flex-start;
    flex-direction: column;
  }

  .kg-search-wrap {
    width: 100%;
    max-width: none;
  }

  .kg-view-tools {
    flex-wrap: wrap;
  }

  .kg-canvas-layout {
    grid-template-columns: 1fr;
  }

  .kg-node-detail {
    max-height: none;
    border-top: 1px solid #e3ece8;
    border-left: 0;
  }
}

@media (max-width: 620px) {
  .kg-page {
    gap: 14px;
  }

  .kg-hero {
    padding: 22px 18px;
    border-radius: 16px;
  }

  .kg-hero h1 {
    font-size: 25px;
  }

  .kg-process > svg {
    display: none;
  }

  .kg-input-card {
    grid-template-columns: 1fr;
    padding: 17px;
    border-radius: 15px;
  }

  .kg-input-card > * {
    grid-column: 1 !important;
  }

  .kg-detail-levels {
    grid-template-columns: 1fr;
  }

  .kg-result-head,
  .kg-summary-row {
    padding-right: 16px;
    padding-left: 16px;
  }

  .kg-result-stats {
    width: 100%;
  }

  .kg-canvas {
    min-height: 500px;
    height: 500px;
  }

  .kg-canvas-layout {
    min-height: 500px;
  }

  .kg-node-detail {
    padding: 17px;
  }

  .kg-view-tools button.with-label {
    font-size: 0;
  }
}
</style>
