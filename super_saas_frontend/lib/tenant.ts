export const tenantPath = (_tenantId: string | number, path: string) =>
  `${path.startsWith("/") ? path : `/${path}`}`;
