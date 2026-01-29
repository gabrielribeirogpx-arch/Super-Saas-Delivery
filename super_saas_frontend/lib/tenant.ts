export const tenantPath = (tenantId: string | number, path: string) =>
  `/t/${tenantId}${path.startsWith("/") ? path : `/${path}`}`;
