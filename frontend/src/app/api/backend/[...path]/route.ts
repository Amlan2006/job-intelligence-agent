import { NextRequest } from "next/server";
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
  const origin = request.headers.get("origin");
  if (request.method !== "GET" && origin && origin !== request.nextUrl.origin) {
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
    const base = (process.env.BACKEND_URL || "http://127.0.0.1:8000").replace(
      /\/$/,
      "",
    );
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
            "Could not reach your workspace. Start the backend on port 8000 and try again.",
        },
      },
      { status: 503 },
    );
  }
}
export { proxy as GET, proxy as POST };
