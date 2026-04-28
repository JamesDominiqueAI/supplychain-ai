import { SignedIn, SignedOut, useAuth } from "@clerk/nextjs";
import Head from "next/head";
import { useMemo, useState } from "react";

import { WorkspaceShell } from "../components/WorkspaceShell";
import { AIAuditLog, ObservabilityMetrics, useWorkspaceQuery } from "../lib/workspace-api";

type AuditStatusFilter = "all" | "accepted" | "fallback" | "refused";

function statusClass(status: AIAuditLog["status"]) {
  if (status === "accepted") return "healthy";
  if (status === "fallback") return "watch";
  return "critical";
}

function tokenLabel(log: AIAuditLog) {
  if (log.total_tokens === null || log.total_tokens === undefined) {
    return "tokens n/a";
  }
  return `${log.total_tokens.toLocaleString()} tokens`;
}

export default function AuditPage() {
  const { getToken } = useAuth();
  const [statusFilter, setStatusFilter] = useState<AuditStatusFilter>("all");
  const [featureFilter, setFeatureFilter] = useState("all");
  const auditQuery = useWorkspaceQuery<AIAuditLog[]>(getToken, "/api/ai/audit?limit=50");
  const metricsQuery = useWorkspaceQuery<ObservabilityMetrics>(getToken, "/api/observability/metrics");
  const auditLogs = auditQuery.data || [];
  const metrics = metricsQuery.data;

  const features = useMemo(() => {
    return Array.from(new Set(auditLogs.map((log) => log.feature))).sort();
  }, [auditLogs]);

  const filteredLogs = useMemo(() => {
    return auditLogs.filter((log) => {
      const statusMatches = statusFilter === "all" || log.status === statusFilter;
      const featureMatches = featureFilter === "all" || log.feature === featureFilter;
      return statusMatches && featureMatches;
    });
  }, [auditLogs, featureFilter, statusFilter]);

  const latestRefusal = auditLogs.find((log) => log.status === "refused");
  const latestFallback = auditLogs.find((log) => log.status === "fallback");

  return (
    <>
      <Head><title>AI Audit | SupplyChain AI</title></Head>
      <SignedOut><main className="page shell"><section className="panel"><h1>Sign in required.</h1></section></main></SignedOut>
      <SignedIn>
        <WorkspaceShell title="AI Audit" description="Review accepted, fallback, and refused AI decisions with reasons, previews, tokens, and workspace metrics.">
          <section className="stats-grid stats-grid-wide">
            <article className="stat-card"><span>AI Events</span><strong>{metrics?.ai.total_ai_events ?? auditLogs.length}</strong></article>
            <article className="stat-card"><span>Success Rate</span><strong>{Math.round((metrics?.ai.success_rate || 0) * 100)}%</strong></article>
            <article className="stat-card"><span>Fallback Rate</span><strong>{Math.round((metrics?.ai.fallback_rate || 0) * 100)}%</strong></article>
            <article className="stat-card"><span>Refusal Rate</span><strong>{Math.round((metrics?.ai.refusal_rate || 0) * 100)}%</strong></article>
            <article className="stat-card accent-card"><span>Total Tokens</span><strong>{metrics?.ai.token_usage.total_tokens.toLocaleString() || 0}</strong></article>
          </section>

          <section className="workspace-grid lower-grid">
            <section className="panel stacked-panels">
              <div className="command-bar">
                <div className="panel-heading">
                  <h2>Decision Trail</h2>
                  <p>Filter recent AI events and inspect the exact decision path the backend recorded.</p>
                </div>
                <div className="command-actions">
                  <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as AuditStatusFilter)}>
                    <option value="all">All statuses</option>
                    <option value="accepted">Accepted</option>
                    <option value="fallback">Fallback</option>
                    <option value="refused">Refused</option>
                  </select>
                  <select value={featureFilter} onChange={(event) => setFeatureFilter(event.target.value)}>
                    <option value="all">All features</option>
                    {features.map((feature) => <option key={feature} value={feature}>{feature}</option>)}
                  </select>
                </div>
              </div>

              <div className="history-list">
                {filteredLogs.map((log) => (
                  <article className="history-card" key={log.audit_id}>
                    <div className="history-topline">
                      <strong>{log.feature}</strong>
                      <span className={`risk ${statusClass(log.status)}`}>{log.status}</span>
                    </div>
                    <p>{log.input_preview || "No input preview recorded."}</p>
                    {log.output_preview ? <p className="muted-copy">{log.output_preview}</p> : null}
                    {log.reason ? <div className="notice info">{log.reason}</div> : null}
                    <div className="history-meta">
                      <span>{new Date(log.created_at).toLocaleString()}</span>
                      <span>{log.used_ai ? "AI used" : "rules/fallback"}</span>
                      <span>{log.confidence || "n/a"} confidence</span>
                      <span>{tokenLabel(log)}</span>
                    </div>
                  </article>
                ))}
                {filteredLogs.length === 0 ? (
                  <article className="history-card"><p>No audit events match the current filters.</p></article>
                ) : null}
              </div>
            </section>

            <section className="panel stacked-panels">
              <div>
                <div className="panel-heading"><h2>Interview Examples</h2><p>Concrete events to show how the guardrails behave.</p></div>
                <div className="history-list">
                  <article className="history-card">
                    <div className="history-topline">
                      <strong>Latest Refusal</strong>
                      <span className="risk critical">{latestRefusal ? "recorded" : "none"}</span>
                    </div>
                    <p>{latestRefusal?.input_preview || "Ask an off-topic or unsupported-action question to create a refusal event."}</p>
                    {latestRefusal?.reason ? <div className="notice info">{latestRefusal.reason}</div> : null}
                  </article>
                  <article className="history-card">
                    <div className="history-topline">
                      <strong>Latest Fallback</strong>
                      <span className="risk watch">{latestFallback ? "recorded" : "none"}</span>
                    </div>
                    <p>{latestFallback?.input_preview || "Disable AI or trigger a low-confidence path to create a fallback event."}</p>
                    {latestFallback?.reason ? <div className="notice info">{latestFallback.reason}</div> : null}
                  </article>
                </div>
              </div>

              <div>
                <div className="panel-heading"><h2>Feature Counts</h2><p>Which AI surfaces are active in this workspace.</p></div>
                <div className="history-list">
                  {Object.entries(metrics?.ai.feature_counts || {}).map(([feature, count]) => (
                    <article className="history-card" key={feature}>
                      <div className="history-topline">
                        <strong>{feature}</strong>
                        <span>{count.toLocaleString()}</span>
                      </div>
                    </article>
                  ))}
                  {!metrics || Object.keys(metrics.ai.feature_counts).length === 0 ? (
                    <article className="history-card"><p>No feature counts yet.</p></article>
                  ) : null}
                </div>
              </div>
            </section>
          </section>
        </WorkspaceShell>
      </SignedIn>
    </>
  );
}
