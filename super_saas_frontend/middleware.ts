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
  "/profile",
  "/settings",
  "/orders",
  "/finance",
  "/inventory",
  "/reports",
  "/users",
  "/audit",
  "/kds",
  "/minha-loja",
  "/admin/appearance",
];

const PUBLIC_PREFIXES = ["/login", "/public", "/_next", "/api"];
const ADMIN_SESSION_COOKIE = "admin_session";
const DRIVER_SESSION_COOKIE = "driver_session";
const DRIVER_PUBLIC_PATHS = new Set(["/driver/login"]);
const DRIVER_PROTECTED_PREFIXES = ["/driver/dashboard", "/driver/deliveries", "/driver/delivery"];

const startsWithPrefix = (pathname: string, prefix: string) =>
  pathname === prefix || pathname.startsWith(`${prefix}/`);

const isPublicRoute = (pathname: string) =>
  PUBLIC_PREFIXES.some((prefix) => startsWithPrefix(pathname, prefix));

const isAdminRoute = (pathname: string) =>
  ADMIN_PREFIXES.some((prefix) => startsWithPrefix(pathname, prefix));

const isAuthenticated = (req: NextRequest) => Boolean(req.cookies.get(ADMIN_SESSION_COOKIE)?.value);
const hasDriverSession = (req: NextRequest) => Boolean(req.cookies.get(DRIVER_SESSION_COOKIE)?.value);
const isDriverProtectedRoute = (pathname: string) =>
  pathname === "/driver" || DRIVER_PROTECTED_PREFIXES.some((prefix) => startsWithPrefix(pathname, prefix));

export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;

  if (pathname === "/driver") {
    const url = req.nextUrl.clone();
    url.pathname = hasDriverSession(req) ? "/driver/dashboard" : "/driver/login";
    return NextResponse.redirect(url);
  }

  if (DRIVER_PUBLIC_PATHS.has(pathname)) {
    return NextResponse.next();
  }

  if (isDriverProtectedRoute(pathname) && !hasDriverSession(req)) {
    const url = req.nextUrl.clone();
    url.pathname = "/driver/login";
    url.searchParams.set("next", pathname);
    return NextResponse.redirect(url);
  }

  if (isPublicRoute(pathname)) {
    return NextResponse.next();
  }

  if (!isAdminRoute(pathname)) {
    return NextResponse.next();
  }

  if (isAuthenticated(req)) {
    return NextResponse.next();
  }

  // A sessão administrativa é gravada pelo backend API (domínio próprio) em cookie HTTP-only.
  // Em produção, esse cookie pode não existir no domínio do frontend, então o bloqueio aqui
  // causaria loop de redirecionamento no login. A proteção principal já acontece no AuthGuard
  // via /api/admin/auth/me no cliente.
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!favicon.ico).*)"],
};
