export interface FeatureAccess {
  allowed: boolean; reason: string; limit: number | null; usage: number | null;
  effective_until: string | null;
}
export interface PlanAccess {
  managed: boolean; active: boolean; features: Record<string, FeatureAccess>;
}
export function routeFeature(path: string): string | undefined {
  if (/^\/inventory(?:\/|$)/.test(path)) return "inventory";
  if (/^\/reports(?:\/|$)/.test(path)) return "advanced_reports";
  if (/^\/whatsapp(?:\/|$)/.test(path)) return "whatsapp";
  if (/^\/marketing\/coupons(?:\/|$)/.test(path)) return "coupons";
  if (/^\/marketing\/(loyalty|rewards)(?:\/|$)/.test(path)) return "loyalty";
  if (/^\/admin\/[^/]+\/map(?:\/|$)/.test(path)) return "tracking";
}
export function featureBlocked(access: PlanAccess | undefined, feature: string | undefined) {
  return Boolean(access?.managed && feature && !access.features[feature]?.allowed);
}
