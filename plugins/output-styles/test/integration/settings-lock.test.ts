import { fork, type ChildProcess, type Serializable } from "node:child_process";
import { once } from "node:events";
import { mkdtemp, readdir, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, expect, it, vi } from "vitest";
import { writePersistedStyleName } from "../../src/storage/settings.ts";
import { controlLockRetries } from "../support/lock-retries.ts";

function message(child: ChildProcess, expected: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const cleanup = () => {
      child.off("message", received);
      child.off("error", failed);
      child.off("exit", exited);
    };

    const failed = (error: Error) => {
      cleanup();
      reject(error);
    };

    const exited = (code: number | null) => failed(new Error(`Settings lock owner exited before ${expected}: ${code}`));

    const received = (value: Serializable) => {
      cleanup();

      if (value === expected) resolve();
      else reject(new Error(`Expected ${expected}, got ${String(value)}`));
    };

    child.once("message", received);
    child.once("error", failed);
    child.once("exit", exited);
  });
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
});

// Ignoring Pi's lock would overwrite another process's update with a stale settings object.
it("waits for another process to commit settings and preserves its changes", async () => {
  const directory = await mkdtemp(join(tmpdir(), "output-styles-lock-"));
  const path = join(directory, "settings.json");
  let child: ChildProcess | undefined;

  try {
    await writePersistedStyleName(path, "brief");
    child = fork(fileURLToPath(new URL("../fixtures/settings-lock-owner.mjs", import.meta.url)), [path], {
      stdio: ["ignore", "pipe", "pipe", "ipc"],
      timeout: 3000,
    });
    await message(child, "locked");
    const nextRetry = controlLockRetries();
    let settled = false;

    const write = writePersistedStyleName(path, "terse").finally(() => {
      settled = true;
    });

    await nextRetry(20);
    expect(settled).toBe(false);
    expect(JSON.parse(await readFile(path, "utf8"))).toEqual({ outputStyle: "brief" });

    const committed = message(child, "committed");
    child.send("commit");
    await committed;
    await vi.advanceTimersByTimeAsync(20);
    await write;

    expect(JSON.parse(await readFile(path, "utf8"))).toEqual({ theme: "dark", outputStyle: "terse" });
    expect(await readdir(directory)).toEqual(["settings.json"]);
  } finally {
    if (child && child.exitCode === null && child.signalCode === null) {
      const exited = once(child, "exit");
      child.kill("SIGKILL");
      await exited;
    }

    await rm(directory, { recursive: true, force: true });
  }
});
