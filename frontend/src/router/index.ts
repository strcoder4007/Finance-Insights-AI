import { createRouter, createWebHistory } from "vue-router";
import Chat from "../pages/Chat.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", redirect: "/chat" },
    { path: "/chat", component: Chat },
    { path: "/:pathMatch(.*)*", redirect: "/chat" },
  ],
});

export default router;
