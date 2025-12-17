<script setup lang="ts">
import { computed, nextTick, ref } from "vue";
import ChatThread from "../components/ChatThread.vue";
import ChartModal from "../components/ChartModal.vue";
import MetricChart from "../components/MetricChart.vue";
import { chat, ingest, type Metric } from "../api/client";
import type { ChatMessage, MetricChartSpec } from "../types/chat";

const sessionId = ref<string | null>(localStorage.getItem("fia_session_id"));
const messages = ref<ChatMessage[]>([]);
const input = ref("");
const inputRef = ref<HTMLTextAreaElement | null>(null);
const isSending = ref(false);
const error = ref<string | null>(null);
const showData = ref(false);
const lastSupportingData = ref<unknown>(null);
const lastToolCalls = ref<unknown>(null);
const chartModal = ref<MetricChartSpec | null>(null);

const canSend = computed(() => input.value.trim().length > 0 && !isSending.value);

const exampleQuestions = [
  "From 2024-01-01 to 2024-12-31, show net income by month.",
  "Compare net income between 2024-Q1 and 2024-Q2.",
  "From 2024-01-01 to 2024-12-31, show revenue_total by quarter.",
  "From 2024-01-01 to 2024-12-31, break down operating_expense (high level).",
] as const;

const METRIC_META: Record<Metric, { title: string; color: string }> = {
  revenue_total: { title: "Revenue", color: "rgba(94, 234, 212, 0.9)" },
  cogs_total: { title: "COGS", color: "rgba(251, 113, 133, 0.9)" },
  gross_profit: { title: "Gross Profit", color: "rgba(96, 165, 250, 0.9)" },
  operating_expenses_total: { title: "Operating Expenses", color: "rgba(251, 191, 36, 0.9)" },
  operating_profit: { title: "Operating Profit", color: "rgba(167, 139, 250, 0.9)" },
  non_operating_revenue_total: { title: "Non-operating Revenue", color: "rgba(52, 211, 153, 0.9)" },
  non_operating_expenses_total: { title: "Non-operating Expenses", color: "rgba(249, 115, 22, 0.9)" },
  taxes_total: { title: "Taxes", color: "rgba(244, 114, 182, 0.9)" },
  net_income: { title: "Net Income", color: "rgba(34, 197, 94, 0.9)" },
};

function extractMetricCharts(supportingData: unknown): MetricChartSpec[] {
  const charts: MetricChartSpec[] = [];

  const metrics = (supportingData as any)?.metrics;
  if (Array.isArray(metrics)) {
    for (const m of metrics) {
      const metric = (m as any)?.metric;
      if (typeof metric !== "string") continue;
      if (!Object.prototype.hasOwnProperty.call(METRIC_META, metric)) continue;
      const meta = METRIC_META[metric as Metric];
      const data = m as MetricChartSpec["data"];
      if (!Array.isArray(data?.series) || data.series.length === 0) continue;
      charts.push({
        kind: "metric_timeseries",
        metric: metric as Metric,
        title: meta.title,
        color: meta.color,
        type: "line",
        data,
      });
    }
  }

  const comparisons = (supportingData as any)?.comparisons;
  if (Array.isArray(comparisons)) {
    for (const c of comparisons) {
      const metric = (c as any)?.metric;
      if (typeof metric !== "string") continue;
      if (!Object.prototype.hasOwnProperty.call(METRIC_META, metric)) continue;
      const periodA = String((c as any)?.period_a ?? "");
      const periodB = String((c as any)?.period_b ?? "");
      const aValue = Number((c as any)?.a_value);
      const bValue = Number((c as any)?.b_value);
      if (!periodA || !periodB) continue;
      if (!Number.isFinite(aValue) || !Number.isFinite(bValue)) continue;

      const meta = METRIC_META[metric as Metric];
      const data: MetricChartSpec["data"] = {
        metric,
        total: bValue,
        series: [
          { period: periodA, value: aValue },
          { period: periodB, value: bValue },
        ],
        currency: (c as any)?.currency ?? null,
      };
      charts.push({
        kind: "metric_timeseries",
        metric: metric as Metric,
        title: meta.title,
        color: meta.color,
        type: "line",
        data,
      });
    }
  }
  return charts;
}

async function useExample(q: string) {
  input.value = q;
  await nextTick();
  inputRef.value?.focus();
}

