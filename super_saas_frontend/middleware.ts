import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function middleware(req: NextRequest) {
  const host = req.headers.get("host") || "";
  const url = req.nextUrl.clone();

  if (
    req.nextUrl.pathname.startsWith("/t/") ||
    req.nextUrl.pathname.startsWith("/_next") ||
    req.nextUrl.pathname.startsWith("/api") ||
    req.nextUrl.pathname.startsWith("/favicon")
  ) {
    return NextResponse.next();
  }

  // extrai possível subdomínio
  const hostParts = host.split(".");
  const isLocalhost = host.includes("localhost");
  const isProduction = !isLocalhost;

  // se é produção e tem subdomínio além de `servicedelivery`
  if (isProduction && hostParts.length >= 3) {
    const subdomain = hostParts[0];

    // ignora www, api, etc
    const reserved = ["www", "api"];
    if (!reserved.includes(subdomain)) {
      // rewrite para o padrão interno
      url.pathname = `/t/${subdomain}${req.nextUrl.pathname}`;
      return NextResponse.rewrite(url);
    }
  }

  return NextResponse.next();
}
