import { computed, ref, watch, type ComputedRef, type Ref } from "vue";

export type AiDestination = {
  view: "collaboration" | "tutor" | "english" | "programming" | "workspace";
  module?: "reading" | "vocabulary" | "grammar" | "speaking" | "writing" | "records";
  mode?: "CAREER" | "PROJECT" | "CODING" | "GAOKAO";
};

export type AiTask = {
  id: string;
  studentId: string;
  channel: string;
  title: string;
  destination: AiDestination;
  startedAt: number;
};

export type AiTaskNotification = {
  id: string;
  title: string;
  message: string;
  destination: AiDestination;
  tone: "success" | "error";
  createdAt: number;
};

const persistentStates = new Map<string, Ref<unknown>>();
const activeContext = ref("");
const pendingTasks = ref<AiTask[]>([]);
const notifications = ref<Array<AiTaskNotification & { studentId: string }>>([]);
let taskSequence = 0;

function storageKey(studentId: string, channel: string) {
  return `ai_education_ai_state_v1:${encodeURIComponent(studentId)}:${channel}`;
}

function cloneValue<T>(value: T): T {
  try {
    return JSON.parse(JSON.stringify(value)) as T;
  } catch {
    return value;
  }
}

function serializableValue<T>(value: T, maxItems: number): T {
  const serialized = JSON.parse(
    JSON.stringify(value, (key, item) => {
      if (key === "imageUrl" && typeof item === "string" && item.startsWith("blob:")) {
        return undefined;
      }
      return item;
    }),
  ) as T;
  if (Array.isArray(serialized) && serialized.length > maxItems) {
    return serialized.slice(-maxItems) as T;
  }
  return serialized;
}

export function usePersistentAiState<T>(
  studentId: string,
  channel: string,
  initialValue: T,
  maxItems = 60,
): Ref<T> {
  const key = storageKey(studentId, channel);
  const existing = persistentStates.get(key);
  if (existing) return existing as Ref<T>;

  let restored = cloneValue(initialValue);
  try {
    const raw = window.localStorage.getItem(key);
    if (raw) restored = JSON.parse(raw) as T;
  } catch {
    // Storage can be unavailable in privacy mode. The in-memory state still works.
  }

  const state = ref(restored) as Ref<T>;
  persistentStates.set(key, state as Ref<unknown>);
  watch(
    state,
    (value) => {
      try {
        window.localStorage.setItem(
          key,
          JSON.stringify(serializableValue(value, maxItems)),
        );
      } catch {
        // Keep the live conversation even if the browser storage quota is exhausted.
      }
    },
    { deep: true, flush: "post" },
  );
  return state;
}

function destinationKey(studentId: string, destination: AiDestination) {
  return [
    studentId,
    destination.view,
    destination.module || "",
    destination.mode || "",
  ].join(":");
}

export function setActiveAiContext(studentId: string, destination: AiDestination) {
  activeContext.value = destinationKey(studentId, destination);
}

export function beginAiTask(task: Omit<AiTask, "id" | "startedAt">) {
  taskSequence += 1;
  const id = `ai_task_${Date.now().toString(36)}_${taskSequence}`;
  pendingTasks.value = [...pendingTasks.value, { ...task, id, startedAt: Date.now() }];
  return id;
}

function settleAiTask(
  id: string,
  tone: AiTaskNotification["tone"],
  message: string,
) {
  const task = pendingTasks.value.find((item) => item.id === id);
  if (!task) return;
  pendingTasks.value = pendingTasks.value.filter((item) => item.id !== id);
  if (activeContext.value === destinationKey(task.studentId, task.destination)) return;
  notifications.value = [
    {
      id,
      studentId: task.studentId,
      title: task.title,
      message,
      destination: task.destination,
      tone,
      createdAt: Date.now(),
    },
    ...notifications.value,
  ].slice(0, 6);
}

export function completeAiTask(id: string, message = "AI 已完成回复，点击前往查看。") {
  settleAiTask(id, "success", message);
}

export function failAiTask(id: string, message = "AI 本次处理未完成，点击返回查看原因。") {
  settleAiTask(id, "error", message);
}

export function dismissAiTaskNotification(id: string) {
  notifications.value = notifications.value.filter((item) => item.id !== id);
}

export function aiTaskNotificationsFor(studentId: string): ComputedRef<AiTaskNotification[]> {
  return computed(() =>
    notifications.value
      .filter((item) => item.studentId === studentId)
      .map(({ studentId: _studentId, ...item }) => item),
  );
}

export function pendingAiTasksFor(studentId: string): ComputedRef<AiTask[]> {
  return computed(() => pendingTasks.value.filter((item) => item.studentId === studentId));
}

export function aiTaskPending(studentId: string, channel: string): ComputedRef<boolean> {
  return computed(() =>
    pendingTasks.value.some(
      (item) => item.studentId === studentId && item.channel === channel,
    ),
  );
}
