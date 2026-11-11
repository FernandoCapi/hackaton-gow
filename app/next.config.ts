import type { NextConfig } from "next";

// /api/* goes to the decision engine's /v1/*. Without the trained model the engine itself
// answers with contracts/fixtures (ENGINE_MODE=fixtures forces it), so there is no mock here.
const apiUrl = process.env.API_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  devIndicators: false,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${apiUrl}/v1/:path*` }];
  },
};

export default nextConfig;
