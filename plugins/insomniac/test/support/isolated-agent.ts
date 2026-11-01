import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, beforeEach, vi } from "vitest";

let directory: string;

beforeEach(async () => {
  directory = await mkdtemp(join(tmpdir(), "insomniac-agent-"));
  vi.stubEnv("PI_CODING_AGENT_DIR", directory);

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

afterEach(async () => {
  await rm(directory, { recursive: true, force: true });
  vi.unstubAllEnvs();
});
