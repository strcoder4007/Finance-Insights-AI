import type { Metric, MetricTimeseriesResponse } from "../api/client";

export type MetricChartType = "line" | "bar";

export type MetricChartSpec = {
  kind: "metric_timeseries";
  metric: Metric;
  title: string;
  color: string;
  type: MetricChartType;
  data: MetricTimeseriesResponse;
};

export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  charts?: MetricChartSpec[];
};

