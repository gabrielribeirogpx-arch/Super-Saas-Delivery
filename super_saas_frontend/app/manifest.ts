import type { MetadataRoute } from "next";

// TODO: Replace temporary icons with real PWA PNG assets (192/512/maskable)
const temporarySvgIcon = "/icon.svg";

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
    theme_color: "#0f172a",
    lang: "pt-BR",
    categories: ["business", "productivity", "navigation"],
    icons: [
      { src: temporarySvgIcon, sizes: "any", type: "image/svg+xml", purpose: "any" },
      { src: temporarySvgIcon, sizes: "any", type: "image/svg+xml", purpose: "maskable" },
    ],
  };
}
