/** @type {import('next').NextConfig} */
const RAW_BACKEND_URL =
  process.env.STOREFRONT_BACKEND_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000";

const BACKEND_URL = RAW_BACKEND_URL.replace(/\/+$/, "").replace(/\/api$/, "");

const nextConfig = {
  output: "standalone",
  reactStrictMode: true,
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
