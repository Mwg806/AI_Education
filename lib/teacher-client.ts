import type { LearningPlan, SubjectKey } from "@/lib/types";

const API_BASE = (import.meta.env.VITE_AGENT_API_BASE_URL || "/agent-api").replace(/\/$/, "");

export interface ClassroomSummary {
  id: number;
  class_code: string;
  class_name: string;
  grade: string;
  subject?: SubjectKey | null;
  status: string;
  student_count: number;
  teacher_name?: string;
  school_name?: string;
  joined_at?: string;
}

export interface ClassroomAnnouncement {
  announcement_id: string;
  classroom_id: number;
  class_name?: string;
  announcement_type: "homework" | "holiday" | "notice";
  title: string;
  content: string;
  due_at?: string | null;
  created_at: string;
}

export interface ClassroomExamAssignment {
  assignment_id: string;
  classroom_id: number;
  class_name?: string;
  paper_id: string;
  title: string;
  due_at?: string | null;
  status: "published" | "closed" | "archived";
  created_at: string;
}

export interface ClassroomStudentState {
  student_id: string;
  student_name: string;
  grade: string;
  province_code: string;
  target_exam_year: number;
  joined_at: string;
  latest_plan?: LearningPlan | null;
  latest_diagnosis?: Record<string, any> | null;
  latest_exam?: {
    paper_id: string;
    subject: string;
    status: string;
    score?: number | null;
    paper_max?: number | null;
    completed_at?: string | null;
  } | null;
}

export interface TeacherDashboard {
  classrooms: ClassroomSummary[];
  announcements: ClassroomAnnouncement[];
  exam_assignments: ClassroomExamAssignment[];
}

export interface ClassroomDetail {
  classroom: ClassroomSummary;
  students: ClassroomStudentState[];
  announcements: ClassroomAnnouncement[];
  exam_assignments: ClassroomExamAssignment[];
}

export type StudentClassroomPortal = TeacherDashboard;

async function request<T>(
  path: string,
  init: RequestInit = {},
  timeout = 20_000,
): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: init.body
      ? { "Content-Type": "application/json", ...init.headers }
      : init.headers,
    cache: "no-store",
    signal: AbortSignal.timeout(timeout),
  });
  const data = await response.json().catch(() => ({})) as T & {
    detail?: string;
    errors?: Array<{ message: string }>;
  };
  if (!response.ok) {
    throw new Error(data.errors?.[0]?.message || data.detail || "教师平台服务请求失败");
  }
  return data;
}

export function fetchTeacherDashboard(): Promise<TeacherDashboard> {
  return request("/api/v1/teacher/dashboard");
}

export function createClassroom(input: {
  className: string;
  grade: string;
  subject?: SubjectKey | null;
}): Promise<ClassroomSummary> {
  return request("/api/v1/teacher/classrooms", {
    method: "POST",
    body: JSON.stringify({
      class_name: input.className,
      grade: input.grade,
      subject: input.subject || null,
    }),
  });
}

export function fetchClassroomDetail(classroomId: number): Promise<ClassroomDetail> {
  return request(`/api/v1/teacher/classrooms/${classroomId}`);
}

export function publishAnnouncement(
  classroomId: number,
  input: {
    announcementType: ClassroomAnnouncement["announcement_type"];
    title: string;
    content: string;
    dueAt?: string | null;
  },
): Promise<ClassroomAnnouncement> {
  return request(`/api/v1/teacher/classrooms/${classroomId}/announcements`, {
    method: "POST",
    body: JSON.stringify({
      announcement_type: input.announcementType,
      title: input.title,
      content: input.content,
      due_at: input.dueAt || null,
    }),
  });
}

export function saveExamAssignment(
  classroomId: number,
  input: {
    assignmentId?: string;
    paperId: string;
    title: string;
    dueAt?: string | null;
    status?: ClassroomExamAssignment["status"];
  },
): Promise<ClassroomExamAssignment> {
  return request(`/api/v1/teacher/classrooms/${classroomId}/exam-assignments`, {
    method: "PUT",
    body: JSON.stringify({
      assignment_id: input.assignmentId || null,
      paper_id: input.paperId,
      title: input.title,
      due_at: input.dueAt || null,
      status: input.status || "published",
    }),
  });
}

export function fetchStudentClassroomPortal(): Promise<StudentClassroomPortal> {
  return request("/api/v1/student/classrooms");
}

export function joinClassroom(classCode: string): Promise<ClassroomSummary> {
  return request("/api/v1/student/classrooms/join", {
    method: "POST",
    body: JSON.stringify({ class_code: classCode.trim().toUpperCase() }),
  });
}
