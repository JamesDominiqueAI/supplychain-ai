import { SignedIn, SignedOut, useAuth } from "@clerk/nextjs";
import Head from "next/head";
import { useMemo, useState } from "react";

import { WorkspaceShell } from "../components/WorkspaceShell";
import { InventoryMovement, Product, useWorkspaceQuery } from "../lib/workspace-api";

export default function MovementsPage() {
  const { getToken } = useAuth();
  const [search, setSearch] = useState("");
  const [movementFilter, setMovementFilter] = useState("all");
  const movementsQuery = useWorkspaceQuery<InventoryMovement[]>(getToken, "/api/inventory/movements");
  const productsQuery = useWorkspaceQuery<Product[]>(getToken, "/api/products");
  const movements = movementsQuery.data || [];
  const products = productsQuery.data || [];

  const filteredMovements = useMemo(() => {
    const query = search.trim().toLowerCase();
    return movements.filter((movement) => {
      const product = products.find((item) => item.product_id === movement.product_id);
      const matchesQuery =
        !query ||
        (product?.name || "").toLowerCase().includes(query) ||
        (product?.sku || "").toLowerCase().includes(query) ||
        (movement.note || "").toLowerCase().includes(query);
      const matchesType = movementFilter === "all" || movement.movement_type === movementFilter;
      return matchesQuery && matchesType;
    });
  }, [movementFilter, movements, products, search]);

  const movementSummary = useMemo(() => {
    const saleCount = movements.filter((movement) => movement.movement_type === "sale").length;
    const receiptCount = movements.filter((movement) => movement.movement_type === "purchase").length;
    const adjustmentCount = movements.filter((movement) => movement.movement_type === "adjustment").length;
    return { saleCount, receiptCount, adjustmentCount };
  }, [movements]);

  const topMovingProducts = useMemo(() => {
    const totals = new Map<string, number>();
    for (const movement of movements) {
      totals.set(movement.product_id, (totals.get(movement.product_id) || 0) + movement.quantity);
    }
    return [...totals.entries()]
      .map(([productId, quantity]) => ({
        productId,
        quantity,
        product: products.find((item) => item.product_id === productId),
      }))
      .sort((left, right) => right.quantity - left.quantity)
      .slice(0, 5);
  }, [movements, products]);

  return (
    <>
      <Head><title>Movements | SupplyChain AI</title></Head>
      <SignedOut><main className="page shell"><section className="panel"><h1>Sign in required.</h1></section></main></SignedOut>
      <SignedIn>
        <WorkspaceShell title="Inventory Movements" description="Sales, receipts, and corrections belong in their own history view.">
          <section className="chart-grid">
            <article className="chart-card">
              <div className="panel-heading"><h2>Movement Type Mix</h2><p>How recent inventory activity is split.</p></div>
              <div className="history-list">
                <article className="history-card">
                  <div className="history-topline"><strong>Sales</strong><span className="risk critical">{movementSummary.saleCount}</span></div>
                  <div className="mini-bar"><div className="mini-bar-fill critical" style={{ width: `${(movementSummary.saleCount / Math.max(movements.length, 1)) * 100}%` }} /></div>
                </article>
                <article className="history-card">
                  <div className="history-topline"><strong>Receipts</strong><span className="risk healthy">{movementSummary.receiptCount}</span></div>
                  <div className="mini-bar"><div className="mini-bar-fill healthy" style={{ width: `${(movementSummary.receiptCount / Math.max(movements.length, 1)) * 100}%` }} /></div>
                </article>
                <article className="history-card">
                  <div className="history-topline"><strong>Adjustments</strong><span className="risk watch">{movementSummary.adjustmentCount}</span></div>
                  <div className="mini-bar"><div className="mini-bar-fill watch" style={{ width: `${(movementSummary.adjustmentCount / Math.max(movements.length, 1)) * 100}%` }} /></div>
                </article>
              </div>
            </article>
            <article className="chart-card">
              <div className="panel-heading"><h2>Top Moving SKUs</h2><p>Products with the most recent movement volume.</p></div>
              <div className="chart-list">
                {topMovingProducts.map((item) => (
                  <div className="chart-row" key={item.productId}>
                    <div className="chart-labels">
                      <strong>{item.product?.sku || item.productId}</strong>
                      <span>{item.quantity} units</span>
                    </div>
                    <div className="mini-bar">
                      <div className="mini-bar-fill spend" style={{ width: `${(item.quantity / Math.max(topMovingProducts[0]?.quantity || 1, 1)) * 100}%` }} />
                    </div>
                  </div>
                ))}
              </div>
            </article>
          </section>
          <section className="panel">
            <div className="panel-heading"><h2>Movement Log</h2><p>Full recent inventory history across sales and receipts.</p></div>
            <div className="toolbar">
              <input
                className="search-input"
                placeholder="Search by SKU, product, or note"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
              />
              <select value={movementFilter} onChange={(event) => setMovementFilter(event.target.value)}>
                <option value="all">All movements</option>
                <option value="sale">Sales</option>
                <option value="purchase">Receipts</option>
                <option value="adjustment">Adjustments</option>
              </select>
            </div>
            <div className="history-list">
              {filteredMovements.map((movement) => {
                const product = products.find((item) => item.product_id === movement.product_id);
                return (
                  <article className="history-card" key={movement.movement_id}>
                    <div className="history-topline">
                      <strong>{product?.name || movement.product_id}</strong>
                      <span className={`risk ${movement.movement_type === "sale" ? "critical" : movement.movement_type === "purchase" ? "healthy" : "watch"}`}>
                        {movement.movement_type}
                      </span>
                    </div>
                    <p>{product?.sku || ""} • {movement.quantity} units</p>
                    <div className="history-meta">
                      <span>{new Date(movement.occurred_at).toLocaleString()}</span>
                      <span>{movement.note || "No note"}</span>
                    </div>
                  </article>
                );
              })}
            </div>
          </section>
        </WorkspaceShell>
      </SignedIn>
    </>
  );
}
