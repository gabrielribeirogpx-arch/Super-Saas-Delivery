import type { Metadata, Viewport } from "next";
import "./globals.css";
import "../styles/menu-tokens.css";
import AppPwaFeatures from "@/components/pwa/AppPwaFeatures";
import AdvertisingConsent from "@/components/sales/AdvertisingConsent";
import Providers from "./providers";

export const metadata: Metadata = {
  title: "Fomizero",
  description: "Pedidos, entregas e gestão do seu restaurante.",
  applicationName: "Fomizero",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "Fomizero",
  },
  icons: {
    icon: [{ url: "/brand/fomizero-avatar-app.svg", sizes: "any", type: "image/svg+xml" }, { url: "/icons/fomizero-32.png", sizes: "32x32", type: "image/png" }],
    apple: [{ url: "/icons/fomizero-180.png", sizes: "180x180", type: "image/png" }],
    shortcut: ["/icons/fomizero-32.png"],
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: "#ffffff",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,600;1,300;1,400;1,600&family=DM+Sans:wght@300;400;500&family=Inter:wght@400;500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <Providers>
          <AppPwaFeatures />
          {children}
          <AdvertisingConsent />
        </Providers>
      </body>
    </html>
  );
}
