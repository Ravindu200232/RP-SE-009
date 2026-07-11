/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  transpilePackages: ["@agentforge/shared"],
  // Lint is run separately; don't fail production builds on lint.
  eslint: { ignoreDuringBuilds: true },
  output: "standalone",
  async rewrites() {
    // Proxy /api/* to the FastAPI backend so the browser hits a same-origin URL.
    const base = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
    return [{ source: "/api/:path*", destination: `${base}/:path*` }];
  },
};

export default nextConfig;
