import type { GetToken } from "@clerk/types";
import { useCallback, useEffect, useState } from "react";

import { resolveApiUrl } from "./api";

interface CachePolicy {
  freshMs: number;
  maxAgeMs: number;
}

interface SessionCacheEntry {
  staleAt: number;
  expiresAt: number;
  value: unknown;
}

const sessionResponseCache = new Map<string, SessionCacheEntry>();
const pendingSessionRequests = new Map<string, Promise<unknown>>();
const cacheSubscribers = new Map<string, Set<(value: unknown) => void>>();
const latestPathValues = new Map<string, unknown>();
const AUTH_TOKEN_RETRY_COUNT = 15;
const AUTH_TOKEN_RETRY_DELAY_MS = 150;

interface WorkspaceQueryOptions {
  enabled?: boolean;
}

function cachePolicyForPath(path: string): CachePolicy {
  if (path === "/api/dashboard/summary") {
    return { freshMs: 12_000, maxAgeMs: 75_000 };
  }
  if (path === "/api/business") {
    return { freshMs: 60_000, maxAgeMs: 5 * 60_000 };
  }
  if (path.startsWith("/api/suppliers")) {
    return { freshMs: 45_000, maxAgeMs: 4 * 60_000 };
  }
  if (path === "/api/products" || path.startsWith("/api/reports")) {
    return { freshMs: 20_000, maxAgeMs: 2 * 60_000 };
  }
  if (path.startsWith("/api/orders") || path.startsWith("/api/inventory")) {
    return { freshMs: 5_000, maxAgeMs: 45_000 };
  }
  if (path.startsWith("/api/ai/")) {
    return { freshMs: 8_000, maxAgeMs: 45_000 };
  }
  return { freshMs: 15_000, maxAgeMs: 90_000 };
}

export interface Business {
  business_id: string;
  name: string;
  country: string;
  currency: string;
  available_cash: number;
  ai_enabled: boolean;
  ai_automation_enabled: boolean;
  notification_email?: string | null;
  critical_alerts_enabled: boolean;
}

export interface Product {
  product_id: string;
  sku: string;
  name: string;
  category: string;
  current_stock: number;
  reorder_point: number;
  target_days_of_cover: number;
  lead_time_days: number;
  avg_daily_demand: number;
  unit_cost: number;
  preferred_supplier_id?: string | null;
}

export interface InventoryHealthItem {
  product_id: string;
  sku: string;
  product_name: string;
  current_stock: number;
  reorder_point: number;
  days_of_cover: number;
  lead_time_days: number;
  risk_level: "healthy" | "watch" | "high" | "critical";
}

export interface InventoryMovement {
  movement_id: string;
  product_id: string;
  movement_type: "sale" | "purchase" | "adjustment";
  quantity: number;
  note?: string | null;
  occurred_at: string;
}

export interface Job {
  job_id: string;
  job_type: string;
  status: string;
  result_report_id?: string | null;
  created_at?: string;
  completed_at?: string | null;
}

export interface ReportRecommendation {
  product_id: string;
  sku: string;
  product_name: string;
  current_stock: number;
  reorder_point: number;
  days_of_cover: number;
  eoq_order_qty: number;
  recommended_order_qty: number;
  estimated_cost: number;
  urgency: "low" | "medium" | "high" | "critical";
  recommendation_type: "buy_now" | "wait" | "split_order";
  confidence: "medium" | "high";
  rationale: string;
}

export interface Report {
  report_id: string;
  summary: string;
  total_recommended_spend: number;
  affordable_now: boolean;
  actions: string[];
  recommendations: ReportRecommendation[];
  generated_at?: string;
}

