"use client";

import { PublicMenuPage } from "@/components/PublicMenu/PublicMenuPage";
import { PublicMenuResponse } from "@/components/storefront/types";

interface StorefrontMenuContentProps {
  menu: PublicMenuResponse;
  enableCart?: boolean;
}

export function StorefrontMenuContent({ menu, enableCart = true }: StorefrontMenuContentProps) {
  return <PublicMenuPage menu={menu} enableCart={enableCart} />;
}
