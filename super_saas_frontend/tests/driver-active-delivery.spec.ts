import { expect, test } from "@playwright/test";

test("driver sees active delivery after accepting order", async ({ page }) => {
  await page.goto("/driver/login", { waitUntil: "domcontentloaded" });

  await page.getByLabel("Email").fill("driver@test.com");
  await page.getByLabel("Senha").fill("password");

  await Promise.all([
    page.waitForURL("**/driver/dashboard"),
    page.getByRole("button", { name: "Entrar" }).click(),
  ]);

  await page.goto("/driver/orders", { waitUntil: "networkidle" });

  const acceptOrderButton = page.getByRole("button", { name: /Aceitar entrega|Aceitando\.\.\./i }).first();
  await expect(acceptOrderButton).toBeVisible();

  await Promise.all([
    page.waitForURL("**/driver/delivery"),
    acceptOrderButton.click(),
  ]);

  await page.goto("/driver/delivery", { waitUntil: "networkidle" });
  await expect(page.getByRole("heading", { name: "Entrega ativa" })).toBeVisible();
  await expect(page.locator("text=Pedido #").first()).toBeVisible();
});
