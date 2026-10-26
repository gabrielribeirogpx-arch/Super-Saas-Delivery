import type { Metadata, Viewport } from "next";

export const metadata: Metadata = {
  title: "Fomizero | Entregador",
  description: "Aplicativo de entregas do Fomizero.",
  manifest: "/manifest.webmanifest",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "Fomizero",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  viewportFit: "cover",
  themeColor: "#ffffff",
};

export default function DriverRouteLayout({ children }: { children: React.ReactNode }) {
  return children;
}
