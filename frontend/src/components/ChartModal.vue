<script setup lang="ts">
import { onBeforeUnmount, onMounted } from "vue";

const props = defineProps<{
  open: boolean;
  title: string;
}>();

const emit = defineEmits<{
  (e: "close"): void;
}>();

function onKeyDown(e: KeyboardEvent) {
  if (!props.open) return;
  if (e.key === "Escape") emit("close");
}

onMounted(() => window.addEventListener("keydown", onKeyDown));
onBeforeUnmount(() => window.removeEventListener("keydown", onKeyDown));
</script>

<template>
  <teleport to="body">
    <div v-if="open" class="overlay" @click.self="emit('close')">
      <div class="modal panel">
        <div class="header">
          <div class="title">{{ title }}</div>
          <button class="btn" type="button" @click="emit('close')">Close</button>
        </div>
        <div class="body">
          <slot />
        </div>
      </div>
    </div>
  </teleport>
</template>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.58);
  backdrop-filter: blur(6px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  z-index: 9999;
}

.modal {
  width: min(1100px, 96vw);
  height: min(720px, 92vh);
  display: flex;
  flex-direction: column;
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 14px 14px 10px;
  border-bottom: 1px solid var(--border);
}

.title {
  font-weight: 700;
  font-size: 14px;
  letter-spacing: 0.2px;
}

.body {
  padding: 12px;
  overflow: auto;
  flex: 1;
}
</style>

