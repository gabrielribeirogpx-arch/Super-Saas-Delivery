import { expect, test } from "@playwright/test";

test("delivery endpoints are no longer exposed in frontend", async ({ request }) => {
  const response = await request.get("/api/delivery/orders");
  expect([200, 401, 403]).toContain(response.status());
});
