import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

function upstreamBase(): string {
  return (
    process.env.API_INTERNAL_URL ||
    process.env.NEXT_PUBLIC_API_BASE_URL ||
    "http://127.0.0.1:8000/api/v1"
  ).replace(/\/$/, "");
}

async function proxy(req: NextRequest, path: string[]): Promise<NextResponse> {
  const target = `${upstreamBase()}/${path.join("/")}${req.nextUrl.search}`;
  const headers = new Headers(req.headers);
  headers.delete("host");
  headers.delete("connection");
  headers.delete("content-length");

  const init: RequestInit = {
    method: req.method,
    headers,
    redirect: "manual",
  };
  if (req.method !== "GET" && req.method !== "HEAD") {
    init.body = await req.arrayBuffer();
  }

  try {
    const upstream = await fetch(target, init);
    const outHeaders = new Headers(upstream.headers);
    outHeaders.delete("content-encoding");
    outHeaders.delete("transfer-encoding");
    outHeaders.delete("content-length");
    return new NextResponse(upstream.body, {
      status: upstream.status,
      headers: outHeaders,
    });
  } catch (err: any) {
    return NextResponse.json(
      {
        error: {
          code: "UPSTREAM_UNAVAILABLE",
          message: err?.message || "API upstream unavailable",
          retryable: true,
        },
      },
      { status: 502 },
    );
  }
}

type Ctx = { params: { path: string[] } };

export async function GET(req: NextRequest, ctx: Ctx) {
  return proxy(req, ctx.params.path);
}
export async function POST(req: NextRequest, ctx: Ctx) {
  return proxy(req, ctx.params.path);
}
export async function PUT(req: NextRequest, ctx: Ctx) {
  return proxy(req, ctx.params.path);
}
export async function PATCH(req: NextRequest, ctx: Ctx) {
  return proxy(req, ctx.params.path);
}
export async function DELETE(req: NextRequest, ctx: Ctx) {
  return proxy(req, ctx.params.path);
}
export async function OPTIONS(req: NextRequest, ctx: Ctx) {
  return proxy(req, ctx.params.path);
}
