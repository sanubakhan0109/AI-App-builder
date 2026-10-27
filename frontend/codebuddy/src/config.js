/**
 * Centralized Application Configuration
 *
 * Automatically selects the production backend URL when built for production
 * or when VITE_API_BASE_URL is set, while preserving local development.
 */

const PROD_BACKEND_URL = "https://ai-app-builder-c25a.onrender.com";
const DEV_BACKEND_URL = "http://127.0.0.1:8000";

const rawUrl = typeof import.meta.env.VITE_API_BASE_URL === "string"
  ? import.meta.env.VITE_API_BASE_URL.trim()
  : "";

let targetUrl = rawUrl;

if (import.meta.env.PROD) {
  // In production, NEVER use localhost/127.0.0.1 even if accidentally set in environment variables
  if (!targetUrl || targetUrl.includes("127.0.0.1") || targetUrl.includes("localhost")) {
    targetUrl = PROD_BACKEND_URL;
  }
} else {
  if (!targetUrl) {
    targetUrl = DEV_BACKEND_URL;
  }
}

export const BACKEND_URL = targetUrl.replace(/\/+$/, "");

export const GENERATION_TIMEOUT_MS = 60_000;
export const GENERATION_TIMEOUT_MESSAGE = "Generation took too long. Please try again.";
