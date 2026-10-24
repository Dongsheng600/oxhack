import { NextRequest, NextResponse } from 'next/server';
export const dynamic = 'force-dynamic';
async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  const base = process.env.BACKEND_URL || 'http://127.0.0.1:8000';
  const url = new URL(`${base.replace(/\/$/, '')}/v1/${path.map(encodeURIComponent).join('/')}`);
  url.search = request.nextUrl.search;
  try {
    const upstream = await fetch(url, {
      method: request.method,
      headers: { 'Content-Type': 'application/json' },
      body: ['GET', 'HEAD'].includes(request.method) ? undefined : await request.text(),
      cache: 'no-store',
      signal: request.signal,
    });
    return new NextResponse(upstream.body, {
      status: upstream.status,
      headers: {
        'Content-Type': upstream.headers.get('Content-Type') || 'application/json',
        'Cache-Control': 'no-store',
      },
    });
  } catch {
    return NextResponse.json(
      {
        error: {
          code: 'backend_unavailable',
          message: 'The backend is unavailable. Start the service and retry.',
          retryable: true,
        },
        request_id: null,
      },
      { status: 503 },
    );
  }
}
export { proxy as GET, proxy as POST, proxy as PATCH };
