import { SignedIn, SignedOut, useAuth, useUser } from "@clerk/nextjs";
import Head from "next/head";
import { FormEvent, useEffect, useMemo, useState } from "react";

import { WorkspaceShell } from "../components/WorkspaceShell";
import { authorizedFetch, Product, Supplier, useWorkspaceQuery } from "../lib/workspace-api";

const EMPTY_PRODUCT_FORM = {
  sku: "",
  name: "",
  category: "",
  current_stock: 0,
  reorder_point: 10,
  target_days_of_cover: 14,
  lead_time_days: 7,
  avg_daily_demand: 1,
  unit_cost: 100,
};

export default function ProductsPage() {
  const { getToken } = useAuth();
  const { user } = useUser();
  const [productForm, setProductForm] = useState(EMPTY_PRODUCT_FORM);
  const [saleProductId, setSaleProductId] = useState("");
  const [saleQuantity, setSaleQuantity] = useState(1);
  const [manualOrderProductId, setManualOrderProductId] = useState("");
  const [manualOrderQuantity, setManualOrderQuantity] = useState(1);
  const [manualOrderSupplierId, setManualOrderSupplierId] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const productsQuery = useWorkspaceQuery<Product[]>(getToken, "/api/products");
  const suppliersQuery = useWorkspaceQuery<Supplier[]>(getToken, "/api/suppliers");
  const products = productsQuery.data || [];
  const suppliers = suppliersQuery.data || [];

  useEffect(() => {
    if (productsQuery.error || suppliersQuery.error) {
      setNotice("Could not load products.");
    }
  }, [productsQuery.error, suppliersQuery.error]);

  useEffect(() => {
    setSaleProductId((current) => current || products[0]?.product_id || "");
    setManualOrderProductId((current) => current || products[0]?.product_id || "");
    setManualOrderSupplierId((current) => current || products[0]?.preferred_supplier_id || suppliers[0]?.supplier_id || "");
  }, [products, suppliers]);

  async function handleCreateProduct(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await authorizedFetch<Product>(getToken, "/api/products", {
      method: "POST",
      body: JSON.stringify(productForm),
    });
    setProductForm(EMPTY_PRODUCT_FORM);
    setNotice("Product added.");
    await Promise.all([productsQuery.revalidate(), suppliersQuery.revalidate()]);
  }

  async function handleSale(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await authorizedFetch(getToken, "/api/inventory/movements", {
      method: "POST",
      body: JSON.stringify({
        product_id: saleProductId,
        movement_type: "sale",
        quantity: saleQuantity,
        note: "Recorded from products page",
      }),
    });
    setNotice("Sale recorded.");
    await productsQuery.revalidate();
  }

  async function handleManualOrder(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await authorizedFetch(getToken, "/api/orders", {
      method: "POST",
      headers: {
        "X-Actor-Email": user?.primaryEmailAddress?.emailAddress || "",
      },
      body: JSON.stringify({
        product_id: manualOrderProductId,
        quantity: manualOrderQuantity,
        supplier_id: manualOrderSupplierId || null,
        note: "Placed from products page",
      }),
    });
    setNotice("Order placed.");
    await productsQuery.revalidate();
  }

  const filteredProducts = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return products;
    return products.filter((product) =>
      product.name.toLowerCase().includes(query) ||
      product.sku.toLowerCase().includes(query) ||
      product.category.toLowerCase().includes(query),
    );
  }, [products, search]);

  const categoryCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const product of products) {
      counts.set(product.category, (counts.get(product.category) || 0) + 1);
    }
    return [...counts.entries()]
      .map(([category, count]) => ({ category, count }))
      .sort((left, right) => right.count - left.count);
  }, [products]);

  const stockRiskBands = useMemo(() => {
    const healthy = products.filter((product) => product.current_stock > product.reorder_point).length;
    const watch = products.filter(
      (product) => product.current_stock <= product.reorder_point && product.current_stock > Math.max(1, Math.floor(product.reorder_point / 2)),
    ).length;
    const critical = products.filter(
      (product) => product.current_stock <= Math.max(1, Math.floor(product.reorder_point / 2)),
    ).length;
    return { healthy, watch, critical };
  }, [products]);

  return (
    <>
      <Head><title>Products | SupplyChain AI</title></Head>
      <SignedOut><main className="page shell"><section className="panel"><h1>Sign in required.</h1></section></main></SignedOut>
      <SignedIn>
        <WorkspaceShell title="Products" description="Manage the product catalog, log sales, and place manual replenishment orders.">
          {notice ? <div className="notice info">{notice}</div> : null}
          <section className="chart-grid">
            <article className="chart-card">
              <div className="panel-heading"><h2>Products By Category</h2><p>How the catalog is distributed right now.</p></div>
              <div className="chart-list">
                {categoryCounts.map((item) => (
                  <div className="chart-row" key={item.category}>
                    <div className="chart-labels">
                      <strong>{item.category}</strong>
                      <span>{item.count} products</span>
                    </div>
                    <div className="mini-bar">
                      <div className="mini-bar-fill spend" style={{ width: `${(item.count / Math.max(products.length, 1)) * 100}%` }} />
                    </div>
                  </div>
                ))}
              </div>
            </article>
            <article className="chart-card">
              <div className="panel-heading"><h2>Stock Health Mix</h2><p>Quick split between healthy, watch, and critical items.</p></div>
              <div className="history-list">
                <article className="history-card">
                  <div className="history-topline"><strong>Healthy</strong><span className="risk healthy">{stockRiskBands.healthy}</span></div>
                  <div className="mini-bar"><div className="mini-bar-fill healthy" style={{ width: `${(stockRiskBands.healthy / Math.max(products.length, 1)) * 100}%` }} /></div>
                </article>
                <article className="history-card">
                  <div className="history-topline"><strong>Watch</strong><span className="risk watch">{stockRiskBands.watch}</span></div>
                  <div className="mini-bar"><div className="mini-bar-fill watch" style={{ width: `${(stockRiskBands.watch / Math.max(products.length, 1)) * 100}%` }} /></div>
                </article>
                <article className="history-card">
                  <div className="history-topline"><strong>Critical</strong><span className="risk critical">{stockRiskBands.critical}</span></div>
                  <div className="mini-bar"><div className="mini-bar-fill critical" style={{ width: `${(stockRiskBands.critical / Math.max(products.length, 1)) * 100}%` }} /></div>
                </article>
              </div>
            </article>
          </section>
          <section className="workspace-grid">
            <section className="panel">
              <div className="panel-heading"><h2>Catalog</h2><p>Products currently tracked in the workspace.</p></div>
              <div className="toolbar">
                <input
                  className="search-input"
                  placeholder="Search by SKU, product, or category"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                />
              </div>
              <div className="table">
                <div className="row header products-row"><span>SKU</span><span>Name</span><span>Category</span><span>Stock</span><span>Reorder</span><span>Unit Cost</span></div>
                {filteredProducts.map((product) => (
                  <div className="row products-row" key={product.product_id}>
                    <span>{product.sku}</span>
                    <span>{product.name}</span>
                    <span>{product.category}</span>
                    <span>{product.current_stock}</span>
                    <span>{product.reorder_point}</span>
                    <span>{product.unit_cost}</span>
                  </div>
                ))}
              </div>
            </section>
            <section className="panel stacked-panels">
              <form className="form-card" onSubmit={handleCreateProduct}>
                <div className="form-card-header"><h3>Add Product</h3><p>Create a new tracked SKU.</p></div>
                <div className="form-grid">
                  <label>SKU<input value={productForm.sku} onChange={(e) => setProductForm({ ...productForm, sku: e.target.value })} required /></label>
                  <label>Name<input value={productForm.name} onChange={(e) => setProductForm({ ...productForm, name: e.target.value })} required /></label>
                  <label>Category<input value={productForm.category} onChange={(e) => setProductForm({ ...productForm, category: e.target.value })} required /></label>
                  <label>Current Stock<input type="number" min="0" value={productForm.current_stock} onChange={(e) => setProductForm({ ...productForm, current_stock: Number(e.target.value) })} /></label>
                  <label>Reorder Point<input type="number" min="0" value={productForm.reorder_point} onChange={(e) => setProductForm({ ...productForm, reorder_point: Number(e.target.value) })} /></label>
                  <label>Lead Time Days<input type="number" min="1" value={productForm.lead_time_days} onChange={(e) => setProductForm({ ...productForm, lead_time_days: Number(e.target.value) })} /></label>
                  <label>Target Days Cover<input type="number" min="1" value={productForm.target_days_of_cover} onChange={(e) => setProductForm({ ...productForm, target_days_of_cover: Number(e.target.value) })} /></label>
                  <label>Avg Daily Demand<input type="number" min="0" step="0.1" value={productForm.avg_daily_demand} onChange={(e) => setProductForm({ ...productForm, avg_daily_demand: Number(e.target.value) })} /></label>
                  <label>Unit Cost<input type="number" min="0" step="0.01" value={productForm.unit_cost} onChange={(e) => setProductForm({ ...productForm, unit_cost: Number(e.target.value) })} /></label>
                </div>
                <button className="button primary" type="submit">Add Product</button>
              </form>
              <form className="form-card" onSubmit={handleSale}>
                <div className="form-card-header"><h3>Record Sale</h3><p>Subtract sold stock.</p></div>
                <div className="form-grid compact-grid">
                  <label>Product<select value={saleProductId} onChange={(e) => setSaleProductId(e.target.value)}>{products.map((product) => <option key={product.product_id} value={product.product_id}>{product.name} ({product.sku})</option>)}</select></label>
                  <label>Quantity<input type="number" min="1" value={saleQuantity} onChange={(e) => setSaleQuantity(Number(e.target.value))} /></label>
                </div>
                <button className="button secondary" type="submit">Subtract Sold Units</button>
              </form>
              <form className="form-card" onSubmit={handleManualOrder}>
                <div className="form-card-header"><h3>Place Order</h3><p>Create a manual purchase order.</p></div>
                <div className="form-grid compact-grid">
                  <label>Product<select value={manualOrderProductId} onChange={(e) => setManualOrderProductId(e.target.value)}>{products.map((product) => <option key={product.product_id} value={product.product_id}>{product.name} ({product.sku})</option>)}</select></label>
                  <label>Supplier<select value={manualOrderSupplierId} onChange={(e) => setManualOrderSupplierId(e.target.value)}>{suppliers.map((supplier) => <option key={supplier.supplier_id} value={supplier.supplier_id}>{supplier.name}</option>)}</select></label>
                  <label>Quantity<input type="number" min="1" value={manualOrderQuantity} onChange={(e) => setManualOrderQuantity(Number(e.target.value))} /></label>
                </div>
                <button className="button primary" type="submit">Place Order</button>
              </form>
            </section>
          </section>
        </WorkspaceShell>
      </SignedIn>
    </>
  );
}
