import type { NextConfig } from "next";

// Without API_URL the front uses the mock in src/app/api (contracts/fixtures).
// With API_URL (e.g. http://localhost:8000) /api/* goes to the engine's /v1/*; beforeFiles wins over the mock route.
const apiUrl = process.env.API_URL;

const nextConfig: NextConfig = {
  devIndicators: false,
  async rewrites() {
    return apiUrl ? { beforeFiles: [{ source: "/api/:path*", destination: `${apiUrl}/v1/:path*` }], afterFiles: [], fallback: [] } : [];
  },
};

export default nextConfig;
