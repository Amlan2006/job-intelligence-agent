import { NextRequest } from "next/server";
import { validRequestOrigin } from "../../../../lib/request-origin";
export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 3600;

async function proxy(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  const { path } = await context.params;
  const route = path.join("/");
  const allowed =
    /^(health(?:\/ready)?|api\/v1\/(?:opportunities(?:\/[a-f0-9-]+)?|opportunity\/analyze|resume\/(?:analyze|[a-f0-9-]+)|research\/(?:company|[a-f0-9-]+)|company\/[a-f0-9-]+(?:\/evidence|\/contacts(?:\/discover)?)?|outreach\/(?:generate|[a-f0-9-]+)|discovery\/(?:run|runs(?:\/[a-f0-9-]+)?)))$/;
  if (!allowed.test(route))
    return Response.json(
      { detail: { code: "UNKNOWN_ENDPOINT" } },
      { status: 404 },
    );
  if (!validRequestOrigin(request, process.env.APP_ORIGIN)) {
    return Response.json(
      { detail: { code: "INVALID_ORIGIN" } },
      { status: 403 },
    );
  }
  try {
    const headers = new Headers();
    const contentType = request.headers.get("content-type");
    if (contentType) headers.set("content-type", contentType);
    const body =
      request.method === "GET" ? undefined : await request.arrayBuffer();
    if (body && body.byteLength > 11 * 1024 * 1024)
      return Response.json(
        { detail: { code: "PDF_SIZE_LIMIT" } },
        { status: 413 },
      );
    if (!process.env.BACKEND_URL) {
      return Response.json(
        { detail: { code: "BACKEND_NOT_CONFIGURED" } },
        { status: 503 },
      );
    }
    const base = process.env.BACKEND_URL.replace(/\/$/, "");
    const response = await fetch(`${base}/${route}${request.nextUrl.search}`, {
      method: request.method,
      headers,
      body,
      cache: "no-store",
      redirect: "error",
      signal: AbortSignal.timeout(3_600_000),
    });
    return new Response(response.body, {
      status: response.status,
      headers: {
        "Content-Type":
          response.headers.get("content-type") || "application/json",
        "Cache-Control": "no-store",
      },
    });
  } catch {
    return Response.json(
      {
        detail: {
          code: "BACKEND_UNAVAILABLE",
          message:
            "Could not reach the configured backend. Check BACKEND_URL and the backend service.",
        },
      },
      { status: 503 },
    );
  }
}
export { proxy as GET, proxy as POST };
