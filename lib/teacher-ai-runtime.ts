import { computed, ref, type ComputedRef } from "vue";

export type TeacherAiDestination = {
  view:
    | "preparation-create"
    | "preparation-review"
    | "preparation-library";
};

export type TeacherAiTask = {
  id: string;
  teacherId: string;
  channel: string;
  title: string;
  pendingMessage: string;
  destination: TeacherAiDestination;
  startedAt: number;
};

export type TeacherAiTaskNotification = {
  id: string;
  title: string;
  message: string;
  destination: TeacherAiDestination;
  tone: "success" | "error";
  createdAt: number;
};

type SettleOptions = {
  notify?: boolean;
  destination?: TeacherAiDestination;
};

const activeContext = ref("");
const pendingTasks = ref<TeacherAiTask[]>([]);
const notifications = ref<
  Array<TeacherAiTaskNotification & { teacherId: string }>
>([]);
let taskSequence = 0;

function destinationKey(
  teacherId: string,
  destination: TeacherAiDestination,
) {
  return `${teacherId}:${destination.view}`;
}

export function setActiveTeacherAiContext(
  teacherId: string,
  destination?: TeacherAiDestination,
) {
  activeContext.value = destination
    ? destinationKey(teacherId, destination)
    : `${teacherId}:other`;
}

export function beginTeacherAiTask(
  task: Omit<TeacherAiTask, "id" | "startedAt">,
) {
  taskSequence += 1;
  const id = `teacher_ai_task_${Date.now().toString(36)}_${taskSequence}`;
  pendingTasks.value = [
    ...pendingTasks.value,
    { ...task, id, startedAt: Date.now() },
  ];
  return id;
}

function settleTeacherAiTask(
  id: string,
  tone: TeacherAiTaskNotification["tone"],
  message: string,
  options: SettleOptions = {},
) {
  const task = pendingTasks.value.find((item) => item.id === id);
  if (!task) return;
  pendingTasks.value = pendingTasks.value.filter((item) => item.id !== id);
  const destination = options.destination || task.destination;
  if (options.notify === false) return;
  if (activeContext.value === destinationKey(task.teacherId, destination)) {
    return;
  }
  notifications.value = [
    {
      id,
      teacherId: task.teacherId,
      title: task.title,
      message,
      destination,
      tone,
      createdAt: Date.now(),
    },
    ...notifications.value,
  ].slice(0, 6);
}

export function completeTeacherAiTask(
  id: string,
  message = "备课 AI 已完成，点击前往查看。",
  options?: SettleOptions,
) {
  settleTeacherAiTask(id, "success", message, options);
}

export function failTeacherAiTask(
  id: string,
  message = "备课 AI 本次生成未完成，点击返回查看原因。",
  options?: SettleOptions,
) {
  settleTeacherAiTask(id, "error", message, options);
}

export function dismissTeacherAiTaskNotification(id: string) {
  notifications.value = notifications.value.filter((item) => item.id !== id);
}

export function teacherAiTaskNotificationsFor(
  teacherId: string,
): ComputedRef<TeacherAiTaskNotification[]> {
  return computed(() =>
    notifications.value
      .filter((item) => item.teacherId === teacherId)
      .map(({ teacherId: _teacherId, ...item }) => item),
  );
}

export function pendingTeacherAiTasksFor(
  teacherId: string,
): ComputedRef<TeacherAiTask[]> {
  return computed(() =>
    pendingTasks.value.filter((item) => item.teacherId === teacherId),
  );
}

export function teacherAiTaskPending(
  teacherId: string,
  channel: string,
): ComputedRef<boolean> {
  return computed(() =>
    pendingTasks.value.some(
      (item) => item.teacherId === teacherId && item.channel === channel,
    ),
  );
}
