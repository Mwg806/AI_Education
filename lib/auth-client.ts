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
    const url = typeof input === "string"
      ? input
      : input instanceof URL
        ? input.href
        : input.url;
    const isAgentApi = url.startsWith(API_BASE) || url.startsWith("/api/v1/");
    const token = isAgentApi ? storedAccessToken() : "";
    if (!token) return nativeFetch(input, init);
    const inherited = input instanceof Request ? input.headers : undefined;
    const headers = new Headers(init?.headers || inherited);
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
    const detail = Array.isArray(data.detail)
      ? data.detail[0]?.msg || data.detail[0]?.message
      : data.detail;
    throw new Error(data.errors?.[0]?.message || detail || "账号服务请求失败");
  }
  return data;
}

export async function registerStudent(input: {
  studentId: string;
  password: string;
  passwordConfirmation: string;
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
      password: input.password,
      password_confirmation: input.passwordConfirmation,
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
  studentId: string,
  password: string,
  remember: boolean,
): Promise<AuthSession> {
  const response = await fetch(`${API_BASE}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ student_id: studentId, password, remember }),
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

export async function registerTeacher(input: {
  teacherId: string;
  password: string;
  passwordConfirmation: string;
  teacherName: string;
  schoolName: string;
  subject: TeacherLoginProfile["subject"];
}): Promise<AuthSession> {
  const response = await fetch(`${API_BASE}/api/v1/auth/teacher/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      teacher_id: input.teacherId,
      password: input.password,
      password_confirmation: input.passwordConfirmation,
      teacher_name: input.teacherName,
      school_name: input.schoolName,
      subject: input.subject,
    }),
    signal: AbortSignal.timeout(20_000),
  });
  return responseJson<AuthSession>(response);
}

export async function loginTeacher(
  teacherId: string,
  password: string,
  remember: boolean,
): Promise<AuthSession> {
  const response = await fetch(`${API_BASE}/api/v1/auth/teacher/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ teacher_id: teacherId, password, remember }),
    signal: AbortSignal.timeout(20_000),
  });
  return responseJson<AuthSession>(response);
}

export async function logoutStudent(token: string): Promise<void> {
  await fetch(`${API_BASE}/api/v1/auth/logout`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    signal: AbortSignal.timeout(8_000),
  }).catch(() => undefined);
}
