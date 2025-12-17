export type IngestMode = "replace" | "upsert";

export type Metric =
  | "revenue_total"
  | "cogs_total"
  | "gross_profit"
  | "operating_expenses_total"
  | "operating_profit"
  | "non_operating_revenue_total"
  | "non_operating_expenses_total"
  | "taxes_total"
  | "net_income";

export type Category =
  | "revenue"
  | "cogs"
  | "operating_expense"
  | "non_operating_revenue"
  | "non_operating_expense"
  | "other_income"
  | "other_expense"
  | "unknown";

export type MetricSeriesPoint = { period: string; value: number; provenance?: string };
export type MetricTimeseriesResponse = {
  metric: string;
  total: number;
  series: MetricSeriesPoint[];
  currency: string | null;
};

export type BreakdownRow = { name: string; value: number; share: number | null; provenance?: string };
export type BreakdownResponse = { category: string; total: number; rows: BreakdownRow[]; currency: string | null };

export type ChatResponse = {
  session_id: string;
  answer: string;
  supporting_data?: unknown;
  tool_calls?: unknown;
};

const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://localhost:8000/api/v1";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `Request failed: ${res.status}`);
  }
  return (await res.json()) as T;
}

export function ingest(mode: IngestMode = "replace") {
  return request("/ingest", { method: "POST", body: JSON.stringify({ mode }) });
}

export function getPeriods(includeProvenance = false) {
  const q = includeProvenance ? "?include_provenance=true" : "";
  return request(`/periods${q}`);
}

export function getMetricTimeseries(params: {
  metric: Metric;
  start?: string;
  end?: string;
  group_by?: "month" | "quarter" | "year";
  include_provenance?: boolean;
}) {
  const search = new URLSearchParams();
  search.set("metric", params.metric);
  if (params.start) search.set("start", params.start);
  if (params.end) search.set("end", params.end);
  if (params.group_by) search.set("group_by", params.group_by);
  if (params.include_provenance) search.set("include_provenance", "true");
  return request<MetricTimeseriesResponse>(`/metrics/timeseries?${search.toString()}`);
}

export function getBreakdown(params: {
  category: Category;
  start?: string;
  end?: string;
  level?: number;
  include_provenance?: boolean;
}) {
  const search = new URLSearchParams();
  search.set("category", params.category);
  if (params.start) search.set("start", params.start);
  if (params.end) search.set("end", params.end);
  if (params.level) search.set("level", String(params.level));
  if (params.include_provenance) search.set("include_provenance", "true");
  return request<BreakdownResponse>(`/breakdown?${search.toString()}`);
}

export function chat(sessionId: string | null, message: string) {
  return request<ChatResponse>("/chat", {
    method: "POST",
    body: JSON.stringify({ session_id: sessionId || undefined, message }),
  });
}

