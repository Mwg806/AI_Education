import { createApp } from "vue";

import App from "@/App.vue";
import { installAuthenticatedFetch } from "@/lib/auth-client";
import "@/styles/vue-theme.css";

installAuthenticatedFetch();
createApp(App).mount("#app");
