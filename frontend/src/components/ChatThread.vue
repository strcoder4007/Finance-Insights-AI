<script setup lang="ts">
type ChatMessage = { role: "user" | "assistant"; content: string };

defineProps<{ messages: ChatMessage[] }>();
</script>

<template>
  <div class="thread">
    <div v-if="messages.length === 0" class="empty muted">Ask a question about revenue, net income, or expenses.</div>
    <div v-for="(m, idx) in messages" :key="idx" class="msg" :class="m.role">
      <div class="role">{{ m.role === "user" ? "You" : "AI" }}</div>
      <div class="content">{{ m.content }}</div>
    </div>
  </div>
</template>

<style scoped>
.thread {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.empty {
  padding: 18px;
}

.msg {
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 12px 12px;
  background: rgba(0, 0, 0, 0.16);
}

.msg.user {
  border-color: rgba(94, 234, 212, 0.22);
  background: rgba(94, 234, 212, 0.08);
}

.role {
  font-weight: 600;
  font-size: 12px;
  letter-spacing: 0.3px;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 6px;
}

.content {
  white-space: pre-wrap;
  line-height: 1.35;
}
</style>

