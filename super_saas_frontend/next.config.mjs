/** @type {import('next').NextConfig} */
const BACKEND_URL = "https://service-delivery-backend-production.up.railway.app";

const nextConfig = {
  output: "standalone",
  reactStrictMode: true,
  experimental: {
    middleware: true,
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${BACKEND_URL}/api/:path*`,
      },
      {
        source: "/sse/:path*",
        destination: `${BACKEND_URL}/sse/:path*`,
      },
    ];
  },
};

export default nextConfig;
