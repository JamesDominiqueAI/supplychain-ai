import { expect, test } from "@playwright/test";

const clerkEmail = process.env.E2E_CLERK_EMAIL;
const clerkPassword = process.env.E2E_CLERK_PASSWORD;

test.skip(!clerkEmail || !clerkPassword, "Set E2E_CLERK_EMAIL and E2E_CLERK_PASSWORD to run Clerk login E2E tests.");

test.describe("SupplyChain AI critical workflow", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/login");
    await page.getByRole("textbox", { name: /email/i }).fill(clerkEmail!);
    await page.getByRole("button", { name: /continue|sign in/i }).click();
    await page.getByLabel(/password/i).fill(clerkPassword!);
    await page.getByRole("button", { name: /continue|sign in/i }).click();
    await expect(page).toHaveURL(/dashboard|products|orders|reports/);
  });

  test("login, product creation, sale, report generation, and order flow", async ({ page }) => {
    const sku = `E2E-${Date.now()}`;

    await page.goto("/products");
    await expect(page.getByRole("heading", { name: "Products" })).toBeVisible();

    await page.getByLabel("SKU").fill(sku);
    await page.getByLabel("Name").fill("E2E Test Product");
    await page.getByLabel("Category").fill("E2E");
    await page.getByLabel("Current Stock").fill("8");
    await page.getByLabel("Reorder Point").fill("10");
    await page.getByLabel("Lead Time Days").fill("4");
    await page.getByLabel("Target Days Cover").fill("14");
    await page.getByLabel("Avg Daily Demand").fill("3");
    await page.getByLabel("Unit Cost").fill("50");
    await page.getByRole("button", { name: "Add Product" }).click();
    await expect(page.getByText("Product added.")).toBeVisible();
    await expect(page.getByText(sku)).toBeVisible();

    await page.getByLabel("Product").first().selectOption({ label: `E2E Test Product (${sku})` });
    await page.getByLabel("Quantity").first().fill("5");
    await page.getByRole("button", { name: "Subtract Sold Units" }).click();
    await expect(page.getByText("Sale recorded.")).toBeVisible();

    await page.goto("/reports");
    await page.getByRole("button", { name: /Generate Replenishment Report/i }).click();
    await expect(page.getByText(/Latest Recommendations|Recommendations/i)).toBeVisible();

    await page.goto("/products");
    await page.getByRole("button", { name: "Place Order" }).click();
    await expect(page.getByText("Order placed.")).toBeVisible();

    await page.goto("/orders");
    await expect(page.getByRole("heading", { name: "Orders" })).toBeVisible();
    await expect(page.getByText(/E2E Test Product|Order Pipeline/)).toBeVisible();
  });
});
