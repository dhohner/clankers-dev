import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, beforeEach, vi } from "vitest";

beforeEach(() => {
  // This parent is a file, so tests cannot read or write an agent directory by accident.
  // Suites that exercise persistence override it with registerAgentDirectoryHooks().
  vi.stubEnv("PI_CODING_AGENT_DIR", join(fileURLToPath(import.meta.url), "agent"));

  for (const key of [
    "INSOMNIAC_SOURCE_APP",
    "TERM_PROGRAM",
    "__CFBundleIdentifier",
    "SSH_CONNECTION",
    "SSH_CLIENT",
    "SSH_TTY",
    "TMUX",
    "STY",
  ]) {
    vi.stubEnv(key, undefined);
  }
});

afterEach(() => {
  vi.unstubAllEnvs();
});
