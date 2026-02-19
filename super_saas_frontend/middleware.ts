import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function middleware(req: NextRequest) {
  const host = req.headers.get("host") || "";
  const url = req.nextUrl.clone();

  const ROOT_DOMAIN = "servicedelivery.com.br";

  // Ignorar localhost
  if (host.includes("localhost")) {
    return NextResponse.next();
  }

  // Se for domínio raiz, não tentar resolver tenant
  if (host === ROOT_DOMAIN || host === `www.${ROOT_DOMAIN}`) {
    return NextResponse.next();
  }

  // Extrair subdomínio
  if (host.endsWith(`.${ROOT_DOMAIN}`)) {
    const slug = host.replace(`.${ROOT_DOMAIN}`, "");

    // Evitar subdomínios inválidos
    if (!slug || slug === "www") {
      return NextResponse.next();
    }

    // Reescrever para rota interna
    url.pathname = `/t/${slug}${url.pathname}`;
    return NextResponse.rewrite(url);
  }

  return NextResponse.next();
}