export interface PurchaseOrder {
  order_id: string;
  product_id: string;
  sku: string;
  product_name: string;
  quantity: number;
  estimated_cost: number;
  status:
    | "draft"
    | "approved"
    | "placed"
    | "in_transit"
    | "partially_received"
    | "arrived"
    | "canceled"
    | "delayed";
  supplier_id?: string | null;
  supplier_name?: string | null;
  expected_delivery_date?: string | null;
  received_quantity: number;
  last_received_at?: string | null;
  is_late: boolean;
  days_late: number;
  source_report_id?: string | null;
  placed_by_type: "user" | "llm" | "system";
  placed_by_label?: string | null;
  note?: string | null;
  created_at?: string;
}

export interface Supplier {
  supplier_id: string;
  name: string;
  contact_phone?: string | null;
  lead_time_days: number;
  reliability_score: number;
  notes?: string | null;
}

export interface SupplierScorecard {
  supplier_id: string;
  supplier_name: string;
  reliability_score: number;
  configured_lead_time_days: number;
  total_orders: number;
  open_orders: number;
  arrived_orders: number;
  delayed_orders: number;
  late_open_orders: number;
  on_time_rate: number;
  fill_rate: number;
  average_delay_days: number;
  open_order_value: number;
}

export interface ForecastInsight {
  product_id: string;
  sku: string;
  product_name: string;
  baseline_daily_demand: number;
  forecast_daily_demand: number;
  trend_direction: "up" | "down" | "steady";
  confidence: "medium" | "high";
  recent_sales_average: number;
  predicted_7d_demand: number;
  predicted_30d_demand: number;
}

export interface AnomalyInsight {
  anomaly_type: "sales_spike" | "supplier_delay" | "cash_pressure";
  severity: "watch" | "high" | "critical";
  title: string;
  detail: string;
  related_product_id?: string | null;
  related_supplier_id?: string | null;
  related_order_id?: string | null;
}

export interface AutoOrderResult {
  created_orders: PurchaseOrder[];
  skipped_products: string[];
  summary: string;
}

export interface ChatResponse {
  answer: string;
  used_ai: boolean;
  confidence: "low" | "medium" | "high";
  refused: boolean;
  refusal_reason?: string | null;
}

export interface MorningBriefResponse {
  summary: string;
  priorities: string[];
  used_ai: boolean;
  confidence: "low" | "medium" | "high";
}

export interface DashboardSummaryResponse {
  business: Business;
  inventory_health: InventoryHealthItem[];
  orders: PurchaseOrder[];
  latest_report: Report | null;
  forecasts: ForecastInsight[];
  anomalies: AnomalyInsight[];
  morning_brief: MorningBriefResponse;
}

export interface ScenarioAnalysisResponse {
  scenario_cash: number;
  summary: string;
  recommended_skus: string[];
  deferred_skus: string[];
  used_ai: boolean;
  confidence: "low" | "medium" | "high";
}

export interface ReportComparisonResponse {
  latest_report_id?: string | null;
  previous_report_id?: string | null;
  summary: string;
  changes: string[];
  used_ai: boolean;
  confidence: "low" | "medium" | "high";
}

export interface AIAuditLog {
  audit_id: string;
  feature: "chat" | "report" | "brief" | "scenario" | "comparison";
  used_ai: boolean;
  status: "accepted" | "fallback" | "refused";
  input_preview: string;
  output_preview?: string | null;
  confidence?: "low" | "medium" | "high" | null;
  reason?: string | null;
  input_tokens?: number | null;
  output_tokens?: number | null;
  total_tokens?: number | null;
  created_at: string;
}

export interface ObservabilityMetrics {
  requests: {
    total_requests: number;
    error_rate: number;
    average_latency_ms: number;
    p95_latency_ms: number;
    sample_size: number;
    status_counts: Record<string, number>;
    requests_by_route: Record<string, number>;
    server_errors_by_route: Record<string, number>;
  };
  ai: {
    total_ai_events: number;
    success_rate: number;
    fallback_rate: number;
    refusal_rate: number;
    status_counts: Record<string, number>;
    feature_counts: Record<string, number>;
    token_usage: {
      input_tokens: number;
      output_tokens: number;
      total_tokens: number;
    };
  };
  notes: string[];
}

