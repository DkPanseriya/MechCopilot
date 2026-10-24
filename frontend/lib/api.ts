// Single source of truth for the backend base URL.
// Override in the browser via NEXT_PUBLIC_API_URL; defaults to the FastAPI
// dev server (uvicorn runs on :8001 — see backend/main.py). The desktop app's static
// build is served by the backend itself, so it calls the API on its own address.
export const API_BASE =
    process.env.NEXT_PUBLIC_API_URL ??
    (process.env.NEXT_PUBLIC_SAME_ORIGIN === "1" ? "" : "http://localhost:8001");

export const apiUrl = (path: string): string =>
    `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;
