import { expect, test } from "@playwright/test";

test.describe("Indian Insurance Multimodal RAG — Material Design 3 E2E Tests", () => {
  test("1. Layout loads with brand, policy select, FinOps, scorecard, and MCP tool drawer", async ({
    page,
  }) => {
    await page.goto("/");
    await expect(page).toHaveTitle(/Indian Insurance Policy Multimodal RAG/);

    // Verify Brand Header
    const brand = page.locator(".m3-app-title");
    await expect(brand).toHaveText("Indian Insurance Multimodal RAG");

    // Verify Policy Select is populated with available policies
    const select = page.locator("#policy-select");
    await expect(select).toBeVisible();
    const options = select.locator("option");
    await expect(options).not.toHaveCount(0);
    const count = await options.count();
    expect(count).toBeGreaterThanOrEqual(2);

    // Verify FinOps and Scorecard Cards
    await expect(page.locator("#finops-card")).toBeVisible();
    await expect(page.locator("#scorecard-card")).toBeVisible();
    await expect(page.locator("#mcp-card")).toBeVisible();
  });

  test("2. Submitting supported query displays Grounded Answer, Confidence >= 70%, and Trace Waterfall", async ({
    page,
  }) => {
    await page.goto("/");

    const input = page.locator("#query-input");
    await input.fill("What is the waiting period for cataract surgery under this policy?");

    const submitBtn = page.locator("#query-submit-btn");
    await submitBtn.click();

    // Verify Grounded Answer Card appears
    const answerCard = page.locator("#answer-card");
    await expect(answerCard).toBeVisible({ timeout: 15000 });

    // Verify Confidence Badge >= 70% and Verified
    const badge = page.locator("#confidence-badge");
    await expect(badge).toBeVisible();
    await expect(badge).toHaveClass(/m3-badge-verified/);
    await expect(badge).toContainText("Verified");

    // Verify Precedence Banner
    const precedence = page.locator("#precedence-banner");
    await expect(precedence).toBeVisible();
    await expect(page.locator("#precedence-text")).toContainText("Policy Wordings");

    // Verify OpenTelemetry Execution Waterfall
    const waterfall = page.locator(".m3-waterfall-row");
    await expect(waterfall.first()).toBeVisible();
    const count = await waterfall.count();
    expect(count).toBeGreaterThanOrEqual(3);
  });

  test("3. Clicking Citation Chip opens Visual Grounding Inspector", async ({ page }) => {
    await page.goto("/");

    // Use Sample Pill for Cataract
    const samplePill = page.locator(
      'button[data-query="What is the waiting period for cataract surgery under this policy?"]',
    );
    await samplePill.click();

    await page.locator("#query-submit-btn").click();
    await expect(page.locator("#answer-card")).toBeVisible({ timeout: 15000 });

    // Check Citation Chip
    const citChip = page.locator('[data-testid="citation-chip-0"]');
    await expect(citChip).toBeVisible();
    await citChip.click();

    // Verify Right Inspector content
    const inspector = page.locator("#inspector-content");
    await expect(inspector).toBeVisible();
    await expect(inspector).toContainText("Verbatim Cited Clause");
  });

  test("4. Adversarial out-of-scope query triggers IRDAI Abstention Disclaimer", async ({
    page,
  }) => {
    await page.goto("/");

    const input = page.locator("#query-input");
    await input.fill(
      "Does this insurance policy cover pet veterinary dental implants in Antarctica?",
    );

    await page.locator("#query-submit-btn").click();

    // Verify Abstention Banner is visible
    const banner = page.locator("#abstention-banner");
    await expect(banner).toBeVisible({ timeout: 15000 });
    await expect(banner).toContainText("IRDAI Abstention Disclaimer");

    // Confidence badge shows abstained
    const badge = page.locator("#confidence-badge");
    await expect(badge).toHaveClass(/m3-badge-error/);
    await expect(badge).toContainText("Abstained");
  });

  test("5. Query with Aadhaar and PAN triggers DPDP Act 2023 Redaction Notice", async ({
    page,
  }) => {
    await page.goto("/");

    const input = page.locator("#query-input");
    await input.fill(
      "My Aadhaar is 1234 5678 9012 and PAN ABCDE1234F. What is the room rent limit?",
    );

    await page.locator("#query-submit-btn").click();

    // Verify PII Redaction Banner is visible
    const piiBanner = page.locator("#pii-banner");
    await expect(piiBanner).toBeVisible({ timeout: 15000 });
    await expect(page.locator("#pii-details")).toContainText("DPDP Act 2023 Masking applied");
  });

  test("6. Clicking Sample Query Pill populates the search bar", async ({ page }) => {
    await page.goto("/");

    const samplePill = page.locator(
      'button[data-query="What is the daily room rent sub-limit and mandatory co-payment percentage?"]',
    );
    await samplePill.click();

    const input = page.locator("#query-input");
    await expect(input).toHaveValue(
      "What is the daily room rent sub-limit and mandatory co-payment percentage?",
    );
  });
});
