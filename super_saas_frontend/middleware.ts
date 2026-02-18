import { NextResponse, type NextRequest } from "next/server";

const BASE_DOMAIN = "servicedelivery.com.br";
const DEFAULT_TENANT_SLUG = process.env.NEXT_PUBLIC_DEFAULT_TENANT_SLUG?.trim();

function normalizeHost(rawHost: string | null): string {
  const host = (rawHost ?? "").trim().toLowerCase();
  if (!host) {
    return "";
  }
  return host.split(":")[0];
}

function extractSlugFromHost(host: string): string | null {
  if (!host) {
    return null;
  }

  if (host.endsWith(`.${BASE_DOMAIN}`)) {
    const slug = host.slice(0, -(BASE_DOMAIN.length + 1));
    if (!slug || slug.includes(".")) {
      return null;
    }
    return slug || null;
  }

  if (host.endsWith(".localhost")) {
    const slug = host.replace(".localhost", "");
    return slug || null;
  }

  return null;
}

function rewriteToSlug(request: NextRequest, slug: string) {
  const rewriteUrl = request.nextUrl.clone();
  rewriteUrl.pathname = `/t/${slug}${request.nextUrl.pathname}`;
  return NextResponse.rewrite(rewriteUrl);
}

function rewriteToNotFound(request: NextRequest) {
  const rewriteUrl = request.nextUrl.clone();
  rewriteUrl.pathname = "/404";
  return NextResponse.rewrite(rewriteUrl, { status: 404 });
}

export async function middleware(request: NextRequest) {
  try {
    const { pathname } = request.nextUrl;

    if (
      pathname.startsWith("/t/") ||
      pathname.startsWith("/_next") ||
      pathname.startsWith("/api") ||
      pathname.startsWith("/favicon")
    ) {
      return NextResponse.next();
    }

    const host = normalizeHost(request.headers.get("host"));
    if (!host) {
      return DEFAULT_TENANT_SLUG ? rewriteToSlug(request, DEFAULT_TENANT_SLUG) : NextResponse.next();
    }

    if (host === BASE_DOMAIN) {
      return NextResponse.next();
    }

    const slugFromHost = extractSlugFromHost(host);
    if (!slugFromHost) {
      return NextResponse.next();
    }

    if (host.endsWith(".localhost")) {
      return rewriteToSlug(request, slugFromHost);
    }

    const apiBase = process.env.NEXT_PUBLIC_API_URL;
    if (!apiBase) {
      return rewriteToNotFound(request);
    }

    const response = await fetch(new URL("/public/tenant/by-host", apiBase), {
      headers: { "x-forwarded-host": host },
    });
    if (!response.ok) {
      return rewriteToNotFound(request);
    }

    const data = (await response.json()) as { slug?: string };
    if (!data.slug) {
      return rewriteToNotFound(request);
    }

    return rewriteToSlug(request, data.slug);
  } catch {
    return NextResponse.next();
  }
}