async function send() {
  if (!canSend.value) return;
  error.value = null;
  const text = input.value.trim();
  input.value = "";
  messages.value.push({ role: "user", content: text });
  isSending.value = true;

  try {
    const res = await chat(sessionId.value, text);
    sessionId.value = res.session_id;
    localStorage.setItem("fia_session_id", res.session_id);
    const charts = extractMetricCharts(res.supporting_data);
    messages.value.push({ role: "assistant", content: res.answer, charts: charts.length ? charts : undefined });
    lastSupportingData.value = res.supporting_data ?? null;
    lastToolCalls.value = res.tool_calls ?? null;
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e);
  } finally {
    isSending.value = false;
  }
}

async function runIngest() {
  error.value = null;
  isSending.value = true;
  try {
    await ingest("replace");
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e);
  } finally {
    isSending.value = false;
  }
}
</script>

<template>
  <div class="layout" :class="{ withAside: showData }">
    <section class="left panel">
      <div class="toolbar">
        <button class="btn" :disabled="isSending" @click="runIngest">Ingest bundled JSON</button>
        <button class="btn" @click="showData = !showData">{{ showData ? "Hide data" : "Show data" }}</button>
      </div>

      <div class="examples">
        <div class="examplesLabel muted">Example questions</div>
        <div class="chips">
          <button v-for="q in exampleQuestions" :key="q" class="chip" type="button" @click="useExample(q)">
            {{ q }}
          </button>
        </div>
      </div>

      <div v-if="error" class="error panel">{{ error }}</div>

      <ChatThread :messages="messages" @open-chart="chartModal = $event" />

      <div class="composer">
        <textarea
          ref="inputRef"
          v-model="input"
          placeholder="Ask: “What’s net income trend in 2024?”"
          rows="3"
          @keydown.enter.exact.prevent="send"
        />
        <button class="btn primary" :disabled="!canSend" @click="send">{{ isSending ? "Working..." : "Send" }}</button>
      </div>
    </section>

    <aside v-if="showData" class="right panel">
      <div class="sideTitle">Query (tool calls)</div>
      <pre class="json">{{ JSON.stringify(lastToolCalls, null, 2) }}</pre>
      <div class="sideTitle">Fetched data (tool outputs)</div>
      <pre class="json">{{ JSON.stringify(lastSupportingData, null, 2) }}</pre>
    </aside>

    <ChartModal :open="chartModal !== null" :title="chartModal?.metric ?? ''" @close="chartModal = null">
      <div v-if="chartModal && chartModal.data.series.length">
        <MetricChart
          :title="chartModal.title"
          :labels="chartModal.data.series.map((s) => s.period)"
          :values="chartModal.data.series.map((s) => s.value)"
          :type="chartModal.type"
          :color="chartModal.color"
          :height="560"
        />
      </div>
      <div v-else class="muted">No data available for this metric.</div>
    </ChartModal>
  </div>
</template>

<style scoped>
.layout {
  display: grid;
  grid-template-columns: 1fr;
  gap: 14px;
}

@media (min-width: 980px) {
  .layout.withAside {
    grid-template-columns: minmax(0, 1fr) 420px;
  }
}

.left {
  min-width: 0;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.toolbar {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.examples {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.examplesLabel {
  font-size: 12px;
  letter-spacing: 0.3px;
  text-transform: uppercase;
}

.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.chip {
  appearance: none;
  border: 1px solid var(--border);
  background: rgba(255, 255, 255, 0.06);
  color: rgba(255, 255, 255, 0.88);
  padding: 8px 10px;
  border-radius: 999px;
  cursor: pointer;
  font-size: 13px;
  text-align: left;
}

.chip:hover {
  border-color: rgba(255, 255, 255, 0.22);
}

.composer {
  display: grid;
  grid-template-columns: 1fr 120px;
  gap: 10px;
  align-items: start;
}

.hint {
  font-size: 12px;
}

.right {
  min-width: 0;
  padding: 14px;
  overflow: auto;
}

.sideTitle {
  font-weight: 700;
  margin-bottom: 8px;
}

.json {
  margin: 0 0 16px;
  font-size: 12px;
  line-height: 1.35;
  white-space: pre-wrap;
  word-break: break-word;
  color: rgba(255, 255, 255, 0.8);
}

.error {
  border-color: rgba(251, 113, 133, 0.35);
  padding: 12px;
  color: rgba(255, 255, 255, 0.9);
  background: rgba(251, 113, 133, 0.12);
}
</style>
