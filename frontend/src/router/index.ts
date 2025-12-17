import { createRouter, createWebHistory } from "vue-router";
import Chat from "../pages/Chat.vue";
import Metrics from "../pages/Metrics.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", redirect: "/chat" },
    { path: "/chat", component: Chat },
    { path: "/metrics", component: Metrics },
  ],
});

export default router;

