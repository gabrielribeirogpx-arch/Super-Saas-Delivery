import { NextResponse, type NextRequest } from "next/server";

const BASE_DOMAIN = "mandarpedido.com";

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  if (
    pathname.startsWith("/t/") ||
    pathname.startsWith("/_next") ||
    pathname.startsWith("/api") ||
    pathname.startsWith("/favicon")
  ) {
    return NextResponse.next();
  }

  const host = request.headers.get("host") ?? "";
  if (!host) {
    return NextResponse.next();
  }

  if (host.endsWith(`.${BASE_DOMAIN}`)) {
    const slug = host.replace(`.${BASE_DOMAIN}`, "");
    if (!slug) {
      return NextResponse.next();
    }
    const rewriteUrl = request.nextUrl.clone();
    rewriteUrl.pathname = `/t/${slug}${pathname}`;
    return NextResponse.rewrite(rewriteUrl);
  }

  const apiBase = process.env.NEXT_PUBLIC_API_URL;
  if (!apiBase) {
    return NextResponse.next();
  }

  try {
    const response = await fetch(new URL("/public/tenant/by-host", apiBase), {
      headers: { "x-forwarded-host": host },
    });
    if (!response.ok) {
      return NextResponse.next();
    }
    const data = (await response.json()) as { slug?: string };
    if (!data.slug) {
      return NextResponse.next();
    }
    const rewriteUrl = request.nextUrl.clone();
    rewriteUrl.pathname = `/t/${data.slug}${pathname}`;
    return NextResponse.rewrite(rewriteUrl);
  } catch {
    return NextResponse.next();
  }
}
