import type { Metadata, Viewport } from "next";

export const metadata: Metadata = {
  title: "Service Delivery Driver",
  description: "PWA instalável para entregadores Service Delivery.",
  manifest: "/manifest.webmanifest",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "Driver",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  viewportFit: "cover",
  themeColor: "#0f172a",
};

export default function DriverRouteLayout({ children }: { children: React.ReactNode }) {
  return children;
}
