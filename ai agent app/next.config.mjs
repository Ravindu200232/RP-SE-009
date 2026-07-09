/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // mongoose and its bson dependency should not be bundled by Next's server compiler.
  serverExternalPackages: ['mongoose'],
  eslint: {
    // The builder is a tool, not a library; don't block dev/build on lint.
    ignoreDuringBuilds: true,
  },
  typescript: {
    ignoreBuildErrors: false,
  },
};

export default nextConfig;
