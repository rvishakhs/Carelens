// Browser regression checks with synthetic API responses. Run against a local Vite
// server: CARELENS_BASE_URL=http://127.0.0.1:5187 node tests/e2e/fall_history.browser.mjs
// Provide CARELENS_PLAYWRIGHT_PATH when Playwright is supplied by the host runtime.
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { chromium } = require(
  process.env.CARELENS_PLAYWRIGHT_PATH || "playwright",
);
const base = process.env.CARELENS_BASE_URL || "http://127.0.0.1:5187";
const browser = await chromium.launch({ headless: true, channel: "chrome" });
const residentId = "11111111-1111-4111-8111-111111111111";
const sourceId = "22222222-2222-4222-8222-222222222222";
const user = {
  id: "test-nurse",
  care_home_id: "test-home",
  care_home_name: "Test home",
  role: "nurse",
  display_name: "Test Nurse",
  email: "nurse@example.test",
  floor_ids: ["floor-a"],
};
const resident = {
  id: residentId,
  first_name: "Synthetic",
  last_name: "Resident",
  preferred_name: null,
  date_of_birth: "1945-01-01",
  gender: "female",
  room_number: "A1",
  floor_id: "floor-a",
  floor_name: "A",
  status: "active",
  dnacpr: false,
  has_allergies: false,
  diabetic: false,
  active_care_domains: [],
  last_activity_at: null,
  photo_url: null,
};
const overview = {
  resident_id: residentId,
  diagnoses: [],
  allergies: [],
  contacts: [],
  advance_directives: [],
  life_history: null,
  top_preferences: [],
  latest_vitals: null,
  weight_trend: [],
  mobility_level: null,
  falls_risk_level: null,
  skin_risk_level: null,
  active_medication_count: 0,
  dnacpr: false,
};
const citation = {
  evidence_id: `fall:${sourceId}`,
  source_type: "fall",
  source_id: sourceId,
  source_version: "2026-10-02T11:00:00Z",
  occurred_at: "2026-10-01T09:00:00Z",
  title: "Fall — no injury",
  excerpt: "Location: Lounge. Action taken: Nurse reviewed.",
};
const result = {
  search_id: "33333333-3333-4333-8333-333333333333",
  resident_id: residentId,
  answer: "One fall was recorded in available fall record history.",
  answer_status: "supported",
  coverage_limitations: [
    "This result currently searches approved fall records only.",
    "Verify details against the cited source records.",
  ],
  citations: [citation],
};
const source = {
  source_type: "fall",
  source_id: sourceId,
  occurred_at: citation.occurred_at,
  source_version: "2026-10-03T11:00:00Z",
  title: citation.title,
  details: {
    severity: "no_injury",
    location: "Lounge",
    witnessed: false,
    injuries: null,
    likely_cause: "Lost balance",
    action_taken: "Nurse reviewed.",
    post_fall_observations_required: true,
    family_informed: false,
  },
  changed_since_search: true,
};

async function setup(
  role = "nurse",
  viewport = { width: 1440, height: 1000 },
  isolated = false,
) {
  const context = await browser.newContext({
    viewport,
    timezoneId: "Europe/London",
    reducedMotion: "reduce",
  });
  const page = await context.newPage();
  const state = {
    mode: "success",
    sourceStatus: 200,
    delay: 0,
    posts: [],
    sourceCalls: 0,
  };
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  // The real transformed app entry runs, with only its authentication bootstrap
  // replaced in this isolated browser context. Production source is untouched.
  await page.route("**/src/main.tsx*", async (route) => {
    const response = await route.fetch();
    const code = await response.text();
    assert.ok(code.includes("bootstrap();"));
    const render = isolated
      ? `Promise.all([import('/src/components/residents/ResidentHistorySearch.tsx'), import('/node_modules/.vite/deps/react.js')]).then(([{ResidentHistorySearch}, ReactModule]) => { const {createElement} = ReactModule.default || ReactModule; createRoot(document.getElementById('root')).render(createElement('div', {style: {padding: '20px'}}, createElement(ResidentHistorySearch, {residentId: '${residentId}'}))); });`
      : "renderApp();";
    await route.fulfill({
      response,
      body: code.replace(
        "bootstrap();",
        `useAuthStore.setState({ user: ${JSON.stringify({ ...user, role })}, isLoading: false }); ${render}`,
      ),
    });
  });
  await page.route("http://localhost:8000/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const reply = (data, status = 200) =>
      route.fulfill({
        status,
        contentType: "application/json",
        headers: { "Access-Control-Allow-Origin": "*" },
        body: JSON.stringify(data),
      });
    if (request.method() === "OPTIONS") return reply({});
    if (path.endsWith("/history-search")) {
      state.posts.push(request.postDataJSON());
      const mode = state.mode;
      if (state.delay)
        await new Promise((resolve) => setTimeout(resolve, state.delay));
      if (mode === "error") return reply({ message: "Unavailable" }, 500);
      if (mode === "denied") return reply({ message: "Denied" }, 403);
      if (mode === "empty")
        return reply({
          ...result,
          answer: "No fall records were found in the selected period.",
          answer_status: "no_evidence",
          citations: [],
        });
      return reply(result, 201);
    }
    if (path.includes("/sources/fall/")) {
      state.sourceCalls++;
      return state.sourceStatus === 200
        ? reply(source)
        : reply({ message: "Source unavailable" }, state.sourceStatus);
    }
    if (path === "/residents") return reply([resident]);
    if (path.endsWith("/overview")) return reply(overview);
    return reply([]);
  });
  await page.route("**/intelligence/v1/**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: route.request().url().includes("/shifts") ? "[]" : "null",
    }),
  );
  await page.goto(`${base}/residents/${residentId}`);
  try {
    await page
      .getByText(isolated ? "Search resident history" : "Synthetic Resident", {
        exact: true,
      })
      .first()
      .waitFor();
  } catch (error) {
    console.error({
      url: page.url(),
      errors,
      text: (await page.locator("body").innerText()).slice(0, 2500),
    });
    throw error;
  }
  return { page, context, state, errors };
}

