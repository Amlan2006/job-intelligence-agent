// Next.js can normalize nextUrl's hostname differently from the incoming Host.
// Compare against the actual request authority; never trust forwarded headers.
export function validRequestOrigin(
  request: {
    method: string;
    headers: Headers;
    nextUrl: { protocol: string };
  },
  configuredOrigin?: string,
) {
  if (request.method === "GET") return true;
  const origin = request.headers.get("origin");
  if (!origin) return request.headers.get("sec-fetch-site") !== "cross-site";
  try {
    const incoming = new URL(origin);
    const host = request.headers.get("host");
    if (!configuredOrigin && (!host || /[\s/@\\?#]/.test(host))) return false;
    const expected = new URL(
      configuredOrigin || `${request.nextUrl.protocol}//${host}`,
    );
    return (
      ["http:", "https:"].includes(incoming.protocol) &&
      incoming.origin === origin &&
      incoming.origin === expected.origin
    );
  } catch {
    return false;
  }
}
