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

  async headers() {
    return [
      {
        source: "/sw.js",
        headers: [
          { key: "Content-Type", value: "application/javascript; charset=utf-8" },
          { key: "Service-Worker-Allowed", value: "/driver" },
          { key: "Cache-Control", value: "no-cache, no-store, must-revalidate" },
        ],
      },
      {
        source: "/customer-sw.js",
        headers: [
          { key: "Content-Type", value: "application/javascript; charset=utf-8" },
          { key: "Service-Worker-Allowed", value: "/" },
          { key: "Cache-Control", value: "no-cache, no-store, must-revalidate" },
        ],
      },
      {
        source: "/manifest.webmanifest",
        headers: [
          { key: "Content-Type", value: "application/manifest+json; charset=utf-8" },
          { key: "Cache-Control", value: "no-cache" },
        ],
      },
      {
        source: "/icons/:path*.svg",
        headers: [{ key: "Content-Type", value: "image/svg+xml; charset=utf-8" }],
      },
    ];
  },
  async rewrites() {
    return [
      {
        source: "/api/public/:path*",
        destination: `${BACKEND_URL}/api/public/:path*`,
      },
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
