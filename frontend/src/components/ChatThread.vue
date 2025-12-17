<script setup lang="ts">
import type { ChatMessage, MetricChartSpec } from "../types/chat";
import MetricChart from "./MetricChart.vue";

defineProps<{ messages: ChatMessage[] }>();

const emit = defineEmits<{
  (e: "open-chart", chart: MetricChartSpec): void;
}>();
</script>

<template>
  <div class="thread">
    <div v-if="messages.length === 0" class="empty muted">Ask a question about revenue, net income, or expenses.</div>
    <div v-for="(m, idx) in messages" :key="idx" class="msg" :class="m.role">
      <div class="role">{{ m.role === "user" ? "You" : "AI" }}</div>
      <div class="content">{{ m.content }}</div>

      <div v-if="m.role === 'assistant' && m.charts && m.charts.length" class="charts">
        <div v-for="c in m.charts" :key="`${idx}-${c.metric}`" class="chartCard">
          <div class="chartHeader">
            <div class="chartTitle">{{ c.metric }}</div>
            <button class="btn" type="button" @click="emit('open-chart', c)">Full screen</button>
          </div>
          <MetricChart
            :title="c.title"
            :labels="c.data.series.map((s) => s.period)"
            :values="c.data.series.map((s) => s.value)"
            :type="c.type"
            :color="c.color"
            :height="190"
          />
        </div>
      </div>
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

.charts {
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.chartCard {
  border: 1px solid var(--border);
  border-radius: 14px;
  background: rgba(0, 0, 0, 0.14);
  overflow: hidden;
}

.chartHeader {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 10px 0;
}

.chartTitle {
  font-weight: 700;
  font-size: 13px;
  letter-spacing: 0.2px;
}
</style>
