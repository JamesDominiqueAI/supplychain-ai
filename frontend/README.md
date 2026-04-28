# Frontend

The frontend is a Clerk-protected Next.js workspace for day-to-day supply-chain operations.

Implemented pages:

- `/dashboard`
- `/products`
- `/movements`
- `/orders`
- `/reports`
- `/audit`
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

Docker image:

```bash
cd frontend
docker build -t supplychain-ai-frontend .
docker run --rm -p 3000:3000 -e NEXT_PUBLIC_API_URL=http://localhost:8010 supplychain-ai-frontend
```

The typed API client lives in `lib/workspace-api.ts`. It attaches Clerk tokens, discovers local API ports, caches short-lived reads, and invalidates relevant workspace paths after mutations.
