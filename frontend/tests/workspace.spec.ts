import { test, expect } from "@playwright/test";
import { previewOpportunities, previewResume } from "../src/lib/preview";

test("job-board discovery submits selected source and shows unverified funding notes", async ({
  page,
}) => {
  let submitted: Record<string, unknown> | undefined;
  await page.route("**/api/backend/**", async (route) => {
    const url = route.request().url();
    if (url.endsWith("/discovery/run")) {
      submitted = route.request().postDataJSON();
      return route.fulfill({
        json: {
          discovery_id: "test-run",
          source: "job_boards",
          started_at: new Date().toISOString(),
          status: "completed",
          results: [],
          skipped_cached: 0,
          warnings: ["RECENT_FUNDING_NOT_VERIFIED: Example Labs"],
        },
      });
    }
    if (url.includes("/opportunities?"))
      return route.fulfill({ json: previewOpportunities });
    if (url.includes("/resume/")) return route.fulfill({ json: previewResume });
    if (url.includes("/discovery/runs?")) return route.fulfill({ json: [] });
    return route.fulfill({ json: { status: "ready" } });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Use my workspace" }).click();
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Discover", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Start discovery", exact: true }),
  ).toBeEnabled();
  await page
    .getByRole("button", { name: "Start discovery", exact: true })
    .click();
  await expect(
    page.getByText("Discovery completed. 0 companies found; 0 researched."),
  ).toBeVisible();
  expect(submitted?.source).toBe("job_boards");
  expect(submitted?.lookback_days).toBe(90);
  await expect(
    page.getByText("This does not mean no jobs exist.", { exact: false }),
  ).toBeVisible();
  await page.locator(".warnings summary").click();
  await expect(
    page.getByText("RECENT FUNDING NOT VERIFIED: Example Labs"),
  ).toBeVisible();
});

test("contact profiles show separate LinkedIn and X links in both views", async ({
  page,
}) => {
  const opportunity = structuredClone(previewOpportunities[0]);
  opportunity.contacts[0].linkedin_url =
    "https://www.linkedin.com/in/luthor-test-contact";
  opportunity.contacts[0].x_url = "https://x.com/luthor_test_contact";
  await page.route("**/api/backend/**", (route) =>
    route.fulfill({
      json: route.request().url().includes("/opportunities?")
        ? [opportunity]
        : { status: "ready" },
    }),
  );
  await page.goto("/");
  await page.getByRole("button", { name: "Use my workspace" }).click();
  await expect(page.getByText("Your live workspace · Connected")).toBeVisible();
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Contacts", exact: true })
    .click();
  const card = page.locator(".contact-card");
  await expect(
    card.getByRole("link", { name: "LinkedIn", exact: true }),
  ).toHaveAttribute("href", opportunity.contacts[0].linkedin_url);
  await expect(
    card.getByRole("link", { name: "X", exact: true }),
  ).toHaveAttribute("href", opportunity.contacts[0].x_url);
  await expect(
    card.getByRole("link", { name: "X", exact: true }),
  ).toHaveAttribute("target", "_blank");
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Overview", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Arcana Senior Frontend Engineer" })
    .click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Contacts", exact: true })
    .click();
  await expect(
    page
      .getByRole("dialog")
      .getByRole("link", { name: "LinkedIn", exact: true }),
  ).toHaveAttribute("href", opportunity.contacts[0].linkedin_url);
  await expect(
    page.getByRole("dialog").getByRole("link", { name: "X", exact: true }),
  ).toHaveAttribute("href", opportunity.contacts[0].x_url);
});