try {
  const { page, context, state, errors } = await setup();
  const show = page.getByRole("button", {
    name: "Show fall history",
    exact: true,
  });
  await show.click();
  await page.getByText(result.answer, { exact: true }).waitFor();
  assert.deepEqual(state.posts[0].source_types, ["fall"]);
  await page.getByRole("button", { name: "Open record", exact: true }).click();
  await page.getByText(/This record changed after the search/).waitFor();
  assert.equal(
    await page.getByText("Not recorded", { exact: true }).count(),
    1,
  );
  await page.getByRole("button", { name: "Close record", exact: true }).click();
  state.sourceStatus = 404;
  await page.getByRole("button", { name: "Open record", exact: true }).click();
  await page
    .getByText(/This result or source is no longer available/)
    .waitFor();
  assert.equal(state.sourceCalls, 2);
  await page.getByRole("button", { name: "Close record", exact: true }).click();

  await page.getByLabel("From date").fill("2026-10-10");
  await page.getByLabel("To date").fill("2026-10-01");
  await show.click();
  await page
    .getByText("Choose an end date on or after the start date.")
    .waitFor();
  assert.equal(state.posts.length, 1);
  assert.equal(
    await page
      .getByLabel("From date")
      .evaluate((element) => element === document.activeElement),
    true,
  );
  await page.getByLabel("From date").fill("2026-10-01");
  await page.getByLabel("To date").fill("2026-10-01");
  state.mode = "empty";
  await show.click();
  await page.getByText(/No fall records matched these dates/).waitFor();
  assert.equal(state.posts.at(-1).from, "2026-09-30T23:00:00.000Z");
  assert.equal(state.posts.at(-1).to, "2026-10-01T23:00:00.000Z");

  state.mode = "error";
  await show.click();
  await page.getByText(/We couldn’t load the fall records/).waitFor();
  state.mode = "denied";
  await show.click();
  await page
    .getByText(/Your current access does not allow this search/)
    .waitFor();
  state.mode = "success";
  state.delay = 800;
  await show.click();
  await page.getByText("Searching fall records…", { exact: true }).waitFor();
  assert.equal(await show.isDisabled(), true);
  await page.getByRole("button", { name: "Clear", exact: true }).click();
  await page.waitForTimeout(900);
  assert.equal(await page.getByText(result.answer, { exact: true }).count(), 0);
  assert.equal(await page.getByLabel("From date").inputValue(), "");
  assert.equal(new URL(page.url()).search, "");
  state.delay = 0;
  await show.focus();
  await page.keyboard.press("Enter");
  await page.getByText(result.answer, { exact: true }).waitFor();
  state.sourceStatus = 200;
  await page.getByRole("button", { name: "Open record", exact: true }).click();
  await page.getByText(/This record changed after the search/).waitFor();
  if (process.env.CARELENS_SCREENSHOT)
    await page.screenshot({
      path: process.env.CARELENS_SCREENSHOT,
      fullPage: true,
    });
  assert.deepEqual(errors, []);
  await context.close();

  // Render the same production component at phone width independently of the
  // existing desktop-only navigation shell. No production styles are overridden.
  const narrow = await setup("nurse", { width: 390, height: 844 }, true);
  const panel = narrow.page
    .getByText("Search resident history", { exact: true })
    .locator("../../..");
  await narrow.page
    .getByRole("button", { name: "Show fall history", exact: true })
    .click();
  await narrow.page.getByText(result.answer, { exact: true }).waitFor();
  assert.equal(
    await panel.evaluate(
      (element) => element.scrollWidth <= element.clientWidth,
    ),
    true,
  );
  assert.equal(
    await narrow.page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
    true,
  );
  await narrow.page
    .getByRole("button", { name: "Open record", exact: true })
    .click();
  await narrow.page.getByText(/This record changed after the search/).waitFor();
  if (process.env.CARELENS_SCREENSHOT)
    await narrow.page.screenshot({
      path: process.env.CARELENS_SCREENSHOT.replace(/\.png$/, "-narrow.png"),
      fullPage: true,
    });
  assert.deepEqual(narrow.errors, []);
  await narrow.context.close();

  const denied = await setup("carer");
  assert.equal(
    await denied.page
      .getByText("Search resident history", { exact: true })
      .count(),
    0,
  );
  assert.equal(denied.state.posts.length, 0);
  await denied.context.close();
  console.log(
    "Fall history browser checks passed: source details/version, missing source, date validation/boundaries, empty/error/403, cancellation, keyboard, narrow panel, role gating.",
  );
} finally {
  await browser.close();
}
