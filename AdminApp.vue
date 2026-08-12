<script setup lang="ts">
import {
  AlertTriangle,
  BookUser,
  ChevronLeft,
  ChevronRight,
  ClipboardList,
  GraduationCap,
  KeyRound,
  LogOut,
  RefreshCw,
  Search,
  ShieldCheck,
  Smartphone,
  Trash2,
  UserCog,
  UsersRound,
  X,
} from "@lucide/vue";
import { computed, onBeforeUnmount, onMounted, reactive, ref } from "vue";

import WenluBrandMark from "@/components/WenluBrandMark.vue";
import {
  currentAdmin,
  getAdminOverview,
  getDeletionImpact,
  listAdminAudits,
  listManagedAccounts,
  loginAdmin,
  logoutAdmin,
  permanentlyDeleteAccount,
  rebindStudentPhone,
  sendStudentRebindCode,
  type AccountOverview,
  type AdminAudit,
  type AdminProfile,
  type AdminSession,
  type DeletionImpact,
  type ManagedAccount,
} from "@/lib/admin-client";

const STORAGE_KEY = "ai_education_admin_session";
const PAGE_SIZE = 10;
const session = ref<AdminSession | null>(null);
const profile = ref<AdminProfile | null>(null);
const restoring = ref(true);
const activeView = ref<"accounts" | "audits">("accounts");
const overview = ref<AccountOverview | null>(null);
const accounts = ref<ManagedAccount[]>([]);
const audits = ref<AdminAudit[]>([]);
const loading = ref(false);
const error = ref("");
const success = ref("");
const query = ref("");
const roleFilter = ref<"student" | "teacher">("student");
const offset = ref(0);
const hasMore = ref(false);
const loginForm = reactive({ username: "", password: "" });
const selected = ref<ManagedAccount | null>(null);
const dialog = ref<"rebind" | "delete" | null>(null);
const impact = ref<DeletionImpact | null>(null);
const actionLoading = ref(false);
const countdown = ref(0);
const rebindForm = reactive({ phone: "", code: "", reason: "" });
const deletionForm = reactive({ confirmId: "", reason: "", acknowledged: false });
let countdownTimer: number | undefined;

const token = computed(() => session.value?.access_token || "");
const pageNumber = computed(() => Math.floor(offset.value / PAGE_SIZE) + 1);
const accountRoleLabel = computed(() => roleFilter.value === "student" ? "学生" : "老师");
const loginReady = computed(() => loginForm.username.trim() && loginForm.password);
const rebindReady = computed(() =>
  /^1[3-9]\d{9}$/.test(rebindForm.phone.replace(/\s|-/g, ""))
  && /^\d{4,8}$/.test(rebindForm.code)
  && rebindForm.reason.trim().length >= 5,
);
const deletionReady = computed(() =>
  deletionForm.acknowledged
  && deletionForm.confirmId.trim().toLowerCase() === selected.value?.account_id.toLowerCase()
  && deletionForm.reason.trim().length >= 5,
);

function restoreSession(): AdminSession | null {
  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) as AdminSession : null;
  } catch {
    return null;
  }
}

function displayDate(value: string): string {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function actionLabel(action: string): string {
  return {
    "admin.login": "管理员登录",
    "admin.login.failed": "登录失败",
    "student.phone_rebind_code_sent": "发送补绑验证码",
    "student.phone_rebound": "学生手机号补绑",
    "student.account_deleted": "注销学生账号",
    "teacher.account_deleted": "注销教师账号",
  }[action] || action;
}

async function refreshOverview() {
  overview.value = await getAdminOverview(token.value);
}

async function loadAccounts(reset = false) {
  if (reset) offset.value = 0;
  loading.value = true;
  error.value = "";
  try {
    const result = await listManagedAccounts(token.value, {
      role: roleFilter.value,
      query: query.value.trim(),
      limit: PAGE_SIZE,
      offset: offset.value,
    });
    accounts.value = result.accounts;
    hasMore.value = result.has_more;
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "账号加载失败";
  } finally {
    loading.value = false;
  }
}

async function loadAudits() {
  loading.value = true;
  error.value = "";
  try {
    audits.value = (await listAdminAudits(token.value)).audits;
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "审计记录加载失败";
  } finally {
    loading.value = false;
  }
}

async function initializeConsole() {
  await Promise.all([refreshOverview(), loadAccounts(true)]);
}

onMounted(async () => {
  session.value = restoreSession();
  if (!session.value) {
    restoring.value = false;
    return;
  }
  try {
    profile.value = await currentAdmin(session.value.access_token);
    await initializeConsole();
  } catch {
    window.sessionStorage.removeItem(STORAGE_KEY);
    session.value = null;
  } finally {
    restoring.value = false;
  }
});

onBeforeUnmount(() => {
  if (countdownTimer) window.clearInterval(countdownTimer);
});

async function submitLogin() {
  if (!loginReady.value) return;
  loading.value = true;
  error.value = "";
  try {
    const result = await loginAdmin(loginForm.username.trim(), loginForm.password);
    session.value = result;
    profile.value = result.profile;
    window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(result));
    loginForm.password = "";
    await initializeConsole();
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "登录失败";
  } finally {
    loading.value = false;
  }
}

