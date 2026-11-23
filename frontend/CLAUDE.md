## Project Context

React frontend for Animal Finder — a generative AI chat agent that finds related animals for a user's query. The API lives in `../backend` (FastAPI).

## Tech Stack

- **Language:** TypeScript
- **Package Manager:** npm
- **Framework:** React 19
- **Build Tool:** Vite
- **Component Library:** shadcn/ui (Radix base, Nova preset, lucide icons)
- **Styling:** Tailwind CSS v4 (via `@tailwindcss/vite`; theme tokens in `src/index.css`)
- **Linting:** oxlint

### UI Components

- shadcn/ui is the main component library. Before building any UI element, check whether a shadcn component exists and use it (https://ui.shadcn.com/docs/components).
- Add components with the CLI, never by hand: `npx shadcn@latest add <component>`. Config lives in `components.json`.
- Generated primitives go in `src/components/ui/` and are owned by the project — editing them is fine, but prefer composing/wrapping them in app components instead.
- App components go in `src/components/` (kebab-case filenames, e.g. `chat-bar.tsx`, named exports e.g. `ChatBar`).
- Style with Tailwind utility classes and shadcn theme tokens (`bg-background`, `text-muted-foreground`, `border-input`, …) rather than hard-coded colors or separate CSS files. Merge classes with `cn()` from `@/lib/utils`.
- Icons come from `lucide-react`.
- Import via the `@/` alias (maps to `src/`), e.g. `import { Button } from "@/components/ui/button"`.

### Development & Environments

- Install deps: `npm install`
- Run dev server: `npm run dev` (http://localhost:5173)
- Type-check + build: `npm run build`
- Lint: `npm run lint`

### Backend API

- In dev, Vite proxies `/api/*` to the backend at `http://127.0.0.1:8000` (not `localhost`, which on Windows tries IPv6 `::1` first and adds latency) with the `/api` prefix stripped (see `vite.config.ts`). Call `fetch('/api/chat/stream', { method: 'POST', body: JSON.stringify({ prompt }) })`, not the backend URL directly — this keeps requests same-origin so the `session_id` cookie works without CORS.
- Start the backend from `../backend` with `uv run uvicorn animal_finder.main:app --reload`.

### Github Commits

Remove the "Co-Authored-By" line on generated commits.
