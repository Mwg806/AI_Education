import { createApp } from "vue";

import AdminApp from "@/AdminApp.vue";
import App from "@/App.vue";
import { installAuthenticatedFetch } from "@/lib/auth-client";
import "@/styles/vue-theme.css";

installAuthenticatedFetch();
createApp(import.meta.env.VITE_APP_MODE === "admin" ? AdminApp : App).mount("#app");
