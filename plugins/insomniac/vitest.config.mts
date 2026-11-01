import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    name: { label: "insomniac", color: "magenta" },
    allowOnly: false,
    setupFiles: ["./test/support/isolated-agent.ts"],
    expect: { requireAssertions: true },
    sequence: { shuffle: { files: true, tests: true } },
  },
});
