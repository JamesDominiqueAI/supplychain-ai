# Frontend

Suggested pages:
- `/dashboard`
- `/inventory`
- `/suppliers`
- `/recommendations`
- `/reports`

Use a layout that makes operational status obvious at a glance.

Development:

```bash
npm run dev
```

Static deployment build for `S3 + CloudFront`:

```bash
npm run build:static
```

That command:

- switches the app into static export mode
- temporarily disables Next middleware during export
- writes deployable assets into `frontend/out`
