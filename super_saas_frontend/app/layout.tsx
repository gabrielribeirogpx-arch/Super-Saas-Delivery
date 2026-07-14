import type { Metadata, Viewport } from "next";
import "./globals.css";
import RegisterServiceWorker from "@/components/pwa/RegisterServiceWorker";
import DriverPwaStatus from "@/components/pwa/DriverPwaStatus";
import "../styles/menu-tokens.css";
import Providers from "./providers";

export const metadata: Metadata = {
  title: "Service Delivery Driver",
  description: "Aplicativo PWA do entregador Service Delivery.",
  manifest: "/manifest.webmanifest",
  applicationName: "Service Delivery Driver",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "Driver",
  },
  // TODO: Replace temporary icons with real PWA PNG assets (192/512/maskable)
  icons: {
    icon: [{ url: "/icon.svg", type: "image/svg+xml" }],
    apple: [{ url: "/icon.svg", type: "image/svg+xml" }],
    shortcut: ["/icon.svg"],
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  viewportFit: "cover",
  themeColor: "#0f172a",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,600;1,300;1,400;1,600&family=DM+Sans:wght@300;400;500&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <Providers><RegisterServiceWorker />
          <DriverPwaStatus />
          {children}</Providers>
      </body>
    </html>
  );
}
