import type {
  AuthSession,
  StudentLoginProfile,
  TeacherLoginProfile,
  UserLoginProfile,
} from "@/lib/types";

const API_BASE = (import.meta.env.VITE_AGENT_API_BASE_URL || "/agent-api").replace(/\/$/, "");
const STORAGE_KEY = "ai_education_auth_session";

function storedAccessToken(): string {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
      || window.sessionStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as Partial<AuthSession>).access_token || "" : "";
  } catch {
    return "";
  }
}

export function installAuthenticatedFetch(): void {
  const nativeFetch = window.fetch.bind(window);
  window.fetch = (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    const token = url.startsWith(API_BASE) || url.startsWith("/api/v1/") ? storedAccessToken() : "";
    if (!token) return nativeFetch(input, init);
    const headers = new Headers(init?.headers || (input instanceof Request ? input.headers : undefined));
    if (!headers.has("Authorization")) headers.set("Authorization", `Bearer ${token}`);
    return nativeFetch(input, { ...init, headers });
  };
}

async function responseJson<T>(response: Response): Promise<T> {
  const data = await response.json().catch(() => ({})) as T & {
    detail?: string | Array<{ msg?: string; message?: string }>;
    errors?: Array<{ message: string }>;
  };
  if (!response.ok) {
    const detail = Array.isArray(data.detail) ? data.detail[0]?.msg || data.detail[0]?.message : data.detail;
    throw new Error(data.errors?.[0]?.message || detail || "账号服务请求失败");
  }
  return data;
}

export async function sendVerificationCode(
  phone: string,
  purpose: "register" | "login",
  role: "student" | "teacher",
): Promise<{ sent: boolean; retry_after: number }> {
  const response = await fetch(`${API_BASE}/api/v1/auth/send-code`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ phone, purpose, role }),
    signal: AbortSignal.timeout(20_000),
  });
  return responseJson(response);
}

export async function registerStudent(input: {
  studentId: string;
  phone: string;
  verificationCode: string;
  studentName: string;
  grade: StudentLoginProfile["grade"];
  provinceCode: string;
  targetExamYear: number;
}): Promise<AuthSession> {
  const response = await fetch(`${API_BASE}/api/v1/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      student_id: input.studentId,
      phone: input.phone,
      verification_code: input.verificationCode,
      student_name: input.studentName,
      grade: input.grade,
      province_code: input.provinceCode,
      target_exam_year: input.targetExamYear,
    }),
    signal: AbortSignal.timeout(20_000),
  });
  return responseJson<AuthSession>(response);
}

export async function loginStudent(
  studentId: string, phone: string, verificationCode: string,
): Promise<AuthSession> {
  const response = await fetch(`${API_BASE}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ student_id: studentId, phone, verification_code: verificationCode, remember: true }),
    signal: AbortSignal.timeout(20_000),
  });
  return responseJson<AuthSession>(response);
}

export async function registerTeacher(input: {
  teacherId: string;
  phone: string;
  verificationCode: string;
  teacherName: string;
  schoolName: string;
  subject: TeacherLoginProfile["subject"];
}): Promise<AuthSession> {
  const response = await fetch(`${API_BASE}/api/v1/auth/teacher/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      teacher_id: input.teacherId,
      phone: input.phone,
      verification_code: input.verificationCode,
      teacher_name: input.teacherName,
      school_name: input.schoolName,
      subject: input.subject,
    }),
    signal: AbortSignal.timeout(20_000),
  });
  return responseJson<AuthSession>(response);
}

export async function loginTeacher(
  teacherId: string, phone: string, verificationCode: string,
): Promise<AuthSession> {
  const response = await fetch(`${API_BASE}/api/v1/auth/teacher/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ teacher_id: teacherId, phone, verification_code: verificationCode, remember: true }),
    signal: AbortSignal.timeout(20_000),
  });
  return responseJson<AuthSession>(response);
}

export async function currentUser(token: string): Promise<UserLoginProfile> {
  const response = await fetch(`${API_BASE}/api/v1/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
    signal: AbortSignal.timeout(12_000),
  });
  const data = await responseJson<{ profile: UserLoginProfile }>(response);
  return data.profile;
}

export async function logoutStudent(token: string): Promise<void> {
  await fetch(`${API_BASE}/api/v1/auth/logout`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    signal: AbortSignal.timeout(8_000),
  }).catch(() => undefined);
}
