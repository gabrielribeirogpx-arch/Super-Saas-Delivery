/** @type {import('next').NextConfig} */
const RAW_BACKEND_URL =
  process.env.STOREFRONT_BACKEND_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000";

const BACKEND_URL = RAW_BACKEND_URL.replace(/\/+$/, "").replace(/\/api$/, "");

const remoteImageSources = [
  BACKEND_URL,
  process.env.NEXT_PUBLIC_STORAGE_URL,
  process.env.STOREFRONT_ASSETS_URL,
].filter(Boolean);

const imageRemotePatterns = remoteImageSources
  .map((rawUrl) => {
    try {
      const parsed = new URL(rawUrl);
      return {
        protocol: parsed.protocol.replace(":", ""),
        hostname: parsed.hostname,
        port: parsed.port || "",
        pathname: "/**",
      };
    } catch {
      return null;
    }
  })
  .filter(Boolean);

imageRemotePatterns.push(
  {
    protocol: "https",
    hostname: "**",
    pathname: "/**",
  },
  {
    protocol: "http",
    hostname: "**",
    pathname: "/**",
  },
);

const nextConfig = {
  output: "standalone",
  reactStrictMode: true,
  images: {
    remotePatterns: imageRemotePatterns,
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
