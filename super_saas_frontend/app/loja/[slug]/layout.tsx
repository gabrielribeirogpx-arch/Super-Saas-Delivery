import type { Metadata } from "next";

async function restaurantName(slug: string): Promise<string> {
  const backend = process.env.STOREFRONT_BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const base = backend.replace(/\/+$/, "").replace(/\/api$/, "");
  try {
    const response = await fetch(`${base}/api/public/pwa/manifest?tenant=${encodeURIComponent(slug)}`, {
      next: { revalidate: 300 },
      signal: AbortSignal.timeout(1500),
    });
    if (response.ok) {
      const data = await response.json() as { name?: string };
      if (data.name?.trim()) return data.name.trim();
    }
  } catch {
    // The store remains available even when its metadata service is unavailable.
  }
  return slug;
}

export async function generateMetadata({ params }: { params: { slug: string } }): Promise<Metadata> {
  const tenant = encodeURIComponent(params.slug);
  const icon = (size: number) => `/api/public/pwa/icon/${size}?tenant=${tenant}`;
  const name = await restaurantName(params.slug);

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

export default function StoreLayout({ children }: { children: React.ReactNode }) {
  return children;
}
