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

const PUBLIC_PREFIXES = ["/login", "/public", "/_next", "/api"];
const ADMIN_SESSION_COOKIE = "admin_session";

const startsWithPrefix = (pathname: string, prefix: string) =>
  pathname === prefix || pathname.startsWith(`${prefix}/`);

const isPublicRoute = (pathname: string) =>
  PUBLIC_PREFIXES.some((prefix) => startsWithPrefix(pathname, prefix));

const isAdminRoute = (pathname: string) =>
  ADMIN_PREFIXES.some((prefix) => startsWithPrefix(pathname, prefix));

const isAuthenticated = (req: NextRequest) => Boolean(req.cookies.get(ADMIN_SESSION_COOKIE)?.value);

export function middleware(req: NextRequest) {
  const { pathname, search } = req.nextUrl;

  if (isPublicRoute(pathname)) {
    return NextResponse.next();
  }

  if (!isAdminRoute(pathname)) {
    return NextResponse.next();
  }

  if (isAuthenticated(req)) {
    return NextResponse.next();
  }

  const loginUrl = new URL("/login", req.url);
  loginUrl.searchParams.set("redirect", `${pathname}${search}`);
  return NextResponse.redirect(loginUrl);
}

export const config = {
  matcher: ["/((?!favicon.ico).*)"],
};
