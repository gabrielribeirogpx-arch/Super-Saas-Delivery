/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  experimental: {
    middleware: true,
  },
  async rewrites() {
    const backendUrl = (
      process.env.NEXT_PUBLIC_API_URL ||
      "https://service-delivery-backend-production.up.railway.app"
    ).replace(/\/$/, "");

    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
      {
        source: "/:path*",
        destination: "/:path*",
      },
    ];
  },
};

export default nextConfig;
