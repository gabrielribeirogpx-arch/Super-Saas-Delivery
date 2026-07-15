import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Service Delivery Driver",
    short_name: "Driver",
    description: "Aplicativo instalável do entregador Service Delivery com suporte offline.",
    id: "/driver",
    start_url: "/driver",
    scope: "/driver",
    display: "standalone",
    orientation: "portrait",
    background_color: "#ffffff",
    theme_color: "#ffffff",
    lang: "pt-BR",
    categories: ["business", "productivity", "navigation"],
    icons: [
      {
        src: "/icons/driver-icon.svg",
        sizes: "any",
        type: "image/svg+xml",
        purpose: "any",
      },
      {
        src: "/icons/maskable-icon.svg",
        sizes: "any",
        type: "image/svg+xml",
        purpose: "maskable",
      },
    ],
  };
}
