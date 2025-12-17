<script setup lang="ts">
import { RouterView } from "vue-router";
</script>

<template>
  <div class="container">
    <header class="header panel">
      <div class="brand">
        <div class="title">Finance Insights AI</div>
      </div>
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
  justify-content: flex-start;
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



</style>
