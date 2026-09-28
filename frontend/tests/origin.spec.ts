import { test, expect } from "@playwright/test";
import { validRequestOrigin } from "../src/lib/request-origin";

const request = (origin: string, host: string, protocol = "http:") => ({
  method: "POST",
  headers: new Headers({ origin, host }),
  nextUrl: { protocol },
});

test("same-origin requests use incoming host rather than Next.js normalized hostname", () => {
  for (const host of [
    "127.0.0.1:3000",
    "localhost:3000",
    "[::1]:4000",
    "luthor.test:8080",
  ]) {
    expect(validRequestOrigin(request(`http://${host}`, host))).toBe(true);
  }
});
test("cross-site, wrong ports and malformed origins are rejected", () => {
  for (const origin of [
    "https://attacker.test",
    "http://localhost:4000",
    "null",
    "not a URL",
    "http://localhost:3000/path",
  ]) {
    expect(validRequestOrigin(request(origin, "localhost:3000"))).toBe(false);
  }
  expect(
    validRequestOrigin({
      method: "POST",
      headers: new Headers({ "sec-fetch-site": "cross-site" }),
      nextUrl: { protocol: "http:" },
    }),
  ).toBe(false);
});
test("configured public origin supports reverse proxies without trusting forwarded host", () => {
  const req = request("https://luthor.test", "internal:3000");
  expect(validRequestOrigin(req, "https://luthor.test")).toBe(true);
  req.headers.set("origin", "https://attacker.test");
  req.headers.set("x-forwarded-host", "attacker.test");
  expect(validRequestOrigin(req, "https://luthor.test")).toBe(false);
});
