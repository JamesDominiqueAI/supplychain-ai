import Link from "next/link";
import { useEffect, useState } from "react";

import { getApiDocsUrl, getFallbackApiDocsUrl, resolveApiUrl } from "../lib/api";

export default function Home() {
  const [docsUrl, setDocsUrl] = useState(getFallbackApiDocsUrl());

  useEffect(() => {
    resolveApiUrl()
      .then((apiUrl) => {
        setDocsUrl(getApiDocsUrl(apiUrl));
      })
      .catch(() => {
        setDocsUrl(getFallbackApiDocsUrl());
      });
  }, []);

  return (
    <main className="landing-page">
      <div className="landing-overlay" />
      <section className="page shell landing-shell">
        <section className="hero hero-grid landing-hero">
          <div>
            <p className="eyebrow">SupplyChain AI</p>
            <h1>Run a real stock room, not a static dashboard.</h1>
            <p className="lede">
              Log in, create products, record sales, generate replenishment plans, place EOQ orders,
              and track inventory from shelf to supplier and back again.
            </p>
            <div className="hero-actions">
              <Link className="button primary" href="/login" prefetch={false}>
                Sign In With Clerk
              </Link>
              <Link className="button secondary" href="/dashboard" prefetch={false}>
                View Operations Board
              </Link>
              <a className="button secondary" href={docsUrl}>
                API Docs
              </a>
            </div>
          </div>
          <div className="hero-card">
            <p className="eyebrow">Live Workflow</p>
            <ul className="hero-list">
              <li>Add a new SKU with reorder rules and daily demand.</li>
              <li>Subtract stock instantly when a sale happens.</li>
              <li>Generate a replenishment report with AI context.</li>
              <li>Place EOQ orders and move them to in transit or arrived.</li>
            </ul>
          </div>
        </section>
      </section>
    </main>
  );
}
