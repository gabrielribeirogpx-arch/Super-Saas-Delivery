import type { AdminUser } from "@/lib/auth";

export type AdminRole = AdminUser["role"];

// Mirrors the roles declared by app/routers/dashboard.py.  This is a UX hint;
// every request is still authorized by the backend.
const DASHBOARD_ROLES = new Set(["admin", "owner", "operator", "cashier"]);

export function normalizeRole(role: AdminRole | null | undefined) {
  return (role ?? "").trim().toLowerCase();
}

export function canAccessDashboard(role: AdminRole | null | undefined) {
  return DASHBOARD_ROLES.has(normalizeRole(role));
}

export function isDeliveryRole(role: AdminRole | null | undefined) {
  return normalizeRole(role) === "delivery";
}

export function permittedLandingPath(user: Pick<AdminUser, "role" | "tenant_id">) {
  return isDeliveryRole(user.role)
    ? `/admin/${user.tenant_id}/delivery`
    : "/dashboard";
}
