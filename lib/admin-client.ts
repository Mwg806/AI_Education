const API_BASE = (import.meta.env.VITE_AGENT_API_BASE_URL || "/agent-api").replace(/\/$/, "");

export interface AdminProfile {
  role: "super_admin";
  username: string;
}

export interface AdminSession {
  access_token: string;
  token_type: "bearer";
  expires_at: string;
  profile: AdminProfile;
}

export interface AccountOverview {
  students: { total: number; active: number; unbound: number };
  teachers: { total: number; active: number; unbound: number };
  operations_24h: number;
}

export interface ManagedAccount {
  role: "student" | "teacher";
  account_id: string;
  display_name: string;
  context: string;
  phone_masked: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface DeletionImpact extends ManagedAccount {
  related_counts: Record<string, number>;
  related_records: number;
}

export interface AdminAudit {
  id: number;
  admin_username: string;
  action: string;
  target_role: "student" | "teacher" | "super_admin" | null;
  target_account_id: string | null;
  reason: string;
  metadata: Record<string, unknown>;
  client_ip: string;
  created_at: string;
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
    throw new Error(data.errors?.[0]?.message || detail || "管理员服务请求失败");
  }
  return data;
}

function adminFetch(token: string, path: string, init?: RequestInit): Promise<Response> {
  const headers = new Headers(init?.headers);
  headers.set("Authorization", `Bearer ${token}`);
  if (init?.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  return fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
    cache: "no-store",
    signal: init?.signal || AbortSignal.timeout(20_000),
  });
}

export async function loginAdmin(username: string, password: string): Promise<AdminSession> {
  const response = await fetch(`${API_BASE}/api/v1/admin/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
    signal: AbortSignal.timeout(20_000),
  });
  return responseJson<AdminSession>(response);
}

export async function currentAdmin(token: string): Promise<AdminProfile> {
  const response = await adminFetch(token, "/api/v1/admin/auth/me");
  return (await responseJson<{ profile: AdminProfile }>(response)).profile;
}

export async function logoutAdmin(token: string): Promise<void> {
  const response = await adminFetch(token, "/api/v1/admin/auth/logout", { method: "POST" });
  if (!response.ok) await responseJson(response);
}

export async function getAdminOverview(token: string): Promise<AccountOverview> {
  return responseJson(await adminFetch(token, "/api/v1/admin/overview"));
}

export async function listManagedAccounts(
  token: string,
  input: { role: "all" | "student" | "teacher"; query: string; limit: number; offset: number },
): Promise<{ accounts: ManagedAccount[]; has_more: boolean; limit: number; offset: number }> {
  const params = new URLSearchParams({
    role: input.role,
    query: input.query,
    limit: String(input.limit),
    offset: String(input.offset),
  });
  return responseJson(await adminFetch(token, `/api/v1/admin/accounts?${params}`));
}

export async function getDeletionImpact(
  token: string,
  account: Pick<ManagedAccount, "role" | "account_id">,
): Promise<DeletionImpact> {
  return responseJson(
    await adminFetch(
      token,
      `/api/v1/admin/accounts/${account.role}/${encodeURIComponent(account.account_id)}/deletion-impact`,
    ),
  );
}

export async function sendStudentRebindCode(
  token: string,
  studentId: string,
  phone: string,
): Promise<{ sent: boolean; retry_after: number }> {
  return responseJson(
    await adminFetch(
      token,
      `/api/v1/admin/students/${encodeURIComponent(studentId)}/phone/rebind-code`,
      { method: "POST", body: JSON.stringify({ phone }) },
    ),
  );
}

export async function rebindStudentPhone(
  token: string,
  studentId: string,
  input: { phone: string; verificationCode: string; reason: string },
): Promise<ManagedAccount> {
  return responseJson(
    await adminFetch(
      token,
      `/api/v1/admin/students/${encodeURIComponent(studentId)}/phone`,
      {
        method: "PUT",
        body: JSON.stringify({
          phone: input.phone,
          verification_code: input.verificationCode,
          reason: input.reason,
        }),
      },
    ),
  );
}

export async function permanentlyDeleteAccount(
  token: string,
  account: Pick<ManagedAccount, "role" | "account_id">,
  reason: string,
): Promise<{ deleted: boolean; related_records: number }> {
  return responseJson(
    await adminFetch(
      token,
      `/api/v1/admin/accounts/${account.role}/${encodeURIComponent(account.account_id)}`,
      {
        method: "DELETE",
        body: JSON.stringify({
          confirm_account_id: account.account_id,
          reason,
          acknowledge_permanent_deletion: true,
        }),
      },
    ),
  );
}

export async function listAdminAudits(
  token: string,
  limit = 40,
  offset = 0,
): Promise<{ audits: AdminAudit[]; has_more: boolean }> {
  return responseJson(
    await adminFetch(token, `/api/v1/admin/audits?limit=${limit}&offset=${offset}`),
  );
}