test("preview is explicit and navigation, saving and search work", async ({
  page,
}) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "See the opportunity." }),
  ).toBeVisible();
  await expect(
    page.getByText("All companies, people and scores are illustrative.", {
      exact: false,
    }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Save Arcana", exact: true }).click();
  await page.getByRole("button", { name: "Saved", exact: true }).click();
  await expect(page.locator(".opportunity-row")).toHaveCount(1);
  await page.getByRole("button", { name: "All opportunities 4" }).click();
  await page
    .getByRole("textbox", { name: "Search opportunities" })
    .fill("Helix");
  await expect(page.locator(".opportunity-row")).toHaveCount(1);
  await expect(page.locator(".company-cell")).toContainText("Helix");
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Contacts" })
    .click();
  await expect(
    page.getByRole("heading", { name: "Contacts", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".contact-card")).toHaveCount(4);
  await expect(
    page.getByText("LinkedIn not found", { exact: true }),
  ).toHaveCount(4);
  await expect(page.getByText("X not found", { exact: true })).toHaveCount(4);
});

test("research detail has evidence, contacts and copyable drafts", async ({
  page,
  context,
}) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.goto("/");
  await page
    .getByRole("button", { name: "Arcana Senior Frontend Engineer" })
    .click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page
    .locator(".drawer-tabs")
    .getByRole("button", { name: "Evidence", exact: true })
    .click();
  await expect(page.getByText("Company evidence score")).toBeVisible();
  await page
    .locator(".drawer-tabs")
    .getByRole("button", { name: "Outreach", exact: true })
    .click();
  await page.getByRole("button", { name: "Email", exact: true }).click();
  await expect(page.locator(".draft-subject")).toHaveText(
    "Exploring engineering at Arcana",
  );
  await page.getByRole("button", { name: "Copy draft" }).click();
  await expect(
    page.getByRole("button", { name: "Copied", exact: true }),
  ).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
});

test("live connection loads API data and research errors are visible", async ({
  page,
}) => {
  await page.route("**/api/backend/**", async (route) => {
    const url = route.request().url();
    if (url.endsWith("/opportunity/analyze"))
      return route.fulfill({
        status: 503,
        json: { detail: { code: "DATABASE_ERROR" } },
      });
    if (url.includes("/opportunities?"))
      return route.fulfill({ json: previewOpportunities.slice(0, 1) });
    if (url.includes("/resume/")) return route.fulfill({ json: previewResume });
    if (url.includes("/discovery/runs?")) return route.fulfill({ json: [] });
    return route.fulfill({ json: { status: "ready" } });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Use my workspace" }).click();
  await expect(page.getByText("Your live workspace · Connected")).toBeVisible();
  await expect(page.locator(".opportunity-row")).toHaveCount(1);
  await page.getByRole("button", { name: "New research" }).click();
  await page
    .getByPlaceholder("https://company.com", { exact: true })
    .fill("https://example.com");
  await page
    .getByRole("button", { name: "Start research", exact: true })
    .click();
  await expect(page.getByRole("main").getByRole("alert")).toContainText(
    "database error",
  );
});

test("resume upload uses multipart and displays returned profile", async ({
  page,
}) => {
  let uploaded = false;
  await page.route("**/api/backend/**", async (route) => {
    const url = route.request().url();
    if (url.endsWith("/resume/analyze")) {
      uploaded = route
        .request()
        .headers()
        ["content-type"].includes("multipart/form-data");
      return route.fulfill({ json: previewResume });
    }
    if (url.includes("opportunities")) return route.fulfill({ json: [] });
    return route.fulfill({ json: { status: "ready" } });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Use my workspace" }).click();
  await expect(page.getByText("Your live workspace · Connected")).toBeVisible();
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "My resume" })
    .click();
  await page.getByLabel("Upload resume PDF").setInputFiles({
    name: "resume.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("%PDF-fixture"),
  });
  await expect(
    page.getByText("Alex_Morgan_Resume.pdf", { exact: true }),
  ).toBeVisible();
  expect(uploaded).toBeTruthy();
  await expect(page.getByText("TypeScript", { exact: true })).toBeVisible();
});

test("mobile navigation and dialogs fit the viewport", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  await page.getByRole("button", { name: "Open navigation" }).click();
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Discover" })
    .click();
  await expect(
    page.getByRole("heading", { name: "Discover", exact: true }),
  ).toBeVisible();
  await expect(page.getByLabel("Discovery source")).toHaveValue("job_boards");
  await page.getByLabel("Discovery source").selectOption("tavily");
  await expect(page.getByLabel("Discovery source")).toHaveValue("tavily");
  await page.getByRole("button", { name: "Explore sample discovery" }).click();
  await expect(
    page.getByText("Sample discovery is complete.", { exact: false }),
  ).toBeVisible();
  await page.getByRole("button", { name: "New research" }).click();
  const bounds = await page.getByRole("dialog").boundingBox();
  expect(bounds!.width).toBeLessThanOrEqual(390);
});
