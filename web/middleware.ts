import { NextResponse, type NextRequest } from "next/server";

// UX guard only: the backend enforces auth on every API call regardless.
export function middleware(request: NextRequest) {
  if (!request.cookies.get("recall_session_jwt")) {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    url.search = "";
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/", "/dashboard/:path*", "/conversations/:path*", "/ask/:path*"],
};
