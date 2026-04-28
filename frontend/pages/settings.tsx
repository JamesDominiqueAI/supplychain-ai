import { SignedIn, SignedOut, useAuth, useUser } from "@clerk/nextjs";
import Head from "next/head";
import { useEffect, useState } from "react";

import { WorkspaceShell } from "../components/WorkspaceShell";
import { authorizedFetch, Business, OrderNotificationEvent, TestNotificationResponse, useWorkspaceQuery } from "../lib/workspace-api";

export default function SettingsPage() {
  const { getToken } = useAuth();
  const { user } = useUser();
  const [saving, setSaving] = useState(false);
  const [testingEmail, setTestingEmail] = useState(false);
  const [retryingEmail, setRetryingEmail] = useState(false);
  const [testNotice, setTestNotice] = useState<string | null>(null);
  const [notificationEmailDraft, setNotificationEmailDraft] = useState("");
  const businessQuery = useWorkspaceQuery<Business>(getToken, "/api/business");
  const notificationsQuery = useWorkspaceQuery<OrderNotificationEvent[]>(getToken, "/api/notifications/orders");
  const business = businessQuery.data;
  const notificationEvents = notificationsQuery.data || [];

  useEffect(() => {
    setNotificationEmailDraft(business?.notification_email || user?.primaryEmailAddress?.emailAddress || "");
  }, [business?.notification_email, user?.primaryEmailAddress?.emailAddress]);

  async function updateSettings(
    patch: Partial<Pick<Business, "ai_enabled" | "ai_automation_enabled" | "notification_email" | "critical_alerts_enabled">>,
  ) {
    setSaving(true);
    try {
      await authorizedFetch<Business>(getToken, "/api/business/settings", {
        method: "PATCH",
        body: JSON.stringify(patch),
      });
      await Promise.all([businessQuery.revalidate(), notificationsQuery.revalidate()]);
    } finally {
      setSaving(false);
    }
  }

  async function sendTestOrderEmail() {
    setTestingEmail(true);
    setTestNotice(null);
    try {
      const response = await authorizedFetch<TestNotificationResponse>(getToken, "/api/notifications/test-order-email", {
        method: "POST",
        headers: {
          "X-Actor-Email": user?.primaryEmailAddress?.emailAddress || business?.notification_email || "",
        },
      });
      setTestNotice(response.sent
        ? `Test order email sent to ${response.recipient_email || "the configured recipient"}.`
        : `Test order email failed: ${response.detail}`);
      await Promise.all([businessQuery.revalidate(), notificationsQuery.revalidate()]);
    } finally {
      setTestingEmail(false);
    }
  }

  async function retryFailedOrderEmails() {
    setRetryingEmail(true);
    setTestNotice(null);
    try {
      const events = await authorizedFetch<OrderNotificationEvent[]>(getToken, "/api/notifications/orders/retry", {
        method: "POST",
        headers: {
          "X-Actor-Email": user?.primaryEmailAddress?.emailAddress || business?.notification_email || "",
        },
      });
      const sentCount = events.filter((event) => event.status === "sent").length;
      setTestNotice(`Retried failed order emails. ${sentCount} sent notification event(s) are now in the log.`);
      await notificationsQuery.revalidate();
    } finally {
      setRetryingEmail(false);
    }
  }

  return (
    <>
      <Head><title>Settings | SupplyChain AI</title></Head>
      <SignedOut><main className="page shell"><section className="panel"><h1>Sign in required.</h1></section></main></SignedOut>
      <SignedIn>
        <WorkspaceShell title="Settings" description="Workspace identity, AI controls, and notification settings live here.">
          <section className="workspace-grid">
            <section className="panel stacked-panels">
              <div>
                <div className="panel-heading"><h2>Business Profile</h2><p>Current workspace business information.</p></div>
                <div className="history-list">
                  <article className="history-card"><div className="history-topline"><strong>Name</strong><span>{business?.name || "Loading"}</span></div></article>
                  <article className="history-card"><div className="history-topline"><strong>Country</strong><span>{business?.country || "-"}</span></div></article>
                  <article className="history-card"><div className="history-topline"><strong>Currency</strong><span>{business?.currency || "-"}</span></div></article>
                  <article className="history-card"><div className="history-topline"><strong>Available Cash</strong><span>{business?.available_cash.toLocaleString() || "-"}</span></div></article>
                </div>
              </div>

              <div className="panel">
                <div className="panel-heading"><h2>AI Controls</h2><p>Guarded AI requires explicit user enablement, and automation has its own separate switch.</p></div>
                <div className="history-list">
                  <article className="history-card">
                    <div className="history-topline">
                      <strong>Use AI</strong>
                      <button
                        className={`button ${business?.ai_enabled ? "primary" : "secondary"}`}
                        disabled={saving || !business}
                        onClick={() => updateSettings({ ai_enabled: !business?.ai_enabled })}
                      >
                        {business?.ai_enabled ? "Enabled" : "Disabled"}
                      </button>
                    </div>
                    <p>Enables AI-assisted report narration and workspace chat. Rule-based fallbacks remain available either way.</p>
                  </article>

                  <article className="history-card">
                    <div className="history-topline">
                      <strong>AI Automation</strong>
                      <button
                        className={`button ${business?.ai_automation_enabled ? "primary" : "secondary"}`}
                        disabled={saving || !business || !business.ai_enabled}
                        onClick={() => updateSettings({ ai_automation_enabled: !business?.ai_automation_enabled })}
                      >
                        {business?.ai_automation_enabled ? "Enabled" : "Disabled"}
                      </button>
                    </div>
                    <p>Allows guarded automatic purchase-order creation for urgent qualifying items. When enabled, the app can place orders for critical materials that qualify under the current rules. This switch is unavailable while AI is off.</p>
                  </article>

                  <article className="history-card">
                    <div className="history-topline">
                      <strong>Critical SKU Email Alerts</strong>
                      <button
                        className={`button ${business?.critical_alerts_enabled ? "primary" : "secondary"}`}
                        disabled={saving || !business}
                        onClick={() => updateSettings({ critical_alerts_enabled: !business?.critical_alerts_enabled })}
                      >
                        {business?.critical_alerts_enabled ? "Enabled" : "Disabled"}
                      </button>
                    </div>
                    <p>When a SKU crosses into the critical zone, the backend sends one alert email for that transition to the address saved below.</p>
                    <form
                      className="inline-form"
                      onSubmit={async (event) => {
                        event.preventDefault();
                        await updateSettings({ notification_email: notificationEmailDraft });
                      }}
                    >
                      <label>
                        Alert Email
                        <input
                          type="email"
                          value={notificationEmailDraft}
                          onChange={(event) => setNotificationEmailDraft(event.target.value)}
                          placeholder={user?.primaryEmailAddress?.emailAddress || "owner@example.com"}
                        />
                      </label>
                      <button className="button secondary" disabled={saving || !business} type="submit">Save Email</button>
                    </form>
                    {!business?.notification_email && user?.primaryEmailAddress?.emailAddress ? (
                      <p>Tip: save your signed-in Clerk email, <strong>{user.primaryEmailAddress.emailAddress}</strong>, here to receive the alerts.</p>
                    ) : null}
                    <div className="card-actions">
                      <button className="button secondary" disabled={testingEmail} onClick={sendTestOrderEmail} type="button">
                        {testingEmail ? "Sending Test Email..." : "Test Order Email"}
                      </button>
                    </div>
                    {testNotice ? <div className="notice info">{testNotice}</div> : null}
                  </article>
                </div>
              </div>
            </section>

            <section className="panel stacked-panels">
              <div>
                <div className="panel-heading"><h2>Guardrail Notes</h2><p>Current AI safety boundaries in this workspace.</p></div>
                <div className="history-list">
                  <article className="history-card"><p>Chat requests are limited to inventory, suppliers, orders, cash, reports, forecasts, delays, and related operations topics.</p></article>
                  <article className="history-card"><p>The assistant refuses unsupported claims like pretending to call suppliers or take arbitrary external actions. Real critical-stock emails only run through the configured backend alert rule.</p></article>
                  <article className="history-card"><p>Low-confidence or weak AI outputs fall back to rule-based answers instead of being shown as if they were reliable.</p></article>
                </div>
              </div>

              <div>
                <div className="panel-heading"><h2>Email Notification Log</h2><p>Recent order-email delivery attempts from the workspace.</p></div>
                <div className="card-actions">
                  <button className="button secondary" disabled={retryingEmail} onClick={retryFailedOrderEmails} type="button">
                    {retryingEmail ? "Retrying..." : "Retry Failed Emails"}
                  </button>
                </div>
                <div className="history-list">
                  {notificationEvents.map((event) => (
                    <article className="history-card" key={event.event_id}>
                      <div className="history-topline">
                        <strong>{event.sku}</strong>
                        <span className={`risk ${event.status === "sent" ? "healthy" : "critical"}`}>{event.status}</span>
                      </div>
                      <p>{event.detail}</p>
                      <div className="history-meta">
                        <span>{new Date(event.created_at).toLocaleString()}</span>
                        <span>{event.recipient_email || "no recipient"}</span>
                        <span>{event.placed_by_type}</span>
                      </div>
                      {event.placed_by_label ? <div className="history-meta"><span>{event.placed_by_label}</span></div> : null}
                    </article>
                  ))}
                  {notificationEvents.length === 0 ? (
                    <article className="history-card"><p>No order-email attempts have been recorded yet.</p></article>
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
