# AEGIS Dashboard

The AEGIS dashboard is a **separate static deployable**. It is not part of the
FastAPI process and is never shipped inside the Python package. Per
[`docs/architecture/container-architecture.md`](../docs/architecture/container-architecture.md)
the dashboard talks **only** to the AEGIS REST API; it never touches the
database or any other backend. This keeps the interface layer decoupled from
the routing layer and lets the API contract the dashboard consumes stay covered
by contract testing.

## Running

Serve this directory with any static server and point it at a running API:

```bash
# one terminal: the API
AEGIS_DEV_LOGIN=1 docker compose up -d --build api

# another terminal: the dashboard (pick any free port)
python -m http.server 5173 --directory frontend
# open http://localhost:5173/
```

`.venv\Scripts\python.exe -m http.server 5173 --directory frontend` works
identically on Windows.

The dashboard authenticates through the dev-login handshake, so run the API
with `AEGIS_DEV_LOGIN=1` in development (see [`docs/usage.md`](../docs/usage.md)).

## Pointing at a remote API

The dashboard reads `window.AEGIS_API_BASE` before `app.js` loads; empty means
same-origin. To run the dashboard on a different origin from the API, copy
`config.example.js` to `config.js` next to `index.html` and set the base URL:

```js
window.AEGIS_API_BASE = "https://aegis.example.com:8000";
```

The API must allow the dashboard's origin (CORS). In a Docker deployment the
API emits `Access-Control-Allow-Origin` per the configured
`AEGIS_CORS_ORIGINS`.

## Layout

- `index.html` — shell; reserves the `window.AEGIS_API_BASE` global
- `app.js` — the single-page app; all network calls go through `API + path`
- `styles.css` — design system (no frameworks, no build step)
- `config.example.js` — deployment wiring example

No build step: the dashboard is plain HTML/CSS/JS and runs from any static
host. End-to-end coverage lives in the E2E suite (`scripts/run_e2e.ps1` /
`e2e_dashboard.py`).