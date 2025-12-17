<script setup lang="ts">
import {
  BarController,
  BarElement,
  CategoryScale,
  Chart,
  Legend,
  LinearScale,
  LineController,
  LineElement,
  PointElement,
  Tooltip,
} from "chart.js";
import { onBeforeUnmount, onMounted, ref, watch } from "vue";

Chart.register(BarController, BarElement, LineController, LineElement, PointElement, LinearScale, CategoryScale, Tooltip, Legend);

const props = defineProps<{
  title: string;
  labels: string[];
  values: number[];
  type?: "line" | "bar";
  color?: string;
  height?: number;
}>();

const canvasRef = ref<HTMLCanvasElement | null>(null);
let chart: Chart | null = null;

function formatNumber(value: unknown): string {
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(n)) return String(value);
  return n.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function render() {
  if (!canvasRef.value) return;
  if (chart) chart.destroy();

  const type = props.type ?? "line";
  const baseColor = props.color ?? "rgba(94, 234, 212, 0.9)";

  const borderColor = baseColor;
  const backgroundColor =
    baseColor.startsWith("rgba(") ? baseColor.replace(/rgba\\(([^)]+),\\s*[^)]+\\)/, "rgba($1, 0.18)") : baseColor;

  chart = new Chart(canvasRef.value, {
    type,
    data: {
      labels: props.labels,
      datasets: [
        {
          label: props.title,
          data: props.values,
          borderColor,
          backgroundColor,
          borderWidth: type === "bar" ? 0 : 2,
          pointRadius: type === "bar" ? 0 : 2,
          tension: type === "bar" ? 0 : 0.25,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: true },
      },
      scales: {
        x: { ticks: { color: "rgba(255,255,255,0.7)" }, grid: { color: "rgba(255,255,255,0.08)" } },
        y: {
          ticks: { color: "rgba(255,255,255,0.7)", callback: (v) => formatNumber(v) },
          grid: { color: "rgba(255,255,255,0.08)" },
        },
      },
    },
  });
}

onMounted(render);
watch(() => [props.labels, props.values, props.title], render, { deep: true });
onBeforeUnmount(() => chart?.destroy());
</script>

<template>
  <div class="chartWrap" :style="{ height: `${height ?? 180}px` }">
    <canvas ref="canvasRef"></canvas>
  </div>
</template>

<style scoped>
.chartWrap {
  width: 100%;
  padding: 10px;
  box-sizing: border-box;
}
</style>
