import { NextResponse, type NextRequest } from "next/server";

const protectedPrefix = "/t/";

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const hasSession = request.cookies.has("admin_session");

  if (pathname.startsWith("/login") && hasSession) {
    const url = request.nextUrl.clone();
    url.pathname = "/t/1/dashboard";
    return NextResponse.redirect(url);
  }

  if (pathname.startsWith(protectedPrefix) && !hasSession) {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    url.searchParams.set("redirect", pathname);
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/t/:path*", "/login"],
};
