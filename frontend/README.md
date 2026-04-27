# Frontend

The frontend is a Clerk-protected Next.js workspace for day-to-day supply-chain operations.

Implemented pages:

- `/dashboard`
- `/products`
- `/movements`
- `/orders`
- `/reports`
- `/suppliers`
- `/settings`
- `/login`

Development:

```bash
npm run dev
```

Production build:

```bash
npm run build
```

Static deployment build for S3 and CloudFront:

```bash
npm run build:static
```

The typed API client lives in `lib/workspace-api.ts`. It attaches Clerk tokens, discovers local API ports, caches short-lived reads, and invalidates relevant workspace paths after mutations.
