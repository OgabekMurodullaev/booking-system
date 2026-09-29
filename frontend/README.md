# Booking System — Frontend

Vite + React 19 + TypeScript (strict), Tailwind v4, shadcn/ui, TanStack Query, React Router,
react-hook-form + zod, date-fns/date-fns-tz. See the repo root `CLAUDE.md` for the full stack and
architecture, and `DESIGN.md` for the visual design system.

## Commands

```bash
npm run dev          # dev server (proxies /api -> http://localhost:8000)
npm run build         # typecheck + production build
npm run typecheck     # tsc, no emit
npm run lint          # eslint
npm run format        # prettier --write
npm run gen:api       # regenerate src/api/schema.d.ts from the running backend's OpenAPI schema
```

Copy `.env.example` to `.env.local` to configure `VITE_API_BASE_URL` and the optional
`VITE_DEMO_*` login-page shortcut credentials.
