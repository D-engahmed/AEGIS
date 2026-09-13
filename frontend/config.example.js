/*
 * Dashboard => API wiring for a deployment that runs the dashboard on a
 * different origin than the AEGIS API.
 *
 * The dashboard is a separate static deployable (it never ships inside the
 * Python package). By default it talks to a same-origin API, so no config is
 * needed when the dashboard is served from behind a proxy that forwards /api
 * style requests to the API. When that is not the case, copy this file to
 * config.js next to index.html and set the API origin:
 *
 *   window.AEGIS_API_BASE = "https://aegis.example.com:8000";
 *
 * config.js must load BEFORE app.js (index.html reserves the
 * window.AEGIS_API_BASE global and falls back to "" when unset).
 */
window.AEGIS_API_BASE = window.AEGIS_API_BASE || "";