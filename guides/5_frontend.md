# Guide 5: Frontend

The frontend is a real workspace app built with Next.js Pages Router, React, TypeScript, and Clerk. It is not a landing page: the first authenticated experience is the operational dashboard.

## Implemented Screens

### `/dashboard`

The operations home shows business health, inventory risk, supplier exposure, pending orders, latest report context, forecast and anomaly signals, morning brief, AI chat, and agent controls.

### `/products`

Operators can create products with SKU, category, current stock, reorder point, demand, lead time, unit cost, and preferred supplier. This screen supports the core catalog workflow needed before forecasting and ordering.

### `/movements`

Operators can record sales, purchases, and adjustments. These movements are the practical stock audit trail and immediately feed inventory health.

### `/orders`

Operators can place manual orders, review AI-drafted orders, update order status, receive quantities, and see late-order/notification state.

### `/reports`

Operators can run replenishment analysis, review recommendation history, export CSV reports, compare reports, test cash scenarios, and inspect AI audit events.

### `/audit`

Operators can inspect accepted, fallback, and refused AI decisions with reasons, previews, confidence, token usage, feature counts, and refusal/fallback rates. This is the clearest screen for demonstrating AI governance in interviews.

### `/suppliers`

Operators can add suppliers and review scorecards with reliability, open orders, delayed orders, fill rate, delay days, and exposure.

### `/settings`

Workspace settings control available cash, AI enablement, automation, notification email, and critical-stock alerts.

## API Integration

The frontend uses `frontend/lib/workspace-api.ts` as the typed API layer. It attaches Clerk session tokens, retries briefly while Clerk finishes loading, caches common reads for short windows, and invalidates paths after mutations.

Local API discovery checks:

- configured `NEXT_PUBLIC_API_URL`
- current browser host on ports `8010`, `8011`, and `8012`
- fallback host from `NEXT_PUBLIC_API_HOST`

## UX Principles

- Put operational work first: dashboard, products, orders, movements, reports, suppliers, and settings.
- Show plain explanations next to recommendations.
- Keep AI visible but accountable through confidence, fallback, audit, and report fields.
- Make risky actions draft-first.
- Favor compact management screens over marketing-style composition.
- Keep the app usable in low-data environments where history may be incomplete.

## Verification

Run a production build:

```bash
cd frontend
npm run build
```

Run browser workflow tests after starting backend and frontend and providing Clerk test credentials:

```bash
cd frontend
E2E_CLERK_EMAIL="your-test-user@example.com" E2E_CLERK_PASSWORD="..." npm run test:e2e
```

Build static assets for S3 and CloudFront:

```bash
cd frontend
npm run build:static
```
