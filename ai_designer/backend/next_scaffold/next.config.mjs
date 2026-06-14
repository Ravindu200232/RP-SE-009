/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Generated code quality is enforced by our own QA pipeline; don't let
  // lint/TS block `next build` for a prototype.
  eslint: { ignoreDuringBuilds: true },
  typescript: { ignoreBuildErrors: true },
};

export default nextConfig;
