import { fork, type ChildProcess } from "node:child_process";
import { once } from "node:events";
import { writeFile } from "node:fs/promises";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { expect, it } from "vitest";
import { NotificationPreference } from "../../src/pi/notification-preference.ts";

function message(child: ChildProcess, expected: string): Promise<void> {
  return new Promise((resolve, reject) => {
    child.once("error", reject);
    child.once("message", (value) => {
      if (value === expected) resolve();
      else reject(new Error(`Expected ${expected}, got ${String(value)}`));
    });
    child.once("exit", (code) => reject(new Error(`Writer exited early: ${code}`)));
  });
}

// Removing atomic replacement or ignoring commit order must lose a complete saved assignment.
it("keeps complete values from concurrent processes and loads the last serialized commit", async () => {
  const path = join(process.env.PI_CODING_AGENT_DIR!, "preference.json");
  await writeFile(path, "true", { mode: 0o600 });
  const script = fileURLToPath(new URL("../fixtures/preference-writer.mjs", import.meta.url));
  const a = fork(script, [path, "false"], { stdio: ["ignore", "pipe", "pipe", "ipc"] });
  const b = fork(script, [path, "true"], { stdio: ["ignore", "pipe", "pipe", "ipc"] });
  const store = new NotificationPreference(path);

  try {
    await Promise.all([message(a, "prepared"), message(b, "prepared")]);
    expect(await store.read()).toEqual({ status: "saved", value: true });
    const first = message(a, "committed");
    a.send("replace");
    await first;
    expect(await store.read()).toEqual({ status: "saved", value: false });
    const second = message(b, "committed");
    b.send("replace");
    await second;
    expect(await store.read()).toEqual({ status: "saved", value: true });
    const exits = [a, b].map(async (child) => child.exitCode ?? (await once(child, "exit"))[0]);
    expect(await Promise.all(exits)).toEqual([0, 0]);
  } finally {
    a.kill("SIGKILL");
    b.kill("SIGKILL");
  }
}, 10000);
