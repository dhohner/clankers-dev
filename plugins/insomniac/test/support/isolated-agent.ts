import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, beforeEach, vi } from "vitest";

let directory: string;

beforeEach(async () => {
  directory = await mkdtemp(join(tmpdir(), "insomniac-agent-"));
  vi.stubEnv("PI_CODING_AGENT_DIR", directory);
});

afterEach(async () => {
  await rm(directory, { recursive: true, force: true });
  vi.unstubAllEnvs();
});
