import type { Metadata, Viewport } from "next";

export const metadata: Metadata = {
  title: "Fomizero | Entregador",
  description: "Acesso do entregador pelo navegador Fomizero.",
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