export interface OrderNotificationEvent {
  event_id: string;
  order_id: string;
  sku: string;
  recipient_email?: string | null;
  placed_by_type: "user" | "llm" | "system";
  placed_by_label?: string | null;
  status: "sent" | "failed";
  detail: string;
  created_at: string;
}

export interface TestNotificationResponse {
  sent: boolean;
  recipient_email?: string | null;
  detail: string;
}

async function readErrorDetail(response: Response): Promise<string | null> {
  const contentType = response.headers.get("content-type") || "";
  try {
    if (contentType.includes("application/json")) {
      const payload = await response.json();
      if (typeof payload?.detail === "string" && payload.detail.trim()) {
        return payload.detail;
      }
    }
    const text = await response.text();
    return text.trim() || null;
  } catch {
    return null;
  }
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

async function getSessionToken(getToken: GetToken): Promise<string | null> {
  for (let attempt = 0; attempt <= AUTH_TOKEN_RETRY_COUNT; attempt += 1) {
    const token = await getToken();
    if (token) {
      return token;
    }
    if (attempt < AUTH_TOKEN_RETRY_COUNT && typeof window !== "undefined") {
      await delay(AUTH_TOKEN_RETRY_DELAY_MS);
    }
  }
  return null;
}

function normalizeMethod(init?: RequestInit): string {
  return (init?.method || "GET").toUpperCase();
}

function isCacheableRequest(method: string, init?: RequestInit): boolean {
  return method === "GET" && !init?.body;
}

function cacheKeyForRequest(apiUrl: string, path: string, token: string | null): string {
  return `${token || "anonymous"}::${apiUrl}${path}`;
}

function scopedPathKey(path: string, token: string | null): string {
  return `${token || "anonymous"}::${path}`;
}

function isScopedPathMatch(scopedKey: string, path: string): boolean {
  return scopedKey.endsWith(`::${path}`) || scopedKey.includes(`::${path}/`);
}

function cacheKeyMatchesPath(cacheKey: string, path: string): boolean {
  return cacheKey.endsWith(path) || cacheKey.includes(`${path}/`);
}

function subscribeToPath(path: string, token: string | null, listener: (value: unknown) => void): () => void {
  const key = scopedPathKey(path, token);
  const listeners = cacheSubscribers.get(key) || new Set<(value: unknown) => void>();
  listeners.add(listener);
  cacheSubscribers.set(key, listeners);
  return () => {
    const current = cacheSubscribers.get(key);
    if (!current) {
      return;
    }
    current.delete(listener);
    if (current.size === 0) {
      cacheSubscribers.delete(key);
    }
  };
}

function publishPathUpdate(path: string, token: string | null, value: unknown): void {
  const key = scopedPathKey(path, token);
  latestPathValues.set(key, value);
  const listeners = cacheSubscribers.get(key);
  if (!listeners) {
    return;
  }
  for (const listener of listeners) {
    listener(value);
  }
}

function readCachedEntry<T>(cacheKey: string): SessionCacheEntry | null {
  const cached = sessionResponseCache.get(cacheKey);
  if (!cached) {
    return null;
  }
  if (cached.expiresAt <= Date.now()) {
    sessionResponseCache.delete(cacheKey);
    return null;
  }
  return cached;
}

function storeCachedValue<T>(
  cacheKey: string,
  path: string,
  token: string | null,
  value: T,
  policy: CachePolicy,
): void {
  const now = Date.now();
  sessionResponseCache.set(cacheKey, {
    staleAt: now + policy.freshMs,
    expiresAt: now + policy.maxAgeMs,
    value,
  });
  publishPathUpdate(path, token, value);
}

export function clearWorkspaceSessionCache(): void {
  sessionResponseCache.clear();
  pendingSessionRequests.clear();
  latestPathValues.clear();
}

function invalidateWorkspacePaths(paths: string[]): void {
  for (const [cacheKey] of sessionResponseCache.entries()) {
    if (paths.some((path) => cacheKeyMatchesPath(cacheKey, path))) {
      sessionResponseCache.delete(cacheKey);
    }
  }
  for (const [cacheKey] of pendingSessionRequests.entries()) {
    if (paths.some((path) => cacheKeyMatchesPath(cacheKey, path))) {
      pendingSessionRequests.delete(cacheKey);
    }
  }
  for (const [scopedKey] of latestPathValues.entries()) {
    if (paths.some((path) => isScopedPathMatch(scopedKey, path))) {
      latestPathValues.delete(scopedKey);
    }
  }
}

function invalidationPathsForMutation(path: string): string[] {
  if (path === "/api/products") {
    return ["/api/products", "/api/inventory/health", "/api/ai/forecast", "/api/ai/anomalies", "/api/ai/brief", "/api/dashboard/summary"];
  }
  if (path === "/api/inventory/movements") {
    return ["/api/products", "/api/inventory/movements", "/api/inventory/health", "/api/ai/forecast", "/api/ai/anomalies", "/api/ai/brief", "/api/dashboard/summary"];
  }
  if (path.endsWith("/receive")) {
    return [
      "/api/orders",
      "/api/products",
      "/api/inventory/movements",
      "/api/inventory/health",
      "/api/ai/forecast",
      "/api/ai/anomalies",
      "/api/ai/brief",
      "/api/notifications/orders",
      "/api/suppliers/scorecards",
      "/api/dashboard/summary",
    ];
  }
  if (path === "/api/orders" || path.startsWith("/api/orders/")) {
    return ["/api/orders", "/api/ai/anomalies", "/api/ai/brief", "/api/notifications/orders", "/api/suppliers/scorecards", "/api/dashboard/summary"];
  }
  if (path === "/api/suppliers" || path.startsWith("/api/suppliers/")) {
    return ["/api/suppliers", "/api/suppliers/scorecards", "/api/products", "/api/orders", "/api/dashboard/summary"];
  }
  if (path === "/api/business/settings") {
    return ["/api/business", "/api/ai/audit", "/api/notifications/orders", "/api/ai/brief", "/api/dashboard/summary"];
  }
  if (path === "/api/notifications/test-order-email") {
    return ["/api/notifications/orders"];
  }
  if (path === "/api/notifications/orders/retry") {
    return ["/api/notifications/orders"];
  }
  if (path === "/api/analysis/replenishment") {
    return ["/api/reports", "/api/jobs", "/api/ai/report-comparison", "/api/ai/brief", "/api/ai/anomalies", "/api/dashboard/summary"];
  }
  if (path === "/api/ai/auto-orders") {
    return ["/api/orders", "/api/ai/anomalies", "/api/ai/brief", "/api/notifications/orders", "/api/suppliers/scorecards", "/api/dashboard/summary"];
  }
  if (path === "/api/ai/scenario" || path === "/api/ai/chat") {
    return [];
  }
  return [path];
}

export function useWorkspaceQuery<T>(
  getToken: GetToken,
  path: string,
  options?: WorkspaceQueryOptions,
): {
  data: T | null;
  loading: boolean;
  error: string | null;
  revalidate: () => Promise<void>;
} {
  const enabled = options?.enabled ?? true;
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(Boolean(enabled));
  const [error, setError] = useState<string | null>(null);

  const revalidate = useCallback(async () => {
    if (!enabled) {
      setLoading(false);
      return;
    }
    setLoading((current) => current || data === null);
    try {
      const result = await authorizedFetch<T>(getToken, path);
      setData(result);
      setError(null);
    } catch (queryError) {
      setError(queryError instanceof Error ? queryError.message : "Could not load workspace data.");
    } finally {
      setLoading(false);
    }
  }, [data, enabled, getToken, path]);

  useEffect(() => {
    if (!enabled) {
      setLoading(false);
      return () => undefined;
    }
    let cancelled = false;
    let unsubscribe: (() => void) | undefined;

    const connect = async () => {
      const token = await getSessionToken(getToken);
      if (cancelled) {
        return;
      }
      const initialValue = latestPathValues.get(scopedPathKey(path, token));
      if (initialValue !== undefined) {
        setData(initialValue as T);
        setLoading(false);
      }
      unsubscribe = subscribeToPath(path, token, (value) => {
        setData(value as T);
        setError(null);
        setLoading(false);
      });
      revalidate().catch(() => undefined);
    };

    connect().catch(() => {
      if (!cancelled) {
        revalidate().catch(() => undefined);
      }
    });

    return () => {
      cancelled = true;
      unsubscribe?.();
    };
  }, [enabled, path, revalidate]);

  return { data, loading, error, revalidate };
}

export async function authorizedFetch<T>(
  getToken: GetToken,
  path: string,
  init?: RequestInit,
): Promise<T> {
  const token = await getSessionToken(getToken);
  const method = normalizeMethod(init);
  const headers = new Headers(init?.headers);
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  if (init?.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const apiUrl = await resolveApiUrl();
  const cacheKey = cacheKeyForRequest(apiUrl, path, token ?? null);
  const cachePolicy = cachePolicyForPath(path);

  if (isCacheableRequest(method, init)) {
    const cachedEntry = readCachedEntry<T>(cacheKey);
    if (cachedEntry) {
      if (cachedEntry.staleAt > Date.now()) {
        return cachedEntry.value as T;
      }
      if (!pendingSessionRequests.has(cacheKey)) {
        const backgroundRefresh = (async () => {
          let response: Response;
          try {
            response = await fetch(`${apiUrl}${path}`, {
              ...init,
              headers,
            });
            if (!response.ok) {
              return;
            }
            const payload = await response.json() as T;
            storeCachedValue(cacheKey, path, token ?? null, payload, cachePolicy);
          } catch {
            return;
          } finally {
            pendingSessionRequests.delete(cacheKey);
          }
        })();
        pendingSessionRequests.set(cacheKey, backgroundRefresh);
      }
      return cachedEntry.value as T;
    }
    const pending = pendingSessionRequests.get(cacheKey);
    if (pending) {
      return pending as Promise<T>;
    }
  } else {
    invalidateWorkspacePaths(invalidationPathsForMutation(path));
  }

  const requestPromise = (async () => {
    let response: Response;
    try {
      response = await fetch(`${apiUrl}${path}`, {
        ...init,
        headers,
      });
    } catch {
      throw new Error(`Could not connect to API at ${apiUrl}. Make sure the backend server is running.`);
    }
    if (!response.ok) {
      const detail = await readErrorDetail(response);
      throw new Error(detail ? `API error ${response.status}: ${detail}` : `API error ${response.status} from ${apiUrl}${path}`);
    }
    const payload = await response.json() as T;
    if (isCacheableRequest(method, init)) {
      storeCachedValue(cacheKey, path, token ?? null, payload, cachePolicy);
    }
    return payload;
  })();

  if (isCacheableRequest(method, init)) {
    pendingSessionRequests.set(cacheKey, requestPromise);
    try {
      return await requestPromise;
    } finally {
      pendingSessionRequests.delete(cacheKey);
    }
  }

  return requestPromise;
}

export async function authorizedDownload(
  getToken: GetToken,
  path: string,
  filename: string,
): Promise<void> {
  const token = await getSessionToken(getToken);
  const headers = new Headers();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  const apiUrl = await resolveApiUrl();
  let response: Response;
  try {
    response = await fetch(`${apiUrl}${path}`, { headers });
  } catch {
    throw new Error(`Could not connect to API at ${apiUrl}. Make sure the backend server is running.`);
  }
  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new Error(detail ? `Download failed (${response.status}): ${detail}` : `Download failed (${response.status})`);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
