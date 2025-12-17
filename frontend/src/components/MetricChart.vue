<script setup lang="ts">
import { Chart, LineController, LineElement, PointElement, LinearScale, CategoryScale, Tooltip, Legend } from "chart.js";
import { onBeforeUnmount, onMounted, ref, watch } from "vue";

Chart.register(LineController, LineElement, PointElement, LinearScale, CategoryScale, Tooltip, Legend);

const props = defineProps<{
  title: string;
  labels: string[];
  values: number[];
}>();

const canvasRef = ref<HTMLCanvasElement | null>(null);
let chart: Chart | null = null;

function render() {
  if (!canvasRef.value) return;
  if (chart) chart.destroy();

  chart = new Chart(canvasRef.value, {
    type: "line",
    data: {
      labels: props.labels,
      datasets: [
        {
          label: props.title,
          data: props.values,
          borderColor: "rgba(94, 234, 212, 0.9)",
          backgroundColor: "rgba(94, 234, 212, 0.2)",
          pointRadius: 2,
          tension: 0.25,
        },
      ],
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: true },
      },
      scales: {
        x: { ticks: { color: "rgba(255,255,255,0.7)" }, grid: { color: "rgba(255,255,255,0.08)" } },
        y: { ticks: { color: "rgba(255,255,255,0.7)" }, grid: { color: "rgba(255,255,255,0.08)" } },
      },
    },
  });
}

onMounted(render);
watch(() => [props.labels, props.values, props.title], render, { deep: true });
onBeforeUnmount(() => chart?.destroy());
</script>

<template>
  <div class="chartWrap">
    <canvas ref="canvasRef"></canvas>
  </div>
</template>

<style scoped>
.chartWrap {
  width: 100%;
  padding: 10px;
}
</style>

