import { SignedIn, SignedOut, useAuth, useUser } from "@clerk/nextjs";
import Head from "next/head";
import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";

import { WorkspaceShell } from "../components/WorkspaceShell";
import {
  AgentRunResponse,
  AnomalyInsight,
  AutoOrderResult,
  authorizedFetch,
  Business,
  ChatResponse,
  DashboardSummaryResponse,
  ForecastInsight,
  InventoryHealthItem,
  MorningBriefResponse,
  PurchaseOrder,
  Report,
  useWorkspaceQuery,
} from "../lib/workspace-api";

function renderFormattedAnswer(answer: string) {
  const normalizedAnswer = answer
    .replace(/\s+(\d+\))/g, "\n$1")
    .replace(/\s+(Current cash\b)/gi, "\n$1")
    .replace(/\s+(Late orders:)/gi, "\n$1")
    .replace(/\s+(Action plan:)/gi, "\n$1");

  const lines = normalizedAnswer
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);

  const blocks: Array<{ type: "paragraph" | "list" | "risk" | "callout"; items: string[]; title?: string }> = [];

  for (const line of lines) {
    const numberedRisk = line.match(/^(\d+)[).]\s+([^:]+):\s*(.+)$/);
    if (numberedRisk) {
      blocks.push({
        type: "risk",
        title: numberedRisk[2].trim(),
        items: [numberedRisk[3].trim()],
      });
      continue;
    }

    const isCallout = /^(Current cash\b|Late orders:|Action plan:)/i.test(line);
    if (isCallout) {
      blocks.push({ type: "callout", items: [line] });
      continue;
    }

    const isListItem = /^(-|\*|\d+[.)])\s+/.test(line);
    const content = line.replace(/^(-|\*|\d+[.)])\s+/, "").trim();

    if (isListItem) {
      const lastBlock = blocks[blocks.length - 1];
      if (lastBlock?.type === "list") {
        lastBlock.items.push(content);
      } else {
        blocks.push({ type: "list", items: [content] });
      }
      continue;
    }

    blocks.push({ type: "paragraph", items: [line] });
  }

  return blocks.map((block, index) => {
    if (block.type === "risk") {
      return (
        <article className="answer-risk-card" key={`risk-${index}`}>
          <strong>{block.title}</strong>
          <p>{block.items[0]}</p>
        </article>
      );
    }

    if (block.type === "callout") {
      return (
        <p className="answer-callout" key={`callout-${index}`}>
          {block.items[0]}
        </p>
      );
    }

    if (block.type === "list") {
      return (
        <ul className="answer-list" key={`list-${index}`}>
          {block.items.map((item, itemIndex) => (
            <li key={`item-${index}-${itemIndex}`}>{item}</li>
          ))}
        </ul>
      );
    }

    return (
      <p className="answer-paragraph" key={`paragraph-${index}`}>
        {block.items[0]}
      </p>
    );
  });
}

export default function Dashboard() {
  if (!process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY) {
    return (
      <main className="page shell">
        <section className="panel">
          <p className="eyebrow">Clerk Setup Required</p>
          <h1>Dashboard authentication is waiting on Clerk keys.</h1>
        </section>
      </main>
    );
  }

  return <OverviewPage />;
}

