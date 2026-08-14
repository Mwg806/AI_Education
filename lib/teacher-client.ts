import type { LearningPlan, SubjectKey } from "@/lib/types";

const API_BASE = (
  import.meta.env.VITE_AGENT_API_BASE_URL || "/agent-api"
).replace(/\/$/, "");

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
  leave_request_id?: string | null;
  leave_request_status?: ClassroomLeaveRequest["status"] | null;
  owner_teacher_name?: string;
  owner_school_name?: string;
  teacher_access_role?: "owner" | "collaborator";
  join_policy?: "open" | "approval";
  student_join_policy?: "open" | "approval";
  join_request_id?: string | null;
  membership_status?: "active" | "pending" | "rejected" | "removed" | "left";
  teacher_joined_at?: string;
  teacher_leave_request_id?: string | null;
  teacher_leave_request_status?: "pending" | "approved" | "rejected" | null;
}

export interface ClassroomTeacherMember {
  teacher_id: string;
  teacher_name: string;
  school_name: string;
  subject?: SubjectKey | null;
  role: "owner" | "collaborator";
  status: "active" | "pending" | "rejected" | "removed" | "left";
  joined_at: string;
  reviewed_at?: string | null;
  updated_at?: string;
}

export interface BatchPublishResult<T> {
  requested: number;
  succeeded: T[];
  failed: Array<{ classroom_id: number; reason: string }>;
}

export interface ClassroomJoinRequest {
  request_id: string;
  classroom_id: number;
  class_code?: string;
  class_name: string;
  student_id: string;
  student_name: string;
  grade?: string;
  province_code?: string;
  target_exam_year?: number;
  teacher_name?: string;
  school_name?: string;
  status: "pending" | "approved" | "rejected";
  requested_at: string;
  reviewed_at?: string | null;
  reviewer_note?: string | null;
}

export interface ClassroomLeaveRequest {
  request_id: string;
  request_source?: "student" | "collaborator";
  classroom_id: number;
  class_name: string;
  applicant_id?: string;
  applicant_name?: string;
  student_id?: string;
  student_name?: string;
  teacher_id?: string;
  teacher_name?: string;
  status: "pending" | "approved" | "rejected";
  requested_at: string;
  reviewed_at?: string | null;
  reviewer_note?: string | null;
}

export interface ClassroomAnnouncement {
  announcement_id: string;
  classroom_id: number;
  class_name?: string;
  publisher_teacher_id?: string;
  publisher_teacher_name?: string;
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
  publisher_teacher_id?: string;
  publisher_teacher_name?: string;
  paper_id: string;
  title: string;
  due_at?: string | null;
  status: "published" | "closed" | "archived";
  created_at: string;
  latest_session_id?: string | null;
  submission_status?:
    | "in_progress"
    | "provisional"
    | "manual_review_required"
    | "completed"
    | null;
  task_status?: "not_started" | "in_progress" | "completed";
  score?: number | null;
  paper_max?: number | null;
  started_at?: string | null;
  completed_at?: string | null;
}

export interface TeacherExamAssignmentStudentResult {
  student_id: string;
  student_name: string;
  grade: string;
  session_id?: string | null;
  status?:
    | "in_progress"
    | "provisional"
    | "manual_review_required"
    | "completed"
    | null;
  progress_status: "not_started" | "in_progress" | "completed";
  score?: number | null;
  paper_max?: number | null;
  started_at?: string | null;
  completed_at?: string | null;
  result?: Record<string, any> | null;
  learning_record?: {
    objective_accuracy?: number;
    score_accuracy?: number;
    total_duration_seconds?: number;
    knowledge_statistics?: Array<{
      knowledge_tag: string;
      accuracy?: number | null;
      score: number;
      max_score: number;
      duration_seconds: number;
    }>;
  } | null;
  learning_diagnosis?: Record<string, any> | null;
}

