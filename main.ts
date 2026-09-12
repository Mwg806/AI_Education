import { createApp } from "vue";

import AdminApp from "@/AdminApp.vue";
import App from "@/App.vue";
import { installAuthenticatedFetch } from "@/lib/auth-client";
import "@/styles/vue-theme.css";

const appMode = import.meta.env.VITE_APP_MODE ?? "student";
const pageMetadata = {
  student: {
    title: "问鹿 · 学生端",
    description: "问鹿学生端智能学习与个性化规划平台",
  },
  teacher: {
    title: "问鹿 · 教师端",
    description: "问鹿教师端智能备课与教学协作平台",
  },
  admin: {
    title: "问鹿 · 管理员端",
    description: "问鹿管理员端账号管理与安全审计平台",
  },
} satisfies Record<
  NonNullable<ImportMetaEnv["VITE_APP_MODE"]>,
  { title: string; description: string }
>;

const metadata = pageMetadata[appMode];
document.title = metadata.title;
document
  .querySelector<HTMLMetaElement>('meta[name="description"]')
  ?.setAttribute("content", metadata.description);

installAuthenticatedFetch();
createApp(appMode === "admin" ? AdminApp : App).mount("#app");
