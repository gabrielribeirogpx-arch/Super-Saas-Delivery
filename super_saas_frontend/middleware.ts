import { NextRequest, NextResponse } from "next/server";

const ROOT_DOMAIN = "servicedelivery.com.br";

export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  const host = req.headers.get("host") || "";

  // Ignorar assets e _next
  if (
    pathname.startsWith("/_next") ||
    pathname.startsWith("/api") ||
    pathname.includes(".")
  ) {
    return NextResponse.next();
  }

  // Se for domínio raiz → comportamento normal
  if (host === ROOT_DOMAIN || host.startsWith("www.")) {
    return NextResponse.next();
  }

  // Extrair subdomínio
  if (host.endsWith(`.${ROOT_DOMAIN}`)) {
    const subdomain = host.replace(`.${ROOT_DOMAIN}`, "");

    const rewriteUrl = req.nextUrl.clone();
    rewriteUrl.pathname = `/t/${subdomain}${pathname}`;

    return NextResponse.rewrite(rewriteUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next|api|favicon.ico).*)"],
};
