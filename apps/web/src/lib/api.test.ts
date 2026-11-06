import { describe, it, expect } from "vitest";
import { API_BASE } from "./api";

describe("api client", () => {
  it("exposes a base url", () => {
    expect(API_BASE).toContain("/api/v1");
  });
});
