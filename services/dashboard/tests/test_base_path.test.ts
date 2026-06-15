import { describe, expect, it } from "vitest";

describe("base path helpers", () => {
  it("prefixes app paths and VNC websockify paths when NEXT_PUBLIC_BASE_PATH is configured", async () => {
    process.env.NEXT_PUBLIC_BASE_PATH = "/vexa2";
    const mod = await import(`../src/lib/base-path?case=base-${Date.now()}`);

    expect(mod.withBasePath("/api/config")).toBe("/vexa2/api/config");
    expect(mod.withBasePath("/ws")).toBe("/vexa2/ws");
    expect(mod.vncWsPath("abc")).toBe("vexa2/b/abc/vnc/websockify");
  });

  it("leaves paths unprefixed when no base path is configured", async () => {
    delete process.env.NEXT_PUBLIC_BASE_PATH;
    const mod = await import(`../src/lib/base-path?case=empty-${Date.now()}`);

    expect(mod.withBasePath("/api/config")).toBe("/api/config");
    expect(mod.withBasePath("/ws")).toBe("/ws");
    expect(mod.vncWsPath("abc")).toBe("b/abc/vnc/websockify");
  });
});
