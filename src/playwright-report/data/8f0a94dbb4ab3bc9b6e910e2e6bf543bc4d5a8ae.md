# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: cors.spec.ts >> backend CORS allows localhost origin
- Location: e2e\cors.spec.ts:8:5

# Error details

```
Error: expect(received).toBeTruthy()

Received: false
```

# Test source

```ts
  1  | import { test, expect } from "@playwright/test";
  2  |
  3  | test("proxy path works: request to :3000/api/status returns data", async ({ request }) => {
  4  |   const response = await request.get("http://localhost:3000/api/status");
  5  |   expect(response.ok()).toBeTruthy();
  6  | });
  7  |
  8  | test("backend CORS allows localhost origin", async ({ request }) => {
  9  |   const response = await request.get("http://localhost:8000/api/status", {
  10 |     headers: {
  11 |       Origin: "http://localhost:3000",
  12 |     },
  13 |   });
> 14 |   expect(response.ok()).toBeTruthy();
     |                         ^ Error: expect(received).toBeTruthy()
  15 | });
  16 |
```