function OverviewPage() {
  const { getToken } = useAuth();
  const { user } = useUser();
  const [chatPrompt, setChatPrompt] = useState("What inventory risks and late orders should I focus on today?");
  const [chatAnswer, setChatAnswer] = useState<string | null>(null);
  const [chatUsedAi, setChatUsedAi] = useState(false);
  const [chatLoading, setChatLoading] = useState(false);
  const [autoOrderMessage, setAutoOrderMessage] = useState<string | null>(null);
  const [autoOrdering, setAutoOrdering] = useState(false);
  const [agentRun, setAgentRun] = useState<AgentRunResponse | null>(null);
  const [agentRunning, setAgentRunning] = useState(false);
  const summaryQuery = useWorkspaceQuery<DashboardSummaryResponse>(getToken, "/api/dashboard/summary");
  const briefQuery = useWorkspaceQuery<MorningBriefResponse>(getToken, "/api/ai/brief", {
    enabled: Boolean(summaryQuery.data?.business.ai_enabled),
  });

  const business = summaryQuery.data?.business || null;
  const health = summaryQuery.data?.inventory_health || [];
  const orders = summaryQuery.data?.orders || [];
  const report = summaryQuery.data?.latest_report || null;
  const forecasts = summaryQuery.data?.forecasts || [];
  const anomalies = summaryQuery.data?.anomalies || [];
  const morningBrief = briefQuery.data || summaryQuery.data?.morning_brief || null;
  const loading = summaryQuery.loading;
  const aiLoading = briefQuery.loading && !briefQuery.data;
  const error = summaryQuery.error;
  const aiError = briefQuery.error;

  const critical = health.filter((item) => item.risk_level === "critical").length;
  const watch = health.filter((item) => item.risk_level !== "critical" && item.risk_level !== "healthy").length;
  const inTransit = orders.filter((item) => item.status === "in_transit").length;
  const lateOrders = orders.filter((item) => item.is_late).length;

  async function askAI(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setChatLoading(true);
    try {
      const response = await authorizedFetch<ChatResponse>(getToken, "/api/ai/chat", {
        method: "POST",
        body: JSON.stringify({ message: chatPrompt }),
      });
      setChatAnswer(response.answer);
      setChatUsedAi(response.used_ai);
    } finally {
      setChatLoading(false);
    }
  }

  async function runAutoOrders() {
    setAutoOrdering(true);
    try {
      const result = await authorizedFetch<AutoOrderResult>(getToken, "/api/ai/auto-orders", {
        method: "POST",
        headers: {
          "X-Actor-Email": user?.primaryEmailAddress?.emailAddress || "",
        },
      });
      setAutoOrderMessage(result.summary);
      await Promise.all([summaryQuery.revalidate(), briefQuery.revalidate()]);
    } finally {
      setAutoOrdering(false);
    }
  }

  async function runOperationsAgent() {
    setAgentRunning(true);
    try {
      const result = await authorizedFetch<AgentRunResponse>(getToken, "/api/ai/agents/operations", {
        method: "POST",
        headers: {
          "X-Actor-Email": user?.primaryEmailAddress?.emailAddress || "",
        },
        body: JSON.stringify({
          goal: "Monitor today's inventory risks, late orders, cash pressure, and safe replenishment actions.",
          allow_order_drafts: Boolean(business?.ai_automation_enabled),
        }),
      });
      setAgentRun(result);
      await Promise.all([summaryQuery.revalidate(), briefQuery.revalidate()]);
    } finally {
      setAgentRunning(false);
    }
  }

  return (
    <>
      <Head>
        <title>Overview | SupplyChain AI</title>
      </Head>
      <SignedOut>
        <main className="page shell">
          <section className="panel">
            <p className="eyebrow">Clerk Login Required</p>
            <h1>Sign in to open the operations workspace.</h1>
          </section>
        </main>
      </SignedOut>
      <SignedIn>
        <WorkspaceShell
          title={business?.name || "Operations Overview"}
          description="Use this overview for quick triage, then dive into dedicated pages for products, orders, movement history, reports, suppliers, and settings."
        >
          {error ? <div className="notice error">Dashboard could not reach the API: {error}</div> : null}
          {loading ? (
            <section className="panel">Loading overview...</section>
          ) : (
            <>
              <section className="stats-grid stats-grid-wide">
                <article className="stat-card accent-card">
                  <span>Available Cash</span>
                  <strong>{business?.available_cash.toLocaleString()} {business?.currency}</strong>
                </article>
                <article className="stat-card">
                  <span>Critical Items</span>
                  <strong>{critical}</strong>
                </article>
                <article className="stat-card">
                  <span>Watch Items</span>
                  <strong>{watch}</strong>
                </article>
                <article className="stat-card">
                  <span>Orders In Transit</span>
                  <strong>{inTransit}</strong>
                </article>
                <article className="stat-card">
                  <span>Late Orders</span>
                  <strong>{lateOrders}</strong>
                </article>
                <article className="stat-card">
                  <span>Latest AI Recommendations</span>
                  <strong>{report?.recommendations.length || 0}</strong>
                </article>
              </section>

              <section className="workspace-grid">
                <section className="panel">
                  <div className="panel-heading">
                    <h2>Morning Brief</h2>
                    <p>AI-backed owner summary of what matters right now.</p>
                  </div>
                  {aiError ? <div className="notice info">AI insights are slow right now: {aiError}</div> : null}
                  <div className="history-list">
                    <article className="history-card summary-focus-card">
                      <div className="history-topline">
                        <strong>Summary</strong>
                        <span className={`risk ${morningBrief?.used_ai ? "healthy" : "watch"}`}>{morningBrief?.used_ai ? "AI" : "rules"}</span>
                      </div>
                      <p>{morningBrief?.summary || (aiLoading ? "Loading AI brief..." : "Morning brief will appear once workspace data loads.")}</p>
                    </article>
                    {(morningBrief?.priorities || []).map((priority, index) => (
                      <article className="history-card" key={`${index}-${priority}`}>
                        <div className="history-topline">
                          <strong>Priority {index + 1}</strong>
                          <span className="risk watch">today</span>
                        </div>
                        <p>{priority}</p>
                      </article>
                    ))}
                    <Link href="/reports" className="history-card">
                      <div className="history-topline">
                        <strong>Open Reports</strong>
                        <span className="risk healthy">analysis</span>
                      </div>
                      <p>Review what-if cash scenarios and compare replenishment runs.</p>
                    </Link>
                  </div>
                </section>

                <section className="panel">
                  <div className="panel-heading">
                    <h2>AI Brief</h2>
                    <p>The AI layer now adds forecasts, anomaly monitoring, workspace chat, and automatic order creation for urgent items.</p>
                  </div>
                  <div className="history-list">
                    <article className="history-card">
                      <div className="history-topline">
                        <strong>Latest Report</strong>
                        <span className="risk healthy">{report ? "ready" : "idle"}</span>
                      </div>
                      <p>{report?.summary || "Generate a replenishment report from the Reports page."}</p>
                    </article>
                    <article className="history-card">
                      <div className="history-topline">
                        <strong>Forecast Signal</strong>
                        <span className={`risk ${forecasts[0]?.trend_direction === "up" ? "watch" : forecasts[0]?.trend_direction === "down" ? "healthy" : "high"}`}>
                          {forecasts[0]?.trend_direction || "steady"}
                        </span>
                      </div>
                      <p>
                        {forecasts[0]
                          ? `${forecasts[0].sku} is forecasting ${forecasts[0].predicted_7d_demand} units over 7 days.`
                          : aiLoading
                            ? "Loading forecast insights..."
                            : "Forecast insights will appear once products and sales history are available."}
                      </p>
                    </article>
                    <article className="history-card">
                      <div className="history-topline">
                        <strong>Anomalies</strong>
                        <span className={`risk ${anomalies[0]?.severity || "healthy"}`}>{anomalies.length}</span>
                      </div>
                      <p>{anomalies[0]?.detail || (aiLoading ? "Loading anomaly scan..." : "No major anomaly signal is active right now.")}</p>
                    </article>
                    <button
                      className="button secondary wide-button"
                      onClick={runAutoOrders}
                      disabled={autoOrdering || !business?.ai_enabled || !business?.ai_automation_enabled}
                    >
                      {autoOrdering ? "Running Auto Orders..." : "Run Auto Orders"}
                    </button>
                    {!business?.ai_enabled || !business?.ai_automation_enabled ? (
                      <div className="notice info">Enable both `Use AI` and `AI Automation` in Settings before automatic order placement can run.</div>
                    ) : null}
                    {autoOrderMessage ? <div className="notice info">{autoOrderMessage}</div> : null}
                    <article className="history-card">
                      <div className="history-topline">
                        <strong>Operations Agent</strong>
                        <span className={`risk ${agentRun?.status === "completed" ? "healthy" : "watch"}`}>
                          {agentRun?.status || "ready"}
                        </span>
                      </div>
                      <p>
                        Runs a guarded internal workflow: scan risky SKUs, check late orders, review cash pressure,
                        and draft replenishment orders only when automation is enabled.
                      </p>
                    </article>
                    <button
                      className="button primary wide-button"
                      onClick={runOperationsAgent}
                      disabled={agentRunning || !business?.ai_enabled}
                    >
                      {agentRunning ? "Running Agent..." : "Run Operations Agent"}
                    </button>
                    {!business?.ai_enabled ? (
                      <div className="notice info">Enable `Use AI` in Settings before the operations agent can run.</div>
                    ) : null}
                    {agentRun ? (
                      <div className="history-card">
                        <div className="history-topline">
                          <strong>Latest Agent Run</strong>
                          <span>{agentRun.steps.length} tool steps</span>
                        </div>
                        <p>{agentRun.summary}</p>
                        <div className="answer-content">
                          {agentRun.steps.map((step) => (
                            <article className="answer-risk-card" key={step.step_id}>
                              <strong>{step.tool_name.replace(/_/g, " ")}</strong>
                              <p>{step.summary}</p>
                              {step.details.length ? (
                                <ul className="answer-list">
                                  {step.details.map((detail, index) => (
                                    <li key={`${step.step_id}-${index}`}>{detail}</li>
                                  ))}
                                </ul>
                              ) : null}
                            </article>
                          ))}
                        </div>
                      </div>
                    ) : null}
                    <form className="form-card" onSubmit={askAI}>
                      <div className="form-card-header">
                        <h3>Ask Workspace AI</h3>
                        <p>Ask about risk, suppliers, delays, cash, or what to do next.</p>
                      </div>
                      <label>
                        Question
                        <input value={chatPrompt} onChange={(event) => setChatPrompt(event.target.value)} />
                      </label>
                      <button className="button primary" type="submit" disabled={chatLoading}>
                        {chatLoading ? "Thinking..." : "Ask AI"}
                      </button>
                      {chatAnswer ? (
                        <div className="history-card">
                          <div className="history-topline">
                            <strong>Answer</strong>
                            <span className={`risk ${chatUsedAi ? "healthy" : "watch"}`}>{chatUsedAi ? "AI" : "rules"}</span>
                          </div>
                          <div className="answer-content">{renderFormattedAnswer(chatAnswer)}</div>
                        </div>
                      ) : null}
                    </form>
                    <Link href="/reports" className="button primary wide-button" prefetch={false}>
                      Open Reports Workspace
                    </Link>
                  </div>
                </section>
              </section>
            </>
          )}
        </WorkspaceShell>
      </SignedIn>
    </>
  );
}
