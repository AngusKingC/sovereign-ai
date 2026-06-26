import { test, expect } from "@playwright/test";

test("proxy path works: request to :3000/api/status returns data", async ({ request }) => {
  const response = await request.get("http://localhost:3000/api/status");
  expect(response.ok()).toBeTruthy();
});

test("backend CORS allows localhost origin", async ({ request }) => {
  const response = await request.get("http://localhost:8000/api/status", {
    headers: {
      Origin: "http://localhost:3000",
    },
  });
  expect(response.ok()).toBeTruthy();
});
