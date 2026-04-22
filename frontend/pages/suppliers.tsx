import { SignedIn, SignedOut, useAuth } from "@clerk/nextjs";
import Head from "next/head";
import { FormEvent, useMemo, useState } from "react";

import { WorkspaceShell } from "../components/WorkspaceShell";
import { authorizedFetch, Supplier, SupplierScorecard, useWorkspaceQuery } from "../lib/workspace-api";

export default function SuppliersPage() {
  const { getToken } = useAuth();
  const [query, setQuery] = useState("");
  const [form, setForm] = useState({ name: "", contact_phone: "", lead_time_days: 7, reliability_score: 0.8, notes: "" });
  const suppliersQuery = useWorkspaceQuery<Supplier[]>(getToken, "/api/suppliers");
  const scorecardsQuery = useWorkspaceQuery<SupplierScorecard[]>(getToken, "/api/suppliers/scorecards");
  const suppliers = suppliersQuery.data || [];
  const scorecards = scorecardsQuery.data || [];

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await authorizedFetch(getToken, "/api/suppliers", { method: "POST", body: JSON.stringify(form) });
    setForm({ name: "", contact_phone: "", lead_time_days: 7, reliability_score: 0.8, notes: "" });
    await Promise.all([suppliersQuery.revalidate(), scorecardsQuery.revalidate()]);
  }

  const filteredSuppliers = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return suppliers;
    return suppliers.filter((supplier) =>
      supplier.name.toLowerCase().includes(normalized) ||
      (supplier.contact_phone || "").toLowerCase().includes(normalized) ||
      (supplier.notes || "").toLowerCase().includes(normalized),
    );
  }, [query, suppliers]);

  const topRisk = scorecards[0];
  const supplierValueSummary = useMemo(
    () => [...scorecards].sort((left, right) => right.open_order_value - left.open_order_value).slice(0, 5),
    [scorecards],
  );

  return (
    <>
      <Head><title>Suppliers | SupplyChain AI</title></Head>
      <SignedOut><main className="page shell"><section className="panel"><h1>Sign in required.</h1></section></main></SignedOut>
      <SignedIn>
        <WorkspaceShell title="Suppliers" description="Manage supplier records and monitor live scorecards instead of treating suppliers like static contact data.">
          <section className="stats-grid stats-grid-wide">
            <article className="stat-card"><span>Total Suppliers</span><strong>{suppliers.length}</strong></article>
            <article className="stat-card"><span>Suppliers With Open Orders</span><strong>{scorecards.filter((item) => item.open_orders > 0).length}</strong></article>
            <article className="stat-card"><span>Late Open Orders</span><strong>{scorecards.reduce((sum, item) => sum + item.late_open_orders, 0)}</strong></article>
            <article className="stat-card"><span>Avg On-Time Rate</span><strong>{scorecards.length ? Math.round((scorecards.reduce((sum, item) => sum + item.on_time_rate, 0) / scorecards.length) * 100) : 0}%</strong></article>
            <article className="stat-card accent-card"><span>Highest Risk Supplier</span><strong>{topRisk?.supplier_name || "None"}</strong></article>
          </section>
          <section className="chart-grid">
            <article className="chart-card">
              <div className="panel-heading"><h2>Supplier Reliability Mix</h2><p>How supplier quality is distributed across the directory.</p></div>
              <div className="history-list">
                <article className="history-card">
                  <div className="history-topline"><strong>Strong</strong><span className="risk healthy">{suppliers.filter((item) => item.reliability_score >= 0.85).length}</span></div>
                  <div className="mini-bar"><div className="mini-bar-fill healthy" style={{ width: `${(suppliers.filter((item) => item.reliability_score >= 0.85).length / Math.max(suppliers.length, 1)) * 100}%` }} /></div>
                </article>
                <article className="history-card">
                  <div className="history-topline"><strong>Watch</strong><span className="risk watch">{suppliers.filter((item) => item.reliability_score >= 0.75 && item.reliability_score < 0.85).length}</span></div>
                  <div className="mini-bar"><div className="mini-bar-fill watch" style={{ width: `${(suppliers.filter((item) => item.reliability_score >= 0.75 && item.reliability_score < 0.85).length / Math.max(suppliers.length, 1)) * 100}%` }} /></div>
                </article>
                <article className="history-card">
                  <div className="history-topline"><strong>Risky</strong><span className="risk critical">{suppliers.filter((item) => item.reliability_score < 0.75).length}</span></div>
                  <div className="mini-bar"><div className="mini-bar-fill critical" style={{ width: `${(suppliers.filter((item) => item.reliability_score < 0.75).length / Math.max(suppliers.length, 1)) * 100}%` }} /></div>
                </article>
              </div>
            </article>
            <article className="chart-card">
              <div className="panel-heading"><h2>Open Order Value</h2><p>Which suppliers carry the most current purchasing exposure.</p></div>
              <div className="chart-list">
                {supplierValueSummary.map((scorecard) => (
                  <div className="chart-row" key={scorecard.supplier_id}>
                    <div className="chart-labels">
                      <strong>{scorecard.supplier_name}</strong>
                      <span>{scorecard.open_order_value.toLocaleString()} HTG</span>
                    </div>
                    <div className="mini-bar">
                      <div className="mini-bar-fill spend" style={{ width: `${(scorecard.open_order_value / Math.max(supplierValueSummary[0]?.open_order_value || 1, 1)) * 100}%` }} />
                    </div>
                  </div>
                ))}
              </div>
            </article>
          </section>

          <section className="workspace-grid">
            <section className="panel">
              <div className="panel-heading"><h2>Supplier Directory</h2><p>Lead time, contact details, and quick performance context.</p></div>
              <div className="toolbar">
                <input
                  className="search-input"
                  placeholder="Search suppliers"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                />
              </div>
              <div className="history-list">
                {filteredSuppliers.map((supplier) => {
                  const scorecard = scorecards.find((item) => item.supplier_id === supplier.supplier_id);
                  return (
                    <article className="history-card" key={supplier.supplier_id}>
                      <div className="history-topline">
                        <strong>{supplier.name}</strong>
                        <span className={`risk ${supplier.reliability_score >= 0.85 ? "healthy" : supplier.reliability_score >= 0.75 ? "watch" : "critical"}`}>{Math.round(supplier.reliability_score * 100)}%</span>
                      </div>
                      <p>{supplier.lead_time_days} day lead time • {supplier.contact_phone || "No phone"}</p>
                      <div className="history-meta">
                        <span>{supplier.notes || "No notes recorded."}</span>
                      </div>
                      {scorecard ? (
                        <div className="supplier-metrics-grid">
                          <div><span>Open Orders</span><strong>{scorecard.open_orders}</strong></div>
                          <div><span>On Time</span><strong>{Math.round(scorecard.on_time_rate * 100)}%</strong></div>
                          <div><span>Fill Rate</span><strong>{Math.round(scorecard.fill_rate * 100)}%</strong></div>
                          <div><span>Late Open</span><strong>{scorecard.late_open_orders}</strong></div>
                        </div>
                      ) : null}
                    </article>
                  );
                })}
              </div>
            </section>
            <section className="panel stacked-panels">
              <div className="panel">
                <div className="panel-heading"><h2>Scorecards</h2><p>Operational performance based on current purchase orders.</p></div>
                <div className="history-list">
                  {scorecards.map((scorecard) => (
                    <article className="history-card" key={scorecard.supplier_id}>
                      <div className="history-topline">
                        <strong>{scorecard.supplier_name}</strong>
                        <span className={`risk ${scorecard.late_open_orders > 0 ? "critical" : scorecard.on_time_rate >= 0.8 ? "healthy" : "watch"}`}>
                          {scorecard.late_open_orders > 0 ? "attention" : "stable"}
                        </span>
                      </div>
                      <div className="chart-list compact-heading">
                        <div className="chart-row">
                          <div className="chart-labels"><span>On-time rate</span><span>{Math.round(scorecard.on_time_rate * 100)}%</span></div>
                          <div className="mini-bar"><div className={`mini-bar-fill ${scorecard.on_time_rate >= 0.8 ? "healthy" : "watch"}`} style={{ width: `${scorecard.on_time_rate * 100}%` }} /></div>
                        </div>
                        <div className="chart-row">
                          <div className="chart-labels"><span>Fill rate</span><span>{Math.round(scorecard.fill_rate * 100)}%</span></div>
                          <div className="mini-bar"><div className={`mini-bar-fill ${scorecard.fill_rate >= 0.8 ? "healthy" : "watch"}`} style={{ width: `${scorecard.fill_rate * 100}%` }} /></div>
                        </div>
                      </div>
                      <div className="history-meta">
                        <span>{scorecard.late_open_orders} late open orders</span>
                        <span>{scorecard.average_delay_days.toFixed(1)} avg delay days</span>
                        <span>{scorecard.open_order_value.toLocaleString()} HTG open value</span>
                      </div>
                    </article>
                  ))}
                </div>
              </div>
              <form className="form-card" onSubmit={submit}>
                <div className="form-card-header"><h3>Add Supplier</h3><p>Create a supplier record for richer purchasing workflows.</p></div>
                <div className="form-grid">
                  <label>Name<input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required /></label>
                  <label>Phone<input value={form.contact_phone} onChange={(e) => setForm({ ...form, contact_phone: e.target.value })} /></label>
                  <label>Lead Time Days<input type="number" min="1" value={form.lead_time_days} onChange={(e) => setForm({ ...form, lead_time_days: Number(e.target.value) })} /></label>
                  <label>Reliability<input type="number" min="0" max="1" step="0.01" value={form.reliability_score} onChange={(e) => setForm({ ...form, reliability_score: Number(e.target.value) })} /></label>
                  <label>Notes<input value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} /></label>
                </div>
                <button className="button primary" type="submit">Add Supplier</button>
              </form>
            </section>
          </section>
        </WorkspaceShell>
      </SignedIn>
    </>
  );
}