export interface TeacherExamAssignmentResults {
  assignment: ClassroomExamAssignment;
  summary: {
    student_count: number;
    not_started: number;
    in_progress: number;
    completed: number;
    manual_review_required: number;
  };
  students: TeacherExamAssignmentStudentResult[];
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
  join_requests: ClassroomJoinRequest[];
  leave_requests: ClassroomLeaveRequest[];
}

export interface ClassroomDetail {
  classroom: ClassroomSummary;
  students: ClassroomStudentState[];
  announcements: ClassroomAnnouncement[];
  exam_assignments: ClassroomExamAssignment[];
  join_requests: ClassroomJoinRequest[];
  leave_requests: ClassroomLeaveRequest[];
}

export interface StudentClassroomPortal {
  classrooms: ClassroomSummary[];
  announcements: ClassroomAnnouncement[];
  exam_assignments: ClassroomExamAssignment[];
  join_requests: ClassroomJoinRequest[];
  leave_requests: ClassroomLeaveRequest[];
}

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
  const data = (await response.json().catch(() => ({}))) as T & {
    detail?: string;
    errors?: Array<{ message: string }>;
  };
  if (!response.ok) {
    throw new Error(
      data.errors?.[0]?.message || data.detail || "教师平台服务请求失败",
    );
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

export function joinTeacherClassroom(
  classCode: string,
): Promise<ClassroomSummary> {
  return request("/api/v1/teacher/classrooms/join", {
    method: "POST",
    body: JSON.stringify({ class_code: classCode.trim().toUpperCase() }),
  });
}

export function fetchClassroomDetail(
  classroomId: number,
): Promise<ClassroomDetail> {
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

export function updateStudentClassroomJoinPolicy(
  classroomId: number,
  studentJoinPolicy: "open" | "approval",
): Promise<ClassroomSummary> {
  return request(
    `/api/v1/teacher/classrooms/${classroomId}/student-join-policy`,
    {
      method: "PATCH",
      body: JSON.stringify({ student_join_policy: studentJoinPolicy }),
    },
  );
}

export function reviewStudentClassroomJoin(
  requestId: string,
  decision: "approved" | "rejected",
  reviewerNote?: string,
): Promise<ClassroomJoinRequest> {
  return request(`/api/v1/teacher/classroom-join-requests/${requestId}`, {
    method: "PUT",
    body: JSON.stringify({
      decision,
      reviewer_note: reviewerNote || null,
    }),
  });
}

export function requestClassroomLeave(
  classroomId: number,
): Promise<ClassroomLeaveRequest> {
  return request(`/api/v1/student/classrooms/${classroomId}/leave-requests`, {
    method: "POST",
  });
}

export function reviewClassroomLeave(
  requestId: string,
  decision: "approved" | "rejected",
  reviewerNote?: string,
): Promise<ClassroomLeaveRequest> {
  return request(`/api/v1/teacher/classroom-leave-requests/${requestId}`, {
    method: "PUT",
    body: JSON.stringify({ decision, reviewer_note: reviewerNote || null }),
  });
}

export interface TeachingResourceReference {
  resource_id: string;
  subject: SubjectKey;
  title: string;
  material_type: string;
  source_organization: string;
  source_location: string;
  source_url: string;
  page_count: number;
  excerpt: string;
  copyright_status: string;
  checksum_verified: boolean;
}

export interface LessonObjective {
  objective_id: string;
  description: string;
  priority: "must" | "recommended" | "extension";
  observable_behavior: string;
  exam_ability_tags: string[];
}

export interface LessonActivity {
  activity_id: string;
  stage: string;
  duration_minutes: number;
  objective_ids: string[];
  teacher_action: string;
  student_action: string;
  organization: string;
  expected_output: string;
  assessment_method: string;
  decision_rule: string;
}

export interface LessonAssessment {
  question_id: string;
  objective_ids: string[];
  purpose: "in_class_check" | "homework";
  prompt: string;
  answer_outline: string;
  scoring_rubric: string[];
  difficulty: number;
  knowledge_tags: string[];
  ability_tags: string[];
  common_error_tags: string[];
  decision_rule: string;
}

export interface LessonPlan {
  lesson_plan_id: string;
  version: number;
  parent_version?: number | null;
  status:
    | "draft"
    | "teacher_review"
    | "approved"
    | "published"
    | "executed"
    | "feedback_recorded"
    | "superseded"
    | "archived";
  context: {
    teacher_id: string;
    classroom_id: number;
    grade: string;
    subject: SubjectKey;
    lesson_type: string;
    topic: string;
    lesson_request: string;
    duration_minutes: number;
    buffer_minutes: number;
    teaching_stage: string;
    textbook_version: string;
    exam_year: number;
    diagnosis_adapted: boolean;
    diagnosis_summary: Record<string, any>;
  };
  title: string;
  summary: string;
  key_points: string[];
  difficult_points: string[];
  objectives: LessonObjective[];
  activities: LessonActivity[];
  resources?: TeachingResourceReference[];
  board_plan: {
    board_plan_id: string;
    layout: Record<string, string>;
    timeline: string[];
    persistent_content: string[];
    slide_only_content: string[];
    compact_version: string[];
    estimated_writing_minutes: number;
  };
  assessments: LessonAssessment[];
  differentiation_plan: Array<{
    layer_id: "support" | "core" | "advanced";
    target_profile: string;
    task_adjustment: string;
    scaffolds: string[];
    objective_ids: string[];
  }>;
  contingency_paths: string[];
  alignment_matrix: Array<{
    objective_id: string;
    objective_description: string;
    activity_ids: string[];
    assessment_ids: string[];
    diagnosis_adaptation: string;
    status: "pass" | "fail";
  }>;
  quality_report: {
    alignment_status: "pass" | "fail";
    feasibility_status: "pass" | "fail";
    resource_compliance_status: "pass" | "review_required" | "fail";
    estimated_activity_minutes: number;
    buffer_minutes: number;
    issues: Array<{
      code: string;
      severity: string;
      message: string;
      component_id?: string | null;
    }>;
    teacher_review_required: boolean;
    publishable: boolean;
  };
  locked_component_ids: string[];
  change_summary: string[];
  generation_mode: "llm" | "reference_template";
  approved_by?: string | null;
  approved_at?: string | null;
  published_at?: string | null;
  created_at: string;
}

interface AgentEnvelope<T> {
  status: string;
  lifecycle_status: string;
  result: T;
  warnings: Array<{ code: string; message: string }>;
  errors: Array<{ code: string; message: string }>;
}

async function agentRequest<T>(
  path: string,
  init: RequestInit = {},
  timeout = 90_000,
): Promise<T> {
  const envelope = await request<AgentEnvelope<T>>(path, init, timeout);
  if (envelope.status === "failed" || envelope.errors.length) {
    throw new Error(envelope.errors[0]?.message || "智能备课操作失败");
  }
  return envelope.result;
}

export function fetchTeacherPreparationCatalog(): Promise<{
  status: string;
  resource_count: number;
  subject_count: number;
  subjects: Array<{
    subject: SubjectKey;
    resource_count: number;
    resources: Array<{
      title: string;
      page_count: number;
      source_organization: string;
    }>;
  }>;
  integrity: { valid: boolean; verified_count: number };
}> {
  return request("/api/v1/teacher/preparation/resources/catalog");
}

export function searchTeachingResources(
  subject: SubjectKey,
  query: string,
): Promise<TeachingResourceReference[]> {
  const params = new URLSearchParams({ subject, query, limit: "3" });
  return agentRequest<{ resources: TeachingResourceReference[] }>(
    `/api/v1/teacher/preparation/resources/search?${params}`,
  ).then((result) => result.resources);
}

export function fetchLessonPlans(classroomId?: number): Promise<LessonPlan[]> {
  const query = classroomId ? `?classroom_id=${classroomId}` : "";
  return agentRequest<{ lesson_plans: LessonPlan[] }>(
    `/api/v1/teacher/lesson-plans${query}`,
  ).then((result) => result.lesson_plans);
}

export function fetchLessonPlan(lessonPlanId: string): Promise<LessonPlan> {
  return agentRequest<{ lesson_plan: LessonPlan }>(
    `/api/v1/teacher/lesson-plans/${encodeURIComponent(lessonPlanId)}`,
  ).then((result) => result.lesson_plan);
}

export function createLessonPlan(input: {
  classroomId: number;
  subject: SubjectKey;
  lessonType: string;
  topic: string;
  lessonRequest: string;
  durationMinutes: number;
  teachingStage: string;
  textbookVersion: string;
  examYear: number;
}): Promise<LessonPlan> {
  return agentRequest<{ lesson_plan: LessonPlan }>(
    "/api/v1/teacher/lesson-plans",
    {
      method: "POST",
      body: JSON.stringify({
        classroom_id: input.classroomId,
        subject: input.subject,
        lesson_type: input.lessonType,
        topic: input.topic,
        lesson_request: input.lessonRequest,
        duration_minutes: input.durationMinutes,
        teaching_stage: input.teachingStage,
        textbook_version: input.textbookVersion,
        exam_year: input.examYear,
        idempotency_key: `lesson-create-${input.classroomId}-${Date.now()}`,
      }),
    },
  ).then((result) => result.lesson_plan);
}

export function reviseLessonPlan(
  lessonPlanId: string,
  input: {
    expectedVersion: number;
    component: string;
    revisionRequest: string;
    lockedComponentIds: string[];
  },
): Promise<LessonPlan> {
  return agentRequest<{ lesson_plan: LessonPlan }>(
    `/api/v1/teacher/lesson-plans/${encodeURIComponent(lessonPlanId)}/revise`,
    {
      method: "POST",
      body: JSON.stringify({
        expected_version: input.expectedVersion,
        component: input.component,
        revision_request: input.revisionRequest,
        locked_component_ids: input.lockedComponentIds,
        idempotency_key: `lesson-revise-${lessonPlanId}-${input.expectedVersion}-${Date.now()}`,
      }),
    },
  ).then((result) => result.lesson_plan);
}

function transitionLessonPlan(
  lessonPlanId: string,
  action: "approve" | "publish",
  expectedVersion: number,
): Promise<LessonPlan> {
  return agentRequest<{ lesson_plan: LessonPlan }>(
    `/api/v1/teacher/lesson-plans/${encodeURIComponent(lessonPlanId)}/${action}`,
    {
      method: "POST",
      body: JSON.stringify({
        expected_version: expectedVersion,
        idempotency_key: `lesson-${action}-${lessonPlanId}-${expectedVersion}`,
      }),
    },
  ).then((result) => result.lesson_plan);
}

export const approveLessonPlan = (lessonPlanId: string, version: number) =>
  transitionLessonPlan(lessonPlanId, "approve", version);

export const publishLessonPlan = (lessonPlanId: string, version: number) =>
  transitionLessonPlan(lessonPlanId, "publish", version);

export function recordLessonFeedback(
  lessonPlanId: string,
  input: {
    lessonVersion: number;
    actualDurationMinutes: number;
    completedActivityIds: string[];
    skippedActivityIds: string[];
    classCheckAccuracy?: number;
    teacherRating: number;
    effectiveComponents: string[];
    issues: string[];
    teacherNotes: string;
  },
): Promise<LessonPlan> {
  return agentRequest<{ lesson_plan: LessonPlan }>(
    `/api/v1/teacher/lesson-plans/${encodeURIComponent(lessonPlanId)}/feedback`,
    {
      method: "POST",
      body: JSON.stringify({
        lesson_version: input.lessonVersion,
        actual_duration_minutes: input.actualDurationMinutes,
        completed_activity_ids: input.completedActivityIds,
        skipped_activity_ids: input.skippedActivityIds,
        class_check_accuracy: input.classCheckAccuracy,
        teacher_rating: input.teacherRating,
        effective_components: input.effectiveComponents,
        issues: input.issues,
        teacher_notes: input.teacherNotes,
        idempotency_key: `lesson-feedback-${lessonPlanId}-${Date.now()}`,
      }),
    },
  ).then((result) => result.lesson_plan);
}

export function fetchClassroomTeachers(
  classroomId: number,
): Promise<{ members: ClassroomTeacherMember[] }> {
  return request(`/api/v1/teacher/classrooms/${classroomId}/teachers`);
}

export function removeClassroomTeacher(
  classroomId: number,
  teacherId: string,
): Promise<Record<string, unknown>> {
  return request(
    `/api/v1/teacher/classrooms/${classroomId}/teachers/${encodeURIComponent(teacherId)}`,
    { method: "DELETE" },
  );
}

export function leaveTeacherClassroom(
  classroomId: number,
): Promise<ClassroomLeaveRequest> {
  return request(
    `/api/v1/teacher/classrooms/${classroomId}/teachers/leave-requests`,
    { method: "POST" },
  );
}

export function reviewTeacherClassroomLeave(
  requestId: string,
  decision: "approved" | "rejected",
): Promise<ClassroomLeaveRequest> {
  return request(`/api/v1/teacher/teacher-leave-requests/${requestId}`, {
    method: "PUT",
    body: JSON.stringify({ decision }),
  });
}

export function transferClassroomOwner(
  classroomId: number,
  teacherId: string,
): Promise<ClassroomSummary> {
  return request(`/api/v1/teacher/classrooms/${classroomId}/owner`, {
    method: "PUT",
    body: JSON.stringify({ teacher_id: teacherId }),
  });
}

export function reviewTeacherJoin(
  classroomId: number,
  teacherId: string,
  decision: "approved" | "rejected",
): Promise<Record<string, unknown>> {
  return request(
    `/api/v1/teacher/classrooms/${classroomId}/teachers/${encodeURIComponent(teacherId)}/review`,
    { method: "POST", body: JSON.stringify({ decision }) },
  );
}

export function updateClassroomJoinPolicy(
  classroomId: number,
  joinPolicy: "open" | "approval",
): Promise<ClassroomSummary> {
  return request(`/api/v1/teacher/classrooms/${classroomId}/join-policy`, {
    method: "PATCH",
    body: JSON.stringify({ join_policy: joinPolicy }),
  });
}

export function publishAnnouncementsBatch(input: {
  classroomIds: number[];
  announcementType: ClassroomAnnouncement["announcement_type"];
  title: string;
  content: string;
  dueAt?: string | null;
  idempotencyKey?: string;
}): Promise<BatchPublishResult<ClassroomAnnouncement>> {
  return request("/api/v1/teacher/announcements/batch", {
    method: "POST",
    body: JSON.stringify({
      classroom_ids: input.classroomIds,
      announcement_type: input.announcementType,
      title: input.title,
      content: input.content,
      due_at: input.dueAt || null,
      idempotency_key: input.idempotencyKey || crypto.randomUUID(),
    }),
  });
}

export function publishExamAssignmentsBatch(input: {
  classroomIds: number[];
  paperId: string;
  title: string;
  dueAt?: string | null;
  status?: ClassroomExamAssignment["status"];
  idempotencyKey?: string;
}): Promise<BatchPublishResult<ClassroomExamAssignment>> {
  return request("/api/v1/teacher/exam-assignments/batch", {
    method: "POST",
    body: JSON.stringify({
      classroom_ids: input.classroomIds,
      paper_id: input.paperId,
      title: input.title,
      due_at: input.dueAt || null,
      status: input.status || "published",
      idempotency_key: input.idempotencyKey || crypto.randomUUID(),
    }),
  });
}

export function fetchTeacherExamAssignmentResults(
  assignmentId: string,
): Promise<TeacherExamAssignmentResults> {
  return request(`/api/v1/teacher/exam-assignments/${assignmentId}/results`);
}
