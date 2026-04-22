import { SignedIn, SignedOut, useAuth } from "@clerk/nextjs";
import Head from "next/head";
import { FormEvent, useEffect, useMemo, useState } from "react";

import { WorkspaceShell } from "../components/WorkspaceShell";
import { authorizedFetch, PurchaseOrder, Supplier, useWorkspaceQuery } from "../lib/workspace-api";

const STATUS_FLOW: PurchaseOrder["status"][] = [
  "draft",
  "approved",
  "placed",
  "in_transit",
  "partially_received",
  "arrived",
  "delayed",
  "canceled",
];

function labelForStatus(status: PurchaseOrder["status"]): string {
  return status.replace(/_/g, " ");
}

export default function OrdersPage() {
  const { getToken } = useAuth();
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [notice, setNotice] = useState<string | null>(null);
  const [receiveQuantities, setReceiveQuantities] = useState<Record<string, number>>({});
  const ordersQuery = useWorkspaceQuery<PurchaseOrder[]>(getToken, "/api/orders");
  const suppliersQuery = useWorkspaceQuery<Supplier[]>(getToken, "/api/suppliers");
  const orders = ordersQuery.data || [];
  const suppliers = suppliersQuery.data || [];

  useEffect(() => {
    if (ordersQuery.error || suppliersQuery.error) {
      setNotice("Could not load orders.");
    }
  }, [ordersQuery.error, suppliersQuery.error]);

  useEffect(() => {
    setReceiveQuantities((current) => {
      const next = { ...current };
      for (const order of orders) {
        const remaining = Math.max(order.quantity - order.received_quantity, 1);
        next[order.order_id] = current[order.order_id] || remaining;
      }
      return next;
    });
  }, [orders]);

  async function advance(order: PurchaseOrder, status: PurchaseOrder["status"]) {
    await authorizedFetch(getToken, `/api/orders/${order.order_id}/status`, {
      method: "POST",
      body: JSON.stringify({ status }),
    });
    setNotice(`Order ${order.sku} updated to ${labelForStatus(status)}.`);
    await ordersQuery.revalidate();
  }

  async function receive(event: FormEvent<HTMLFormElement>, order: PurchaseOrder) {
    event.preventDefault();
    const quantity = receiveQuantities[order.order_id] || 1;
    await authorizedFetch(getToken, `/api/orders/${order.order_id}/receive`, {
      method: "POST",
      body: JSON.stringify({
        quantity_received: quantity,
        note: `Receipt logged for ${order.sku}`,
      }),
    });
    setNotice(`Received ${quantity} units for ${order.sku}.`);
    await ordersQuery.revalidate();
  }

  const filteredOrders = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return orders.filter((order) => {
      const matchesQuery =
        !normalized ||
        order.product_name.toLowerCase().includes(normalized) ||
        order.sku.toLowerCase().includes(normalized) ||
        (order.supplier_name || "").toLowerCase().includes(normalized);
      const matchesStatus =
        statusFilter === "all" ||
        (statusFilter === "late" ? order.is_late : order.status === statusFilter);
      return matchesQuery && matchesStatus;
    });
  }, [orders, query, statusFilter]);

  const statusCounts = STATUS_FLOW.map((status) => ({
    status,
    count: orders.filter((order) => order.status === status).length,
  })).filter((item) => item.count > 0);

  const activeSupplierCount = new Set(
    orders.map((order) => order.supplier_id).filter(Boolean),
  ).size;

  const supplierExposure = useMemo(() => {
    const totals = new Map<string, { supplierName: string; value: number }>();
    for (const order of orders) {
      const key = order.supplier_id || "unassigned";
      const current = totals.get(key) || {
        supplierName: order.supplier_name || "Unassigned",
        value: 0,
      };
      current.value += order.estimated_cost;
      totals.set(key, current);
    }
    return [...totals.values()].sort((left, right) => right.value - left.value).slice(0, 5);
  }, [orders]);

  return (
    <>
      <Head><title>Orders | SupplyChain AI</title></Head>
      <SignedOut><main className="page shell"><section className="panel"><h1>Sign in required.</h1></section></main></SignedOut>
      <SignedIn>
        <WorkspaceShell title="Orders" description="Track purchasing from placement to delivery, with supplier context and partial receipt handling.">
          {notice ? <div className="notice info">{notice}</div> : null}
          <section className="stats-grid stats-grid-wide">
            <article className="stat-card"><span>Open Orders</span><strong>{orders.filter((order) => !["arrived", "canceled"].includes(order.status)).length}</strong></article>
            <article className="stat-card"><span>In Transit</span><strong>{orders.filter((order) => order.status === "in_transit").length}</strong></article>
            <article className="stat-card"><span>Partial Receipts</span><strong>{orders.filter((order) => order.status === "partially_received").length}</strong></article>
            <article className="stat-card"><span>Late Orders</span><strong>{orders.filter((order) => order.is_late).length}</strong></article>
            <article className="stat-card accent-card"><span>Active Suppliers</span><strong>{activeSupplierCount || suppliers.length}</strong></article>
          </section>
          <section className="chart-grid">
            <article className="chart-card">
              <div className="panel-heading"><h2>Order Status Mix</h2><p>Distribution of orders across workflow states.</p></div>
              <div className="chart-list">
                {statusCounts.map((item) => (
                  <div className="chart-row" key={item.status}>
                    <div className="chart-labels">
                      <strong>{labelForStatus(item.status)}</strong>
                      <span>{item.count} orders</span>
                    </div>
                    <div className="mini-bar">
                      <div className={`mini-bar-fill ${item.status}`} style={{ width: `${(item.count / Math.max(orders.length, 1)) * 100}%` }} />
                    </div>
                  </div>
                ))}
              </div>
            </article>
            <article className="chart-card">
              <div className="panel-heading"><h2>Supplier Exposure</h2><p>Open purchasing value concentrated by supplier.</p></div>
              <div className="chart-list">
                {supplierExposure.map((item) => (
                  <div className="chart-row" key={item.supplierName}>
                    <div className="chart-labels">
                      <strong>{item.supplierName}</strong>
                      <span>{item.value.toLocaleString()} HTG</span>
                    </div>
                    <div className="mini-bar">
                      <div className="mini-bar-fill spend" style={{ width: `${(item.value / Math.max(supplierExposure[0]?.value || 1, 1)) * 100}%` }} />
                    </div>
                  </div>
                ))}
              </div>
            </article>
          </section>

          <section className="workspace-grid lower-grid">
            <section className="panel">
              <div className="panel-heading">
                <h2>Order Pipeline</h2>
                <p>Search, filter, and move orders through a more realistic workflow.</p>
              </div>
              <div className="toolbar">
                <input
                  className="search-input"
                  placeholder="Search by SKU, product, or supplier"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                />
                <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
                  <option value="all">All statuses</option>
                  <option value="late">Late only</option>
                  {STATUS_FLOW.map((status) => (
                    <option key={status} value={status}>{labelForStatus(status)}</option>
                  ))}
                </select>
              </div>
              <div className="orders-board">
                {filteredOrders.map((order) => {
                  const remaining = Math.max(order.quantity - order.received_quantity, 0);
                  const progress = Math.min((order.received_quantity / order.quantity) * 100, 100);
                  return (
                    <article className="order-card" key={order.order_id}>
                      <div className="recommendation-head">
                        <div>
                          <h3>{order.product_name}</h3>
                          <p>{order.sku} • {order.supplier_name || "Supplier not assigned"}</p>
                        </div>
                        <div className="badge-stack">
                          <span className={`risk ${order.status}`}>{labelForStatus(order.status)}</span>
                          {order.is_late ? <span className="risk critical">late by {order.days_late} day{order.days_late === 1 ? "" : "s"}</span> : null}
                        </div>
                      </div>
                      <div className="recommendation-metrics order-metrics">
                        <span>Ordered: {order.quantity}</span>
                        <span>Received: {order.received_quantity}</span>
                        <span>Remaining: {remaining}</span>
                        <span>Cost: {order.estimated_cost.toLocaleString()}</span>
                        <span>Expected: {order.expected_delivery_date ? new Date(order.expected_delivery_date).toLocaleDateString() : "Not set"}</span>
                        <span>Placed by: {order.placed_by_type === "llm" ? "LLM" : order.placed_by_type === "system" ? "System" : "User"}</span>
                      </div>
                      <div className="progress-meter">
                        <div className="progress-fill" style={{ width: `${progress}%` }} />
                      </div>
                      <p className="muted-copy">
                        {order.note || "No purchasing note recorded yet."}
                        {order.placed_by_label ? ` Placed by ${order.placed_by_label}.` : ""}
                      </p>
                      <div className="card-actions">
                        {order.status === "draft" ? <button className="button secondary" onClick={() => advance(order, "approved")}>Approve</button> : null}
                        {order.status === "approved" ? <button className="button secondary" onClick={() => advance(order, "placed")}>Place Order</button> : null}
                        {order.status === "placed" ? <button className="button secondary" onClick={() => advance(order, "in_transit")}>Mark In Transit</button> : null}
                        {["placed", "in_transit", "partially_received"].includes(order.status) ? <button className="button secondary" onClick={() => advance(order, "delayed")}>Mark Delayed</button> : null}
                        {["draft", "approved", "placed"].includes(order.status) ? <button className="button secondary" onClick={() => advance(order, "canceled")}>Cancel</button> : null}
                      </div>
                      {!["arrived", "canceled"].includes(order.status) ? (
                        <form className="inline-form" onSubmit={(event) => receive(event, order)}>
                          <label>
                            Receive Qty
                            <input
                              type="number"
                              min="1"
                              max={Math.max(remaining, 1)}
                              value={receiveQuantities[order.order_id] || 1}
                              onChange={(event) =>
                                setReceiveQuantities((current) => ({
                                  ...current,
                                  [order.order_id]: Number(event.target.value),
                                }))
                              }
                            />
                          </label>
                          <button className="button primary" type="submit" disabled={remaining === 0}>Log Receipt</button>
                        </form>
                      ) : null}
                    </article>
                  );
                })}
              </div>
            </section>

            <section className="panel stacked-panels">
              <div>
                <div className="panel-heading">
                  <h2>Status Snapshot</h2>
                  <p>Quick visual of the current purchasing mix.</p>
                </div>
                <div className="history-list">
                  {statusCounts.map((item) => (
                    <article className="history-card" key={item.status}>
                      <div className="history-topline">
                        <strong>{labelForStatus(item.status)}</strong>
                        <span className={`risk ${item.status}`}>{item.count}</span>
                      </div>
                      <div className="mini-bar">
                        <div
                          className={`mini-bar-fill ${item.status}`}
                          style={{ width: `${(item.count / Math.max(orders.length, 1)) * 100}%` }}
                        />
                      </div>
                    </article>
                  ))}
                </div>
              </div>
              <div>
                <div className="panel-heading">
                  <h2>Supplier Directory</h2>
                  <p>Current suppliers available for manual and AI-driven purchasing.</p>
                </div>
                <div className="history-list">
                  {suppliers.map((supplier) => (
                    <article className="history-card" key={supplier.supplier_id}>
                      <div className="history-topline">
                        <strong>{supplier.name}</strong>
                        <span className={`risk ${supplier.reliability_score >= 0.85 ? "healthy" : supplier.reliability_score >= 0.75 ? "watch" : "critical"}`}>
                          {(supplier.reliability_score * 100).toFixed(0)}%
                        </span>
                      </div>
                      <p>{supplier.lead_time_days} day lead time</p>
                    </article>
                  ))}
                </div>
              </div>
            </section>
          </section>
        </WorkspaceShell>
      </SignedIn>
    </>
  );
}
