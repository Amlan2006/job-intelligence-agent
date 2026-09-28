export async function api<T>(path: string, body?: unknown): Promise<T> {
  const multipart = body instanceof FormData;
  const response = await fetch(`/api/backend/${path}`, {
    method: body === undefined ? "GET" : "POST",
    headers:
      body !== undefined && !multipart
        ? { "Content-Type": "application/json" }
        : undefined,
    body:
      body === undefined ? undefined : multipart ? body : JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) {
    const detail = data.detail;
    const code =
      detail?.code ||
      data.warnings?.[0] ||
      `Request failed (${response.status})`;
    const messages: Record<string, string> = {
      BACKEND_UNAVAILABLE:
        "Your backend is offline. Check BACKEND_URL and start the backend, then reconnect.",
      BACKEND_NOT_CONFIGURED:
        "Set BACKEND_URL in frontend/.env.local, then restart the frontend.",
      INVALID_ORIGIN:
        "This request came from a different app origin. Check APP_ORIGIN in the frontend configuration.",
      PDF_SIZE_LIMIT: "Please choose a PDF smaller than 10 MB.",
      RESUME_NOT_FOUND: "This resume is no longer available. Upload it again.",
      DISCOVERY_ALREADY_RUNNING:
        "Discovery is already running for this resume. Check discovery history shortly.",
      TAVILY_API_KEY_REQUIRED:
        "Add your Tavily key to the backend configuration, then restart it.",
      INSUFFICIENT_OUTREACH_EVIDENCE:
        "There isn’t enough supported evidence to create this draft yet.",
    };
    throw new Error(
      messages[code] ||
        detail?.message ||
        (Array.isArray(detail)
          ? detail.map((d: { msg: string }) => d.msg).join(". ")
          : code.replaceAll("_", " ").toLowerCase()),
    );
  }
  return data as T;
}
export function safeUrl(url?: string | null) {
  if (!url) return undefined;
  try {
    const parsed = new URL(url);
    return ["https:", "http:"].includes(parsed.protocol)
      ? parsed.href
      : undefined;
  } catch {
    return undefined;
  }
}
