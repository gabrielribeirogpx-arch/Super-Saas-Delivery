import { NextRequest, NextResponse } from "next/server";

const ADMIN_PREFIXES = [
  "/dashboard",
  "/pedidos",
  "/financeiro",
  "/estoque",
  "/relatorios",
  "/usuarios",
  "/whatsapp",
  "/ia",
  "/settings",
  "/orders",
  "/finance",
  "/inventory",
  "/reports",
  "/users",
  "/audit",
  "/kds",
  "/minha-loja",
];

const ADMIN_SESSION_COOKIE = "admin_session";

const isAdminRoute = (pathname: string) =>
  ADMIN_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`)
  );

const isAuthenticated = (req: NextRequest) => Boolean(req.cookies.get(ADMIN_SESSION_COOKIE)?.value);

export function middleware(req: NextRequest) {
  const { pathname, search } = req.nextUrl;
  const authenticated = isAuthenticated(req);

  if (pathname === "/login") {
    if (authenticated) {
      return NextResponse.redirect(new URL("/dashboard", req.url));
    }
    return NextResponse.next();
  }

  if (!isAdminRoute(pathname)) {
    return NextResponse.next();
  }

  if (authenticated) {
    return NextResponse.next();
  }

  const loginUrl = new URL("/login", req.url);
  const redirectTarget = `${pathname}${search}`;
  loginUrl.searchParams.set("redirect", redirectTarget);
  return NextResponse.redirect(loginUrl);
}

export const config = {
  matcher: ["/((?!_next|api|favicon.ico).*)"],
};
