import { SignedIn, SignedOut, useAuth } from "@clerk/nextjs";
import Head from "next/head";
import { useEffect, useMemo, useState } from "react";

import { WorkspaceShell } from "../components/WorkspaceShell";
import {
  authorizedDownload,
  authorizedFetch,
  Business,
  InventoryHealthItem,
  Job,
  ReportComparisonResponse,
  Report,
  ScenarioAnalysisResponse,
  useWorkspaceQuery,
} from "../lib/workspace-api";

export default function ReportsPage() {
  const { getToken } = useAuth();
  const [running, setRunning] = useState(false);
  const [reportFilter, setReportFilter] = useState("");
  const [scenarioCash, setScenarioCash] = useState(100000);
  const [scenarioAnalysis, setScenarioAnalysis] = useState<ScenarioAnalysisResponse | null>(null);
  const businessQuery = useWorkspaceQuery<Business>(getToken, "/api/business");
  const healthQuery = useWorkspaceQuery<InventoryHealthItem[]>(getToken, "/api/inventory/health");
  const reportsQuery = useWorkspaceQuery<Report[]>(getToken, "/api/reports");
  const jobsQuery = useWorkspaceQuery<Job[]>(getToken, "/api/jobs");
  const comparisonQuery = useWorkspaceQuery<ReportComparisonResponse>(getToken, "/api/ai/report-comparison");
  const business = businessQuery.data;
  const health = healthQuery.data || [];
  const reports = reportsQuery.data || [];
  const jobs = jobsQuery.data || [];
  const reportComparison = comparisonQuery.data;

  useEffect(() => {
    if (business) {
      setScenarioCash(Math.round(business.available_cash));
    }
  }, [business?.available_cash, business?.business_id]);

  async function runReport() {
    setRunning(true);
    await authorizedFetch(getToken, "/api/analysis/replenishment", { method: "POST" });
    await Promise.all([
      businessQuery.revalidate(),
      healthQuery.revalidate(),
      reportsQuery.revalidate(),
      jobsQuery.revalidate(),
      comparisonQuery.revalidate(),
    ]);
    await runScenario(Math.round((business?.available_cash ?? scenarioCash)));
    setRunning(false);
  }

  async function runScenario(cashValue: number) {
    const result = await authorizedFetch<ScenarioAnalysisResponse>(getToken, "/api/ai/scenario", {
      method: "POST",
      body: JSON.stringify({ cash: cashValue }),
    });
    setScenarioAnalysis(result);
  }

  async function exportLatestCsv() {
    if (!latestReport) return;
    await authorizedDownload(
      getToken,
      `/api/reports/${latestReport.report_id}/export.csv`,
      `replenishment-report-${latestReport.report_id}.csv`,
    );
  }

  const latestReport = reports[0] || null;
  const filteredReports = useMemo(() => {
    const query = reportFilter.trim().toLowerCase();
    if (!query) return reports;
    return reports.filter((report) =>
      report.summary.toLowerCase().includes(query) ||
      report.recommendations.some((item) =>
        item.product_name.toLowerCase().includes(query) || item.sku.toLowerCase().includes(query),
      ),
    );
  }, [reports, reportFilter]);

  const riskDistribution = useMemo(() => {
    return {
      healthy: health.filter((item) => item.risk_level === "healthy").length,
      watch: health.filter((item) => item.risk_level === "watch" || item.risk_level === "high").length,
      critical: health.filter((item) => item.risk_level === "critical").length,
    };
  }, [health]);

  const topSpendRecommendations = useMemo(() => {
    return [...(latestReport?.recommendations || [])]
      .sort((left, right) => right.estimated_cost - left.estimated_cost)
      .slice(0, 5);
  }, [latestReport]);

  const riskyCoverRecommendations = useMemo(() => {
    return [...(latestReport?.recommendations || [])]
      .sort((left, right) => left.days_of_cover - right.days_of_cover)
      .slice(0, 5);
  }, [latestReport]);

  const scenarioCoverage = latestReport
    ? latestReport.recommendations.filter((item) => item.estimated_cost <= scenarioCash).length
    : 0;

  const riskTotal = Math.max(
    riskDistribution.healthy + riskDistribution.watch + riskDistribution.critical,
    1,
  );
  const recommendationMix = latestReport
    ? {
        buy_now: latestReport.recommendations.filter((item) => item.recommendation_type === "buy_now").length,
        split_order: latestReport.recommendations.filter((item) => item.recommendation_type === "split_order").length,
        wait: latestReport.recommendations.filter((item) => item.recommendation_type === "wait").length,
      }
    : { buy_now: 0, split_order: 0, wait: 0 };

  useEffect(() => {
    if (!business) return;
    runScenario(Math.round(business.available_cash)).catch(() => undefined);
  }, [business?.business_id, reports.length]);

  return (
    <>
      <Head><title>Reports | SupplyChain AI</title></Head>
      <SignedOut><main className="page shell"><section className="panel"><h1>Sign in required.</h1></section></main></SignedOut>
      <SignedIn>
        <WorkspaceShell title="Reports" description="AI-backed replenishment analysis with charts, job history, and a quick affordability scenario.">
          <section className="stats-grid stats-grid-wide">
            <article className="stat-card"><span>Latest Recommendations</span><strong>{latestReport?.recommendations.length || 0}</strong></article>
            <article className="stat-card"><span>Recommended Spend</span><strong>{latestReport?.total_recommended_spend.toLocaleString() || 0} {business?.currency}</strong></article>
            <article className="stat-card"><span>Available Cash</span><strong>{business?.available_cash.toLocaleString() || 0} {business?.currency}</strong></article>
            <article className="stat-card"><span>Critical Products</span><strong>{riskDistribution.critical}</strong></article>
            <article className="stat-card accent-card"><span>Completed Jobs</span><strong>{jobs.filter((job) => job.status === "completed").length}</strong></article>
          </section>

          <section className="panel stacked-panels">
            <div className="command-bar">
              <div>
                <div className="panel-heading">
                  <h2>Replenishment Analysis</h2>
                  <p>Generate a fresh report, then compare spend, risk, and stock cover visually.</p>
                </div>
              </div>
              <div className="command-actions">
                <button className="button secondary" onClick={exportLatestCsv} disabled={!latestReport}>Export CSV</button>
                <button className="button primary" onClick={runReport} disabled={running}>{running ? "Generating..." : "Generate Replenishment Report"}</button>
              </div>
            </div>

            {latestReport ? (
              <section className="chart-grid">
                <article className="chart-card">
                  <div className="panel-heading"><h2>Spend By SKU</h2><p>Highest-cost recommendations first.</p></div>
                  <div className="chart-list">
                    {topSpendRecommendations.map((item) => (
                      <div className="chart-row" key={item.product_id}>
                        <div className="chart-labels">
                          <strong>{item.sku}</strong>
                          <span>{item.estimated_cost.toLocaleString()} {business?.currency}</span>
                        </div>
                        <div className="mini-bar"><div className="mini-bar-fill spend" style={{ width: `${(item.estimated_cost / Math.max(latestReport.total_recommended_spend, 1)) * 100}%` }} /></div>
                      </div>
                    ))}
                  </div>
                </article>

                <article className="chart-card">
                  <div className="panel-heading"><h2>Risk Distribution</h2><p>Healthy, watch, and critical product mix.</p></div>
                  <div className="risk-donut">
                    <div
                      className="risk-donut-ring"
                      style={{
                        background: `conic-gradient(
                          var(--healthy) 0 ${(riskDistribution.healthy / riskTotal) * 360}deg,
                          var(--high) ${(riskDistribution.healthy / riskTotal) * 360}deg ${((riskDistribution.healthy + riskDistribution.watch) / riskTotal) * 360}deg,
                          var(--critical) ${((riskDistribution.healthy + riskDistribution.watch) / riskTotal) * 360}deg 360deg
                        )`,
                      }}
                    />
                    <div className="risk-legend">
                      <span><strong>{riskDistribution.healthy}</strong> healthy</span>
                      <span><strong>{riskDistribution.watch}</strong> watch</span>
                      <span><strong>{riskDistribution.critical}</strong> critical</span>
                    </div>
                  </div>
                </article>

                <article className="chart-card">
                  <div className="panel-heading"><h2>Days Of Cover</h2><p>Lowest cover first among current recommendations.</p></div>
                  <div className="chart-list">
                    {riskyCoverRecommendations.map((item) => (
                      <div className="chart-row" key={item.product_id}>
                        <div className="chart-labels">
                          <strong>{item.sku}</strong>
                          <span>{item.days_of_cover.toFixed(1)} days</span>
                        </div>
                        <div className="mini-bar"><div className={`mini-bar-fill ${item.days_of_cover <= 3 ? "critical" : item.days_of_cover <= 7 ? "watch" : "healthy"}`} style={{ width: `${Math.min((item.days_of_cover / 21) * 100, 100)}%` }} /></div>
                      </div>
                    ))}
                  </div>
                </article>

                <article className="chart-card">
                  <div className="panel-heading"><h2>Cash Scenario</h2><p>Simple what-if view for the current report.</p></div>
                  <label className="stacked-input">
                    Scenario cash
                    <input
                      type="number"
                      min="0"
                      value={scenarioCash}
                      onChange={(event) => setScenarioCash(Number(event.target.value))}
                      onBlur={() => runScenario(scenarioCash).catch(() => undefined)}
                    />
                  </label>
                  <div className="chart-list">
                    <div className="chart-row">
                      <div className="chart-labels"><strong>Scenario Cash</strong><span>{scenarioCash.toLocaleString()} {business?.currency}</span></div>
                      <div className="mini-bar"><div className="mini-bar-fill healthy" style={{ width: `${Math.min((scenarioCash / Math.max(latestReport.total_recommended_spend, scenarioCash, 1)) * 100), 100}%` }} /></div>
                    </div>
                    <div className="chart-row">
                      <div className="chart-labels"><strong>Recommended Spend</strong><span>{latestReport.total_recommended_spend.toLocaleString()} {business?.currency}</span></div>
                      <div className="mini-bar"><div className="mini-bar-fill spend" style={{ width: `${Math.min((latestReport.total_recommended_spend / Math.max(latestReport.total_recommended_spend, scenarioCash, 1)) * 100), 100}%` }} /></div>
                    </div>
                  </div>
                  <p className="muted-copy">{scenarioCoverage} individual recommendations fit within this scenario cash level.</p>
                  <div className="history-list">
                    <article className="history-card">
                      <div className="history-topline">
                        <strong>Scenario Advice</strong>
                        <span className={`risk ${scenarioAnalysis?.used_ai ? "healthy" : "watch"}`}>{scenarioAnalysis?.used_ai ? "AI" : "rules"}</span>
                      </div>
                      <p>{scenarioAnalysis?.summary || "Scenario advice will appear here."}</p>
                    </article>
                    <article className="history-card">
                      <div className="history-topline"><strong>Buy First</strong><span className="risk healthy">{scenarioAnalysis?.recommended_skus.length || 0}</span></div>
                      <p>{scenarioAnalysis?.recommended_skus.join(", ") || "No SKUs selected yet."}</p>
                    </article>
                    <article className="history-card">
                      <div className="history-topline"><strong>Defer</strong><span className="risk watch">{scenarioAnalysis?.deferred_skus.length || 0}</span></div>
                      <p>{scenarioAnalysis?.deferred_skus.join(", ") || "Nothing deferred under this scenario."}</p>
                    </article>
                  </div>
                </article>

                <article className="chart-card">
                  <div className="panel-heading"><h2>Decision Mix</h2><p>How the engine is classifying actions right now.</p></div>
                  <div className="history-list">
                    <article className="history-card">
                      <div className="history-topline"><strong>Buy now</strong><span className="risk healthy">{recommendationMix.buy_now}</span></div>
                      <p>Recommendations the current cash position can support immediately.</p>
                    </article>
                    <article className="history-card">
                      <div className="history-topline"><strong>Split order</strong><span className="risk watch">{recommendationMix.split_order}</span></div>
                      <p>Urgent recommendations that may need smaller phased purchasing.</p>
                    </article>
                    <article className="history-card">
                      <div className="history-topline"><strong>Wait</strong><span className="risk critical">{recommendationMix.wait}</span></div>
                      <p>Lower-priority lines that should wait until cash or risk changes.</p>
                    </article>
                  </div>
                </article>

                <article className="chart-card">
                  <div className="panel-heading"><h2>Report Comparison</h2><p>What changed versus the previous replenishment run.</p></div>
                  <div className="history-list">
                    <article className="history-card">
                      <div className="history-topline">
                        <strong>Change Summary</strong>
                        <span className={`risk ${reportComparison?.used_ai ? "healthy" : "watch"}`}>{reportComparison?.used_ai ? "AI" : "rules"}</span>
                      </div>
                      <p>{reportComparison?.summary || "Generate at least two reports to compare runs."}</p>
                    </article>
                    {(reportComparison?.changes || []).map((change, index) => (
                      <article className="history-card" key={`${index}-${change}`}>
                        <div className="history-topline"><strong>Change {index + 1}</strong><span className="risk watch">delta</span></div>
                        <p>{change}</p>
                      </article>
                    ))}
                  </div>
                </article>
              </section>
            ) : (
              <section className="panel">Generate your first replenishment report to unlock charts and AI analysis.</section>
            )}
          </section>

          <section className="workspace-grid lower-grid">
            <section className="panel">
              <div className="panel-heading"><h2>Report History</h2><p>Search prior report summaries and recommendation sets.</p></div>
              <div className="toolbar">
                <input
                  className="search-input"
                  placeholder="Search reports by summary or SKU"
                  value={reportFilter}
                  onChange={(event) => setReportFilter(event.target.value)}
                />
              </div>
              <div className="history-list">
                {filteredReports.map((report) => (
                  <article className="history-card" key={report.report_id}>
                    <div className="history-topline">
                      <strong>{new Date(report.generated_at || Date.now()).toLocaleString()}</strong>
                      <span className={`risk ${report.affordable_now ? "healthy" : "watch"}`}>{report.affordable_now ? "affordable" : "review"}</span>
                    </div>
                    <p>{report.summary}</p>
                    <div className="history-meta">
                      <span>{report.recommendations.length} recommendations</span>
                      <span>{report.total_recommended_spend.toLocaleString()} {business?.currency}</span>
                      <span>{report.recommendations.filter((item) => item.recommendation_type === "buy_now").length} buy now</span>
                    </div>
                    {report.recommendations.slice(0, 2).map((item) => (
                      <div className="history-meta" key={`${report.report_id}-${item.sku}`}>
                        <span><strong>{item.sku}</strong></span>
                        <span>{item.rationale}</span>
                      </div>
                    ))}
                  </article>
                ))}
              </div>
            </section>
            <section className="panel stacked-panels">
              <div className="panel-heading"><h2>Jobs</h2><p>Recent replenishment analysis runs.</p></div>
              <div className="history-list">
                {jobs.map((job) => (
                  <article className="history-card" key={job.job_id}>
                    <div className="history-topline">
                      <strong>{job.job_type}</strong>
                      <span className={`risk ${job.status === "completed" ? "healthy" : job.status === "failed" ? "critical" : "watch"}`}>{job.status}</span>
                    </div>
                    <p>Created {job.created_at ? new Date(job.created_at).toLocaleString() : "recently"}</p>
                  </article>
                ))}
              </div>
            </section>
          </section>
        </WorkspaceShell>
      </SignedIn>
    </>
  );
}
