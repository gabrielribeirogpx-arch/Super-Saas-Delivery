import type { Metadata, Viewport } from "next";
import type { CSSProperties } from "react";
import { cache } from "react";

type RestaurantManifest = { name: string; themeColor: string; backgroundColor: string };

const restaurantManifest = cache(async (slug: string): Promise<RestaurantManifest> => {
  const fallback = { name: slug, themeColor: "#dc2626", backgroundColor: "#ffffff" };
  const backend = process.env.STOREFRONT_BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const base = backend.replace(/\/+$/, "").replace(/\/api$/, "");
  try {
    const response = await fetch(`${base}/api/public/pwa/manifest?tenant=${encodeURIComponent(slug)}`, {
      next: { revalidate: 60 },
      signal: AbortSignal.timeout(1500),
    });
    if (response.ok) {
      const data = await response.json() as { name?: string; theme_color?: string; background_color?: string };
      const validColor = (value?: string) => typeof value === "string" && /^#[0-9a-f]{6}$/i.test(value);
      return {
        name: data.name?.trim() || fallback.name,
        themeColor: validColor(data.theme_color) ? data.theme_color! : fallback.themeColor,
        backgroundColor: data.background_color === "#0f0e0d" ? "#0f0e0d" : fallback.backgroundColor,
      };
    }
  } catch {
    // The store remains available even when its metadata service is unavailable.
  }
  return fallback;
});

export async function generateMetadata({ params }: { params: { slug: string } }): Promise<Metadata> {
  const tenant = encodeURIComponent(params.slug);
  const icon = (size: number) => `/api/public/pwa/icon/${size}?tenant=${tenant}`;
  const { name } = await restaurantManifest(params.slug);

  return {
    title: name,
    applicationName: name,
    appleWebApp: { capable: true, statusBarStyle: "black-translucent", title: name },
    manifest: `/api/public/pwa/manifest?tenant=${tenant}`,
    icons: {
      icon: [
        { url: icon(192), sizes: "192x192", type: "image/png" },
        { url: icon(512), sizes: "512x512", type: "image/png" },
      ],
      apple: [{ url: icon(180), sizes: "180x180", type: "image/png" }],
      shortcut: [icon(192)],
    },
  };
}

export async function generateViewport({ params }: { params: { slug: string } }): Promise<Viewport> {
  const { themeColor } = await restaurantManifest(params.slug);
  return { width: "device-width", initialScale: 1, maximumScale: 1, viewportFit: "cover", themeColor };
}

export default async function StoreLayout({ children, params }: { children: React.ReactNode; params: { slug: string } }) {
  const { themeColor, backgroundColor } = await restaurantManifest(params.slug);
  const style = {
    ["--storefront-loading-accent" as string]: themeColor,
    ["--storefront-loading-bg" as string]: backgroundColor,
    ["--storefront-loading-text" as string]: backgroundColor === "#0f0e0d" ? "#f5efe6" : "#334155",
    colorScheme: backgroundColor === "#0f0e0d" ? "dark" : "light",
  } as CSSProperties;
  return <div className="storefront-shell" style={style}>{children}</div>;
}