async function signOut() {
  if (token.value) await logoutAdmin(token.value).catch(() => undefined);
  window.sessionStorage.removeItem(STORAGE_KEY);
  session.value = null;
  profile.value = null;
  accounts.value = [];
  audits.value = [];
}

async function switchView(view: "accounts" | "audits") {
  activeView.value = view;
  if (view === "audits") await loadAudits();
}

async function selectAccountRole(role: "student" | "teacher") {
  activeView.value = "accounts";
  roleFilter.value = role;
  await loadAccounts(true);
}

function openRebind(account: ManagedAccount) {
  selected.value = account;
  rebindForm.phone = "";
  rebindForm.code = "";
  rebindForm.reason = "";
  error.value = "";
  success.value = "";
  dialog.value = "rebind";
}

async function openDelete(account: ManagedAccount) {
  selected.value = account;
  deletionForm.confirmId = "";
  deletionForm.reason = "";
  deletionForm.acknowledged = false;
  impact.value = null;
  error.value = "";
  success.value = "";
  dialog.value = "delete";
  actionLoading.value = true;
  try {
    impact.value = await getDeletionImpact(token.value, account);
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "影响范围读取失败";
  } finally {
    actionLoading.value = false;
  }
}

function closeDialog() {
  if (actionLoading.value) return;
  dialog.value = null;
  selected.value = null;
  impact.value = null;
}

async function sendCode() {
  if (!selected.value || countdown.value > 0) return;
  actionLoading.value = true;
  error.value = "";
  success.value = "";
  try {
    const result = await sendStudentRebindCode(
      token.value,
      selected.value.account_id,
      rebindForm.phone,
    );
    countdown.value = result.retry_after;
    success.value = "验证码已发送到新手机号";
    countdownTimer = window.setInterval(() => {
      countdown.value -= 1;
      if (countdown.value <= 0 && countdownTimer) {
        window.clearInterval(countdownTimer);
        countdownTimer = undefined;
      }
    }, 1000);
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "验证码发送失败";
  } finally {
    actionLoading.value = false;
  }
}

async function submitRebind() {
  if (!selected.value || !rebindReady.value) return;
  actionLoading.value = true;
  error.value = "";
  success.value = "";
  try {
    await rebindStudentPhone(token.value, selected.value.account_id, {
      phone: rebindForm.phone,
      verificationCode: rebindForm.code,
      reason: rebindForm.reason,
    });
    success.value = `学生 ${selected.value.account_id} 的手机号已完成补绑，旧会话已失效`;
    dialog.value = null;
    await Promise.all([loadAccounts(), refreshOverview()]);
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "手机号补绑失败";
  } finally {
    actionLoading.value = false;
  }
}

async function submitDeletion() {
  if (!selected.value || !deletionReady.value) return;
  actionLoading.value = true;
  error.value = "";
  success.value = "";
  try {
    const account = { ...selected.value };
    const result = await permanentlyDeleteAccount(
      token.value,
      account,
      deletionForm.reason.trim(),
    );
    success.value = `${account.role === "student" ? "学生" : "教师"}账号 ${account.account_id} 已永久注销；删除范围包含已统计的 ${result.related_records} 条关联记录及其级联数据`;
    dialog.value = null;
    if (accounts.value.length === 1 && offset.value > 0) offset.value -= PAGE_SIZE;
    await Promise.all([loadAccounts(), refreshOverview()]);
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "账号注销失败";
  } finally {
    actionLoading.value = false;
  }
}

async function changePage(direction: -1 | 1) {
  offset.value = Math.max(0, offset.value + direction * PAGE_SIZE);
  await loadAccounts();
}
</script>

