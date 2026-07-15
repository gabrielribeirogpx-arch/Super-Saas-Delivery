import type { Metadata, Viewport } from "next";
import "./globals.css";
import RegisterServiceWorker from "@/components/pwa/RegisterServiceWorker";
import DriverPwaStatus from "@/components/pwa/DriverPwaStatus";
import DriverInstallPrompt from "@/components/pwa/DriverInstallPrompt";
import DriverPwaDiagnostics from "@/components/pwa/DriverPwaDiagnostics";
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
  icons: {
    icon: [{ url: "/icons/driver-icon.svg", sizes: "any", type: "image/svg+xml" }],
    apple: [{ url: "/icons/driver-icon.svg", sizes: "any", type: "image/svg+xml" }],
    shortcut: ["/icons/driver-icon.svg"],
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
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
          href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,600;1,300;1,400;1,600&family=DM+Sans:wght@300;400;500&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <Providers>
          <RegisterServiceWorker />
          <DriverPwaStatus />
          <DriverInstallPrompt />
          <DriverPwaDiagnostics />
          {children}
        </Providers>
      </body>
    </html>
  );
}
