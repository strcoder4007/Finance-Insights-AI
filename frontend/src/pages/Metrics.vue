<script setup lang="ts">
import { computed, ref } from "vue";
import MetricChart from "../components/MetricChart.vue";
import { Metric, getMetricTimeseries, ingest } from "../api/client";

const metric = ref<Metric>("net_income");
const groupBy = ref<"month" | "quarter" | "year">("month");
const includeProvenance = ref(false);
const start = ref<string>("");
const end = ref<string>("");

const loading = ref(false);
const error = ref<string | null>(null);

const series = ref<{ period: string; value: number; provenance?: string }[]>([]);
const total = ref<number>(0);
const currency = ref<string | null>(null);

const labels = computed(() => series.value.map((p) => p.period));
const values = computed(() => series.value.map((p) => p.value));

async function fetchSeries() {
  error.value = null;
  loading.value = true;
  try {
    const res = await getMetricTimeseries({
      metric: metric.value,
      group_by: groupBy.value,
      start: start.value || undefined,
      end: end.value || undefined,
      include_provenance: includeProvenance.value,
    });
    series.value = res.series;
    total.value = res.total;
    currency.value = res.currency;
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e);
  } finally {
    loading.value = false;
  }
}

async function runIngest() {
  error.value = null;
  loading.value = true;
  try {
    await ingest("replace");
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e);
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <section class="panel wrap">
    <div class="controls">
      <div class="row">
        <label>
          Metric
          <select v-model="metric">
            <option value="net_income">net_income</option>
            <option value="revenue_total">revenue_total</option>
            <option value="cogs_total">cogs_total</option>
            <option value="gross_profit">gross_profit</option>
            <option value="operating_expenses_total">operating_expenses_total</option>
            <option value="operating_profit">operating_profit</option>
            <option value="non_operating_revenue_total">non_operating_revenue_total</option>
            <option value="non_operating_expenses_total">non_operating_expenses_total</option>
            <option value="taxes_total">taxes_total</option>
          </select>
        </label>

        <label>
          Group by
          <select v-model="groupBy">
            <option value="month">month</option>
            <option value="quarter">quarter</option>
            <option value="year">year</option>
          </select>
        </label>

        <label class="toggle">
          <input type="checkbox" v-model="includeProvenance" />
          include provenance
        </label>
      </div>

      <div class="row">
        <label>
          Start
          <input type="date" v-model="start" />
        </label>
        <label>
          End
          <input type="date" v-model="end" />
        </label>

        <button class="btn" :disabled="loading" @click="runIngest">Ingest bundled JSON</button>
        <button class="btn primary" :disabled="loading" @click="fetchSeries">{{ loading ? "Loading..." : "Fetch" }}</button>
      </div>
    </div>

    <div v-if="error" class="error panel">{{ error }}</div>

    <div v-if="series.length === 0" class="empty muted">Fetch a metric to display a chart.</div>

    <div v-else class="content">
      <div class="summary">
        <div class="kpi">
          <div class="kpiLabel muted">Total</div>
          <div class="kpiValue">
            {{ total.toLocaleString(undefined, { maximumFractionDigits: 2 }) }}
            <span class="muted" v-if="currency">{{ currency }}</span>
          </div>
        </div>
      </div>

      <MetricChart :title="metric" :labels="labels" :values="values" />

      <div class="tableWrap">
        <table>
          <thead>
            <tr>
              <th>Period</th>
              <th>Value</th>
              <th v-if="includeProvenance">Provenance</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="p in series" :key="p.period">
              <td>{{ p.period }}</td>
              <td>{{ p.value.toLocaleString(undefined, { maximumFractionDigits: 2 }) }}</td>
              <td v-if="includeProvenance">{{ p.provenance ?? "" }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </section>
</template>

<style scoped>
.wrap {
  padding: 14px;
}

.controls {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 12px;
}

.row {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  align-items: end;
}

label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
}

.toggle {
  flex-direction: row;
  align-items: center;
  gap: 8px;
  padding: 10px 0 0;
}

.content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.summary {
  display: flex;
  gap: 12px;
}

.kpiLabel {
  font-size: 12px;
}

.kpiValue {
  font-size: 22px;
  font-weight: 700;
}

.tableWrap {
  overflow: auto;
  border: 1px solid var(--border);
  border-radius: 12px;
}

.empty {
  padding: 18px;
}

.error {
  border-color: rgba(251, 113, 133, 0.35);
  padding: 12px;
  background: rgba(251, 113, 133, 0.12);
}
</style>

