import type { NextConfig } from "next";

// The browser only ever talks to this origin; /api is proxied to FastAPI so the
// session cookie stays same-origin and no backend URL or secret reaches the client.
const backend = process.env.BACKEND_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
};

export default nextConfig;
