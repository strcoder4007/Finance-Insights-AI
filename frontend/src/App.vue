<script setup lang="ts">
import { RouterLink, RouterView } from "vue-router";
</script>

<template>
  <div class="container">
    <header class="header panel">
      <div class="brand">
        <div class="title">Finance Insights AI</div>
      </div>
      <nav class="nav">
        <RouterLink class="navlink" to="/chat">Chat</RouterLink>
        <RouterLink class="navlink" to="/metrics">Metrics</RouterLink>
      </nav>
    </header>

    <main class="main">
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  margin-bottom: 16px;
}

.title {
  font-weight: 700;
  font-size: 18px;
  letter-spacing: 0.2px;
}

.subtitle {
  margin-top: 2px;
  font-size: 13px;
}

.nav {
  display: flex;
  gap: 10px;
}

.navlink {
  padding: 8px 10px;
  border-radius: 10px;
  border: 1px solid transparent;
}

.navlink.router-link-active {
  border-color: rgba(94, 234, 212, 0.35);
  background: rgba(94, 234, 212, 0.14);
}
</style>