<template>
  <main v-if="restoring" class="admin-restoring">
    <span />
    <strong>正在验证管理会话</strong>
    <small>连接问鹿账号管理服务…</small>
  </main>

  <main v-else-if="!profile" class="admin-login">
    <section class="admin-login-story">
      <div class="admin-brand">
        <WenluBrandMark :size="29" />
        <span><strong>问鹿</strong><small>SUPER ADMIN CONSOLE</small></span>
      </div>
      <div class="admin-story-copy">
        <span><ShieldCheck :size="16" />受控账号管理</span>
        <h1>让每一次账号变更<br>都有依据，也有记录。</h1>
        <p>管理学生与教师账号，完成离校注销和学生手机号补绑。敏感信息默认脱敏，所有操作进入审计记录。</p>
        <div>
          <article><Smartphone :size="20" /><span><strong>安全补绑</strong><small>新手机号必须完成短信验证</small></span></article>
          <article><Trash2 :size="20" /><span><strong>谨慎注销</strong><small>执行前预览主要关联数据</small></span></article>
          <article><ClipboardList :size="20" /><span><strong>完整审计</strong><small>操作原因与结果持久留存</small></span></article>
        </div>
      </div>
      <p>管理入口独立于学生端和教师端 · 端口 3010</p>
    </section>
    <section class="admin-login-form">
      <form @submit.prevent="submitLogin">
        <div class="admin-login-icon"><UserCog :size="26" /></div>
        <small>ADMINISTRATOR ACCESS</small>
        <h2>超级管理员登录</h2>
        <p>仅限已授权的系统管理员使用</p>
        <label>
          <span>管理员账号</span>
          <div><BookUser :size="18" /><input v-model="loginForm.username" autocomplete="username" placeholder="请输入管理员账号"></div>
        </label>
        <label>
          <span>管理员密码</span>
          <div><KeyRound :size="18" /><input v-model="loginForm.password" type="password" autocomplete="current-password" placeholder="请输入管理员密码"></div>
        </label>
        <p v-if="error" class="admin-message error">{{ error }}</p>
        <button type="submit" :disabled="!loginReady || loading">
          <RefreshCw v-if="loading" class="spin" :size="17" />
          <ShieldCheck v-else :size="17" />
          {{ loading ? "正在验证" : "进入管理中心" }}
        </button>
        <footer><ShieldCheck :size="14" />会话只保存在当前标签页，关闭后需重新登录</footer>
      </form>
    </section>
  </main>

  <main v-else class="admin-shell">
    <aside class="admin-sidebar">
      <div class="admin-brand">
        <WenluBrandMark :size="27" />
        <span><strong>问鹿管理中心</strong><small>ACCOUNT OPERATIONS</small></span>
      </div>
      <nav>
        <small>账号运营</small>
        <div class="admin-nav-group" :class="{ active: activeView === 'accounts' }">
          <div class="admin-nav-parent"><UsersRound :size="18" /><span>账号管理</span></div>
          <div class="admin-subnav">
            <button :class="{ active: activeView === 'accounts' && roleFilter === 'student' }" @click="selectAccountRole('student')"><i /><span>学生管理</span></button>
            <button :class="{ active: activeView === 'accounts' && roleFilter === 'teacher' }" @click="selectAccountRole('teacher')"><i /><span>老师管理</span></button>
          </div>
        </div>
        <button :class="{ active: activeView === 'audits' }" @click="switchView('audits')">
          <ClipboardList :size="18" /><span>操作审计</span>
        </button>
      </nav>
      <section class="admin-identity">
        <span>{{ profile.username.slice(0, 1).toUpperCase() }}</span>
        <div><strong>{{ profile.username }}</strong><small>超级管理员</small></div>
        <button aria-label="退出登录" title="退出登录" @click="signOut"><LogOut :size="17" /></button>
      </section>
    </aside>

    <section class="admin-main">
      <header>
        <div>
          <small>SUPER ADMIN · 账号安全与数据治理</small>
          <strong>{{ activeView === "accounts" ? accountRoleLabel + "账号管理" : "管理员操作审计" }}</strong>
        </div>
        <span><i />账号服务在线</span>
      </header>

      <div class="admin-content">
        <section v-if="activeView === 'accounts'" class="admin-hero">
          <div>
            <span><ShieldCheck :size="15" />单管理员安全工作台</span>
            <h1>账号管理，应当清晰而克制。</h1>
            <p>手机号始终脱敏展示。学生补绑需要新手机号验证码；账号注销会永久删除关联数据。</p>
          </div>
          <div class="hero-note">
            <AlertTriangle :size="22" />
            <span><strong>教师注销影响更广</strong><small>教师名下班级、成员关系与教案将同步清理</small></span>
          </div>
        </section>

        <section v-if="overview" class="admin-metrics">
          <article><span class="blue"><GraduationCap :size="20" /></span><div><small>学生账号</small><strong>{{ overview.students.total }}</strong><p>{{ overview.students.unbound }} 个未绑手机号</p></div></article>
          <article><span class="green"><UsersRound :size="20" /></span><div><small>教师账号</small><strong>{{ overview.teachers.total }}</strong><p>{{ overview.teachers.unbound }} 个未绑手机号</p></div></article>
          <article><span class="amber"><Smartphone :size="20" /></span><div><small>待补绑账号</small><strong>{{ overview.students.unbound }}</strong><p>仅统计学生账号</p></div></article>
          <article><span class="violet"><ClipboardList :size="20" /></span><div><small>24 小时操作</small><strong>{{ overview.operations_24h }}</strong><p>不含失败登录</p></div></article>
        </section>

        <p v-if="success" class="admin-message success">{{ success }}</p>
        <p v-if="error" class="admin-message error">{{ error }}</p>

        <section v-if="activeView === 'accounts'" class="admin-panel">
          <div class="panel-heading">
            <div><small>ACCOUNT DIRECTORY</small><h2>{{ accountRoleLabel }}账号目录</h2><p>按账号、姓名或完整手机号精确检索，仅显示{{ accountRoleLabel }}账号</p></div>
            <button class="refresh-button" aria-label="刷新账号" title="刷新账号" @click="loadAccounts()"><RefreshCw :size="17" /></button>
          </div>
          <form class="account-toolbar" @submit.prevent="loadAccounts(true)">
            <div class="search-box"><Search :size="17" /><input v-model="query" placeholder="搜索学号、工号、姓名或手机号"><button type="submit">查询</button></div>
          </form>

          <div class="account-table-wrap">
            <table class="account-table">
              <thead><tr><th>身份与账号</th><th>姓名</th><th>学习/任职信息</th><th>绑定手机</th><th>注册时间</th><th>操作</th></tr></thead>
              <tbody>
                <tr v-for="account in accounts" :key="`${account.role}_${account.account_id}`">
                  <td><span class="role-badge" :class="account.role">{{ account.role === "student" ? "学生" : "教师" }}</span><strong>{{ account.account_id }}</strong></td>
                  <td>{{ account.display_name }}</td>
                  <td class="muted-cell">{{ account.context }}</td>
                  <td><span :class="['phone-state', { unbound: account.phone_masked === '未绑定' }]">{{ account.phone_masked }}</span></td>
                  <td class="muted-cell">{{ displayDate(account.created_at) }}</td>
                  <td>
                    <div class="row-actions">
                      <button v-if="account.role === 'student'" class="rebind-button" @click="openRebind(account)"><Smartphone :size="15" />补绑</button>
                      <button class="delete-button" @click="openDelete(account)"><Trash2 :size="15" />注销</button>
                    </div>
                  </td>
                </tr>
                <tr v-if="!loading && accounts.length === 0"><td colspan="6" class="empty-row">没有找到符合条件的{{ accountRoleLabel }}账号</td></tr>
              </tbody>
            </table>
          </div>
          <footer class="table-footer">
            <span>第 {{ pageNumber }} 页 · 每页 {{ PAGE_SIZE }} 条</span>
            <div>
              <button :disabled="offset === 0 || loading" @click="changePage(-1)"><ChevronLeft :size="16" />上一页</button>
              <button :disabled="!hasMore || loading" @click="changePage(1)">下一页<ChevronRight :size="16" /></button>
            </div>
          </footer>
        </section>

        <section v-else class="admin-panel audit-panel">
          <div class="panel-heading">
            <div><small>IMMUTABLE AUDIT TRAIL</small><h2>操作审计</h2><p>记录登录、手机号补绑与账号永久注销</p></div>
            <button class="refresh-button" aria-label="刷新审计" title="刷新审计" @click="loadAudits"><RefreshCw :size="17" /></button>
          </div>
          <div class="audit-list">
            <article v-for="audit in audits" :key="audit.id">
              <span class="audit-icon" :class="{ danger: audit.action.includes('deleted') }">
                <Trash2 v-if="audit.action.includes('deleted')" :size="18" />
                <Smartphone v-else-if="audit.action.includes('phone')" :size="18" />
                <ShieldCheck v-else :size="18" />
              </span>
              <div><strong>{{ actionLabel(audit.action) }}</strong><p>{{ audit.reason }}</p><small>{{ audit.target_account_id || "系统管理员" }} · {{ displayDate(audit.created_at) }}</small></div>
              <span class="audit-status">已记录</span>
            </article>
            <p v-if="!loading && audits.length === 0" class="empty-row">暂无管理员操作记录</p>
          </div>
        </section>
      </div>
    </section>

    <div v-if="dialog" class="admin-dialog-backdrop" @mousedown.self="closeDialog">
      <section class="admin-dialog" :class="{ danger: dialog === 'delete' }" role="dialog" aria-modal="true">
        <button class="dialog-close" aria-label="关闭" @click="closeDialog"><X :size="19" /></button>
        <span class="dialog-icon"><Smartphone v-if="dialog === 'rebind'" :size="24" /><AlertTriangle v-else :size="24" /></span>
        <small>{{ dialog === "rebind" ? "STUDENT PHONE RECOVERY" : "PERMANENT ACCOUNT DELETION" }}</small>
        <h2>{{ dialog === "rebind" ? "为学生补绑手机号" : "确认永久注销账号" }}</h2>
        <p v-if="selected" class="dialog-account">{{ selected.display_name }} · {{ selected.account_id }} · {{ selected.phone_masked }}</p>

        <template v-if="dialog === 'rebind'">
          <div class="dialog-notice"><ShieldCheck :size="17" /><span>新手机号必须由持有人完成短信验证，补绑完成后学生原登录会话将全部失效。</span></div>
          <label><span>新手机号</span><div class="dialog-input"><input v-model="rebindForm.phone" inputmode="tel" maxlength="20" placeholder="请输入中国大陆手机号"><button :disabled="actionLoading || countdown > 0 || !/^1[3-9]\d{9}$/.test(rebindForm.phone.replace(/\s|-/g, ''))" @click="sendCode">{{ countdown > 0 ? `${countdown}s` : "发送验证码" }}</button></div></label>
          <label><span>短信验证码</span><input v-model="rebindForm.code" inputmode="numeric" maxlength="8" placeholder="请输入验证码"></label>
          <label><span>补绑原因</span><textarea v-model="rebindForm.reason" maxlength="500" placeholder="请记录身份核验依据和补绑原因（至少 5 个字符）" /></label>
          <p v-if="success" class="admin-message success">{{ success }}</p>
          <p v-if="error" class="admin-message error">{{ error }}</p>
          <button class="dialog-primary" :disabled="!rebindReady || actionLoading" @click="submitRebind"><Smartphone :size="17" />确认完成补绑</button>
        </template>

        <template v-else>
          <div v-if="impact" class="impact-box">
            <strong>本次将永久清理 {{ impact.related_records }} 条已统计关联记录</strong>
            <div><span v-for="(count, label) in impact.related_counts" :key="label">{{ label }} <b>{{ count }}</b></span></div>
            <p v-if="selected?.role === 'teacher'"><AlertTriangle :size="15" />教师名下班级会被级联删除，班级成员、通知、诊断任务和相关教案也将一并清理。</p>
          </div>
          <label><span>注销原因</span><textarea v-model="deletionForm.reason" maxlength="500" placeholder="例如：学生已离校，经本人/学校确认注销" /></label>
          <label><span>输入账号 {{ selected?.account_id }} 以确认</span><input v-model="deletionForm.confirmId" autocomplete="off" placeholder="请输入完整账号"></label>
          <label class="danger-check"><input v-model="deletionForm.acknowledged" type="checkbox"><span>我确认该操作不可恢复，并已核实账号身份及离校/注销申请。</span></label>
          <p v-if="error" class="admin-message error">{{ error }}</p>
          <button class="dialog-primary danger" :disabled="!deletionReady || actionLoading || !impact" @click="submitDeletion"><Trash2 :size="17" />永久注销并清理数据</button>
        </template>
      </section>
    </div>
  </main>
</template>

<style src="./styles/admin-theme.css"></style>
