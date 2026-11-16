const FALLBACK_PATH = "/dashboard";
const APP_ORIGIN = "https://avsar.invalid";

export function safeReturnTo(value, fallback = FALLBACK_PATH) {
  if (typeof value !== "string" || !value.startsWith("/") || value.startsWith("//") || value.includes("\\")) {
    return fallback;
  }
  try {
    const destination = new URL(value, APP_ORIGIN);
    if (destination.origin !== APP_ORIGIN) return fallback;
    return `${destination.pathname}${destination.search}${destination.hash}`;
  } catch {
    return fallback;
  }
}

export function returnToFromSearch(search) {
  return safeReturnTo(new URLSearchParams(search || "").get("next"));
}
