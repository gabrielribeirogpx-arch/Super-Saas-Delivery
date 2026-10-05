import type { PublicMenuItem } from "@/components/storefront/types";

export function hasRequiredCustomization(item: PublicMenuItem): boolean {
  return (item.modifier_groups ?? []).some(
    (group) => group.options.length > 0 && (group.required || group.min_selection > 0),
  );
}

export function hasOptionalCustomization(item: PublicMenuItem): boolean {
  return (item.modifier_groups ?? []).some(
    (group) => group.options.length > 0 && !group.required && group.min_selection === 0,
  );
}
