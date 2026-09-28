# Luthor frontend

Local-first Next.js workspace with an icy-cyan, deep-navy visual system, bundled
Inter typography, and responsive desktop/mobile layouts.

## Run

Requires Node.js 20.9 or newer. From this directory:

```bash
npm ci
cp .env.example .env.local
npm run dev
```

Open http://127.0.0.1:3000. The app starts in a clearly labeled, fictional preview
workspace. No inference or external search runs just by opening the preview.

To work with real data, start the FastAPI backend using the root README, then
choose **Use my workspace**. Upload a resume under **My resume**, research a
company with **New research**, or discover funded companies under **Discover**.
Research, discovery, and draft generation can take several minutes. Outreach
is draft-only; Luthor never sends messages.

The server requires `BACKEND_URL` in `.env.local` (see `.env.example` for local
development values). There is no backend URL fallback in application code.
The browser uses relative API paths. Origin checks use the incoming host and
protocol; behind a reverse proxy, set `APP_ORIGIN` to the exact public origin.
Forwarded-host headers are not trusted. Keep Tavily and
model-provider keys in the backend environment, never in browser variables.
This is a local personal workspace without authentication; do not expose it
publicly without adding access control.

Only the workspace mode, active resume ID, and bookmarks are stored in browser
local storage. Reports and resume profiles stay in the backend database.
Preview data is separate from the live workspace.

## Checks

```bash
npm run typecheck
npm run build
npx playwright install chromium
npm test
```

The browser suite covers preview navigation, search, bookmarks, detail drawers,
draft copying, mocked live API/error states, mocked multipart resume upload,
and mobile layouts. It does not submit personal data or run paid inference.

## Layout

- `src/app`: entry point, theme, and allowlisted same-origin backend proxy.
- `src/components`: workspace screens and the original Luthor brand mark.
- `src/lib`: typed API client, response types, and illustrative preview data.
- `tests`: Playwright interaction tests.
